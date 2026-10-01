"""桌面版图片加载。

按稳定英文 ID 从 exe 同级目录读取图片：
- assets/gems/<id>.png
- assets/treasures/<id>.png

读取 exe 旁边自带或用户替换的图片；缺失或损坏时返回清晰的占位图，程序仍可用。
用户日后替换对应文件并重新打开程序即可看到新图片，无需重新打包。
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageTk


def _base_dir() -> Path:
    """程序运行目录：打包后为 exe 所在目录，源码运行时为项目根目录。"""
    if getattr(sys, "frozen", False):
        # PyInstaller 打包后：sys.executable 是 exe 路径。
        return Path(sys.executable).resolve().parent
    # 源码运行时：本项目位于项目根目录的 desktop/ 子包下，
    # assets 放在项目根目录，因此向上回溯一级。
    return Path(__file__).resolve().parent.parent


def asset_dir() -> Path:
    """返回 assets 根目录（exe 同级的 assets/）。"""
    return _base_dir() / "assets"


def gem_image_path(gem_id: str) -> Path:
    return asset_dir() / "gems" / f"{gem_id}.png"


def treasure_image_path(treasure_id: str) -> Path:
    return asset_dir() / "treasures" / f"{treasure_id}.png"


def _placeholder_text_image(size: int, text: str) -> Image.Image:
    """生成一张清晰的占位图：浅灰底 + 深灰边框 + 居中文字。"""
    img = Image.new("RGB", (size, size), (240, 240, 240))
    draw = ImageDraw.Draw(img)
    # 边框。
    draw.rectangle([0, 0, size - 1, size - 1], outline=(180, 180, 180), width=2)
    # 对角线（提示这是占位）。
    draw.line([0, 0, size - 1, size - 1], fill=(210, 210, 210), width=1)
    draw.line([0, size - 1, size - 1, 0], fill=(210, 210, 210), width=1)
    # 居中文字：优先用中文字体，找不到则用默认。
    font = None
    for name in ("msyh.ttc", "simhei.ttf", "simsun.ttc", "arial.ttf"):
        try:
            font = ImageFont.truetype(name, size=max(10, size // 5))
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default()
    # 文字居中。
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(((size - tw) / 2, (size - th) / 2), text, fill=(130, 130, 130), font=font)
    return img


@lru_cache(maxsize=128)
def _load_resized_png(path_str: str, size: int) -> ImageTk.PhotoImage | None:
    """加载并等比例缩放到 size×size，返回 Tk PhotoImage；失败返回 None。"""
    path = Path(path_str)
    try:
        if not path.is_file():
            return None
        with Image.open(path) as im:
            im = im.convert("RGBA")
            # 等比例缩放（thumbnail 不放大，这里允许放大以填满，用 cover 方式）。
            im.thumbnail((size, size), Image.LANCZOS)
            # 缩放到精确尺寸，居中到透明画布，保证对齐。
            canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            canvas.paste(im, ((size - im.width) // 2, (size - im.height) // 2), im if im.mode == "RGBA" else None)
            return ImageTk.PhotoImage(canvas)
    except Exception:
        # 图片损坏或格式不支持：返回 None，由调用方回退到占位图。
        return None


def load_image(path: Path, size: int, placeholder_text: str) -> ImageTk.PhotoImage:
    """加载图片；缺失/损坏时返回占位图（带文字）。

    Args:
        path: 图片文件路径。
        size: 目标边长（像素）。
        placeholder_text: 占位图上的文字。
    """
    photo = _load_resized_png(str(path), size)
    if photo is not None:
        return photo
    return ImageTk.PhotoImage(_placeholder_text_image(size, placeholder_text))
