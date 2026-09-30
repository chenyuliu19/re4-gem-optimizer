"""宝物数据配置。

每件宝物：英文名、空槽基础价格、圆形槽数、矩形槽数。
使用稳定英文 ID 作为唯一标识，中文名作显示名。

价格单位为 ptas。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Treasure:
    """一种可镶嵌宝物的定义。

    Attributes:
        treasure_id: 稳定英文 ID。
        name_cn: 中文名称。
        name_en: 英文名称。
        base_price: 空槽基础价格（ptas）。
        round_slots: 圆形槽数。
        rect_slots: 矩形槽数。
    """

    treasure_id: str
    name_cn: str
    name_en: str
    base_price: int
    round_slots: int
    rect_slots: int

    @property
    def total_slots(self) -> int:
        return self.round_slots + self.rect_slots


# 顺序即界面展示顺序。
TREASURES: list[Treasure] = [
    Treasure("flagon", "酒壶", "Flagon", 4000, 2, 0),
    Treasure("splendid_bangle", "华丽手镯", "Splendid Bangle", 4000, 0, 2),
    Treasure("elegant_bangle", "典雅手镯", "Elegant Bangle", 5000, 2, 0),
    Treasure("elegant_mask", "典雅面具", "Elegant Mask", 5000, 3, 0),
    Treasure("butterfly_lamp", "蝴蝶灯", "Butterfly Lamp", 6000, 3, 0),
    Treasure("chalice_of_atonement", "赎罪圣杯", "Chalice of Atonement", 7000, 0, 3),
    Treasure("extravagant_clock", "奢华座钟", "Extravagant Clock", 9000, 1, 1),
    Treasure("golden_lynx", "黄金猞猁", "Golden Lynx", 15000, 2, 1),
    Treasure("ornate_necklace", "华丽项链", "Ornate Necklace", 11000, 2, 2),
    Treasure("elegant_crown", "典雅皇冠", "Elegant Crown", 19000, 2, 3),
]

TREASURE_BY_ID: dict[str, Treasure] = {t.treasure_id: t for t in TREASURES}

NUM_TREASURES = len(TREASURES)
