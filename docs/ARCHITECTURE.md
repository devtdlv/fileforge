# FileForge Architecture

## Goals

FileForge is a local-first Windows desktop app with:

- A maintainable `src/` package layout
- A PySide6 UI shell and shared design system
- SQLite persistence with versioned migrations
- Read-only folder scanning and duplicate detection
- Preview-first organizer and bulk renamer with journaling
- Read-only Operation History over the shared journal

## Package layout

```
src/fileforge/
  core/
  database/
    connection.py
    schema.py           # migrations (currently v2)
    settings_store.py
    journal.py          # write path for batches/entries
  services/
    scanner/
    organizer/
    duplicates/
    renamer/
    history/
      models.py         # filters, batch/entry summaries, labels
      queries.py        # parameterized read-only SQL
  ui/
    models/
    workers/
    pages/
    windows/
```

## Operation History design

1. `HistoryQueryService` reads `operation_batches` and `operation_entries` only (no writes).
2. Listing uses `LIMIT`/`OFFSET` (default 50, max 200) with `ORDER BY created_at, id` for stable paging.
3. Filters: `operation_type` (`organize_move` / `bulk_rename`), batch `status`, and literal `LIKE` search with `ESCAPE '\'` after escaping `%`, `_`, and `\`.
4. Entry aggregates (`success` / `failed` / `pending`) are computed with conditional `SUM` over a `LEFT JOIN`.
5. Background loads open a **separate** short-lived `DatabaseManager` connection on a worker thread (same pattern as Organizer/Renamer apply), then close it.
6. The UI never calls undo, delete, or journal mutation APIs.

### Known journaled operation types

| Layer | Values |
|-------|--------|
| Batch | `organize_move`, `bulk_rename` |
| Entry | `move`, `rename` |
| Batch status | `pending`, `completed`, `partial`, `cancelled`, `failed` |
| Entry status | `pending`, `success`, `failed` |

Schema remains at **v2**; no migration was required for Milestone 6.

## Bulk renamer / organizer / duplicates

Unchanged from Milestones 3–5. Organizer and Renamer continue to write through `OperationJournal`. Duplicate Finder remains read-only and does not journal.

## Database schema (v2)

- `settings`
- `operation_journal` (legacy summary rows)
- `operation_batches`
- `operation_entries`

## Safety boundaries

See `fileforge.core.safety`. Previews and history browsing are read-only. Apply paths require confirmation and refuse overwrites. Undo is not implemented.

## Testing

Temporary SQLite databases only. Coverage includes history filters, search escaping, pagination, entry details, UI navigation/refresh, and prior feature suites.
