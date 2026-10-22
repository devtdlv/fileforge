# FileForge

FileForge is a local-first Windows desktop application for safely organizing files, detecting duplicates, bulk renaming, reviewing storage information, and reversing supported operations when it is safe to do so.

Built with Python 3.13 and PySide6. All data stays on your machine. No cloud services, paid APIs, or external databases.

## Current status

**Milestone 3 (Safe Smart Organizer)** builds on the shell and read-only Folder Scanner:

- Desktop application window with sidebar navigation
- Seven content pages (Dashboard through Settings)
- SQLite foundation with schema versioning, settings, and an operation journal
- **Folder Scanner**: read-only inventory with filter/sort/cancel
- **Organizer**: preview-first moves by extension, category, or modified year/month
- Background workers for scanning, preview, and apply
- Conflict detection with no silent overwrites
- Automated tests and Ruff lint configuration

**Not yet implemented:** duplicate detection/deletion, bulk renaming, undo/recovery UI, scan inventory persistence across restarts, and PyInstaller packaging.

## Planned features

| Feature | Status |
|---------|--------|
| Application shell and navigation | Available |
| Local SQLite settings and operation journal | Available |
| Folder Scanner inventory (read-only) | Available |
| Rules-based Organizer with preview | Available |
| Duplicate Finder (no automatic deletion) | Planned |
| Bulk Renamer with conflict checks | Planned |
| Operation History and safe undo | Planned |
| Storage review insights | Planned |
| PyInstaller packaging | Planned |

## Technology stack

- Python 3.13
- PySide6
- SQLite (`sqlite3` standard library)
- pytest and pytest-qt
- Ruff
- PyInstaller (later milestone)
- Windows PowerShell for setup commands

## Prerequisites

- Windows 10 or later
- Python **3.13** (use `py -3.13`; do not rely on the default `python` if it points elsewhere)
- Git (optional, for version control)

## Installation (Windows PowerShell)

From the project root:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Verify the virtual environment interpreter:

```powershell
.\.venv\Scripts\python.exe --version
```

Expected: `Python 3.13.x`

## Launch

```powershell
.\.venv\Scripts\python.exe -m fileforge
```

## Organizer quick start

1. Open **Organizer** (Ctrl+3).
2. Choose a **source** folder and a **destination** folder.
3. Select a mode: extension, category, or modified year/month.
4. Click **Preview Plan**. Preview never modifies files.
5. Review the before/after table. Conflicts disable Apply.
6. Click **Apply Organization Plan** and confirm the dialog.
7. Use **Cancel** to stop an in-progress preview or apply between moves.

Moves are journaled in SQLite. Undo is not implemented yet.

## Folder Scanner quick start

1. Open **Folder Scanner** (Ctrl+2).
2. Choose a folder and click **Start Scan**.
3. Filter/sort results as needed. Scanning is read-only.

## Tests and lint

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
```

## Safety philosophy

1. Preview before applying changes.
2. No silent file overwrites.
3. No automatic deletion of duplicates.
4. Explicit user confirmation before modifying files.
5. Operation journaling and recovery.
6. Undo only when safe and verifiable.
7. No filesystem changes during scanning or preview.
8. Tests use temporary directories, never personal files.

## Development roadmap

1. **Milestone 1** - Project foundation, UI shell, SQLite, tests, docs
2. **Milestone 2** - Folder Scanner and read-only inventory
3. **Milestone 3** - Organizer with preview and confirmed apply *(current)*
4. **Milestone 4** - Duplicate Finder with explicit user decisions
5. **Milestone 5** - Bulk Renamer with conflict handling
6. **Milestone 6** - Operation History and safe undo
7. **Milestone 7** - Packaging, polish, and portfolio screenshots

## Screenshot gallery

> **Pending.** Portfolio screenshots may be added under `docs/screenshots/` from safe demonstration data only. No AI-generated images are included.

## Documentation

- [User Guide](docs/USER_GUIDE.md)
- [Architecture](docs/ARCHITECTURE.md)

## License

MIT License. See [LICENSE](LICENSE).
