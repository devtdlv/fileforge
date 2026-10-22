# FileForge

FileForge is a local-first Windows desktop application for safely organizing files, detecting duplicates, bulk renaming, reviewing storage information, and reversing supported operations when it is safe to do so.

Built with Python 3.13 and PySide6. All data stays on your machine. No cloud services, paid APIs, or external databases.

## Current status

**Milestone 6 (Professional Operation History)** builds on the shell, Scanner, Organizer, Duplicate Finder, and Bulk Renamer:

- Desktop application window with sidebar navigation
- Seven content pages (Dashboard through Settings)
- SQLite foundation with schema versioning, settings, and an operation journal
- **Folder Scanner**: read-only inventory with filter/sort/cancel
- **Organizer**: preview-first moves by extension, category, or modified year/month
- **Duplicate Finder**: staged size filtering + SHA-256 grouping (strictly read-only)
- **Bulk Renamer**: preview-first renames with conflict detection and journaling
- **Operation History**: read-only browser for journaled batches and file outcomes
- Background workers for scanning, organization, duplicates, renaming, and history loads
- Conflict detection with no silent overwrites
- Automated tests and Ruff lint configuration

**Not yet implemented:** duplicate deletion/cleanup, undo/recovery, scan inventory persistence across restarts, and PyInstaller packaging.

## Planned features

| Feature | Status |
|---------|--------|
| Application shell and navigation | Available |
| Local SQLite settings and operation journal | Available |
| Folder Scanner inventory (read-only) | Available |
| Rules-based Organizer with preview | Available |
| Duplicate Finder (detection only, no deletion) | Available |
| Bulk Renamer with conflict checks | Available |
| Operation History (read-only browse) | Available |
| Safe undo / recovery | Planned |
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

## Operation History quick start

1. Open **Operation History** (Ctrl+6).
2. Review summary counts and the batch table (newest first by default).
3. Select a batch to inspect per-file outcomes, including recorded errors.
4. Filter by Organizer / Bulk Renamer, status, or search paths.
5. Click **Refresh** after new Organizer or Renamer applies.

History is read-only. Undo is not available.

## Bulk Renamer quick start

1. Open **Bulk Renamer** (Ctrl+5).
2. Load files, configure rules, preview, then confirm apply.

## Duplicate Finder quick start

1. Open **Duplicate Finder** (Ctrl+4).
2. Choose a folder and start a scan. Detection is read-only.

## Organizer quick start

1. Open **Organizer** (Ctrl+3).
2. Choose source and destination folders, preview, then confirm apply.

## Folder Scanner quick start

1. Open **Folder Scanner** (Ctrl+2).
2. Choose a folder and click **Start Scan**.

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
3. **Milestone 3** - Organizer with preview and confirmed apply
4. **Milestone 4** - Duplicate Finder (detection only)
5. **Milestone 5** - Bulk Renamer (preview-first)
6. **Milestone 6** - Operation History (read-only) *(current)*
7. **Milestone 7** - Packaging, polish, and portfolio screenshots

## Screenshot gallery

> **Pending.** Portfolio screenshots may be added under `docs/screenshots/` from safe demonstration data only. No AI-generated images are included.

## Documentation

- [User Guide](docs/USER_GUIDE.md)
- [Architecture](docs/ARCHITECTURE.md)

## License

MIT License. See [LICENSE](LICENSE).
