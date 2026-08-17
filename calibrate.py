"""
血蓝条坐标校准工具

用法:
    python calibrate.py

功能:
    1. 截取当前屏幕，保存为 calibration_screenshot.png
    2. 你用画图工具打开，找到血条和蓝条的起始位置
    3. 输入坐标，工具自动读取该位置颜色并生成 config 配置片段
"""

import time

import numpy as np
import mss
import cv2


def screenshot():
    """截取全屏并保存"""
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        shot = sct.grab(monitor)
        img = np.array(shot)[:, :, :3]
        cv2.imwrite("calibration_screenshot.png", img)
        print("截图已保存: calibration_screenshot.png")
        return img


def sample_color(img, x, y):
    """读取指定坐标的像素颜色"""
    # OpenCV 是 BGR 格式
    b, g, r = img[y, x]
    return (r, g, b)  # 转回 RGB


def main():
    print("=" * 50)
    print("  冒险岛辅助 - 血蓝条校准工具")
    print("=" * 50)

    print("\n[1/4] 3秒后截屏，请切到游戏画面...")
    for i in range(3, 0, -1):
        print(f"  {i}...")
        time.sleep(1)

    img = screenshot()
    h, w = img.shape[:2]
    print(f"\n截图尺寸: {w} x {h}")

    print("\n[2/4] 请打开 calibration_screenshot.png")
    print("用画图工具（或截图工具）找到：")
    print("  - 血条最左端起始像素的 (x, y) 坐标")
    print("  - 蓝条最左端起始像素的 (x, y) 坐标")
    print("  - 血条/蓝条的总宽度（像素）")

    print("\n[3/4] 输入血条坐标:")
    hp_x = int(input("  血条起始 X: "))
    hp_y = int(input("  血条起始 Y: "))
    hp_w = int(input("  血条宽度: "))

    hp_color_full = sample_color(img, hp_x, hp_y)
    hp_color_empty = sample_color(img, hp_x + hp_w - 1, hp_y)
    print(f"  满血颜色 (RGB): {hp_color_full}")
    print(f"  空血颜色 (RGB): {hp_color_empty}")

    print("\n[4/4] 输入蓝条坐标:")
    mp_x = int(input("  蓝条起始 X: "))
    mp_y = int(input("  蓝条起始 Y: "))
    mp_w = int(input("  蓝条宽度: "))

    mp_color_full = sample_color(img, mp_x, mp_y)
    mp_color_empty = sample_color(img, mp_x + mp_w - 1, mp_y)
    print(f"  满蓝颜色 (RGB): {mp_color_full}")
    print(f"  空蓝颜色 (RGB): {mp_color_empty}")

    print("\n" + "=" * 50)
    print("将以下内容填入 config.py:")
    print("=" * 50)
    print(f"""
HP_BAR = {{
    "x": {hp_x},
    "y": {hp_y},
    "bar_width": {hp_w},
    "color_full":  {hp_color_full},
    "color_empty": {hp_color_empty},
}}

MP_BAR = {{
    "x": {mp_x},
    "y": {mp_y},
    "bar_width": {mp_w},
    "color_full":  {mp_color_full},
    "color_empty": {mp_color_empty},
}}
""")
    print("校准完成！")


if __name__ == "__main__":
    main()
