"""
内存数值搜索工具（类简化版 Cheat Engine）

用途：定位血量/蓝量/坐标在内存中的地址，不用装 CE 也能找。

原理（经典「精确值扫描」）:
  1. 你告诉它当前血量数值（比如 1523）
  2. 它扫整个进程内存，记录所有值等于 1523 的地址
  3. 你在游戏里掉血（比如掉到 1499），再输入 1499 做二次筛选
  4. 重复 2~3 次后剩下一个地址，就是血量的内存地址

用法:
    python scanner.py

流程结束后把地址填到 config.py 的 MEMORY 里。
"""

import sys

import pymem
import pymem.process
import pymem.memory


def scan_process(pm, value, prev_results=None):
    """扫描进程内存，返回值等于 value 的地址列表"""
    results = []
    target = value.to_bytes(4, byteorder="little")

    # 遍历进程所有可读内存区域
    mem_regions = list(pymem.memory.virtual_query_ex(pm.process_handle))

    for region in mem_regions:
        # 只扫已提交、可读的内存
        if region.State != 0x1000:  # MEM_COMMIT
            continue
        if region.Protect in (0, 0x01, 0x20, 0x40):  # 跳过不可读区域
            continue

        size = region.RegionSize
        if size > 0x10000000:  # 跳过超大区域
            continue

        try:
            data = pm.read_bytes(region.BaseAddress, size)
        except (pymem.exception.MemoryReadError, OSError):
            continue

        # 如果是二次筛选，只检查上次的地址是否还匹配
        if prev_results is not None:
            for addr in prev_results:
                if region.BaseAddress <= addr < region.BaseAddress + size:
                    offset = addr - region.BaseAddress
                    if data[offset:offset + 4] == target:
                        results.append(addr)
        else:
            # 首次扫描，找所有匹配位置
            pos = 0
            while True:
                idx = data.find(target, pos)
                if idx == -1:
                    break
                results.append(region.BaseAddress + idx)
                pos = idx + 1

    return results


def main():
    print("=" * 55)
    print("  内存数值搜索工具 - 定位血量/坐标地址")
    print("=" * 55)

    process_name = input("\n游戏进程名 (如 MapleStory.exe): ").strip()
    try:
        pm = pymem.Pymem(process_name)
    except pymem.exception.ProcessNotFound:
        print(f"找不到进程 {process_name}")
        sys.exit(1)
    except pymem.exception.CouldNotOpenProcess:
        print("无法打开进程，请以管理员身份运行本工具")
        sys.exit(1)

    print(f"已附加: {process_name} (PID={pm.process_id})")

    results = None
    round_num = 0

    while True:
        round_num += 1
        print(f"\n--- 第 {round_num} 轮扫描 ---")
        raw = input("当前数值 (回车退出): ").strip()
        if not raw:
            break

        try:
            value = int(raw)
        except ValueError:
            print("请输入整数")
            continue

        results = scan_process(pm, value, results)

        if len(results) == 0:
            print("没有匹配地址，数值可能变了或不是 4 字节整数")
            results = None
            continue
        elif len(results) == 1:
            print(f"\n[锁定] 唯一地址: 0x{results[0]:X}")
            print("把这个地址填到 config.py 的 MEMORY 配置中")
            print("(如果重启游戏后地址变化，还需要用 CE 找基址偏移)")
            break
        elif len(results) <= 10:
            print(f"剩 {len(results)} 个候选:")
            for a in results:
                print(f"  0x{a:X}")
            print("去游戏里让数值变化，再扫描一次")
        else:
            print(f"剩 {len(results)} 个候选，继续在游戏里改变数值后再扫")

    pm.close_process()


if __name__ == "__main__":
    main()
