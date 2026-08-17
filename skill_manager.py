"""
技能管理模块

按优先级和冷却时间循环释放技能。
"""

import time

import config


class SkillManager:
    def __init__(self, controller):
        self.ctrl = controller
        # 初始化每个技能的上次释放时间
        self._last_cast = {}
        for skill in config.SKILL_ROTATION:
            self._last_cast[skill["key"]] = 0.0

    def cast_next(self):
        """
        找到可用（冷却结束）且优先级最高的技能释放。
        返回 True 表示释放了技能，False 表示所有技能都在冷却。
        """
        now = time.time()
        # 按优先级排序（priority 数字小的先放）
        rotation = sorted(config.SKILL_ROTATION, key=lambda s: s["priority"])

        for skill in rotation:
            key = skill["key"]
            cd = skill["cooldown"]
            if now - self._last_cast[key] >= cd:
                self.ctrl.cast_skill(key)
                self._last_cast[key] = now
                return True
        return False

    def reset(self):
        """重置所有技能冷却记录"""
        for key in self._last_cast:
            self._last_cast[key] = 0.0
