"""验收测试与规则单元测试。"""

import pytest

from re4_gems.gem_data import GEMS, GEM_BY_ID
from re4_gems.pricing import (
    color_counts_from_vector,
    multiplier_for_color_counts,
    multiplier_name,
    price_for_vector,
)
from re4_gems.solver import MODE_TOTAL, solve
from re4_gems.treasure_data import TREASURE_BY_ID
from re4_gems.brute_force import cross_validate


def gem_vec(**kwargs):
    """按 gem_id 构造六维向量。"""
    v = [0] * len(GEMS)
    for gid, cnt in kwargs.items():
        v[list(GEM_BY_ID.keys()).index(gid)] = cnt
    return v


def gem_inventory(**kwargs):
    return gem_vec(**kwargs)


# ---------- 倍率规则单元测试 ----------

def test_multiplier_rules():
    # 颜色数量分布 -> 期望倍率（整数 10~20）。
    cases = [
        ({}, 10),
        ({"red": 1}, 10),
        ({"red": 1, "blue": 1}, 11),  # 2 色
        ({"red": 2}, 12),  # 某色 2 颗
        ({"red": 1, "blue": 1, "yellow": 1}, 13),  # 3 色
        ({"red": 3}, 14),  # 某色 3 颗
        ({"red": 2, "blue": 2}, 15),  # 两种色各 2 颗
        ({"red": 1, "blue": 1, "yellow": 1, "green": 1}, 16),  # 4 色
        ({"red": 4}, 17),  # 某色 4 颗
        ({"red": 3, "blue": 2}, 18),  # 3+2
        ({"red": 5}, 19),  # 某色 5 颗
        ({"red": 1, "blue": 1, "yellow": 1, "green": 1, "purple": 1}, 20),  # 5 色
    ]
    for cc, expected in cases:
        assert multiplier_for_color_counts(cc) == expected, f"颜色分布 {cc} 期望 {expected}"

    # 规则 4：颜色数量分布 [2,1,1] 取 1.3；[2,1,1,1] 取 1.6。
    assert multiplier_for_color_counts({"red": 2, "blue": 1, "yellow": 1}) == 13
    assert multiplier_for_color_counts({"red": 2, "blue": 1, "yellow": 1, "green": 1}) == 16


def test_ruby_red_beryl_same_color():
    # Ruby 2 + Red Beryl 3 = 五颗红色。
    vec = gem_vec(ruby=2, red_beryl=3)
    cc = color_counts_from_vector(vec)
    assert cc["red"] == 5
    assert multiplier_for_color_counts(cc) == 19


# ---------- 验收案例 ----------

def _solve(treasures, gems, reserved=None, mode=MODE_TOTAL):
    return solve(treasures, gems, reserved, mode=mode, time_limit_seconds=30.0)


def test_case1_crown_five_colors():
    # Sapphire + Yellow Diamond + Emerald + Alexandrite + Red Beryl 各 1。
    result = _solve(
        {"elegant_crown": 1},
        gem_inventory(
            sapphire=1, yellow_diamond=1, emerald=1, alexandrite=1, red_beryl=1
        ),
    )
    assert result.status == "OPTIMAL"
    assert result.objective == 100000
    # 验证方案倍率 2.0。
    crown = [a for a in result.assignments if a.treasure_id == "elegant_crown"]
    assert crown and crown[0].combination.multiplier == 20
    assert crown[0].combination.price_x10 // 10 == 100000


def test_case2_crown_high_value_two_color():
    # Yellow Diamond 2 + Red Beryl 3 -> 108000，倍率 1.8。
    result = _solve(
        {"elegant_crown": 1},
        gem_inventory(yellow_diamond=2, red_beryl=3),
    )
    assert result.status == "OPTIMAL"
    assert result.objective == 108000
    crown = [a for a in result.assignments if a.treasure_id == "elegant_crown"]
    assert crown and crown[0].combination.multiplier == 18


def test_case3_crown_five_red():
    # Ruby 2 + Red Beryl 3 -> 98800，倍率 1.9。
    result = _solve(
        {"elegant_crown": 1},
        gem_inventory(ruby=2, red_beryl=3),
    )
    assert result.status == "OPTIMAL"
    assert result.objective == 98800
    crown = [a for a in result.assignments if a.treasure_id == "elegant_crown"]
    assert crown and crown[0].combination.multiplier == 19


def test_case5_global_allocation():
    # Flagon 1 + Butterfly Lamp 1；Ruby 2 + Yellow Diamond 3。
    result = _solve(
        {"flagon": 1, "butterfly_lamp": 1},
        gem_inventory(ruby=2, yellow_diamond=3),
    )
    assert result.status == "OPTIMAL"
    assert result.objective == 49800

    # 验证方案：Flagon 镶 2 Ruby（12000），灯镶 3 YD（37800）。
    by_treasure = {}
    for a in result.assignments:
        by_treasure.setdefault(a.treasure_id, []).append(a)
    flagon = by_treasure["flagon"][0]
    lamp = by_treasure["butterfly_lamp"][0]
    assert flagon.combination.vector[list(GEM_BY_ID.keys()).index("ruby")] == 2
    assert flagon.combination.price_x10 // 10 == 12000
    assert lamp.combination.vector[list(GEM_BY_ID.keys()).index("yellow_diamond")] == 3
    assert lamp.combination.price_x10 // 10 == 37800


def test_case6_empty_and_no_gems():
    # 全空：收入 0。
    r0 = _solve({}, [0] * len(GEMS))
    assert r0.objective == 0

    # 无宝石，只有宝物：收入 = 宝物基础价之和。
    r1 = _solve({"flagon": 1, "elegant_crown": 1}, [0] * len(GEMS))
    assert r1.objective == TREASURE_BY_ID["flagon"].base_price + TREASURE_BY_ID["elegant_crown"].base_price

    # 只有宝石、无宝物：收入 = 未保留宝石单卖价值。
    r2 = _solve({}, gem_inventory(ruby=1, sapphire=2))
    assert r2.objective == 3000 + 4000 * 2

    # 保留宝石不被消耗/出售。
    r3 = _solve(
        {"elegant_crown": 1},
        gem_inventory(sapphire=1, yellow_diamond=1, emerald=1, alexandrite=1, red_beryl=1),
        reserved=gem_vec(red_beryl=1),
    )
    # 保留 red_beryl 后，皇冠只剩 4 色（Sapphire+YD+Emerald+Alexandrite=22000），
    # 倍率 1.6：(19000+22000)*1.6 = 65600。被保留的 red_beryl 既不消耗也不出售。
    assert r3.objective == 65600
    # 校验 red_beryl 未被消耗（保留的宝石不进可用池，也不会被镶嵌或出售）。
    rb_idx = list(GEM_BY_ID.keys()).index("red_beryl")
    assert r3.consumed_gems[rb_idx] == 0


def test_case7_cross_validation():
    records = cross_validate(num_cases=40, seed=999)
    for r in records:
        assert r["match"], f"案例 {r['case']} 不一致：CP={r['cp_objective']} BF={r['brute_force']} msg={r['verify_msg']}"


def test_case8_multiple_same_treasure_diff_scheme():
    # 同款多件可用不同方案：两个 Flagon，宝石 Ruby 2 + Sapphire 2。
    # Flagon 各 2 槽（圆形）。全局最优应是两个 Flagon 各镶 2 颗同色（1.2 倍率）。
    result = _solve(
        {"flagon": 2},
        gem_inventory(ruby=2, sapphire=2),
    )
    assert result.status == "OPTIMAL"
    # Ruby 两颗的酒壶售价 12000，Sapphire 两颗的酒壶售价 14400。
    assert result.objective == 26400
    assert len(result.assignments) == 2
    # 验证宝石不超库存、每件恰好一种方案。
    from re4_gems.brute_force import verify_solution
    ok, msg = verify_solution({"flagon": 2}, gem_inventory(ruby=2, sapphire=2), [0] * len(GEMS), result)
    assert ok, msg


def test_multiplier_name_covers_all():
    for m in range(10, 21):
        assert multiplier_name(m)
