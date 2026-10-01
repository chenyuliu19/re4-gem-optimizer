"""Windows 构建脚本。

用 Python 3.12 64 位运行，产出：
- dist/RE4GemOptimizer/  整个可运行文件夹（--onedir --windowed）
- dist/RE4GemOptimizer.zip  本地自用压缩包（含用户自行放入的图片）
- dist/RE4GemOptimizer-public.zip  公开发布包（含仓库自带的 16 张图片）

最终用户解压 ZIP 后双击 RE4GemOptimizer.exe 即可，无需安装 Python。

图片保护策略：
- 用户手动放入 dist/RE4GemOptimizer/assets 的 PNG 图片是「用户资产」，绝不能被清理。
- 本脚本先构建到临时目录 build_tmp/，再把临时产物搬运到 dist/RE4GemOptimizer/，
  搬运时保留原 assets 下的用户图片（不删除、不覆盖已存在的同名图片）。
- 若项目根目录存在 assets_backup/（安全备份），构建后会把其中缺失的图片补回，
  确保重新构建后 16 张 PNG 仍在。

用法：
    py -3.12 build_desktop.py            # 完整构建（构建到临时目录，不删用户图片）
    py -3.12 build_desktop.py --no-clean # 跳过清理 build_tmp 与 PyInstaller build 缓存

注意：本脚本不执行 git clean / git reset，也不删除旧 dist 目录整体；
只覆盖由 PyInstaller 生成的程序文件，用户图片始终保留。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
APP_DIR = DIST / "RE4GemOptimizer"
ZIP_PATH = DIST / "RE4GemOptimizer.zip"
PUBLIC_ZIP_PATH = DIST / "RE4GemOptimizer-public.zip"

# 临时构建输出目录（PyInstaller --distpath 指向这里，避免直接写入 dist 时误删用户图片）。
TMP_DIST = ROOT / "build_tmp" / "dist"
TMP_BUILD = ROOT / "build_tmp" / "build"

GEMS_README = """把宝石图片放到本目录，按英文名命名（PNG 格式最佳）：
  ruby.png            红宝石
  sapphire.png        蓝宝石
  yellow_diamond.png  黄钻石
  emerald.png         祖母绿
  alexandrite.png     亚历山大石
  red_beryl.png       红色线柱石

放好后重新打开程序即可显示图片，无需重新打包。
没有图片时程序会显示文字占位图，不影响使用。
"""

TREASURES_README = """把宝物图片放到本目录，按英文名命名（PNG 格式最佳）：
  flagon.png               酒壶
  splendid_bangle.png      华丽手镯
  elegant_bangle.png       典雅手镯
  elegant_mask.png         典雅面具
  butterfly_lamp.png       蝴蝶灯
  chalice_of_atonement.png 赎罪圣杯
  extravagant_clock.png    奢华座钟
  golden_lynx.png          黄金猞猁
  ornate_necklace.png      华丽项链
  elegant_crown.png        典雅皇冠

放好后重新打开程序即可显示图片，无需重新打包。
没有图片时程序会显示文字占位图，不影响使用。
"""

# 期望的用户图片（英文 ID 命名）。
EXPECTED_GEM_IDS = [
    "ruby", "sapphire", "yellow_diamond", "emerald", "alexandrite", "red_beryl",
]
EXPECTED_TREASURE_IDS = [
    "flagon", "splendid_bangle", "elegant_bangle", "elegant_mask",
    "butterfly_lamp", "chalice_of_atonement", "extravagant_clock",
    "golden_lynx", "ornate_necklace", "elegant_crown",
]

BUNDLED_IMAGE_PATHS = tuple(
    Path("assets") / kind / f"{item_id}.png"
    for kind, ids in (("gems", EXPECTED_GEM_IDS), ("treasures", EXPECTED_TREASURE_IDS))
    for item_id in ids
)


def bundled_images() -> list[tuple[Path, Path]]:
    """返回仓库自带图片的 (源文件, 相对路径)，缺图就阻止发布。"""
    images = []
    for relative in BUNDLED_IMAGE_PATHS:
        source = ROOT / relative
        if not source.is_file():
            raise FileNotFoundError(f"缺少发布图片：{source}")
        images.append((source, relative))
    return images


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def ensure_assets(target: Path) -> None:
    gems_dir = target / "assets" / "gems"
    treasures_dir = target / "assets" / "treasures"
    gems_dir.mkdir(parents=True, exist_ok=True)
    treasures_dir.mkdir(parents=True, exist_ok=True)
    # 说明文件（仅当不存在时写入，避免覆盖用户已有说明）。
    gems_readme = gems_dir / "放图片说明.txt"
    if not gems_readme.exists():
        gems_readme.write_text(GEMS_README, encoding="utf-8")
    treasures_readme = treasures_dir / "放图片说明.txt"
    if not treasures_readme.exists():
        treasures_readme.write_text(TREASURES_README, encoding="utf-8")


def restore_user_images(target: Path) -> int:
    """把项目根目录 assets_backup/ 里的图片补回 target，返回补回的图片数。

    不会删除 target 里已有图片，也不覆盖已存在的同名图片。
    """
    backup = ROOT / "assets_backup"
    restored = 0
    for kind, ids in (("gems", EXPECTED_GEM_IDS), ("treasures", EXPECTED_TREASURE_IDS)):
        src_dir = backup / kind
        dst_dir = target / "assets" / kind
        if not src_dir.is_dir():
            continue
        dst_dir.mkdir(parents=True, exist_ok=True)
        for img_id in ids:
            src = src_dir / f"{img_id}.png"
            dst = dst_dir / f"{img_id}.png"
            if src.is_file() and not dst.exists():
                shutil.copy2(src, dst)
                restored += 1
    return restored


def copy_bundled_images(target: Path) -> int:
    """用仓库自带图片补齐缺项，保留用户已放入或从备份恢复的版本。"""
    copied = 0
    for source, relative in bundled_images():
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copy2(source, destination)
            copied += 1
    return copied


def collect_user_images_into_backup() -> None:
    """首次运行：若 dist 里已有用户图片但 assets_backup 缺失，则先备份。

    这一步保证「先保护用户图片」——在任何清理/重建之前把用户图片安全落地。
    """
    backup = ROOT / "assets_backup"
    if (backup / "manifest.json").exists():
        return  # 已有备份，跳过。
    src_gems = APP_DIR / "assets" / "gems"
    src_tres = APP_DIR / "assets" / "treasures"
    for kind, src_dir, ids in (
        ("gems", src_gems, EXPECTED_GEM_IDS),
        ("treasures", src_tres, EXPECTED_TREASURE_IDS),
    ):
        dst_dir = backup / kind
        if src_dir.is_dir():
            dst_dir.mkdir(parents=True, exist_ok=True)
            for img_id in ids:
                src = src_dir / f"{img_id}.png"
                if src.is_file():
                    dst = dst_dir / f"{img_id}.png"
                    if not dst.exists():
                        shutil.copy2(src, dst)


def make_zip() -> None:
    if ZIP_PATH.exists():
        # 单文件删除，不触发批量删除确认。
        import os
        os.remove(ZIP_PATH)
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in APP_DIR.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(DIST))


def make_public_zip() -> None:
    """只收录程序文件及仓库自带图片，避免带进本机私人文件。"""
    images = bundled_images()
    if PUBLIC_ZIP_PATH.exists():
        PUBLIC_ZIP_PATH.unlink()
    with zipfile.ZipFile(PUBLIC_ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in APP_DIR.rglob("*"):
            if not f.is_file():
                continue
            relative = f.relative_to(APP_DIR)
            if relative.parts[0] != "_internal" and relative.as_posix() not in {
                "RE4GemOptimizer.exe",
                "使用说明.txt",
                "assets/gems/放图片说明.txt",
                "assets/treasures/放图片说明.txt",
            }:
                continue
            zf.write(f, f.relative_to(DIST))
        for source, relative in images:
            zf.write(source, Path("RE4GemOptimizer") / relative)


def main() -> None:
    # 某些英文 Windows 控制台默认 cp1252；中文进度提示不应中断构建。
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    do_clean = "--no-clean" not in sys.argv

    # 0. 先保护用户图片：确保 dist 里已放好的图片进入 assets_backup。
    collect_user_images_into_backup()

    # 1. 清理临时构建目录（不是 dist，不含用户图片）。
    if do_clean:
        for p in (ROOT / "build_tmp", ROOT / "build"):
            if p.exists():
                print(f"清理 {p}")
                shutil.rmtree(p, ignore_errors=True)

    # 2. 用 PyInstaller 打包到临时 dist 目录。
    run([
        sys.executable, "-m", "PyInstaller", "--noconfirm",
        "--distpath", str(TMP_DIST),
        "--workpath", str(TMP_BUILD),
        "RE4GemOptimizer.spec",
    ])

    tmp_app = TMP_DIST / "RE4GemOptimizer"
    if not (tmp_app / "RE4GemOptimizer.exe").exists():
        print("错误：未找到打包产物 RE4GemOptimizer.exe")
        sys.exit(1)

    # 3. 把临时产物搬运到正式 dist/RE4GemOptimizer/，保留用户图片。
    APP_DIR.mkdir(parents=True, exist_ok=True)
    _move_tmp_to_app(tmp_app, APP_DIR)

    # 4. 确保 assets 目录存在。
    ensure_assets(APP_DIR)

    # 5. 从备份恢复用户图片（缺失才补，不覆盖已有）。
    restored = restore_user_images(APP_DIR)
    print(f"从备份恢复用户图片：{restored} 张")
    copied = copy_bundled_images(APP_DIR)
    print(f"补齐随程序附带的图片：{copied} 张")

    # 6. 复制面向普通用户的使用说明到产物目录。
    shutil.copy2(ROOT / "DESKTOP_README.txt", APP_DIR / "使用说明.txt")

    # 7. 打成 ZIP（本地自用，含用户图片）。
    make_zip()
    # 8. 单独生成只含仓库自带图片的公开发布包。
    make_public_zip()

    print(f"\n构建完成：\n  文件夹：{APP_DIR}\n  本地 ZIP：{ZIP_PATH}\n  公开 ZIP：{PUBLIC_ZIP_PATH}")


def _move_tmp_to_app(tmp_app: Path, app_dir: Path) -> None:
    """把临时产物搬运到正式目录。

    逐项复制，遇到与用户 assets 同名文件时保留用户版本（不覆盖）。
    """
    # 先删除正式目录里由 PyInstaller 生成的旧程序文件（保留 assets 下的用户图片）。
    # 只删除已知的程序文件/目录，不触碰 assets。
    for name in ("_internal", "RE4GemOptimizer.exe", "使用说明.txt"):
        p = app_dir / name
        if p.exists():
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            else:
                import os
                os.remove(p)

    # 复制程序文件与依赖。
    for item in tmp_app.iterdir():
        src = item
        dst = app_dir / item.name
        if item.name == "assets":
            # assets：只补缺，不覆盖用户已有图片。
            ensure_assets(app_dir)
            for kind in ("gems", "treasures"):
                src_kind = src / kind
                dst_kind = dst / kind
                if src_kind.is_dir():
                    dst_kind.mkdir(parents=True, exist_ok=True)
                    for f in src_kind.iterdir():
                        if f.is_file() and not (dst_kind / f.name).exists():
                            shutil.copy2(f, dst_kind / f.name)
            continue
        if item.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)


if __name__ == "__main__":
    main()
