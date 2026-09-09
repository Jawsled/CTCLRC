# -*- mode: python ; coding: utf-8 -*-

import os
import platform
from pathlib import Path

from PyInstaller.utils.hooks import collect_all


datas = []
binaries = []
hiddenimports = []
icon_path = "assets/ctclrc.ico" if os.name == "nt" else None


for pkg in [
    "torch",
    "torchcodec",
    "transformers",
    "av",
    "ctc_forced_aligner",
    "uroman",
    "unidecode",
]:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass


# PySide6's XCB platform plugin dynamically loads these on Linux.  Bundle them
# so the resulting executable also starts on Mint installations where optional
# XCB packages (notably libxcb-cursor0) are not installed.
if os.name != "nt":
    linux_gui_libraries = [
        "libxcb-cursor.so.0",
        "libxcb-icccm.so.4",
        "libxcb-image.so.0",
        "libxcb-keysyms.so.1",
        "libxcb-randr.so.0",
        "libxcb-render-util.so.0",
        "libxcb-shm.so.0",
        "libxcb-sync.so.1",
        "libxcb-xfixes.so.0",
        "libxcb-render.so.0",
        "libxcb-shape.so.0",
        "libxcb-xkb.so.1",
        "libxcb-util.so.1",
        "libxkbcommon-x11.so.0",
        "libxkbcommon.so.0",
    ]
    library_dirs = [Path(path) for path in ("/lib", "/lib64", "/usr/lib", "/usr/lib64")]
    machine = platform.machine()
    library_dirs += [
        path
        for base in library_dirs[:]
        for path in base.glob(f"{machine}-linux-gnu")
    ]

    for library in linux_gui_libraries:
        candidates = [base / library for base in library_dirs]
        found = next((path for path in candidates if path.exists()), None)
        if found:
            # System libraries are filtered from ``binaries`` by PyInstaller.
            # Package them as data instead; the runtime hook loads them before
            # Qt loads its XCB platform plugin.
            datas.append((str(found), "."))


# Optional offline Hugging Face model bundle.
# Put the downloaded model here before building:
# models/mms-300m-1130-forced-aligner/
if os.path.isdir("models"):
    datas += [
        ("models", "models"),
    ]

if os.path.isdir("assets"):
    datas += [
        ("assets", "assets"),
    ]


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["packaging/pyi_rth_linux_gui.py"] if os.name != "nt" else [],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    exclude_binaries=False,
    name="CTCLRC",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=icon_path,
)
