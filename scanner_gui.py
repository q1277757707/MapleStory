"""
内存数值扫描器 GUI 版

用途：图形化找血量/蓝量/坐标在内存中的地址，扫到后一键写入 settings.json，
主程序下次启动自动用上，不用手改 config.py。

流程（类简化版 Cheat Engine）:
  1. 选进程名 → 点「附加」
  2. 在游戏里看当前血量（比如 1523）→ 输入到「当前数值」→ 点「扫描」
  3. 在游戏里掉血（比如掉到 1499）→ 输入新值 → 再点「扫描」
  4. 重复 2~3 直到只剩 1 个地址 → 选字段（HP/MP/X/Y 等）→ 点「写入 settings」
  5. 关闭本工具，启动主 gui.py 即可使用

注意：动态地址游戏重启就失效，需要重扫。memory.py 启动时会自校验，
失效会自动回退到指针链模式（如果配过）。
"""

import json
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, scrolledtext

import pymem
import pymem.exception

import config
from scanner import enum_regions, scan_process


# ---------- settings.json 路径（和主 gui.py 保持一致）----------
def _settings_path():
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "settings.json")


SETTINGS_FILE = _settings_path()


# 字段中英文映射（用于下拉框和写入 settings 的 cached_addresses）
FIELD_OPTIONS = [
    ("HP（当前血量）",      "hp"),
    ("Max HP（最大血量）",  "max_hp"),
    ("MP（当前蓝量）",      "mp"),
    ("Max MP（最大蓝量）",  "max_mp"),
    ("X 坐标",              "x"),
    ("Y 坐标",              "y"),
    ("地图 ID",             "map_id"),
]


class ScannerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("内存数值扫描器 - 冒险岛辅助")
        self.root.geometry("760x640")
        self.root.minsize(700, 560)

        self.pm = None
        self.process_name = tk.StringVar(value=config.MEMORY.get("process_name", "MapleStory.exe"))
        self.value_str = tk.StringVar()
        self.field_var = tk.StringVar(value=FIELD_OPTIONS[0][1])
        self.prev_results = None
        self.round_num = 0
        self.scanning = False

        self._build_ui()
        self._load_settings_preview()

    # ---------- UI ----------

    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}

        # ---- 进程附加区 ----
        f1 = ttk.LabelFrame(self.root, text="1. 进程附加")
        f1.pack(fill="x", **pad)

        ttk.Label(f1, text="进程名:").grid(row=0, column=0, sticky="w", padx=8, pady=8)
        ttk.Entry(f1, textvariable=self.process_name, width=28).grid(
            row=0, column=1, sticky="w", padx=4, pady=8)
        ttk.Button(f1, text="附加进程", command=self.on_attach).grid(
            row=0, column=2, padx=4, pady=6)
        ttk.Button(f1, text="刷新进程列表", command=self.on_list_procs).grid(
            row=0, column=3, padx=4, pady=6)

        self.proc_status = ttk.Label(f1, text="状态: 未附加", foreground="#888")
        self.proc_status.grid(row=1, column=0, columnspan=4, sticky="w", padx=8, pady=(0, 6))

        # ---- 扫描区 ----
        f2 = ttk.LabelFrame(self.root, text="2. 输入数值并扫描")
        f2.pack(fill="x", **pad)

        ttk.Label(f2, text="当前数值:").grid(row=0, column=0, sticky="w", padx=8, pady=8)
        ttk.Entry(f2, textvariable=self.value_str, width=14).grid(
            row=0, column=1, sticky="w", padx=4, pady=8)
        ttk.Button(f2, text="首次扫描", command=lambda: self.on_scan(first=True)).grid(
            row=0, column=2, padx=4, pady=6)
        ttk.Button(f2, text="二次筛选", command=lambda: self.on_scan(first=False)).grid(
            row=0, column=3, padx=4, pady=6)
        ttk.Button(f2, text="重置", command=self.on_reset).grid(
            row=0, column=4, padx=4, pady=6)

        self.count_label = ttk.Label(f2, text="候选: 0 个", foreground="#0066cc")
        self.count_label.grid(row=1, column=0, columnspan=5, sticky="w", padx=8, pady=(0, 6))

        # ---- 结果列表 ----
        f3 = ttk.LabelFrame(self.root, text="3. 候选地址")
        f3.pack(fill="both", expand=True, **pad)

        self.listbox = tk.Listbox(f3, height=10, font=("Consolas", 10))
        self.listbox.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        sb = ttk.Scrollbar(f3, orient="vertical", command=self.listbox.yview)
        sb.pack(side="right", fill="y", pady=8)
        self.listbox.config(yscrollcommand=sb.set)

        # ---- 写入区 ----
        f4 = ttk.LabelFrame(self.root, text="4. 锁定后写入 settings.json")
        f4.pack(fill="x", **pad)

        ttk.Label(f4, text="这个地址是什么字段:").grid(row=0, column=0, sticky="w", padx=8, pady=8)
        self.field_combo = ttk.Combobox(
            f4, textvariable=self.field_var, width=22, state="readonly",
            values=[f"{label} ({key})" for label, key in FIELD_OPTIONS])
        self.field_combo.current(0)
        self.field_combo.grid(row=0, column=1, sticky="w", padx=4, pady=8)
        ttk.Button(f4, text="写入 settings.json", command=self.on_write_settings).grid(
            row=0, column=2, padx=4, pady=6)
        ttk.Button(f4, text="查看已写入的地址", command=self.on_show_cached).grid(
            row=0, column=3, padx=4, pady=6)

        # ---- 日志 ----
        f5 = ttk.LabelFrame(self.root, text="日志")
        f5.pack(fill="both", expand=True, **pad)
        self.log = scrolledtext.ScrolledText(f5, height=10, font=("Consolas", 9))
        self.log.pack(fill="both", expand=True, padx=8, pady=8)

    # ---------- 进程 ----------

    def on_attach(self):
        name = self.process_name.get().strip()
        if not name:
            self._log("[错误] 进程名不能为空")
            return
        try:
            self.pm = pymem.Pymem(name)
            self.proc_status.config(
                text=f"状态: 已附加 {name} (PID={self.pm.process_id})",
                foreground="#008800")
            self._log(f"[OK] 已附加 {name} PID={self.pm.process_id}")
            self._log(f"     找到进程后就可以开始扫描了")
        except pymem.exception.ProcessNotFound:
            self.proc_status.config(text="状态: 找不到进程", foreground="#cc0000")
            self._log(f"[错误] 找不到进程 {name}，请先启动游戏")
        except pymem.exception.CouldNotOpenProcess:
            self.proc_status.config(text="状态: 权限不足", foreground="#cc0000")
            self._log("[错误] 无法打开进程，请以管理员身份运行本工具")
        except Exception as e:
            self.proc_status.config(text="状态: 附加失败", foreground="#cc0000")
            self._log(f"[错误] 附加异常: {e}")

    def on_list_procs(self):
        """列出系统里所有可能的冒险岛进程"""
        try:
            import pymem.process
            # 枚举所有进程
            procs = pymem.process.EnumProcesses() if hasattr(pymem.process, "EnumProcesses") else None
            if not procs:
                self._log("[提示] 当前 pymem 版本不支持枚举进程，请手动输入进程名")
                return
            names = []
            for p in procs:
                try:
                    n = pymem.process.ProcessHandle(p).name if hasattr(pymem.process, "ProcessHandle") else None
                    if n and ("maple" in n.lower() or "story" in n.lower()):
                        names.append(n)
                except Exception:
                    continue
            if names:
                self._log("[进程] 找到可能的冒险岛进程: " + ", ".join(set(names)))
            else:
                self._log("[进程] 没找到名字含 maple/story 的进程，请手动输入")
        except Exception as e:
            self._log(f"[提示] 枚举进程失败: {e}，请手动输入进程名")

    # ---------- 扫描 ----------

    def on_scan(self, first):
        if self.pm is None:
            self._log("[错误] 请先附加进程")
            return
        if self.scanning:
            self._log("[提示] 正在扫描中，请稍候")
            return

        raw = self.value_str.get().strip()
        try:
            value = int(raw)
        except ValueError:
            self._log("[错误] 请输入整数")
            return

        if not first and not self.prev_results:
            self._log("[提示] 还没做过首次扫描，自动转为首次扫描")
            first = True

        self.scanning = True
        self.count_label.config(text="扫描中...")
        self._log(f"--- 第 {self.round_num + 1} 轮{'（首次）' if first else '（筛选）'} ---")
        self._log(f"     数值 = {value}")

        # 在后台线程跑，避免界面卡死
        def task():
            t0 = time.time()
            try:
                if first:
                    results = scan_process(self.pm, value, None)
                else:
                    results = scan_process(self.pm, value, self.prev_results)
                dt = time.time() - t0
                self.prev_results = results
                self.round_num += 1
                self.root.after(0, lambda: self._show_results(results, dt))
            except Exception as e:
                err = str(e)
                self.root.after(0, lambda: self._log(f"[错误] 扫描异常: {err}"))
            finally:
                self.scanning = False

        threading.Thread(target=task, daemon=True).start()

    def _show_results(self, results, dt):
        self.listbox.delete(0, "end")
        self._log(f"     耗时 {dt:.2f}s, 剩 {len(results)} 个候选")

        if len(results) == 0:
            self.count_label.config(text="候选: 0 个 (没有匹配)", foreground="#cc0000")
            self._log("[提示] 没有匹配，数值变了或不是 4 字节整数，已自动重置")
            self.prev_results = None
            return

        if len(results) == 1:
            self.count_label.config(text=f"候选: 1 个 (已锁定!)", foreground="#008800")
            self.listbox.insert("end", f"0x{results[0]:X}")
            self._log(f"[锁定] 唯一地址: 0x{results[0]:X}")
            self._log(f"       选择字段后点「写入 settings.json」")
        elif len(results) <= 50:
            self.count_label.config(text=f"候选: {len(results)} 个", foreground="#0066cc")
            for a in results:
                self.listbox.insert("end", f"0x{a:X}")
            self._log(f"       去游戏里让数值变化，再来一次")
        else:
            self.count_label.config(text=f"候选: {len(results)} 个 (太多，继续筛)", foreground="#cc6600")
            for a in results[:200]:
                self.listbox.insert("end", f"0x{a:X}")
            self._log(f"       显示前 200 个，去游戏里改变数值再扫")

    def on_reset(self):
        self.prev_results = None
        self.round_num = 0
        self.listbox.delete(0, "end")
        self.count_label.config(text="候选: 0 个", foreground="#0066cc")
        self._log("[重置] 已清空候选列表，下一轮将是首次扫描")

    # ---------- 写入 settings ----------

    def _load_settings(self):
        """读 settings.json，没有就返回 default_settings 副本"""
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                self._log(f"[警告] settings.json 读取失败: {e}，使用默认配置")
        # 没文件就用 config 默认值
        s = {
            "process_name": config.MEMORY.get("process_name", "MapleStory.exe"),
            "cached_addresses": dict(config.MEMORY.get("cached_addresses", {})),
        }
        return s

    def _load_settings_preview(self):
        s = self._load_settings()
        cached = s.get("cached_addresses", {})
        filled = {k: v for k, v in cached.items() if v}
        if filled:
            self._log(f"[缓存] 已有 {len(filled)} 个缓存地址:")
            for k, v in filled.items():
                self._log(f"     {k:8s} = 0x{v:X}")

    def on_write_settings(self):
        sel = self.listbox.curselection()
        if not sel:
            # 没选就用第一个（如果只有1个结果）
            if self.prev_results and len(self.prev_results) == 1:
                addr = self.prev_results[0]
            else:
                self._log("[错误] 请先在列表里选中一个地址（或扫描到只剩 1 个）")
                return
        else:
            text = self.listbox.get(sel[0])
            try:
                addr = int(text, 16) if text.startswith("0x") else int(text)
            except ValueError:
                self._log(f"[错误] 无法解析地址: {text}")
                return

        field_key = self.field_var.get()
        # combobox 显示的是 "HP（当前血量） (hp)"，取括号里的 key
        for label, key in FIELD_OPTIONS:
            if field_key.endswith(key) or field_key == key:
                field_key = key
                break

        s = self._load_settings()
        s.setdefault("cached_addresses", {})
        s["cached_addresses"][field_key] = addr
        # 同步进程名，方便主程序
        s["process_name"] = self.process_name.get().strip() or s.get("process_name", "MapleStory.exe")

        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(s, f, ensure_ascii=False, indent=2)
            self._log(f"[OK] 已写入 {SETTINGS_FILE}")
            self._log(f"     cached_addresses[{field_key}] = 0x{addr:X}")
            self._log(f"     关闭本工具，启动主 gui.py 即可生效")
        except Exception as e:
            self._log(f"[错误] 写入失败: {e}")

    def on_show_cached(self):
        s = self._load_settings()
        cached = s.get("cached_addresses", {})
        if not cached:
            self._log("[缓存] 还没写入任何地址")
            return
        self._log("[缓存] 当前 settings.json 中的地址:")
        for k, v in cached.items():
            tag = "✓" if v else "✗"
            self._log(f"     {tag} {k:8s} = 0x{v:X}" if v else f"     {tag} {k:8s} = (未填)")

    # ---------- 日志 ----------

    def _log(self, msg):
        ts = time.strftime("%H:%M:%S")
        self.log.insert("end", f"[{ts}] {msg}\n")
        self.log.see("end")


def main():
    root = tk.Tk()
    app = ScannerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
