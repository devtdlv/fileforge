"""Packaging invariants for Junction Windows distribution (no full rebuild)."""

from __future__ import annotations

import ast
import re
import struct
from pathlib import Path

import pytest
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from fileforge import __app_name__, __version__
from fileforge.core.paths import get_app_data_dir, get_default_database_path
from fileforge.core.resources import application_icon_path
from fileforge.main import _load_application_icon

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ICO_SIZES = {(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)}


def test_product_version_matches_package() -> None:
    assert __app_name__ == "Junction"
    assert __version__ == "0.1.0"


def test_database_path_remains_fileforge_compatible(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    app_dir = get_app_data_dir()
    db_path = get_default_database_path()
    assert app_dir == tmp_path / "FileForge"
    assert db_path == tmp_path / "FileForge" / "fileforge.db"
    assert db_path.name == "fileforge.db"
    # Must never resolve under a frozen/_MEIPASS style temp name by default.
    assert "_MEI" not in str(db_path)
    assert "dist" not in str(db_path).lower()


def test_packaging_assets_exist() -> None:
    assert (ROOT / "packaging" / "Junction.spec").is_file()
    assert (ROOT / "packaging" / "junction_entry.py").is_file()
    assert (ROOT / "packaging" / "version_info.txt").is_file()
    assert (ROOT / "tools" / "build_windows.ps1").is_file()
    assert (ROOT / "assets" / "icons" / "junction.svg").is_file()
    assert (ROOT / "assets" / "icons" / "Junction.ico").is_file()
    assert (ROOT / "assets" / "icons" / "junction-256.png").is_file()
    assert (ROOT / "src" / "fileforge" / "resources" / "icons" / "Junction.ico").is_file()


def test_application_icon_ico_contains_expected_sizes() -> None:
    data = (ROOT / "assets" / "icons" / "Junction.ico").read_bytes()
    _reserved, itype, count = struct.unpack_from("<HHH", data, 0)
    assert itype == 1
    assert count == len(EXPECTED_ICO_SIZES)
    sizes: set[tuple[int, int]] = set()
    offset = 6
    for _ in range(count):
        width, height, _c, _r, _p, _b, nbytes, data_off = struct.unpack_from(
            "<BBBBHHII", data, offset
        )
        sizes.add((256 if width == 0 else width, 256 if height == 0 else height))
        assert data[data_off : data_off + 8] == b"\x89PNG\r\n\x1a\n"
        assert nbytes > 0
        offset += 16
    assert sizes == EXPECTED_ICO_SIZES


def test_application_icon_path_resolves_and_loads(qapp: QApplication) -> None:
    path = application_icon_path()
    assert path.is_file()
    assert path.suffix.lower() in {".ico", ".png"}
    icon = QIcon(str(path))
    assert not icon.isNull()
    loaded = _load_application_icon()
    assert loaded is not None
    assert not loaded.isNull()
    qapp.setWindowIcon(loaded)
    assert not qapp.windowIcon().isNull()


def test_version_info_matches_package_version() -> None:
    text = (ROOT / "packaging" / "version_info.txt").read_text(encoding="utf-8")
    assert 'StringStruct("ProductName", "Junction")' in text
    assert f'StringStruct("ProductVersion", "{__version__}")' in text
    assert f'StringStruct("FileVersion", "{__version__}")' in text
    assert 'StringStruct("CompanyName", "devtdlv")' in text
    assert "Junction - Local-First File Toolkit" in text


def test_entry_point_reuses_main_run() -> None:
    source = (ROOT / "packaging" / "junction_entry.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = [
        node
        for node in tree.body
        if isinstance(node, (ast.ImportFrom, ast.Import))
    ]
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "fileforge.main"
        and any(alias.name == "run" for alias in node.names)
        for node in imports
    )


def test_spec_is_onedir_windowed_and_path_safe() -> None:
    text = (ROOT / "packaging" / "Junction.spec").read_text(encoding="utf-8")
    assert "console=False" in text
    assert 'name="Junction"' in text
    assert "COLLECT(" in text
    assert "Junction.ico" in text
    assert "fileforge/resources" in text
    assert "Users\\\\vin_c" not in text
    assert "Users/vin_c" not in text
    assert ".venv" not in text or "virtual-environment" in text.lower()
    # Hard-coded absolute drive paths should not appear.
    assert not re.search(r"[A-Za-z]:\\\\Users\\\\", text)


def test_gitignore_excludes_dist_and_release_artifacts() -> None:
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "dist/" in text
    assert "build/" in text
    assert "release/" in text
    assert "Junction-v*-windows-x64.zip" in text


@pytest.mark.skipif(
    not (ROOT / "dist" / "Junction" / "Junction.exe").is_file(),
    reason="Junction.exe not built in this workspace",
)
def test_built_exe_name_and_qt_platform_plugin() -> None:
    exe = ROOT / "dist" / "Junction" / "Junction.exe"
    assert exe.is_file()
    platforms = ROOT / "dist" / "Junction" / "_internal" / "PySide6" / "plugins" / "platforms"
    assert (platforms / "qwindows.dll").is_file()


@pytest.mark.skipif(
    not (ROOT / "release" / "Junction-v0.1.0-windows-x64.zip").is_file(),
    reason="Release ZIP not present",
)
def test_release_zip_contains_onedir_layout() -> None:
    import zipfile

    zip_path = ROOT / "release" / "Junction-v0.1.0-windows-x64.zip"
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
    assert "Junction/Junction.exe" in names
    assert any(name.endswith("plugins/platforms/qwindows.dll") for name in names)
    # Must not ship developer venv or personal DB.
    joined = "\n".join(names).lower()
    assert ".venv" not in joined
    assert "fileforge.db" not in joined
    assert "appdata" not in joined
