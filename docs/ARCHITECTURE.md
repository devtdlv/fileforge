# FileForge Architecture

## Goals

FileForge is a local-first Windows desktop app. Milestone 1 establishes:

- A maintainable `src/` package layout
- A PySide6 UI shell with a shared design system
- A SQLite persistence layer separated from the UI
- Explicit safety boundaries for future filesystem work

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
  services/            # reserved for future file-operation services
  ui/
    styles/theme.py    # central stylesheet / design system
    widgets/           # sidebar, headers, empty states
    pages/             # one module per navigation destination
    windows/           # MainWindow shell
  resources/           # local assets (no remote downloads)
```

Tests live under `tests/` and always use temporary directories for databases.

## Separation of concerns

| Layer | Responsibility | Must not |
|-------|----------------|----------|
| `ui` | Presentation, navigation, user prompts | Own SQL or filesystem mutation logic |
| `database` | Connections, migrations, settings/journal storage | Import Qt widgets |
| `core` | Paths, shared constants, safety docs | Perform file organization |
| `services` | Future orchestration of scan/organize/rename | Bypass confirmation/preview rules |

## Database

- Default path: `%LOCALAPPDATA%\FileForge\fileforge.db`
- Path is injectable for tests via `DatabaseManager(database_path=...)`
- Foreign keys are enabled with `PRAGMA foreign_keys = ON`
- Schema version is tracked in `schema_version`
- Current schema (version 1):
  - `settings(key, value, updated_at)`
  - `operation_journal(id, operation_type, status, summary, details_json, created_at, completed_at)`

The journal table is a foundation only. Milestone 1 does not record or reverse file operations.

## UI design system

`ui/styles/theme.py` defines a single stylesheet applied to `MainWindow`. Pages and widgets use object names (`PageTitle`, `SectionCard`, `NavList`, etc.) instead of scattered one-off styles. Focus indicators and contrast are part of that shared sheet.

## Safety architecture

Future file operations must honor the principles in `fileforge.core.safety`:

1. Preview before applying changes.
2. No silent file overwrites.
3. No automatic deletion of duplicates.
4. Explicit user confirmation before modifying files.
5. Operation journaling and recovery.
6. Undo only when safe and verifiable.
7. No filesystem changes during scanning or preview.
8. Tests must use temporary directories rather than personal files.

Scanning and preview code (later milestones) must be read-only with respect to user files.

## Testing strategy

- Database tests use `tmp_path` isolation.
- GUI tests use pytest-qt (`qapp`, `qtbot`) against an injectable database path.
- Tests must not scan or modify personal user folders.

## Packaging note

PyInstaller packaging is deferred. The editable install and `python -m fileforge` entry are the supported Milestone 1 launch paths.
