# FileForge Architecture

## Goals

FileForge is a local-first Windows desktop app with:

- A maintainable `src/` package layout
- A PySide6 UI shell and shared design system
- SQLite persistence with versioned migrations
- A reusable read-only folder scanner
- A preview-first organizer with fail-closed execution and journaling
- A read-only duplicate detection engine (size filter + SHA-256)

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
    duplicates/
      models.py         # groups, progress, status
      hasher.py         # chunked SHA-256 + change detection
      engine.py         # DuplicateFinder (no PySide6)
  ui/
    models/             # Qt table models
    workers/            # QThread controllers
    pages/
    windows/
```

## Duplicate detection design

1. `DuplicateFinder` reuses `FolderScanner` for metadata collection (no symlink/junction follow).
2. Files are grouped by size. Sizes with fewer than two distinct `(device, inode)` identities are skipped.
3. Each physical file is hashed once with chunked SHA-256. Size/mtime are checked before and after reading; mismatches exclude the file.
4. Groups require matching digests and at least two unique physical identities.
5. Potential savings = `(unique_physical_count - 1) × size`. Hard-linked paths share one physical identity so savings are not overstated.
6. Results are session-only in memory. Nothing is uploaded or persisted to SQLite for duplicate scans.
7. The UI worker (`DuplicateWorkerController`) mirrors scanner/organizer conventions: progress/finished/failed signals, cooperative cancel, safe thread cleanup. Widgets are never updated from the worker thread.

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

Journal writes happen around verified filesystem outcomes. Undo is not implemented. Duplicate Finder does not write to these tables.

## Safety boundaries

See `fileforge.core.safety`. Scanning, duplicate detection, and organizer preview are read-only. Apply requires confirmation, refuses overwrites, and fails closed when safety cannot be established (including journal initialization failure). Duplicate Finder never deletes or selects a “keeper” copy.

## Testing

Temporary directories only. Coverage includes planner rules, preview immutability, execution, collisions, stale plans, cancellation, journaling, Organizer UI confirmation, SHA-256 correctness, size-based candidate filtering, duplicate grouping, hard-link-aware savings, and Duplicate Finder worker cleanup.
