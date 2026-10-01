"""The public release archive must never include user-provided asset files."""

import zipfile

import build_desktop


def test_public_zip_contains_program_but_no_user_assets(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    app = dist / "RE4GemOptimizer"
    gems = app / "assets" / "gems"
    treasures = app / "assets" / "treasures"
    gems.mkdir(parents=True)
    treasures.mkdir(parents=True)
    (app / "RE4GemOptimizer.exe").write_bytes(b"program")
    (gems / "ruby.png").write_bytes(b"user image")
    (treasures / "flagon.jpg").write_bytes(b"user image")
    (gems / "放图片说明.txt").write_text("说明", encoding="utf-8")
    monkeypatch.setattr(build_desktop, "APP_DIR", app)
    monkeypatch.setattr(build_desktop, "DIST", dist)
    monkeypatch.setattr(build_desktop, "PUBLIC_ZIP_PATH", dist / "public.zip")

    build_desktop.make_public_zip()

    with zipfile.ZipFile(dist / "public.zip") as archive:
        names = set(archive.namelist())
    assert "RE4GemOptimizer/RE4GemOptimizer.exe" in names
    assert "RE4GemOptimizer/assets/gems/放图片说明.txt" in names
    assert not any(name.endswith((".png", ".jpg")) for name in names)
