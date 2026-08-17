"""
画面捕获模块

使用 mss 进行高速截图，比 PIL ImageGrab 快 5~10 倍。
返回 numpy 数组，直接喂给 OpenCV 处理。
"""

import numpy as np
import mss


class ScreenCapture:
    def __init__(self, width=1920, height=1080):
        self.sct = mss.mss()
        self.monitor = {"top": 0, "left": 0, "width": width, "height": height}

    def grab(self):
        """截取整个屏幕，返回 BGR 格式 numpy 数组（OpenCV 标准）"""
        shot = self.sct.grab(self.monitor)
        # mss 返回 BGRA，转成 BGR 给 OpenCV
        img = np.array(shot)
        return img[:, :, :3]  # 去掉 Alpha 通道

    def grab_region(self, x, y, w, h):
        """截取屏幕指定区域"""
        monitor = {"top": y, "left": x, "width": w, "height": h}
        shot = self.sct.grab(monitor)
        return np.array(shot)[:, :, :3]
