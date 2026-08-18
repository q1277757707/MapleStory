"""
冒险岛辅助 - 全局配置

所有可调参数集中在这里，方便不同角色/地图快速切换。
"""

import os
import sys


def resource_path(relative_path):
    """
    兼容 PyInstaller 打包和开发模式的资源路径解析。
    打包后优先找 exe 同级目录（用户可自定义的文件：模板/配置），
    再回退到 PyInstaller 内部 _MEIPASS/_internal 目录。
    """
    # 1. PyInstaller onedir: exe 同级优先（用户自定义）
    base_external = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.getcwd()
    p = os.path.join(base_external, relative_path)
    if os.path.exists(p):
        return p

    # 2. PyInstaller 内部资源目录
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            q = os.path.join(meipass, relative_path)
            if os.path.exists(q):
                return q
        # 新版 PyInstaller onedir 内部资源在 exe 同级的 _internal
        q = os.path.join(base_external, "_internal", relative_path)
        if os.path.exists(q):
            return q

    # 3. 开发模式 / 原始相对路径
    return os.path.join(os.getcwd(), relative_path)

# ======================== 按键映射 ========================
# 冒险岛默认按键布局，按你实际设置改
KEYS = {
    "left":       "left",        # 左方向键
    "right":      "right",       # 右方向键
    "up":         "up",          # 上方向键
    "down":       "down",        # 下方向键
    "jump":       "alt",         # 跳跃
    "attack":     "z",           # 普攻
    "hp_potion":  "end",         # 红药快捷键
    "mp_potion":  "delete",      # 蓝药快捷键
    "skill_1":    "a",           # 技能1
    "skill_2":    "s",           # 技能2
    "skill_3":    "d",           # 技能3
    "skill_4":    "f",           # 技能4
}

# ======================== 血蓝条检测 ========================
# 冒险岛血蓝条通常在屏幕左上角或底部，具体坐标需要你截图后量取
# 截一张游戏图，用画图/截图工具找到血条和蓝条的像素位置
HP_BAR = {
    "x": 165,          # 血条采样点 X 坐标（屏幕内）
    "y": 35,           # 血条采样点 Y 坐标
    "bar_width": 120,   # 血条总宽度（像素）
    # 血条满时颜色和空时颜色（RGB），用于判断剩余比例
    "color_full":  (255, 0, 0),    # 红色满血
    "color_empty": (50, 0, 0),     # 暗红空血
}

MP_BAR = {
    "x": 165,
    "y": 50,
    "bar_width": 120,
    "color_full":  (0, 0, 255),    # 蓝色满蓝
    "color_empty": (0, 0, 50),     # 暗蓝空蓝
}

# 吃药阈值：低于这个比例自动吃药
HP_POTION_THRESHOLD = 0.5    # 血量低于 50% 吃红
MP_POTION_THRESHOLD = 0.3    # 蓝量低于 30% 吃蓝

# 吃药后冷却（秒），防止狂按
POTION_COOLDOWN = 1.5

# ======================== 怪物检测 ========================
# 怪物模板图片放在 templates/ 目录下，截图裁剪怪物贴图即可
MONSTER_TEMPLATES = [
    "templates/snail.png",      # 蜗牛
    "templates/slime.png",      # 蓝水灵
    # 添加更多怪物模板...
]
MATCH_THRESHOLD = 0.75         # 模板匹配置信度阈值 (0~1)，越高越严格

# ======================== 寻路参数 ========================
# 角色在屏幕中心附近，怪物偏左就往左走，偏右就往右走
SCREEN_CENTER_X = 960          # 1920分辨率中心，按你实际分辨率改
MOVE_DEADZONE = 50             # 怪物在中心50像素内不移动，直接打
ATTACK_RANGE = 80              # 图色模式：怪物在此像素距离内开始攻击
ATTACK_RANGE_GAME = 60         # 内存模式：游戏坐标距离内开始攻击（按技能射量调）

# ---- Y轴/跳跃/梯子（冒险岛游戏坐标 Y 向下为正，怪物在上方 = 怪物Y < 玩家Y）----
VERTICAL_TOLERANCE = 20        # Y差小于此值视为同层，不跳不爬
JUMP_HEIGHT_THRESHOLD = 30     # Y差达到此值触发跳跃（中等高度差，比如台阶）
LADDER_HEIGHT_THRESHOLD = 50   # Y差达到此值触发爬梯子（大高度差，平台间）

# ---- 卡住检测 ----
STUCK_TIMEOUT = 2.0            # 坐标多久没变化判定卡住（秒）
STUCK_MOVE_THRESHOLD = 5       # 位移小于此值算卡住（游戏坐标）

# ---- 巡逻路径模式 ----
PATROL_REACH_TOLERANCE = 30    # 到达路径点的X容差（游戏坐标），小于此算到达

# ======================== 技能循环 ========================
SKILL_ROTATION = [
    {"key": "skill_1", "cooldown": 1.0, "priority": 1},
    {"key": "skill_2", "cooldown": 2.0, "priority": 2},
    {"key": "skill_3", "cooldown": 3.0, "priority": 3},
    {"key": "attack",  "cooldown": 0.3, "priority": 9},  # 普攻兜底
]

# ======================== 全局行为 ========================
BOT_HOTKEY = "f9"       # 按F9启动/暂停
BOT_INTERVAL = 0.15     # 主循环间隔（秒），太快可能卡
BOT_MODE = "memory"     # "memory" 内存驱动 / "vision" 图色驱动

# 游戏窗口分辨率（截图和坐标都基于此）
GAME_WIDTH = 1920
GAME_HEIGHT = 1080

# ======================== 内存读取配置 ========================
# 运行 scanner.py 或 Cheat Engine 找到地址后填这里
# 注意：每次重启游戏，动态地址会变。长期使用需要找「基址+偏移」
MEMORY = {
    # 游戏进程名，任务管理器里看
    "process_name": "MapleStory.exe",

    # ---- 玩家数据 ----
    # 结构: 主模块基址 + base_offset，再逐级解引用 offsets
    # 例: offsets = [0x10, 0x1C, 0x8] 表示 [[[base+0x10]+0x1C]+0x8]
    "player": {
        "base_offset":   0x000000,   # 主模块基址偏移（待逆向填写）
        "offsets":       [0x10, 0x1C, 0x8],   # 多级指针偏移（待逆向填写）
        "x_offset":      0x0C,       # 玩家X坐标 相对结构体偏移
        "y_offset":      0x10,       # 玩家Y坐标
        "hp_offset":     0x14,       # 当前血量
        "max_hp_offset": 0x18,       # 最大血量
        "mp_offset":     0x1C,       # 当前蓝量
        "max_mp_offset": 0x20,       # 最大蓝量
        "map_id_offset": 0x24,       # 地图ID
    },

    # ---- 直填动态地址（scanner_gui.py 扫描后自动写入这里）----
    # 优先级最高：填了就直接读，不用指针链。
    # 注意：游戏重启后地址会失效，需要重扫（scanner_gui 启动时自校验，失效会提示）。
    "cached_addresses": {
        "hp":      0,   # 当前血量地址
        "max_hp":  0,   # 最大血量地址
        "mp":      0,   # 当前蓝量地址
        "max_mp":  0,   # 最大蓝量地址
        "x":       0,   # 玩家X坐标地址
        "y":       0,   # 玩家Y坐标地址
        "map_id":  0,   # 地图ID地址（可选）
    },

    # ---- 怪物列表（链表结构）----
    "monster": {
        "base_offset":  0x000000,    # 怪物链表头（待逆向填写）
        "offsets":      [0x10, 0x20, 0x4],
        "next_offset":  0x00,        # 链表 next 指针偏移
        "x_offset":     0x0C,        # 怪物X坐标
        "y_offset":     0x10,        # 怪物Y坐标
        "hp_offset":    0x14,        # 怪物血量
        "id_offset":    0x18,        # 怪物ID
    },
}

# 内存模式的吃药判断直接用数值比例，不需要图色阈值
# HP_POTION_THRESHOLD / MP_POTION_THRESHOLD 同样生效
