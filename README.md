# 冒险岛怀旧服辅助

纯图色识别方案，不读内存，兼容性好。支持自动加血加蓝、寻路找怪、技能循环释放。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 截取怪物模板

进游戏，截几张怪物的图，裁剪成只有怪物本体的小图片，放到 `templates/` 目录：

```
templates/
  snail.png      # 蜗牛
  slime.png      # 蓝水灵
  ...
```

> 截图时尽量裁掉背景，只保留怪物本身。每个怪种一张图就够，不同形态可以多截几张。

### 3. 校准血蓝条坐标

运行校准工具：

```bash
python calibrate.py
```

按提示截游戏画面，工具会帮你找到血蓝条的像素坐标和颜色，把结果填入 `config.py`。

### 4. 配置按键

打开 `config.py`，确认 `KEYS` 里的按键和你游戏里的快捷键一致。

### 5. 启动

```bash
python main.py
```

按 **F9** 启动/暂停，`Ctrl+C` 退出。

## 配置说明

所有参数在 `config.py` 中：

| 参数 | 说明 |
|------|------|
| `HP_BAR / MP_BAR` | 血蓝条的屏幕坐标和颜色 |
| `HP_POTION_THRESHOLD` | 血量低于多少比例吃红药 (0.5 = 50%) |
| `MP_POTION_THRESHOLD` | 蓝量低于多少比例吃蓝药 |
| `MONSTER_TEMPLATES` | 怪物模板图片路径列表 |
| `MATCH_THRESHOLD` | 模板匹配置信度，0.75 比较平衡 |
| `SKILL_ROTATION` | 技能循环列表，配置按键+冷却+优先级 |
| `SCREEN_CENTER_X` | 屏幕中心X坐标，角色默认在此位置 |

## 架构

```
main.py          启动入口
bot.py           主循环 + 状态机
config.py        全局配置
capture.py       画面截图 (mss)
detector.py      血蓝检测 + 怪物模板匹配 (OpenCV)
controller.py    按键输入 (pydirectinput)
pathfinder.py    寻路（方向逼近）
skill_manager.py 技能循环管理
calibrate.py     血蓝条坐标校准工具
```

## 常见问题

**Q: 按键没反应？**
确认游戏窗口在前台。如果 pydirectinput 仍无效，试试以管理员身份运行 Python。

**Q: 找不到怪？**
降低 `MATCH_THRESHOLD`（如 0.6），或重新截更清晰的怪物模板。不同地图的怪物需要不同模板。

**Q: 误判吃药？**
调高 `HP_POTION_THRESHOLD` 或检查血条坐标是否正确。

**Q: 角色不在屏幕中心？**
修改 `SCREEN_CENTER_X` 为你角色站立位置的 X 坐标。
