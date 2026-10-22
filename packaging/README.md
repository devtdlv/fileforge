# Packaging assets

| File | Purpose |
|------|---------|
| `junction_entry.py` | Frozen entry point calling `fileforge.main.run` |
| `Junction.spec` | PyInstaller onedir specification |
| `version_info.txt` | Windows VERSIONINFO resource for `Junction.exe` |

Build from the repository root:

```powershell
.\tools\build_windows.ps1 -Clean
```

Application icon sources live under `assets/icons/`. Rebuild raster outputs with:

```powershell
.\.venv\Scripts\python.exe tools\render_junction_icon.py
```

`Junction.spec` embeds `assets/icons/Junction.ico` into `Junction.exe` and bundles
`src/fileforge/resources/icons/` for runtime `QApplication.setWindowIcon()`.
