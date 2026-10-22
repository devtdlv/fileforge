# FileForge Architecture

## Goals

FileForge is a local-first Windows desktop app with:

- A maintainable `src/` package layout
- A PySide6 UI shell and shared design system
- SQLite persistence with versioned migrations
- A reusable read-only folder scanner
- A preview-first organizer with fail-closed execution and journaling
- A read-only duplicate detection engine (size filter + SHA-256)
- A preview-first bulk renamer with conflict detection and journaling

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
    organizer/          # preview + safe moves
    duplicates/         # size + SHA-256 grouping
    renamer/
      models.py         # rules, items, plan, execution result
      names.py          # stem/extension policy + Windows validation
      rules.py          # ordered rule application
      planner.py        # dry-run preview + collisions
      executor.py       # staged renames + journal hooks
  ui/
    models/             # Qt table models
    workers/            # QThread controllers
    pages/
    windows/
```

## Bulk renamer design

1. `RenamePlanner.inventory` reuses `FolderScanner` (no symlink/junction follow; dedupe by device/inode).
2. `RenamePlanner.build_plan` applies rules in fixed order to selected files only and classifies Ready / Unchanged / Conflict / Invalid / Missing.
3. Collisions are case-insensitive within each parent directory. Occupied destinations block apply unless the occupant is another selected file that is itself renaming away (chain).
4. `RenameExecutor` revalidates fingerprints before each rename. Independent renames use `os.rename` (fails if destination exists on Windows). Chains, swaps, and case-only renames use a two-phase temp-name strategy in the same directory, then finalize. Mid-stage cancellation is not honored once a staged directory group starts; rollback restores temps to original names when possible.
5. Successful and failed outcomes are journaled as `operation_type=bulk_rename` / entry `rename` via the shared `OperationJournal`. Schema v2 tables are reused; no destructive migration.
6. Renames are not filesystem transactions. Partial batches are possible; undo is not implemented.

### Rule order

`search/replace → prefix → suffix → numbering → case (stem only)`

### Extension policy

Final `Path` suffix is preserved (including casing). Stem transforms never rewrite the extension unless a future explicit feature is added.

## Duplicate detection design

Unchanged from Milestone 4: size filter → chunked SHA-256 → hard-link-aware savings. UI refinements separate status text from statistics so completion messaging is not duplicated. Page headers allow subtitle wrapping without clipping.

## Organizer design

1. `OrganizePlanner` uses `FolderScanner` to list files, then maps each file to a destination by mode.
2. Conflicts mark the plan `BLOCKED`.
3. `OrganizeExecutor` re-validates before `Path.rename`, refuses overwrites, journals outcomes.

## Database schema (v2)

- `settings`
- `operation_journal` (summary rows)
- `operation_batches` (batch id, roots, mode, status)
- `operation_entries` (per-file source/destination/status/error)

Organizer writes `organize_move`. Renamer writes `bulk_rename`. Duplicate Finder does not write journal rows.

## Safety boundaries

See `fileforge.core.safety`. Scanning, duplicate detection, and all previews are read-only. Apply paths require confirmation, refuse overwrites, and fail closed when the journal cannot start. Undo is not available.

## Testing

Temporary directories only. Coverage includes renamer rules, planner conflicts, staged chain execution, journaling, renamer UI confirmation, duplicate messaging, and prior scanner/organizer suites.
