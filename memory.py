"""
内存读取模块

用 pymem 附加游戏进程，直接读取玩家数据和怪物列表。
不碰游戏的写保护，只读不写，检测风险相对低。

前置条件：先用 scanner.py（或 Cheat Engine）找到基址和偏移，
填到 config.py 的 MEMORY 配置里。
"""

import time

import pymem
import pymem.process

import config


class MemoryReader:
    def __init__(self):
        self.pm = None
        self.module_base = 0
        self._ptr_cache = {}

    # ---------- 进程管理 ----------

    def attach(self, process_name=None):
        """附加到游戏进程"""
        process_name = process_name or config.MEMORY["process_name"]
        try:
            self.pm = pymem.Pymem(process_name)
            # 拿主模块基址（用于 module_base + offset 形式的地址）
            module = pymem.process.module_from_name(
                self.pm.process_handle, process_name
            )
            if module:
                self.module_base = module.lpBaseOfDll
            print(f"[内存] 已附加进程: {process_name} (PID={self.pm.process_id})")
            print(f"[内存] 模块基址: 0x{self.module_base:X}")
            return True
        except pymem.exception.ProcessNotFound:
            print(f"[内存] 找不到进程 {process_name}，请先启动游戏")
            return False
        except pymem.exception.CouldNotOpenProcess:
            print(f"[内存] 无法打开进程，可能权限不足。尝试以管理员身份运行本脚本")
            return False

    def detach(self):
        if self.pm:
            self.pm.close_process()
            self.pm = None

    def is_alive(self):
        return self.pm is not None

    # ---------- 基础读取 ----------

    def read_int(self, address):
        """读 4 字节整数"""
        return self.pm.read_int(address)

    def read_long(self, address):
        """读 8 字节整数"""
        return self.pm.read_longlong(address)

    def read_float(self, address):
        """读浮点（坐标常用 float）"""
        return self.pm.read_float(address)

    def read_bytes(self, address, length):
        return self.pm.read_bytes(address, length)

    # ---------- 指针解析 ----------

    def resolve_pointer(self, base, offsets):
        """
        解析多级指针: [[base + off1] + off2] + off3 ...
        冒险岛的玩家数据通常是多级指针，如 [[[base+0x10]+0x1C]+0x8]
        """
        addr = base
        for off in offsets[:-1]:
            addr = self.pm.read_int(addr + off)
        return addr + offsets[-1]

    # ---------- 玩家数据 ----------

    def _read_cached(self, key):
        """从 cached_addresses 直读一个字段。地址=0 视为未填，返回 None。"""
        addr = config.MEMORY.get("cached_addresses", {}).get(key, 0)
        if not addr:
            return None
        try:
            if key in ("x", "y"):
                return self.read_float(addr)
            return self.read_int(addr)
        except (pymem.exception.MemoryReadError, OSError):
            return None

    def _validate_player(self, data):
        """校验读到的玩家数据是否合理（用于检测缓存地址是否失效）"""
        try:
            hp = data.get("hp", -1)
            max_hp = data.get("max_hp", -1)
            if hp is not None and not (0 <= hp <= 999999):
                return False
            if max_hp is not None and not (0 < max_hp <= 999999):
                return False
            if hp is not None and max_hp is not None and hp > max_hp + 5:
                return False
            return True
        except Exception:
            return False

    def get_player(self):
        """
        读取玩家信息，返回 dict:
        {x, y, hp, max_hp, mp, max_mp, map_id}

        优先级:
          1. cached_addresses 直填地址（scanner_gui 扫描结果，方便快捷但重启失效）
          2. player 指针链（base_offset + offsets，CE 逆向结果，长期稳定）
        """
        # ---- 1. 优先用 cached_addresses ----
        cached = config.MEMORY.get("cached_addresses", {})
        if any(cached.get(k) for k in ("hp", "max_hp", "x")):
            try:
                data = {}
                for key in ("x", "y", "hp", "max_hp", "mp", "max_mp", "map_id"):
                    val = self._read_cached(key)
                    if val is not None:
                        data[key] = val
                if self._validate_player(data):
                    return data
                print("[内存] cached_addresses 校验失败，地址可能失效（游戏重启了？），尝试指针链")
            except Exception as e:
                print(f"[内存] cached 读取异常: {e}")

        # ---- 2. 回退到指针链 ----
        m = config.MEMORY["player"]
        try:
            ptr = self.resolve_pointer(self.module_base + m["base_offset"], m["offsets"])
            return {
                "x":      self.read_float(ptr + m["x_offset"]),
                "y":      self.read_float(ptr + m["y_offset"]),
                "hp":     self.read_int(ptr + m["hp_offset"]),
                "max_hp": self.read_int(ptr + m["max_hp_offset"]),
                "mp":     self.read_int(ptr + m["mp_offset"]),
                "max_mp": self.read_int(ptr + m["max_mp_offset"]),
                "map_id": self.read_int(ptr + m["map_id_offset"]),
                "pointer": ptr,
            }
        except (pymem.exception.MemoryReadError, OSError):
            print("[内存] 读取玩家数据失败，地址可能失效（游戏更新了？）")
            return None

    # ---------- 怪物列表 ----------

    def get_monsters(self):
        """
        遍历怪物列表，返回 [{x, y, hp, id}]

        冒险岛怪物通常是链表结构:
        怪物头节点 -> 怪1 -> 怪2 -> ... -> NULL
        每个节点: +0x00 next指针, +0x0C x坐标, +0x10 y坐标, ...

        具体偏移需要你逆向后填到 config.MEMORY["monster"]
        """
        m = config.MEMORY["monster"]
        monsters = []
        try:
            node = self.resolve_pointer(
                self.module_base + m["base_offset"], m["offsets"]
            )
            count = 0
            while node and count < 100:  # 防死循环，最多100只
                x = self.read_float(node + m["x_offset"])
                y = self.read_float(node + m["y_offset"])
                hp = self.read_int(node + m["hp_offset"])
                mob_id = self.read_int(node + m["id_offset"])

                # 过滤已死怪物（hp=0 但还在链表里的）
                if hp > 0:
                    monsters.append({
                        "x": x, "y": y, "hp": hp, "id": mob_id, "node": node
                    })

                node = self.pm.read_int(node + m["next_offset"])
                count += 1
            return monsters
        except (pymem.exception.MemoryReadError, OSError):
            print("[内存] 读取怪物列表失败")
            return monsters

    def get_nearest_monster(self, monsters, player):
        """找离玩家最近的活怪"""
        if not monsters or not player:
            return None
        return min(
            monsters,
            key=lambda m: abs(m["x"] - player["x"]) + abs(m["y"] - player["y"]) * 2,
        )
