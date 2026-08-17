"""
主逻辑 - 状态机（支持双模式）

BOT_MODE = "memory"  内存驱动（精确坐标+血量数值，推荐）
BOT_MODE = "vision"  图色驱动（模板匹配，备用）

状态流转:
  IDLE -> SEARCHING -> MOVING -> ATTACKING -> SEARCHING ...
"""

import time

import config
from controller import Controller
from skill_manager import SkillManager


class BotState:
    IDLE = "idle"
    SEARCHING = "searching"
    MOVING = "moving"
    ATTACKING = "attacking"


class Bot:
    def __init__(self):
        self.ctrl = Controller()
        self.skills = SkillManager(self.ctrl)
        self.mode = config.BOT_MODE

        # 内存模式组件
        self.mem = None
        # 图色模式组件（惰性加载）
        self._vision = None

        if self.mode == "memory":
            from memory import MemoryReader
            self.mem = MemoryReader()
            ok = self.mem.attach()
            if not ok:
                print("[BOT] 内存附加失败，回退到图色模式")
                self.mode = "vision"

        if self.mode == "vision":
            from capture import ScreenCapture
            from detector import Detector
            from pathfinder import Pathfinder
            cap = ScreenCapture(config.GAME_WIDTH, config.GAME_HEIGHT)
            self._vision = {
                "cap": cap,
                "detector": Detector(cap),
                "pathfinder": Pathfinder(self.ctrl),
            }

        self.state = BotState.IDLE
        self.running = False
        self._last_potion_time = 0

    def toggle(self):
        """启动/暂停"""
        self.running = not self.running
        if self.running:
            self.state = BotState.SEARCHING
            print(f"[BOT] 启动 (模式: {self.mode})")
        else:
            print("[BOT] 暂停")

    # ==================== 内存模式 ====================

    def tick_memory(self):
        player = self.mem.get_player()
        if player is None:
            return

        # ---- 第1优先级：血蓝（精确数值判断）----
        if self._check_hp_mp_memory(player):
            return  # 吃药这轮跳过打怪

        # ---- 找怪 ----
        monsters = self.mem.get_monsters()
        target = self.mem.get_nearest_monster(monsters, player)

        if target is None:
            self._patrol()
            return

        # ---- 移动+攻击（用真实游戏坐标）----
        dx = target["x"] - player["x"]
        dy = target["y"] - player["y"]

        if abs(dx) < config.ATTACK_RANGE_GAME:
            # 进入攻击范围，朝向怪物放技能
            if dx > 0:
                self.ctrl.hold("right", 0.02)
            else:
                self.ctrl.hold("left", 0.02)
            time.sleep(0.02)
            self.skills.cast_next()
            self.state = BotState.ATTACKING
        else:
            # 向怪物移动
            if dx > 0:
                self.ctrl.move_right(0.15)
            else:
                self.ctrl.move_left(0.15)
            self.state = BotState.MOVING

    def _check_hp_mp_memory(self, player):
        """内存模式血蓝检查，返回 True 表示本轮吃了药"""
        now = time.time()
        if now - self._last_potion_time < config.POTION_COOLDOWN:
            return False

        max_hp = max(player["max_hp"], 1)
        max_mp = max(player["max_mp"], 1)
        hp_ratio = player["hp"] / max_hp
        mp_ratio = player["mp"] / max_mp

        if hp_ratio < config.HP_POTION_THRESHOLD:
            self.ctrl.use_hp_potion()
            self._last_potion_time = now
            print(f"  [吃药] HP {player['hp']}/{player['max_hp']}"
                  f" ({hp_ratio:.0%})，吃红药")
            return True

        if mp_ratio < config.MP_POTION_THRESHOLD:
            self.ctrl.use_mp_potion()
            self._last_potion_time = now
            print(f"  [吃药] MP {player['mp']}/{player['max_mp']}"
                  f" ({mp_ratio:.0%})，吃蓝药")
            return True

        return False

    # ==================== 图色模式 ====================

    def tick_vision(self):
        v = self._vision
        cap, detector, pathfinder = v["cap"], v["detector"], v["pathfinder"]

        self._check_hp_mp_vision(detector, cap)

        screen = cap.grab()
        monsters = detector.find_monsters(screen)
        target = detector.find_nearest_monster(monsters)

        if target is None:
            self._patrol()
            return

        status = pathfinder.move_to(target["x"])
        if status == "reached":
            pathfinder.face_direction(target["x"])
            time.sleep(0.02)
            self.skills.cast_next()
        else:
            self.state = BotState.MOVING

    def _check_hp_mp_vision(self, detector, cap):
        now = time.time()
        if now - self._last_potion_time < config.POTION_COOLDOWN:
            return

        screen = cap.grab()
        hp = detector.get_hp_ratio(screen)
        if hp < config.HP_POTION_THRESHOLD:
            self.ctrl.use_hp_potion()
            self._last_potion_time = now
            print(f"  [吃药] HP={hp:.0%}，吃红药")
            return

        mp = detector.get_mp_ratio(screen)
        if mp < config.MP_POTION_THRESHOLD:
            self.ctrl.use_mp_potion()
            self._last_potion_time = now
            print(f"  [吃药] MP={mp:.0%}，吃蓝药")

    # ==================== 公共 ====================

    def _patrol(self):
        """没怪时左右巡逻"""
        self.state = BotState.SEARCHING
        import random
        direction = random.choice(["left", "right"])
        self.ctrl.hold(direction, duration=0.3)

    def tick(self):
        if not self.running:
            return
        if self.mode == "memory":
            self.tick_memory()
        else:
            self.tick_vision()

    def run_forever(self):
        print(f"[BOT] 就绪，按 {config.BOT_HOTKEY.upper()} 启动/暂停")
        import keyboard
        keyboard.on_press_key(config.BOT_HOTKEY, lambda _: self.toggle())

        try:
            while True:
                self.tick()
                time.sleep(config.BOT_INTERVAL)
        except KeyboardInterrupt:
            print("\n[BOT] 已退出")
        finally:
            if self.mem:
                self.mem.detach()
