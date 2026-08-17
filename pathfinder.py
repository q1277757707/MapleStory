"""
寻路模块

策略：简单方向逼近。
角色默认在屏幕中心，怪物在左边就按左走，在右边就按右走。
进入攻击范围后停止移动，开始攻击。
"""

import config


class Pathfinder:
    def __init__(self, controller):
        self.ctrl = controller

    def move_to(self, target_x, target_y=None):
        """
        向目标位置移动
        返回: "reached" 已到达攻击范围 / "moving" 移动中 / "unknown" 无目标
        """
        if target_x is None:
            return "unknown"

        dx = target_x - config.SCREEN_CENTER_X

        if abs(dx) < config.ATTACK_RANGE:
            # 已进入攻击范围
            return "reached"
        elif abs(dx) < config.MOVE_DEADZONE:
            # 在死区内，不移动
            return "reached"
        elif dx > 0:
            # 怪物在右边
            self.ctrl.move_right(duration=0.15)
            return "moving"
        else:
            # 怪物在左边
            self.ctrl.move_left(duration=0.15)
            return "moving"

    def face_direction(self, target_x):
        """确保角色朝向怪物方向"""
        dx = target_x - config.SCREEN_CENTER_X
        if dx > config.MOVE_DEADZONE:
            self.ctrl.hold("right", 0.02)
        elif dx < -config.MOVE_DEADZONE:
            self.ctrl.hold("left", 0.02)
