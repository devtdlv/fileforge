# FileForge Architecture

## Goals

FileForge is a local-first Windows desktop app with:

- A maintainable `src/` package layout
- A PySide6 UI shell and shared design system
- SQLite persistence with versioned migrations
- A reusable read-only folder scanner
- A preview-first organizer with fail-closed execution and journaling

## Package layout

```
src/fileforge/
  core/                 # paths, safety principles
  database/
    connection.py
    schema.py           # migrations (currently v2)
    settings_store.py
    journal.py          # operation batches/entries
  services/
    scanner/            # read-only inventory engine
    organizer/
      models.py
      categories.py
      paths.py
      planner.py        # dry-run plans
      executor.py       # safe moves + journal hooks
  ui/
    models/             # Qt table models
    workers/            # QThread controllers
    pages/
    windows/
```

## Organizer design

1. `OrganizePlanner` uses `FolderScanner` to list files, then maps each file to a destination by mode.
2. Conflicts (existing paths, case-insensitive collisions, invalid scope) mark the plan `BLOCKED`.
3. `OrganizeExecutor` re-validates each file immediately before `Path.rename`, verifies outcomes, then journals success/failure.
4. UI workers never touch widgets from background threads; results cross via Qt signals.

### Organization modes

| Mode | Destination layout |
|------|--------------------|
| `EXTENSION` | `{dest}/{ext}/{filename}` |
| `CATEGORY` | `{dest}/{Images\|Documents\|...}/{filename}` |
| `YEAR_MONTH` | `{dest}/{YYYY}/{MM}/{filename}` |

## Database schema (v2)

- `settings`
- `operation_journal` (summary rows)
- `operation_batches` (batch id, roots, mode, status)
- `operation_entries` (per-file source/destination/status/error)

Journal writes happen around verified filesystem outcomes. Undo is not implemented.

## Safety boundaries

See `fileforge.core.safety`. Scanning and preview are read-only. Apply requires confirmation, refuses overwrites, and fails closed when safety cannot be established (including journal initialization failure).

## Testing

Temporary directories only. Coverage includes planner rules, preview immutability, execution, collisions, stale plans, cancellation, journaling, and Organizer UI confirmation.
