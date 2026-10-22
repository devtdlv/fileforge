# Junction Release Guide (v0.1.0)

Windows release package prepared; public GitHub release pending user approval.

## What is produced

| Artifact | Location |
|----------|----------|
| Onedir app | `dist/Junction/Junction.exe` (+ `_internal/`) |
| Portable ZIP | `release/Junction-v0.1.0-windows-x64.zip` |
| SHA-256 | `release/Junction-v0.1.0-windows-x64.zip.sha256` |

Layout inside the ZIP:

```text
Junction/
  Junction.exe
  LICENSE
  _internal/
    ... bundled runtime, PySide6, Qt plugins ...
```

## Build requirements

- Windows 10 or later (x64)
- Python 3.13 virtual environment at `.venv`
- Project installed with packaging extras: `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"`
- PyInstaller (included in `[project.optional-dependencies].dev`)

## Build command

From the repository root:

```powershell
.\tools\build_windows.ps1 -Clean
```

Optional:

```powershell
.\tools\build_windows.ps1 -SkipZip
```

The script validates Python 3.13, imports `fileforge` and PyInstaller, builds `packaging/Junction.spec`, copies `LICENSE`, and creates the ZIP + checksum.

## End-user install (after a public release)

1. Download `Junction-v0.1.0-windows-x64.zip`.
2. Optionally verify SHA-256 against the published `.sha256` file.
3. Extract the complete `Junction` folder (do not run only the `.exe` without `_internal`).
4. Double-click `Junction.exe`.
5. Operation history remains at `%LOCALAPPDATA%\FileForge\fileforge.db`.

## Unsigned executable warning

The build is **not** digitally signed. Windows SmartScreen or Defender may warn on first launch. That is expected for an unsigned community release. Do not disable antivirus to “fix” the warning.

## Verification checklist (maintainer)

- [ ] `.\tools\build_windows.ps1 -Clean` succeeds
- [ ] `dist\Junction\Junction.exe` exists
- [ ] `qwindows.dll` present under `_internal\PySide6\plugins\platforms\`
- [ ] `FILEFORGE_SMOKE_EXIT=1` launch returns exit code 0
- [ ] Extract ZIP to a folder outside the repo and smoke-launch again
- [ ] VersionInfo shows ProductName Junction / 0.1.0
- [ ] `Junction.exe` shows the Junction icon in Explorer (allow for icon-cache delay)
- [ ] Running app shows the icon in the window title bar and taskbar
- [ ] Existing `%LOCALAPPDATA%\FileForge\fileforge.db` history still opens
- [ ] Manual click-through: Dashboard, Scanner, Organizer, Duplicates, Renamer, History, Settings
- [ ] `.\.venv\Scripts\python.exe -m pytest`
- [ ] `.\.venv\Scripts\python.exe -m ruff check .`

## Publishing (manual only)

Do **not** automate these steps from the agent session:

1. Review artifacts and checksum.
2. Commit packaging sources (not `dist/` / `release/` binaries unless intentionally publishing binaries in-repo).
3. Create a GitHub Release for tag `v0.1.0`.
4. Upload the ZIP and `.sha256` files.
5. Paste release notes from `docs/RELEASE_NOTES_v0.1.0.md`.

## Troubleshooting

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| Missing `qwindows.dll` / platform plugin error | Incomplete extract or antivirus quarantine | Re-extract full ZIP; allow the folder in Defender |
| Missing DLL | Incomplete ZIP copy | Re-download and extract the whole `Junction` folder |
| Empty history after upgrade | Looking in a different data folder | Confirm `%LOCALAPPDATA%\FileForge\fileforge.db` |
| SmartScreen warning | Unsigned EXE | Expected; publish as unsigned until a certificate is available |
