"""
GUI 版冒险岛辅助（tkinter）

用法:
    python gui.py

功能:
  - 附加游戏进程（填进程名即可）
  - 界面上填内存地址/偏移（逆向好后直接填，不改代码）
  - 按键映射、血蓝阈值、攻击范围界面配置
  - 实时显示 HP/MP/坐标/怪物数
  - 挂机日志滚动输出
  - 配置保存 settings.json，下次自动加载
"""

import json
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, scrolledtext

import config
from controller import Controller
from skill_manager import SkillManager

SETTINGS_FILE = "settings.json"


# ==================== 配置持久化 ====================

def default_settings():
    return {
        "process_name": config.MEMORY["process_name"],
        "player": dict(config.MEMORY["player"]),
        "monster": dict(config.MEMORY["monster"]),
        "keys": dict(config.KEYS),
        "hp_threshold": config.HP_POTION_THRESHOLD,
        "mp_threshold": config.MP_POTION_THRESHOLD,
        "attack_range": config.ATTACK_RANGE_GAME,
        "potion_cooldown": config.POTION_COOLDOWN,
        "skills": [dict(s) for s in config.SKILL_ROTATION],
    }


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = default_settings()
            for k, v in data.items():
                if k in merged:
                    merged[k] = v
            return merged
        except Exception as e:
            print(f"配置加载失败: {e}")
    return default_settings()


def save_settings(data):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_hex(text):
    text = str(text).strip()
    if not text:
        return 0
    text = text.replace("0x", "").replace("0X", "")
    return int(text, 16)


def fmt_hex(v):
    return f"0x{v:X}" if v else "0x0"


# ==================== 后台挂机线程 ====================

class BotThread:
    """挂机逻辑线程，通过 state 字典向 GUI 报告状态"""

    def __init__(self, settings, log_queue):
        self.settings = settings
        self.log_queue = log_queue
        self.ctrl = Controller()
        self.skills = SkillManager(self.ctrl)
        self.mem = None
        self.running = False
        self.thread = None
        self._last_potion = 0
        self._lock = threading.Lock()
        self.state = {
            "hp": 0, "max_hp": 0, "mp": 0, "max_mp": 0,
            "x": 0.0, "y": 0.0, "map_id": 0,
            "monster_count": 0, "nearest": None,
            "bot_state": "未启动", "connected": False,
        }

    def _log(self, msg):
        self.log_queue.put(msg)

    def apply_settings(self, s):
        self.settings = s
        config.KEYS.clear()
        config.KEYS.update(s["keys"])
        config.SKILL_ROTATION[:] = s["skills"]
        self.skills.reset()

    def connect(self):
        from memory import MemoryReader
        self.mem = MemoryReader()
        ok = self.mem.attach(self.settings["process_name"])
        with self._lock:
            self.state["connected"] = ok
        return ok

    def disconnect(self):
        self.stop()
        if self.mem:
            self.mem.detach()
            self.mem = None
        with self._lock:
            self.state["connected"] = False

    def start(self):
        if not self.mem:
            self._log("[错误] 请先附加进程")
            return False
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        self._log("[BOT] 挂机启动")
        return True

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
            self.thread = None
        self._log("[BOT] 挂机停止")

    def _loop(self):
        while self.running:
            try:
                self._tick()
            except Exception as e:
                self._log(f"[异常] {e}")
                time.sleep(1)
            time.sleep(config.BOT_INTERVAL)

    def _tick(self):
        cfg = self.settings

        player = self.mem.get_player()
        if player is None:
            with self._lock:
                self.state["bot_state"] = "读取失败"
            return

        with self._lock:
            self.state.update({
                "hp": player["hp"], "max_hp": player["max_hp"],
                "mp": player["mp"], "max_mp": player["max_mp"],
                "x": player["x"], "y": player["y"],
                "map_id": player["map_id"],
            })

        # ---- 血蓝检查 ----
        now = time.time()
        if now - self._last_potion >= cfg["potion_cooldown"]:
            max_hp = max(player["max_hp"], 1)
            max_mp = max(player["max_mp"], 1)
            if player["hp"] / max_hp < cfg["hp_threshold"]:
                self.ctrl.use_hp_potion()
                self._last_potion = now
                self._log(f"[吃药] HP {player['hp']}/{player['max_hp']}")
                with self._lock:
                    self.state["bot_state"] = "吃药"
                return
            if player["mp"] / max_mp < cfg["mp_threshold"]:
                self.ctrl.use_mp_potion()
                self._last_potion = now
                self._log(f"[吃药] MP {player['mp']}/{player['max_mp']}")
                with self._lock:
                    self.state["bot_state"] = "吃药"
                return

        # ---- 找怪 ----
        monsters = self.mem.get_monsters()
        with self._lock:
            self.state["monster_count"] = len(monsters)
        target = self.mem.get_nearest_monster(monsters, player)

        if target is None:
            import random
            with self._lock:
                self.state["bot_state"] = "巡逻"
                self.state["nearest"] = None
            self.ctrl.hold(random.choice(["left", "right"]), 0.3)
            return

        dx = target["x"] - player["x"]
        with self._lock:
            self.state["nearest"] = (target["x"], target["y"])

        if abs(dx) < cfg["attack_range"]:
            if dx > 0:
                self.ctrl.hold("right", 0.02)
            else:
                self.ctrl.hold("left", 0.02)
            time.sleep(0.02)
            self.skills.cast_next()
            with self._lock:
                self.state["bot_state"] = "攻击"
        else:
            if dx > 0:
                self.ctrl.move_right(0.15)
            else:
                self.ctrl.move_left(0.15)
            with self._lock:
                self.state["bot_state"] = "移动"

    def get_state(self):
        with self._lock:
            return dict(self.state)


# ==================== GUI ====================

class App:
    def __init__(self, root):
        self.root = root
        root.title("冒险岛怀旧服辅助")
        root.geometry("780x860")
        root.resizable(False, False)

        self.settings = load_settings()
        self.log_queue = queue.Queue()
        self.bot = BotThread(self.settings, self.log_queue)
        self.entries = {}

        self._build_top()
        self._build_tabs()
        self._build_status()
        self._build_log()
        self._build_controls()

        self.refresh()

    # ---------- 公共组件 ----------

    def _hex_row(self, parent, label, tag, default):
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=3)
        ttk.Label(frame, text=label, width=22, anchor="w").pack(side="left")
        entry = ttk.Entry(frame, width=14)
        entry.insert(0, default)
        entry.pack(side="left", padx=5)
        self.entries[tag] = entry
        return entry

    def _build_top(self):
        frame = ttk.Frame(self.root)
        frame.pack(fill="x", padx=10, pady=8)

        ttk.Label(frame, text="冒险岛怀旧服辅助",
                  font=("Microsoft YaHei", 14, "bold")).pack(side="left", padx=(0, 20))

        ttk.Label(frame, text="进程名:").pack(side="left")
        self.proc_entry = ttk.Entry(frame, width=18)
        self.proc_entry.insert(0, self.settings["process_name"])
        self.proc_entry.pack(side="left", padx=5)

        ttk.Button(frame, text="附加进程", command=self.on_connect).pack(side="left", padx=2)
        ttk.Button(frame, text="断开", command=self.on_disconnect).pack(side="left", padx=2)
        ttk.Button(frame, text="保存配置", command=self.on_save).pack(side="left", padx=2)

        self.conn_label = ttk.Label(frame, text="未连接", foreground="red")
        self.conn_label.pack(side="left", padx=10)

    def _build_tabs(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=5)

        self.tab_player = ttk.Frame(self.notebook)
        self.tab_monster = ttk.Frame(self.notebook)
        self.tab_keys = ttk.Frame(self.notebook)
        self.tab_params = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_player, text="玩家数据")
        self.notebook.add(self.tab_monster, text="怪物列表")
        self.notebook.add(self.tab_keys, text="按键设置")
        self.notebook.add(self.tab_params, text="挂机参数")

        self._fill_player()
        self._fill_monster()
        self._fill_keys()
        self._fill_params()

    def _fill_player(self):
        p = self.settings["player"]
        ttk.Label(self.tab_player, text="玩家结构体偏移",
                  foreground="#555").pack(anchor="w", pady=(10, 5), padx=10)

        self._hex_row(self.tab_player, "基址偏移 base_offset", "p_base",
                      fmt_hex(p["base_offset"]))

        frame = ttk.Frame(self.tab_player)
        frame.pack(fill="x", pady=3, padx=10)
        ttk.Label(frame, text="多级偏移 (逗号分隔)", width=22, anchor="w").pack(side="left")
        entry = ttk.Entry(frame, width=28)
        entry.insert(0, ",".join(fmt_hex(o) for o in p["offsets"]))
        entry.pack(side="left", padx=5)
        self.entries["p_offsets"] = entry

        for label, tag, key in [
            ("X坐标偏移", "p_x", "x_offset"),
            ("Y坐标偏移", "p_y", "y_offset"),
            ("当前HP偏移", "p_hp", "hp_offset"),
            ("最大HP偏移", "p_maxhp", "max_hp_offset"),
            ("当前MP偏移", "p_mp", "mp_offset"),
            ("最大MP偏移", "p_maxmp", "max_mp_offset"),
            ("地图ID偏移", "p_map", "map_id_offset"),
        ]:
            self._hex_row(self.tab_player, label, tag, fmt_hex(p[key]))

        ttk.Button(self.tab_player, text="验证读取",
                   command=self.on_verify).pack(anchor="w", padx=10, pady=10)

    def _fill_monster(self):
        m = self.settings["monster"]
        ttk.Label(self.tab_monster, text="怪物链表偏移",
                  foreground="#555").pack(anchor="w", pady=(10, 5), padx=10)

        self._hex_row(self.tab_monster, "链表头基址偏移", "m_base",
                      fmt_hex(m["base_offset"]))

        frame = ttk.Frame(self.tab_monster)
        frame.pack(fill="x", pady=3, padx=10)
        ttk.Label(frame, text="多级偏移 (逗号分隔)", width=22, anchor="w").pack(side="left")
        entry = ttk.Entry(frame, width=28)
        entry.insert(0, ",".join(fmt_hex(o) for o in m["offsets"]))
        entry.pack(side="left", padx=5)
        self.entries["m_offsets"] = entry

        for label, tag, key in [
            ("next指针偏移", "m_next", "next_offset"),
            ("X坐标偏移", "m_x", "x_offset"),
            ("Y坐标偏移", "m_y", "y_offset"),
            ("血量偏移", "m_hp", "hp_offset"),
            ("怪物ID偏移", "m_id", "id_offset"),
        ]:
            self._hex_row(self.tab_monster, label, tag, fmt_hex(m[key]))

    def _fill_keys(self):
        ttk.Label(self.tab_keys, text="按键名称 -> 键值（改完记得保存配置）",
                  foreground="#555").pack(anchor="w", pady=(10, 5), padx=10)
        keys = self.settings["keys"]
        for name, key in keys.items():
            frame = ttk.Frame(self.tab_keys)
            frame.pack(fill="x", pady=2, padx=10)
            ttk.Label(frame, text=name, width=16, anchor="w").pack(side="left")
            entry = ttk.Entry(frame, width=12)
            entry.insert(0, key)
            entry.pack(side="left", padx=5)
            self.entries[f"key_{name}"] = entry

    def _fill_params(self):
        s = self.settings

        # HP
        frame = ttk.Frame(self.tab_params)
        frame.pack(fill="x", pady=5, padx=10)
        ttk.Label(frame, text="HP吃药阈值 (%)", width=18, anchor="w").pack(side="left")
        self.hp_scale = ttk.Scale(frame, from_=5, to=95, orient="horizontal", length=220)
        self.hp_scale.set(int(s["hp_threshold"] * 100))
        self.hp_scale.pack(side="left")
        self.hp_label = ttk.Label(frame, text=f"{int(s['hp_threshold'] * 100)}%")
        self.hp_label.pack(side="left", padx=5)
        self.hp_scale.configure(command=lambda v: self.hp_label.configure(text=f"{int(float(v))}%"))

        # MP
        frame = ttk.Frame(self.tab_params)
        frame.pack(fill="x", pady=5, padx=10)
        ttk.Label(frame, text="MP吃药阈值 (%)", width=18, anchor="w").pack(side="left")
        self.mp_scale = ttk.Scale(frame, from_=5, to=95, orient="horizontal", length=220)
        self.mp_scale.set(int(s["mp_threshold"] * 100))
        self.mp_scale.pack(side="left")
        self.mp_label = ttk.Label(frame, text=f"{int(s['mp_threshold'] * 100)}%")
        self.mp_label.pack(side="left", padx=5)
        self.mp_scale.configure(command=lambda v: self.mp_label.configure(text=f"{int(float(v))}%"))

        # 攻击范围
        frame = ttk.Frame(self.tab_params)
        frame.pack(fill="x", pady=5, padx=10)
        ttk.Label(frame, text="攻击范围 (游戏坐标)", width=18, anchor="w").pack(side="left")
        self.atk_entry = ttk.Entry(frame, width=12)
        self.atk_entry.insert(0, str(s["attack_range"]))
        self.atk_entry.pack(side="left", padx=5)

        # 吃药冷却
        frame = ttk.Frame(self.tab_params)
        frame.pack(fill="x", pady=5, padx=10)
        ttk.Label(frame, text="吃药冷却 (秒)", width=18, anchor="w").pack(side="left")
        self.cd_entry = ttk.Entry(frame, width=12)
        self.cd_entry.insert(0, str(s["potion_cooldown"]))
        self.cd_entry.pack(side="left", padx=5)

        # 技能 JSON
        ttk.Label(self.tab_params, text="技能循环 JSON (priority 小的先放):",
                  foreground="#555").pack(anchor="w", pady=(15, 5), padx=10)
        self.skills_text = tk.Text(self.tab_params, width=80, height=8)
        self.skills_text.insert("1.0", json.dumps(s["skills"], ensure_ascii=False, indent=2))
        self.skills_text.pack(fill="x", padx=10, pady=5)

    def _build_status(self):
        frame = ttk.LabelFrame(self.root, text="实时状态")
        frame.pack(fill="x", padx=10, pady=5)

        # HP
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=2, padx=5)
        ttk.Label(row, text="HP", width=4).pack(side="left")
        self.hp_bar = ttk.Progressbar(row, orient="horizontal", length=220,
                                      mode="determinate", maximum=100)
        self.hp_bar.pack(side="left", padx=5)
        self.hp_text = ttk.Label(row, text="HP -/-")
        self.hp_text.pack(side="left")

        # MP
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=2, padx=5)
        ttk.Label(row, text="MP", width=4).pack(side="left")
        self.mp_bar = ttk.Progressbar(row, orient="horizontal", length=220,
                                      mode="determinate", maximum=100)
        self.mp_bar.pack(side="left", padx=5)
        self.mp_text = ttk.Label(row, text="MP -/-")
        self.mp_text.pack(side="left")

        # 坐标/地图/怪物
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=2, padx=5)
        self.pos_label = ttk.Label(row, text="坐标: -")
        self.pos_label.pack(side="left", padx=10)
        self.map_label = ttk.Label(row, text="地图: -")
        self.map_label.pack(side="left", padx=10)
        self.mob_label = ttk.Label(row, text="怪物: 0")
        self.mob_label.pack(side="left", padx=10)
        self.near_label = ttk.Label(row, text="最近怪: -")
        self.near_label.pack(side="left", padx=10)

        self.state_label = ttk.Label(frame, text="状态: 已停止", foreground="green")
        self.state_label.pack(anchor="w", padx=5, pady=5)

    def _build_log(self):
        frame = ttk.LabelFrame(self.root, text="日志")
        frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.log_box = scrolledtext.ScrolledText(frame, wrap="word", state="disabled",
                                                 height=12)
        self.log_box.pack(fill="both", expand=True, padx=5, pady=5)

    def _build_controls(self):
        frame = ttk.Frame(self.root)
        frame.pack(fill="x", padx=10, pady=8)
        ttk.Button(frame, text="▶ 启动挂机", command=self.on_start, width=16).pack(side="left", padx=5)
        ttk.Button(frame, text="■ 停止", command=self.on_stop, width=16).pack(side="left", padx=5)
        ttk.Label(frame, text="挂机时保持游戏窗口在前台", foreground="#888").pack(side="left", padx=20)

    # ---------- 事件 ----------

    def on_connect(self):
        self.collect()
        if self.bot.connect():
            self.conn_label.configure(text="已连接", foreground="green")
            self.log("[连接] 附加成功")
        else:
            self.conn_label.configure(text="连接失败", foreground="red")
            self.log("[连接] 失败，确认进程名，且以管理员运行")

    def on_disconnect(self):
        self.bot.disconnect()
        self.conn_label.configure(text="未连接", foreground="red")
        self.log("[连接] 已断开")

    def on_verify(self):
        if not self.bot.mem:
            self.log("[验证] 请先附加进程")
            return
        self.collect()
        player = self.bot.mem.get_player()
        if player and player["max_hp"] > 0:
            self.log(f"[验证] OK! HP={player['hp']}/{player['max_hp']} "
                     f"坐标=({player['x']:.1f},{player['y']:.1f})")
        else:
            self.log("[验证] 读不到有效数据，检查偏移配置")

    def on_start(self):
        self.collect()
        self.bot.apply_settings(self.settings)
        if self.bot.start():
            self.log("[BOT] 挂机启动")

    def on_stop(self):
        self.bot.stop()

    def on_save(self):
        self.collect()
        save_settings(self.settings)
        self.log("[配置] 已保存到 settings.json")

    def collect(self):
        """从界面收集配置"""
        s = self.settings
        s["process_name"] = self.proc_entry.get().strip()
        try:
            s["player"]["base_offset"] = parse_hex(self.entries["p_base"].get())
            s["player"]["offsets"] = [
                parse_hex(x) for x in self.entries["p_offsets"].get().split(",")
                if x.strip()]
            for key, tag in [("x_offset", "p_x"), ("y_offset", "p_y"),
                             ("hp_offset", "p_hp"), ("max_hp_offset", "p_maxhp"),
                             ("mp_offset", "p_mp"), ("max_mp_offset", "p_maxmp"),
                             ("map_id_offset", "p_map")]:
                s["player"][key] = parse_hex(self.entries[tag].get())

            s["monster"]["base_offset"] = parse_hex(self.entries["m_base"].get())
            s["monster"]["offsets"] = [
                parse_hex(x) for x in self.entries["m_offsets"].get().split(",")
                if x.strip()]
            for key, tag in [("next_offset", "m_next"), ("x_offset", "m_x"),
                             ("y_offset", "m_y"), ("hp_offset", "m_hp"),
                             ("id_offset", "m_id")]:
                s["monster"][key] = parse_hex(self.entries[tag].get())

            for name in s["keys"]:
                s["keys"][name] = self.entries[f"key_{name}"].get().strip()

            s["hp_threshold"] = self.hp_scale.get() / 100
            s["mp_threshold"] = self.mp_scale.get() / 100
            s["attack_range"] = int(self.atk_entry.get().strip() or 50)
            s["potion_cooldown"] = float(self.cd_entry.get().strip() or 1.0)

            skills_raw = self.skills_text.get("1.0", "end").strip()
            if skills_raw:
                s["skills"] = json.loads(skills_raw)
        except ValueError:
            self.log("[错误] 偏移字段需为十六进制（如 0x1C）")
        except json.JSONDecodeError:
            self.log("[错误] 技能JSON格式不对")

    # ---------- 状态刷新 ----------

    def log(self, msg):
        ts = time.strftime("%H:%M:%S")
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{ts}] {msg}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _drain_log_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log(msg)
        except queue.Empty:
            pass

    def refresh(self):
        self._drain_log_queue()

        st = self.bot.get_state()
        if st["max_hp"] > 0:
            ratio = min(st["hp"] / st["max_hp"], 1.0) * 100
            self.hp_bar["value"] = ratio
            self.hp_text.configure(text=f"HP {st['hp']}/{st['max_hp']}")
        if st["max_mp"] > 0:
            ratio = min(st["mp"] / st["max_mp"], 1.0) * 100
            self.mp_bar["value"] = ratio
            self.mp_text.configure(text=f"MP {st['mp']}/{st['max_mp']}")

        self.pos_label.configure(text=f"坐标: ({st['x']:.1f}, {st['y']:.1f})")
        self.map_label.configure(text=f"地图: {st['map_id']}")
        near = (f"({st['nearest'][0]:.1f}, {st['nearest'][1]:.1f})"
                if st["nearest"] else "-")
        self.mob_label.configure(text=f"怪物: {st['monster_count']}")
        self.near_label.configure(text=f"最近怪: {near}")
        state = st["bot_state"] if self.bot.running else "已停止"
        self.state_label.configure(text=f"状态: {state}")

        self.root.after(200, self.refresh)


def main():
    root = tk.Tk()
    app = App(root)
    root.mainloop()
    app.bot.disconnect()


if __name__ == "__main__":
    main()
