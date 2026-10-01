"""网页版图片路径回退测试，不依赖 Streamlit 或 Tk。"""

from pathlib import Path

import web_images


def test_backup_image_is_found_when_other_locations_are_empty(monkeypatch, tmp_path: Path):
    roots = (
        tmp_path / "assets",
        tmp_path / "dist" / "RE4GemOptimizer" / "assets",
        tmp_path / "assets_backup",
    )
    monkeypatch.setattr(web_images, "_CANDIDATE_ROOTS", roots)
    backup = roots[2] / "gems" / "ruby.png"
    backup.parent.mkdir(parents=True)
    backup.write_bytes(web_images._PNG_SIGNATURE + b"test-data")

    assert web_images.find_image_path("gems", "ruby") == backup
    assert web_images.image_bytes("gems", "ruby") == backup.read_bytes()


def test_invalid_primary_image_falls_back_to_valid_backup(monkeypatch, tmp_path: Path):
    roots = (tmp_path / "assets", tmp_path / "assets_backup")
    monkeypatch.setattr(web_images, "_CANDIDATE_ROOTS", roots)
    primary = roots[0] / "treasures" / "flagon.png"
    backup = roots[1] / "treasures" / "flagon.png"
    primary.parent.mkdir(parents=True)
    backup.parent.mkdir(parents=True)
    primary.write_bytes(b"not a PNG")
    backup.write_bytes(web_images._PNG_SIGNATURE + b"test-data")

    assert web_images.find_image_path("treasures", "flagon") == backup
