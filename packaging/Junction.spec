# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir spec for Junction (Windows).

Invoke from the repository root via tools/build_windows.ps1, or:

    .\\.venv\\Scripts\\python.exe -m PyInstaller --noconfirm packaging\\Junction.spec

Paths are resolved relative to this spec file so the developer's username and
virtual-environment location are never hard-coded.

Only the Qt modules Junction imports are collected (Widgets / Gui / Core /
Network). Full ``collect_all('PySide6')`` is avoided to keep the bundle smaller
and free of unused WebEngine / 3D plugins.
"""

from __future__ import annotations

from pathlib import Path

SPECDIR = Path(SPECPATH).resolve()
ROOT = SPECDIR.parent

entry = str(SPECDIR / "junction_entry.py")
version_info = str(SPECDIR / "version_info.txt")
src_path = str(ROOT / "src")
icon_path = ROOT / "assets" / "icons" / "Junction.ico"
resources_dir = ROOT / "src" / "fileforge" / "resources"

datas = []
if resources_dir.is_dir():
    datas.append((str(resources_dir), "fileforge/resources"))

a = Analysis(
    [entry],
    pathex=[src_path],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "fileforge",
        "fileforge.main",
        "fileforge.core.paths",
        "fileforge.core.resources",
        "fileforge.core.safety",
        "fileforge.database.connection",
        "fileforge.database.journal",
        "fileforge.database.schema",
        "fileforge.database.settings_store",
        "fileforge.services.scanner",
        "fileforge.services.organizer",
        "fileforge.services.duplicates",
        "fileforge.services.renamer",
        "fileforge.services.history",
        "fileforge.ui.windows.main_window",
        "fileforge.ui.styles.theme",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtNetwork",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest",
        "pytest_qt",
        "ruff",
        "tkinter",
        "unittest",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineQuick",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DRender",
        "PySide6.Qt3DInput",
        "PySide6.Qt3DAnimation",
        "PySide6.Qt3DExtras",
        "PySide6.Qt3DLogic",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtGraphs",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtBluetooth",
        "PySide6.QtNfc",
        "PySide6.QtPositioning",
        "PySide6.QtLocation",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
        "PySide6.QtSensors",
        "PySide6.QtSerialPort",
        "PySide6.QtTextToSpeech",
        "PySide6.QtWebSockets",
        "PySide6.QtWebChannel",
        "PySide6.QtWebView",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Junction",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=version_info,
    icon=str(icon_path) if icon_path.is_file() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Junction",
)
