"""独立的小库存暴力对照与结果核验，不复用生产组合或定价函数。"""

from __future__ import annotations

import itertools
import random

from .gem_data import GEMS, NUM_GEMS
from .inventory import normalize_gems, normalize_treasures, validate_inventory
from .solver import MODE_TOTAL, MODE_TREASURE_ONLY, STATUS_FEASIBLE, STATUS_OPTIMAL, solve
from .treasure_data import TREASURES, TREASURE_BY_ID, Treasure


def _reference_price(treasure: Treasure, vector: tuple[int, ...]) -> tuple[int, int, dict[str, int]]:
    """直接按颜色数量规则重算售价（整数为原价的十倍）。"""
    colors: dict[str, int] = {}
    gem_value = 0
    for gem, count in zip(GEMS, vector):
        gem_value += gem.price * count
        if count:
            colors[gem.color] = colors.get(gem.color, 0) + count
    counts = sorted(colors.values(), reverse=True)
    distinct = len(counts)
    multiplier = 10
    if distinct >= 2:
        multiplier = 11
    if counts and counts[0] >= 2:
        multiplier = max(multiplier, 12)
    if distinct >= 3:
        multiplier = max(multiplier, 13)
    if counts and counts[0] >= 3:
        multiplier = max(multiplier, 14)
    if len(counts) >= 2 and counts[1] >= 2:
        multiplier = max(multiplier, 15)
    if distinct >= 4:
        multiplier = max(multiplier, 16)
    if counts and counts[0] >= 4:
        multiplier = max(multiplier, 17)
    if len(counts) >= 2 and counts[0] >= 3 and counts[1] >= 2:
        multiplier = max(multiplier, 18)
    if counts and counts[0] >= 5:
        multiplier = max(multiplier, 19)
    if distinct >= 5:
        multiplier = max(multiplier, 20)
    return (treasure.base_price + gem_value) * multiplier, multiplier, colors


def _reference_vectors(treasure: Treasure, available: list[int]):
    """逐槽枚举宝石或空槽，以数量向量去除排列重复。"""
    round_choices = [-1] + [i for i, gem in enumerate(GEMS) if gem.shape == "round"]
    rect_choices = [-1] + [i for i, gem in enumerate(GEMS) if gem.shape == "rect"]
    slots = [round_choices] * treasure.round_slots + [rect_choices] * treasure.rect_slots
    seen: set[tuple[int, ...]] = set()
    for placement in itertools.product(*slots):
        vector = [0] * NUM_GEMS
        for gem_index in placement:
            if gem_index >= 0:
                vector[gem_index] += 1
        vec = tuple(vector)
        if vec not in seen and all(vec[i] <= available[i] for i in range(NUM_GEMS)):
            seen.add(vec)
            yield vec


def brute_force_total(
    treasure_counts: dict[str, int], gem_inventory: list[int], reserved: list[int] | None = None,
    mode: str = MODE_TOTAL,
) -> int:
    """逐件暴力搜索小库存的最优目标值，结果单位为 0.1 ptas。"""
    gems = normalize_gems(gem_inventory)
    kept = normalize_gems(reserved)
    treasures = normalize_treasures(treasure_counts)
    validate_inventory(gems, kept, treasures)
    if mode not in (MODE_TOTAL, MODE_TREASURE_ONLY):
        raise ValueError(f"未知优化目标：{mode}")
    available = [gems[i] - kept[i] for i in range(NUM_GEMS)]
    items = [TREASURE_BY_ID[tid] for tid, quantity in treasures.items() for _ in range(quantity)]
    best = -1

    def dfs(pos: int, remaining: list[int], treasure_sale_x10: int) -> None:
        nonlocal best
        if pos == len(items):
            leftover_sale = sum(GEMS[g].price * 10 * remaining[g] for g in range(NUM_GEMS))
            total = treasure_sale_x10 + (leftover_sale if mode == MODE_TOTAL else 0)
            best = max(best, total)
            return
        treasure = items[pos]
        for vector in _reference_vectors(treasure, remaining):
            price_x10, _, _ = _reference_price(treasure, vector)
            next_remaining = [remaining[g] - vector[g] for g in range(NUM_GEMS)]
            dfs(pos + 1, next_remaining, treasure_sale_x10 + price_x10)

    dfs(0, available, 0)
    return best


def random_small_case(seed: int, max_treasures: int = 3, max_gems: int = 4) -> tuple[dict[str, int], list[int], list[int]]:
    rng = random.Random(seed)
    treasure_counts: dict[str, int] = {}
    for treasure in rng.sample(TREASURES, rng.randint(1, max_treasures)):
        treasure_counts[treasure.treasure_id] = rng.randint(1, 2)
    gem_inventory = [rng.randint(0, max_gems) for _ in range(NUM_GEMS)]
    reserved = [rng.randint(0, g) for g in gem_inventory]
    return treasure_counts, gem_inventory, reserved


def verify_solution(treasure_counts, gem_inventory, reserved, result) -> tuple[bool, str]:
    """独立检查每个组合、形状、库存对账及全部金额。"""
    if result.status not in (STATUS_OPTIMAL, STATUS_FEASIBLE):
        return False, f"求解状态没有可核验的方案：{result.status}"
    gems = normalize_gems(gem_inventory)
    kept = normalize_gems(reserved)
    treasures = normalize_treasures(treasure_counts)
    validate_inventory(gems, kept, treasures)
    available = [gems[i] - kept[i] for i in range(NUM_GEMS)]
    consumed = [0] * NUM_GEMS
    sale_x10 = 0
    used_counts: dict[str, int] = {}

    for assignment in result.assignments:
        tid, quantity, combo = assignment.treasure_id, assignment.count, assignment.combination
        if tid not in treasures or type(quantity) is not int or quantity <= 0:
            return False, f"宝物方案的 ID 或件数无效：{tid}，{quantity}"
        treasure = TREASURE_BY_ID[tid]
        vector = combo.vector
        if len(vector) != NUM_GEMS or any(type(n) is not int or n < 0 for n in vector):
            return False, f"宝物 {tid} 的宝石向量无效"
        round_used = sum(vector[i] for i, gem in enumerate(GEMS) if gem.shape == "round")
        rect_used = sum(vector[i] for i, gem in enumerate(GEMS) if gem.shape == "rect")
        if round_used > treasure.round_slots or rect_used > treasure.rect_slots:
            return False, f"宝物 {tid} 的宝石与槽位形状不匹配"
        expected_price, expected_multiplier, expected_colors = _reference_price(treasure, tuple(vector))
        expected_gem_value = sum(GEMS[i].price * vector[i] for i in range(NUM_GEMS))
        if (combo.price_x10 != expected_price or combo.multiplier != expected_multiplier
                or combo.color_counts != expected_colors
                or combo.empty_slots != treasure.total_slots - sum(vector)
                or combo.gem_value != expected_gem_value):
            return False, f"宝物 {tid} 的倍率、售价或组合明细不正确"
        used_counts[tid] = used_counts.get(tid, 0) + quantity
        sale_x10 += expected_price * quantity
        for g in range(NUM_GEMS):
            consumed[g] += vector[g] * quantity

    if used_counts != {tid: q for tid, q in treasures.items() if q > 0}:
        return False, "宝物方案件数与输入库存不匹配"
    if any(consumed[g] > available[g] for g in range(NUM_GEMS)):
        return False, "宝石消耗超过可用库存"
    remaining = [available[g] - consumed[g] for g in range(NUM_GEMS)]
    leftover_sale_x10 = sum(GEMS[g].price * 10 * remaining[g] for g in range(NUM_GEMS))
    if result.mode not in (MODE_TOTAL, MODE_TREASURE_ONLY):
        return False, "求解结果的目标模式无效"
    expected_gem_sale = leftover_sale_x10 if result.mode == MODE_TOTAL else 0
    if result.consumed_gems != consumed or result.remaining_gems != remaining:
        return False, "宝石消耗或剩余数量对账不一致"
    if result.treasure_sale_x10 != sale_x10 or result.gem_sale_x10 != expected_gem_sale:
        return False, "宝物或剩余宝石售价合计不一致"
    if result.objective_x10 != sale_x10 + expected_gem_sale:
        return False, "总收入与重算金额不一致"
    return True, "OK"


def cross_validate(num_cases: int = 50, seed: int = 12345) -> list[dict]:
    records = []
    for i in range(num_cases):
        tc, gi, rv = random_small_case(seed + i)
        cp = solve(tc, gi, rv, mode=MODE_TOTAL, time_limit_seconds=10.0)
        bf = brute_force_total(tc, gi, rv)
        ok, msg = verify_solution(tc, gi, rv, cp)
        records.append({
            "case": i,
            "cp_objective": cp.objective_x10,
            "brute_force": bf,
            "match": cp.status == STATUS_OPTIMAL and cp.objective_x10 == bf and ok,
            "verify_msg": msg,
        })
    return records
