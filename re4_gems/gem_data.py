"""宝石数据配置。

使用稳定英文 ID 作为唯一标识，中文名仅作显示名/别名。
价格单位为 ptas。

六种宝石，但只有五种颜色（Ruby 与 Red Beryl 均属红色）。
宝石分为圆形（round）与矩形（rect）两种形状，只能放入对应形状的槽位。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Gem:
    """一种宝石的定义。

    Attributes:
        gem_id: 稳定英文 ID。
        name_cn: 中文名称。
        name_en: 英文名称。
        color: 颜色 ID（用于颜色组合统计，Ruby 与 Red Beryl 同为 "red"）。
        color_cn: 颜色中文名。
        shape: 形状，取值 "round"（圆形）或 "rect"（矩形）。
        price: 单颗基础价格（ptas）。
    """

    gem_id: str
    name_cn: str
    name_en: str
    color: str
    color_cn: str
    shape: str
    price: int


# 固定顺序的六维宝石向量：Ruby、Sapphire、Yellow Diamond、Emerald、Alexandrite、Red Beryl。
GEMS: list[Gem] = [
    Gem("ruby", "红宝石", "Ruby", "red", "红色", "round", 3000),
    Gem("sapphire", "蓝宝石", "Sapphire", "blue", "蓝色", "round", 4000),
    Gem("yellow_diamond", "黄钻石", "Yellow Diamond", "yellow", "黄色", "round", 7000),
    Gem("emerald", "祖母绿", "Emerald", "green", "绿色", "rect", 5000),
    Gem("alexandrite", "亚历山大石", "Alexandrite", "purple", "紫色", "rect", 6000),
    Gem("red_beryl", "红色线柱石", "Red Beryl", "red", "红色", "rect", 9000),
]

GEM_BY_ID: dict[str, Gem] = {g.gem_id: g for g in GEMS}

# 六维向量固定顺序（索引 0..5）。
GEM_ORDER: list[str] = [g.gem_id for g in GEMS]

NUM_GEMS = len(GEMS)

# 按形状分组（用于组合枚举时的形状约束）。
ROUND_GEM_IDS = [g.gem_id for g in GEMS if g.shape == "round"]
RECT_GEM_IDS = [g.gem_id for g in GEMS if g.shape == "rect"]

# 颜色 ID 列表（去重后恰好 5 种颜色）。
COLORS = ["red", "blue", "yellow", "green", "purple"]
COLOR_CN = {
    "red": "红色",
    "blue": "蓝色",
    "yellow": "黄色",
    "green": "绿色",
    "purple": "紫色",
}

# gem_id -> 六维向量索引
GEM_INDEX: dict[str, int] = {g.gem_id: i for i, g in enumerate(GEMS)}


def gem_price(gem_id: str) -> int:
    return GEM_BY_ID[gem_id].price


def gem_color(gem_id: str) -> str:
    return GEM_BY_ID[gem_id].color
