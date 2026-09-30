"""组合枚举。

对每类宝物，枚举全部合法镶嵌组合（六维宝石数量向量）：
- 三种圆形宝石数量之和不超过圆形槽数。
- 三种矩形宝石数量之和不超过矩形槽数。
- 每种宝石数量不超过当前可用库存。
- 包含全部留空与部分镶嵌的组合。

同形状槽位之间交换宝石不算新组合，因此只需枚举数量向量，不必枚举槽位排列。
"""

from __future__ import annotations

from dataclasses import dataclass

from .gem_data import NUM_GEMS, RECT_GEM_IDS, ROUND_GEM_IDS, GEMS
from .pricing import color_counts_from_vector, multiplier_for_color_counts
from .treasure_data import Treasure

# 六维向量中圆形宝石的索引（Ruby, Sapphire, Yellow Diamond）。
ROUND_INDEXES = [i for i, g in enumerate(GEMS) if g.shape == "round"]
# 矩形宝石的索引（Emerald, Alexandrite, Red Beryl）。
RECT_INDEXES = [i for i, g in enumerate(GEMS) if g.shape == "rect"]


@dataclass(frozen=True)
class Combination:
    """某类宝物的一个合法镶嵌组合。

    Attributes:
        vector: 六维宝石数量向量（固定顺序 Ruby..Red Beryl）。
        color_counts: 颜色 -> 出现次数。
        multiplier: 倍率（整数 10~20）。
        price_x10: 放大 10 倍的最终售价。
        empty_slots: 剩余空槽数。
        gem_value: 已镶嵌宝石基础价格之和（真实价格，非放大）。
    """

    vector: tuple[int, ...]
    color_counts: dict[str, int]
    multiplier: int
    price_x10: int
    empty_slots: int
    gem_value: int


def _enumerate_vectors(round_slots: int, rect_slots: int) -> list[tuple[int, ...]]:
    """枚举满足形状约束的全部六维向量（不含库存上限限制）。"""
    results: list[tuple[int, ...]] = []

    # 圆形部分：三种圆形宝石（Ruby, Sapphire, Yellow Diamond）。
    round_combos: list[tuple[int, int, int]] = []
    for a in range(round_slots + 1):
        for b in range(round_slots + 1 - a):
            for c in range(round_slots + 1 - a - b):
                round_combos.append((a, b, c))

    # 矩形部分：三种矩形宝石（Emerald, Alexandrite, Red Beryl）。
    rect_combos: list[tuple[int, int, int]] = []
    for a in range(rect_slots + 1):
        for b in range(rect_slots + 1 - a):
            for c in range(rect_slots + 1 - a - b):
                rect_combos.append((a, b, c))

    for rc in round_combos:
        for rc2 in rect_combos:
            vec = [0] * NUM_GEMS
            for i, idx in enumerate(ROUND_INDEXES):
                vec[idx] = rc[i]
            for i, idx in enumerate(RECT_INDEXES):
                vec[idx] = rc2[i]
            results.append(tuple(vec))

    return results


def enumerate_combinations(treasure: Treasure, available: tuple[int, ...]) -> list[Combination]:
    """枚举某类宝物在给定可用宝石库存下的全部合法组合。

    Args:
        treasure: 宝物定义。
        available: 六维可用宝石数量向量（已扣除保留部分）。

    Returns:
        全部合法组合（含全空组合）。
    """
    combos: list[Combination] = []
    for vec in _enumerate_vectors(treasure.round_slots, treasure.rect_slots):
        # 库存上限约束。
        if any(vec[i] > available[i] for i in range(NUM_GEMS)):
            continue
        color_counts = color_counts_from_vector(vec)
        mult = multiplier_for_color_counts(color_counts)
        gem_total = 0
        for i, cnt in enumerate(vec):
            gem_total += GEMS[i].price * cnt
        price_x10 = (treasure.base_price + gem_total) * mult
        empty_slots = treasure.total_slots - sum(vec)
        combos.append(
            Combination(
                vector=vec,
                color_counts=dict(color_counts),
                multiplier=mult,
                price_x10=price_x10,
                empty_slots=empty_slots,
                gem_value=gem_total,
            )
        )
    return combos


# 组合缓存：key = (treasure_id, available_vector)。
_cache: dict[tuple, list[Combination]] = {}


def get_combinations(treasure: Treasure, available: tuple[int, ...]) -> list[Combination]:
    """带缓存的组合枚举。"""
    key = (treasure.treasure_id, tuple(available))
    if key not in _cache:
        _cache[key] = enumerate_combinations(treasure, available)
    return _cache[key]
