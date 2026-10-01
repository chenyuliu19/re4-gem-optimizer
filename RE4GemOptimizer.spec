# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：生成 dist/RE4GemOptimizer/ 目录（--onedir --windowed）。"""

from PyInstaller.utils.hooks import collect_all

# OR-Tools 有动态库和 data 文件，需要完整收集。
ortools_datas, ortools_binaries, ortools_hiddenimports = collect_all("ortools")

datas = ortools_datas + ortools_binaries
binaries = []
hiddenimports = ortools_hiddenimports

# Pillow 在 Windows 上由 PyInstaller 自带 hook 处理，无需额外配置。

a = Analysis(
    ["desktop_app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["streamlit", "matplotlib"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RE4GemOptimizer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # 无控制台窗口（--windowed）。
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="RE4GemOptimizer",
)
