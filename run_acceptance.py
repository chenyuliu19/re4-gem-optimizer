"""运行全部验收案例并打印实际结果。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from re4_gems.gem_data import GEMS, GEM_BY_ID
from re4_gems.pricing import multiplier_name
from re4_gems.solver import MODE_TOTAL, solve
from re4_gems.brute_force import cross_validate

GEM_IDS = list(GEM_BY_ID.keys())


def vec(**kwargs):
    v = [0] * len(GEMS)
    for k, c in kwargs.items():
        v[GEM_IDS.index(k)] = c
    return v


def show(result, title, expected_total, expected_multiplier=None):
    print(f"\n=== {title} ===")
    print(f"状态: {result.status}  耗时: {result.elapsed_seconds:.3f}s")
    print(f"总收入: {result.objective:,} ptas")
    print(f"宝物售价合计: {result.treasure_sale:,}  剩余宝石单卖: {result.gem_sale:,}")
    for a in result.assignments:
        t = a.treasure_id
        combo = a.combination
        parts = []
        for g in GEMS:
            c = combo.vector[GEM_IDS.index(g.gem_id)]
            if c > 0:
                parts.append(f"{g.name_cn}x{c}")
        print(
            f"  {t} x{a.count}: {('、'.join(parts)) or '留空'} "
            f"-> 售价 {combo.price_x10//10:,} (倍率 {combo.multiplier/10:.1f} [{multiplier_name(combo.multiplier)}])"
        )
    if result.status != "OPTIMAL" or result.objective != expected_total:
        raise AssertionError(
            f"{title}: 期望 OPTIMAL / {expected_total:,}，实际 {result.status} / {result.objective:,}"
        )
    if expected_multiplier is not None and (
        len(result.assignments) != 1
        or result.assignments[0].combination.multiplier != expected_multiplier
    ):
        raise AssertionError(f"{title}: 期望倍率 {expected_multiplier / 10:.1f}")


def main():
    # 案例 1
    show(solve({"elegant_crown": 1}, vec(sapphire=1, yellow_diamond=1, emerald=1, alexandrite=1, red_beryl=1)), "案例1 皇冠五色 (期望 100000 / 2.0)", 100000, 20)

    # 案例 2
    show(solve({"elegant_crown": 1}, vec(yellow_diamond=2, red_beryl=3)), "案例2 皇冠高价值双色 (期望 108000 / 1.8)", 108000, 18)

    # 案例 3
    show(solve({"elegant_crown": 1}, vec(ruby=2, red_beryl=3)), "案例3 皇冠五颗红色 (期望 98800 / 1.9)", 98800, 19)

    # 案例 5 全局分配
    show(solve({"flagon": 1, "butterfly_lamp": 1}, vec(ruby=2, yellow_diamond=3)), "案例5 全局分配 (期望 49800)", 49800)

    # 案例 6 边界
    show(solve({}, [0] * 6), "案例6a 全空 (期望 0)", 0)
    show(solve({"flagon": 1, "elegant_crown": 1}, [0] * 6), "案例6b 无宝石仅宝物 (期望 4000+19000=23000)", 23000)
    show(solve({}, vec(ruby=1, sapphire=2)), "案例6c 仅宝石无宝物 (期望 3000+8000=11000)", 11000)

    # 交叉验证
    records = cross_validate(num_cases=50, seed=12345)
    all_match = all(r["match"] for r in records)
    print(f"\n=== 案例7 随机交叉验证 (50 例) ===")
    print(f"全部一致: {all_match}")
    if not all_match:
        for r in records:
            if not r["match"]:
                print(f"  不一致: {r}")
        raise AssertionError("随机交叉验证失败")


if __name__ == "__main__":
    main()
