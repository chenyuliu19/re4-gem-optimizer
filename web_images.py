"""网页版（Streamlit）图片路径查找 —— 不依赖 Tkinter / ImageTk / Pillow。

纯路径查找与字节读取，供 app.py 在每行名称旁显示缩略图使用。

查找顺序（优先用第一个存在且非空的图片文件）：
1. 项目根目录 assets/gems/<id>.png、assets/treasures/<id>.png
2. dist/RE4GemOptimizer/assets/gems/<id>.png、assets/treasures/<id>.png
3. assets_backup/gems/<id>.png、assets_backup/treasures/<id>.png

找不到或文件损坏时返回 None，由调用方显示占位内容，页面与计算仍正常工作。
本模块只读取，绝不移动/删除/覆盖现有 PNG。
"""

from __future__ import annotations

import base64
from pathlib import Path

# 项目根目录（本文件所在目录）。
_PROJECT_ROOT = Path(__file__).resolve().parent

# 候选 assets 目录，按优先级排列。
_CANDIDATE_ROOTS: tuple[Path, ...] = (
    _PROJECT_ROOT / "assets",
    _PROJECT_ROOT / "dist" / "RE4GemOptimizer" / "assets",
    _PROJECT_ROOT / "assets_backup",
)

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _candidate_paths(kind: str, item_id: str) -> list[Path]:
    """返回某个 item 的所有候选图片路径（按优先级）。

    kind 取 "gems" 或 "treasures"。
    """
    if kind not in ("gems", "treasures"):
        raise ValueError(f"kind 必须是 'gems' 或 'treasures'，得到 {kind!r}")
    return [root / kind / f"{item_id}.png" for root in _CANDIDATE_ROOTS]


def find_image_path(kind: str, item_id: str) -> Path | None:
    """返回第一个具有 PNG 文件头的可读图片路径；找不到返回 None。"""
    for path in _candidate_paths(kind, item_id):
        try:
            if path.is_file():
                with path.open("rb") as source:
                    if source.read(8) == _PNG_SIGNATURE:
                        return path
        except OSError:
            continue
    return None


def image_bytes(kind: str, item_id: str) -> bytes | None:
    """返回图片文件字节；缺失/损坏返回 None。"""
    path = find_image_path(kind, item_id)
    if path is None:
        return None
    try:
        data = path.read_bytes()
        if len(data) == 0:
            return None
        # 简单校验 PNG 魔数（避免把损坏文件当图片）。
        if data[:8] == _PNG_SIGNATURE:
            return data
        return None
    except OSError:
        return None


def image_data_url(kind: str, item_id: str) -> str | None:
    """返回内嵌用 base64 data URL；缺失/损坏返回 None。"""
    data = image_bytes(kind, item_id)
    if data is None:
        return None
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:image/png;base64,{b64}"
