# FileForge

FileForge is a local-first Windows desktop application for safely organizing files, detecting duplicates, bulk renaming, reviewing storage information, and reversing supported operations when it is safe to do so.

Built with Python 3.13 and PySide6. All data stays on your machine. No cloud services, paid APIs, or external databases.

## Current status

**Milestone 1 (Application Shell)** is implemented:

- Desktop application window with sidebar navigation
- Seven content pages (Dashboard through Settings)
- SQLite foundation with schema versioning and settings storage
- Safety architecture documented for future file operations
- Automated tests and Ruff lint configuration

**Not yet implemented:** folder scanning, organizing, duplicate detection/deletion, bulk renaming, undo/recovery, and packaging with PyInstaller. Pages for those features show clear “coming later” empty states. Action buttons that are not ready are disabled.

## Planned features

| Feature | Status |
|---------|--------|
| Application shell and navigation | Available |
| Local SQLite settings and journal foundation | Available |
| Folder Scanner inventory | Planned |
| Rules-based Organizer with preview | Planned |
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

## Tests and lint

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
```

## Safety philosophy

FileForge is designed so that destructive or irreversible filesystem changes are hard to trigger by accident:

1. Preview before applying changes.
2. No silent file overwrites.
3. No automatic deletion of duplicates.
4. Explicit user confirmation before modifying files.
5. Operation journaling and recovery.
6. Undo only when safe and verifiable.
7. No filesystem changes during scanning or preview.
8. Tests use temporary directories, never personal files.

Milestone 1 does **not** move, rename, delete, or undo any user files.

## Development roadmap

1. **Milestone 1** - Project foundation, UI shell, SQLite, tests, docs *(current)*
2. **Milestone 2** - Folder Scanner and read-only inventory
3. **Milestone 3** - Organizer with preview and confirmed apply
4. **Milestone 4** - Duplicate Finder with explicit user decisions
5. **Milestone 5** - Bulk Renamer with conflict handling
6. **Milestone 6** - Operation History and safe undo
7. **Milestone 7** - Packaging, polish, and portfolio screenshots

## Screenshot gallery

> **Pending.** Real screenshots will be captured from the running application in a later step. Placeholder files live under `docs/screenshots/`. No AI-generated images are included.

## Documentation

- [User Guide](docs/USER_GUIDE.md) - using the current application shell
- [Architecture](docs/ARCHITECTURE.md) - package layout and separation of concerns

## License

MIT License. See [LICENSE](LICENSE).
