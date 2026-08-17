"""
输入控制模块

使用 pydirectinput 模拟按键，兼容 DirectInput 游戏。
普通 pyautogui 在很多游戏中按键不生效，pydirectinput 走 DirectInput 路径更靠谱。
"""

import time
import pydirectinput

import config


class Controller:
    def press(self, key_name, duration=0.05):
        """按下并抬起某个键"""
        key = config.KEYS.get(key_name, key_name)
        pydirectinput.keyDown(key)
        time.sleep(duration)
        pydirectinput.keyUp(key)

    def hold(self, key_name, duration=0.5):
        """持续按住某个键一段时间"""
        key = config.KEYS.get(key_name, key_name)
        pydirectinput.keyDown(key)
        time.sleep(duration)
        pydirectinput.keyUp(key)

    def tap(self, key_name):
        """快速点按一次"""
        self.press(key_name, 0.03)

    def move_left(self, duration=0.2):
        self.hold("left", duration)

    def move_right(self, duration=0.2):
        self.hold("right", duration)

    def jump(self):
        self.tap("jump")

    def use_hp_potion(self):
        self.tap("hp_potion")

    def use_mp_potion(self):
        self.tap("mp_potion")

    def attack(self):
        self.tap("attack")

    def cast_skill(self, skill_name):
        self.tap(skill_name)
