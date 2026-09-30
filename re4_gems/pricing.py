"""售价与倍率规则。

关键设计：
- 倍率以整数 10~20 表示（1.0 -> 10，2.0 -> 20），内部售价统一放大 10 倍，
  求解与比较过程中不使用浮点金额。
- 最终售价（放大 10 倍）= (宝物基础价格 + 已镶嵌宝石价格之和) * 倍率。
- 空槽不计入颜色；不要求填满全部槽位。
"""

from __future__ import annotations

from typing import Sequence

from .gem_data import GEM_INDEX, GEMS


def color_counts_from_vector(vector: Sequence[int]) -> dict[str, int]:
    """由六维宝石数量向量统计各颜色出现次数。

    Ruby 与 Red Beryl 同属红色，因此合并计数。
    """
    counts: dict[str, int] = {}
    for idx, cnt in enumerate(vector):
        if cnt <= 0:
            continue
        color = GEMS[idx].color
        counts[color] = counts.get(color, 0) + cnt
    return counts


def multiplier_for_color_counts(color_counts: dict[str, int]) -> int:
    """根据颜色数量分布返回倍率（整数，10~20）。

    检查所有满足的条件，只取最高倍率，不叠加。
    """
    counts = sorted(color_counts.values(), reverse=True)
    num_colors = len(counts)

    best = 10  # 无其他适用组合：1.0

    if num_colors >= 2:
        best = max(best, 11)  # 至少 2 种颜色：1.1
    if counts and counts[0] >= 2:
        best = max(best, 12)  # 某色至少 2 颗：1.2
    if num_colors >= 3:
        best = max(best, 13)  # 至少 3 种颜色：1.3
    if counts and counts[0] >= 3:
        best = max(best, 14)  # 某色至少 3 颗：1.4
    if len(counts) >= 2 and counts[0] >= 2 and counts[1] >= 2:
        best = max(best, 15)  # 两种不同颜色分别至少 2 颗：1.5
    if num_colors >= 4:
        best = max(best, 16)  # 至少 4 种颜色：1.6
    if counts and counts[0] >= 4:
        best = max(best, 17)  # 某色至少 4 颗：1.7
    if len(counts) >= 2 and counts[0] >= 3 and counts[1] >= 2:
        best = max(best, 18)  # 两种不同颜色分别至少 3 颗和 2 颗：1.8
    if counts and counts[0] >= 5:
        best = max(best, 19)  # 某色至少 5 颗：1.9
    if num_colors >= 5:
        best = max(best, 20)  # 至少 5 种颜色：2.0

    return best


def multiplier_name(multiplier: int) -> str:
    """返回倍率对应的组合名称（用于界面展示）。"""
    names = {
        10: "无加成",
        11: "至少 2 种颜色",
        12: "某种颜色至少 2 颗",
        13: "至少 3 种颜色",
        14: "某种颜色至少 3 颗",
        15: "两种不同颜色各至少 2 颗",
        16: "至少 4 种颜色",
        17: "某种颜色至少 4 颗",
        18: "两种不同颜色分别至少 3 颗和 2 颗",
        19: "某种颜色至少 5 颗",
        20: "至少 5 种颜色",
    }
    return names.get(multiplier, f"倍率 {multiplier/10:.1f}")


def price_for_vector(base_price: int, vector: Sequence[int]) -> tuple[int, int, dict[str, int]]:
    """给定宝物基础价格与六维宝石向量，返回 (放大10倍售价, 倍率整数, 颜色计数)。

    售价 = (基础价格 + 宝石价格之和) * 倍率，全部使用整数（放大 10 倍）。
    """
    gem_total = 0
    for idx, cnt in enumerate(vector):
        gem_total += GEMS[idx].price * cnt
    color_counts = color_counts_from_vector(vector)
    mult = multiplier_for_color_counts(color_counts)
    # (base + gem_total) * mult，均为整数。
    price_x10 = (base_price + gem_total) * mult
    return price_x10, mult, color_counts
