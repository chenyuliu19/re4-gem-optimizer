"""输入校验与库存 JSON 导入/导出。

库存 JSON 结构示例：
{
  "gems": {"ruby": 3, "sapphire": 0, ...},
  "reserved": {"ruby": 0, ...},
  "treasures": {"elegant_crown": 1, "flagon": 2, ...}
}
"""

from __future__ import annotations

import json
import math

from .gem_data import GEM_BY_ID, GEM_INDEX, NUM_GEMS
from .treasure_data import TREASURE_BY_ID


class InventoryError(Exception):
    """库存输入错误，携带中文提示。"""


def validate_nonneg_int(value, label: str) -> int:
    """校验值为非负整数，返回 int。"""
    if isinstance(value, bool):
        raise InventoryError(f"{label} 不能是布尔值。")
    if isinstance(value, int):
        v = value
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise InventoryError(f"{label} 必须是有限的非负整数。")
        raise InventoryError(f"{label} 必须是整数，不能使用小数（当前值 {value}）。")
    elif isinstance(value, str):
        s = value.strip()
        if not s:
            v = 0
        else:
            try:
                v = int(s)
            except ValueError:
                raise InventoryError(f"{label} 不是有效整数（当前值 {value}）。")
            if str(v) != s and s.lstrip("+") != str(v):
                raise InventoryError(f"{label} 不是有效整数（当前值 {value}）。")
    else:
        raise InventoryError(f"{label} 类型无效（当前值 {value!r}）。")

    if v < 0:
        raise InventoryError(f"{label} 不能为负数（当前值 {v}）。")
    return v


def normalize_gems(data, label: str = "宝石库存") -> list[int]:
    """从 dict 或 list 归一化为六维宝石数量向量。"""
    result = [0] * NUM_GEMS
    if data is None:
        return result
    if isinstance(data, (list, tuple)):
        if len(data) != NUM_GEMS:
            raise InventoryError(f"{label} 列表长度必须为 {NUM_GEMS}，当前为 {len(data)}。")
        for i, v in enumerate(data):
            result[i] = validate_nonneg_int(v, f"{label}[{i}]")
        return result
    if isinstance(data, dict):
        for key, v in data.items():
            if key not in GEM_BY_ID:
                raise InventoryError(f"{label} 含未知宝石 ID：{key}。")
            idx = GEM_INDEX[key]
            result[idx] = validate_nonneg_int(v, f"{label}.{key}")
        return result
    raise InventoryError(f"{label} 必须是对象或数组。")


def normalize_treasures(data) -> dict[str, int]:
    """从 dict 归一化为 treasure_id -> 数量。"""
    result: dict[str, int] = {}
    if data is None:
        return result
    if not isinstance(data, dict):
        raise InventoryError("宝物库存必须是对象。")
    for key, v in data.items():
        if key not in TREASURE_BY_ID:
            raise InventoryError(f"宝物库存含未知宝物 ID：{key}。")
        result[key] = validate_nonneg_int(v, f"宝物.{key}")
    return result


def validate_inventory(gem_inventory: list[int], reserved: list[int], treasure_counts: dict[str, int]) -> None:
    """校验整份库存的一致性，出错抛 InventoryError。"""
    if len(gem_inventory) != NUM_GEMS:
        raise InventoryError(f"宝石库存维度错误：应为 {NUM_GEMS}，实际 {len(gem_inventory)}。")
    if len(reserved) != NUM_GEMS:
        raise InventoryError(f"保留数量维度错误：应为 {NUM_GEMS}，实际 {len(reserved)}。")
    for i in range(NUM_GEMS):
        gem_inventory[i] = validate_nonneg_int(gem_inventory[i], f"宝石库存[{i}]")
        reserved[i] = validate_nonneg_int(reserved[i], f"保留数量[{i}]")
        if reserved[i] > gem_inventory[i]:
            raise InventoryError(
                f"保留数量超过库存：{list(GEM_BY_ID.keys())[i]} 保留 {reserved[i]} > 库存 {gem_inventory[i]}。"
            )
    for tid, q in treasure_counts.items():
        if tid not in TREASURE_BY_ID:
            raise InventoryError(f"未知宝物 ID：{tid}。")
        treasure_counts[tid] = validate_nonneg_int(q, f"宝物.{tid}")


def inventory_to_dict(gem_inventory: list[int], reserved: list[int], treasure_counts: dict[str, int]) -> dict:
    """导出为可 JSON 序列化的 dict。"""
    gem_ids = list(GEM_BY_ID.keys())
    return {
        "gems": {gem_ids[i]: int(gem_inventory[i]) for i in range(NUM_GEMS)},
        "reserved": {gem_ids[i]: int(reserved[i]) for i in range(NUM_GEMS)},
        "treasures": {k: int(v) for k, v in treasure_counts.items()},
    }


def inventory_from_dict(data: dict) -> tuple[list[int], list[int], dict[str, int]]:
    """从 dict 导入，返回 (gem_inventory, reserved, treasure_counts)。"""
    if not isinstance(data, dict):
        raise InventoryError("库存数据必须是 JSON 对象。")
    unknown = set(data) - {"gems", "reserved", "treasures"}
    if unknown:
        raise InventoryError(f"库存数据含未知字段：{', '.join(sorted(map(str, unknown)))}。")
    missing = {"gems", "treasures"} - set(data)
    if missing:
        raise InventoryError(f"库存数据缺少字段：{', '.join(sorted(missing))}。")
    if not isinstance(data["gems"], (dict, list)):
        raise InventoryError("宝石库存必须是对象或数组。")
    if "reserved" in data and not isinstance(data["reserved"], (dict, list)):
        raise InventoryError("保留数量必须是对象或数组。")
    if not isinstance(data["treasures"], dict):
        raise InventoryError("宝物库存必须是对象。")
    gem_inventory = normalize_gems(data.get("gems"), "宝石库存")
    reserved = normalize_gems(data.get("reserved"), "保留数量")
    treasure_counts = normalize_treasures(data.get("treasures"))
    validate_inventory(gem_inventory, reserved, treasure_counts)
    return gem_inventory, reserved, treasure_counts


def inventory_from_json(content: bytes | str) -> tuple[list[int], list[int], dict[str, int]]:
    """读取 UTF-8 JSON 库存，所有解码和格式问题统一转为 InventoryError。"""
    if isinstance(content, bytes):
        try:
            source = content.decode("utf-8-sig")
        except UnicodeError as exc:
            raise InventoryError("文件编码错误：请保存为 UTF-8 编码的 JSON 文件。") from exc
    elif isinstance(content, str):
        source = content
    else:
        raise InventoryError("库存文件必须是 UTF-8 JSON 文本。")

    def reject_constant(value: str):
        raise InventoryError(f"JSON 不能包含非有限数值 {value}。")

    try:
        data = json.loads(source, parse_constant=reject_constant)
    except json.JSONDecodeError as exc:
        raise InventoryError(f"JSON 格式错误：第 {exc.lineno} 行第 {exc.colno} 列。") from exc
    return inventory_from_dict(data)


def example_inventory() -> tuple[list[int], list[int], dict[str, int]]:
    """加载示例：验收案例 5 的全局分配场景。"""
    gem_inventory = [0] * NUM_GEMS
    gem_ids = list(GEM_BY_ID.keys())
    gem_inventory[gem_ids.index("ruby")] = 2
    gem_inventory[gem_ids.index("yellow_diamond")] = 3
    reserved = [0] * NUM_GEMS
    treasure_counts = {"flagon": 1, "butterfly_lamp": 1}
    return gem_inventory, reserved, treasure_counts
