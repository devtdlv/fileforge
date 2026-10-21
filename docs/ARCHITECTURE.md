# FileForge Architecture

## Goals

FileForge is a local-first Windows desktop app. Current milestones establish:

- A maintainable `src/` package layout
- A PySide6 UI shell with a shared design system
- A SQLite persistence layer separated from the UI
- A reusable, UI-independent read-only folder scanner
- Explicit safety boundaries for future filesystem mutations

## Package layout

```
src/fileforge/
  __init__.py          # version and app name
  __main__.py          # python -m fileforge
  main.py              # QApplication bootstrap and error handling
  core/
    paths.py           # per-user app-data locations
    safety.py          # documented safety principles
  database/
    connection.py      # DatabaseManager, foreign keys, errors
    schema.py          # versioned migrations
    settings_store.py  # parameterized settings CRUD
  services/
    scanner/
      models.py        # ScanEntry, ScanResult, statuses
      engine.py        # FolderScanner (pure Python, no Qt)
      formatting.py    # human-readable sizes/timestamps
  ui/
    styles/theme.py    # central stylesheet / design system
    widgets/           # sidebar, headers, empty states
    models/            # Qt table/proxy models for scan results
    workers/           # QThread controllers (scan worker)
    pages/             # one module per navigation destination
    windows/           # MainWindow shell
  resources/           # local assets (no remote downloads)
```

Tests live under `tests/` and always use temporary directories for databases and sample trees.

## Separation of concerns

| Layer | Responsibility | Must not |
|-------|----------------|----------|
| `ui` | Presentation, navigation, user prompts, worker orchestration | Own filesystem walk logic |
| `services.scanner` | Read-only inventory of a selected folder | Import Qt widgets or mutate files |
| `database` | Connections, migrations, settings/journal storage | Import Qt widgets |
| `core` | Paths, shared constants, safety docs | Perform file organization |

## Folder Scanner

`FolderScanner.scan(root, recursive=..., cancel_check=..., progress_callback=...)` walks an explicitly selected directory and returns a `ScanResult`.

Design notes:

- Metadata only (name, paths, extension, size, mtime, kind)
- Does not follow symlinks or Windows junctions by default
- Tracks visited directory identities to avoid traversal loops
- Records permission and disappearance errors without aborting the whole walk
- Supports cooperative cancellation
- Emits indeterminate progress counts (never fabricated percentages)

`ScanWorkerController` runs the engine on a `QThread`. The UI never touches widgets from the worker thread; results cross the thread boundary through Qt signals.

Scan inventories are kept in memory for the session. They are not persisted to SQLite in Milestone 2.

## Database

- Default path: `%LOCALAPPDATA%\FileForge\fileforge.db`
- Path is injectable for tests via `DatabaseManager(database_path=...)`
- Foreign keys are enabled with `PRAGMA foreign_keys = ON`
- Schema version is tracked in `schema_version`
- Current schema (version 1):
  - `settings(key, value, updated_at)`
  - `operation_journal(id, operation_type, status, summary, details_json, created_at, completed_at)`

The journal table remains a foundation only. Milestone 2 does not record file mutations.

## UI design system

`ui/styles/theme.py` defines a single stylesheet applied to `MainWindow`. Pages and widgets use object names (`PageTitle`, `SectionCard`, `NavList`, etc.) instead of scattered one-off styles.

## Safety architecture

File operations must honor the principles in `fileforge.core.safety`:

1. Preview before applying changes.
2. No silent file overwrites.
3. No automatic deletion of duplicates.
4. Explicit user confirmation before modifying files.
5. Operation journaling and recovery.
6. Undo only when safe and verifiable.
7. No filesystem changes during scanning or preview.
8. Tests must use temporary directories rather than personal files.

Scanning is read-only with respect to user files.

## Testing strategy

- Database tests use `tmp_path` isolation.
- Scanner engine tests build temporary trees (including Unicode names and link cases when available).
- GUI tests use pytest-qt (`qapp`, `qtbot`) against injectable database paths and temporary sample folders.
- Tests must not scan or modify personal user folders.

## Packaging note

PyInstaller packaging is deferred. The editable install and `python -m fileforge` entry are the supported launch paths.
