"""
状态检测模块

负责：
1. 血蓝条比例检测（颜色采样）
2. 怪物定位（OpenCV 模板匹配）
"""

import time
import cv2
import numpy as np

import config


class Detector:
    def __init__(self, capture):
        self.cap = capture
        self._monster_templates = self._load_templates()

    def _load_templates(self):
        """加载所有怪物模板图片"""
        from config import resource_path
        templates = []
        for path in config.MONSTER_TEMPLATES:
            resolved = resource_path(path)
            try:
                tpl = cv2.imread(resolved)
                if tpl is not None:
                    templates.append(tpl)
                    print(f"  [模板] 加载成功: {resolved}")
                else:
                    print(f"  [模板] 文件不存在或无法读取: {resolved}")
            except Exception as e:
                print(f"  [模板] 加载失败 {resolved}: {e}")
        if not templates:
            print("  [警告] 没有加载到任何怪物模板，请截图裁剪怪物贴图放入 templates/ 目录")
        return templates

    # ---------- 血蓝检测 ----------

    def get_hp_ratio(self, screen=None):
        """检测血条剩余比例 (0.0 ~ 1.0)"""
        return self._get_bar_ratio(config.HP_BAR, screen)

    def get_mp_ratio(self, screen=None):
        """检测蓝条剩余比例 (0.0 ~ 1.0)"""
        return self._get_bar_ratio(config.MP_BAR, screen)

    def _get_bar_ratio(self, bar_cfg, screen):
        """
        血蓝条检测原理：
        从条左端往右端逐像素采样，统计颜色符合「满」状态的像素数量，
        占总宽度的比例即为剩余比例。
        """
        if screen is None:
            screen = self.cap.grab()

        x, y = bar_cfg["x"], bar_cfg["y"]
        w = bar_cfg["bar_width"]
        full_color = np.array(bar_cfg["color_full"])

        # 截取血条/蓝条这一行
        strip = screen[y, x:x + w]  # shape: (w, 3), BGR

        # 计算每个像素与满色的距离
        dist = np.abs(strip.astype(float) - full_color).sum(axis=1)
        # 距离小于阈值说明颜色接近满色
        matches = (dist < 100).sum()
        return matches / w

    # ---------- 怪物检测 ----------

    def find_monsters(self, screen=None):
        """
        在画面中找怪物，返回怪物列表 [{x, y, w, h, confidence}]
        使用 OpenCV 模板匹配。
        """
        if screen is None:
            screen = self.cap.grab()

        monsters = []
        if not self._monster_templates:
            return monsters

        screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)

        for tpl in self._monster_templates:
            tpl_gray = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
            th, tw = tpl_gray.shape[::-1]

            # 模板匹配
            result = cv2.matchTemplate(screen_gray, tpl_gray, cv2.TM_CCOEFF_NORMED)
            locs = np.where(result >= config.MATCH_THRESHOLD)

            # 用 NMS 去重（重叠的框只保留置信度最高的）
            boxes = []
            scores = []
            for pt in zip(*locs[::-1]):
                boxes.append([pt[0], pt[1], pt[0] + tw, pt[1] + th])
                scores.append(result[pt[1], pt[0]])

            if boxes:
                boxes = np.array(boxes)
                scores = np.array(scores)
                keep = self._nms(boxes, scores, 0.3)
                for i in keep:
                    x1, y1, x2, y2 = boxes[i]
                    monsters.append({
                        "x": (x1 + x2) // 2,
                        "y": (y1 + y2) // 2,
                        "w": x2 - x1,
                        "h": y2 - y1,
                        "confidence": float(scores[i]),
                    })

        return monsters

    @staticmethod
    def _nms(boxes, scores, threshold):
        """非极大值抑制，去除重叠检测框"""
        if len(boxes) == 0:
            return []
        x1 = boxes[:, 0]
        y1 = boxes[:, 1]
        x2 = boxes[:, 2]
        y2 = boxes[:, 3]
        areas = (x2 - x1) * (y2 - y1)
        order = scores.argsort()[::-1]

        keep = []
        while order.size > 0:
            i = order[0]
            keep.append(i)
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
            union = areas[i] + areas[order[1:]] - inter
            iou = inter / union
            inds = np.where(iou <= threshold)[0]
            order = order[inds + 1]
        return keep

    def find_nearest_monster(self, monsters, center_x=config.SCREEN_CENTER_X):
        """找到离角色最近的怪物"""
        if not monsters:
            return None
        return min(monsters, key=lambda m: abs(m["x"] - center_x))
