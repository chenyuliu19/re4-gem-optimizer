"""发布包只包含指定图片，不包含本地用户自行替换的图片。"""

import zipfile

import build_desktop


def _make_bundled_images(root):
    for relative in build_desktop.BUNDLED_IMAGE_PATHS:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"bundled " + relative.name.encode("ascii"))


def test_public_zip_contains_bundled_images_but_not_user_overrides(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    app = dist / "RE4GemOptimizer"
    gems = app / "assets" / "gems"
    treasures = app / "assets" / "treasures"
    gems.mkdir(parents=True)
    treasures.mkdir(parents=True)
    _make_bundled_images(tmp_path)
    (app / "RE4GemOptimizer.exe").write_bytes(b"program")
    (app / "private.txt").write_text("do not publish", encoding="utf-8")
    (gems / "ruby.png").write_bytes(b"user override")
    (treasures / "flagon.jpg").write_bytes(b"user image")
    (gems / "放图片说明.txt").write_text("说明", encoding="utf-8")
    monkeypatch.setattr(build_desktop, "ROOT", tmp_path)
    monkeypatch.setattr(build_desktop, "APP_DIR", app)
    monkeypatch.setattr(build_desktop, "DIST", dist)
    monkeypatch.setattr(build_desktop, "PUBLIC_ZIP_PATH", dist / "public.zip")

    build_desktop.make_public_zip()

    with zipfile.ZipFile(dist / "public.zip") as archive:
        names = set(archive.namelist())
        ruby = archive.read("RE4GemOptimizer/assets/gems/ruby.png")
    expected_images = {
        "RE4GemOptimizer/" + relative.as_posix()
        for relative in build_desktop.BUNDLED_IMAGE_PATHS
    }
    assert expected_images <= names
    assert len(expected_images) == 16
    assert "RE4GemOptimizer/RE4GemOptimizer.exe" in names
    assert "RE4GemOptimizer/assets/gems/放图片说明.txt" in names
    assert "RE4GemOptimizer/assets/treasures/flagon.jpg" not in names
    assert "RE4GemOptimizer/private.txt" not in names
    assert ruby == b"bundled ruby.png"


def test_copy_bundled_images_preserves_existing_user_image(tmp_path, monkeypatch):
    _make_bundled_images(tmp_path)
    target = tmp_path / "app"
    user_ruby = target / "assets" / "gems" / "ruby.png"
    user_ruby.parent.mkdir(parents=True)
    user_ruby.write_bytes(b"user override")
    monkeypatch.setattr(build_desktop, "ROOT", tmp_path)

    copied = build_desktop.copy_bundled_images(target)

    assert copied == 15
    assert user_ruby.read_bytes() == b"user override"
    assert (target / "assets" / "treasures" / "flagon.png").is_file()
