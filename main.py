"""
冒险岛辅助 - 启动入口

用法:
    python main.py

按 F9 启动/暂停辅助，Ctrl+C 退出。
"""

from bot import Bot


def main():
    bot = Bot()
    bot.run_forever()


if __name__ == "__main__":
    main()
