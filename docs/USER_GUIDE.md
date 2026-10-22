# Junction User Guide

This guide describes **Milestone 8**: the desktop shell, Folder Scanner, Smart Organizer, Duplicate Finder, Bulk Renamer, read-only Operation History, polished Dashboard, and the portable Windows executable package. Undo and restore are not available.

## Starting Junction

### Packaged Windows build

Windows release package prepared; public release pending. After you extract `Junction-v0.1.0-windows-x64.zip`:

1. Open the extracted `Junction` folder.
2. Double-click `Junction.exe`.
3. Keep the `_internal` folder next to the executable.

The packaged build does not require Python. The executable is unsigned, so Windows SmartScreen may warn on first launch.

### From source

```powershell
.\.venv\Scripts\python.exe -m fileforge
```

The Python package module remains `fileforge`. On first launch, Junction creates a local SQLite database under `%LOCALAPPDATA%\FileForge\fileforge.db` (legacy folder name preserved so existing operation history stays accessible). The packaged EXE uses the same database path.

## Dashboard

The Dashboard introduces Junction, shows journal-backed batch counts and recent Organizer/Renamer activity (when any exists), and provides shortcuts to each feature page. Folder Scanner and Duplicate Finder results are session-only and are not treated as persisted history.

## Navigation

| Shortcut | Page |
|----------|------|
| Ctrl+1 | Dashboard |
| Ctrl+2 | Folder Scanner |
| Ctrl+3 | Smart Organizer |
| Ctrl+4 | Duplicate Finder |
| Ctrl+5 | Bulk Renamer |
| Ctrl+6 | Operation History |
| Ctrl+7 | Settings |

## Operation History

Operation History browses batches recorded when you **apply** Organizer moves or Bulk Renamer changes. Duplicate Finder and Folder Scanner do not write history rows.

### What is recorded

Each confirmed apply creates:

- A **batch** (`organize_move` or `bulk_rename`) with status, roots, mode, timestamps, and summary
- **Entries** for files that were journaled (source path, destination path, outcome, errors)

Entry outcomes in the journal are typically `success`, `failed`, or `pending` (incomplete). Files cancelled before a journal row was created are not listed.

### How to browse batches

1. Open **Operation History** (Ctrl+6). The page loads automatically on first visit.
2. Review summary counts (all batches, completed, partial, failed, cancelled).
3. Select a row in the batch table for details.

Columns include when, type, status, file counts (total / succeeded / failed / pending), source, and destination. Hover a row for full paths and the batch id.

### How to inspect file-level outcomes

The lower table lists journal entries for the selected batch: original path, destination, operation (Move/Rename), outcome, error text, and completion time. Hover for absolute paths. A failed entry shows the recorded error; history does not invent success.

### Filtering and searching

- **Type**: All, Organizer, or Bulk Renamer
- **Status**: All, Completed, Partial, Failed, Cancelled, Pending
- **Sort**: Newest first or oldest first
- **Search**: Matches source/destination roots, summary, mode, entry paths, and error text (parameterized; wildcards are treated literally)
- **Clear Filters** resets all controls
- **Previous / Next** paginate large histories (50 batches per page)

Filters combine with AND semantics.

### Refresh behavior

Click **Refresh** after new Organizer or Renamer applies. Opening the page also loads history on first show. Viewing history never modifies files or journal rows.

### Local database storage

History lives in the same local SQLite file as settings and the operation journal. Nothing is uploaded.

### Limitations

- Undo, redo, retry, replay, delete history, and edit journal are **not** available
- The Undo button stays disabled
- “Skipped” is not a separate journaled entry status; incomplete work may appear as `pending` or may be absent if never journaled
- Very large entry lists are capped when loading a single batch’s details

## Bulk Renamer

Select files, configure rules (search/replace → prefix → suffix → numbering → case), preview, then confirm apply. Extensions are preserved by default. See prior milestone notes in the docs for rule details. Undo is not available.

## Folder Scanner

Read-only metadata inventory of a chosen folder. Never moves or deletes files.

## Duplicate Finder

Read-only content duplicate detection (size filter + SHA-256). No deletion.

## Smart Organizer

Preview-first moves by extension, category, or year/month. Apply requires confirmation. Overwrites are refused. Moves are journaled. Undo is not available.

## Settings

Display name, exit confirmation, and database path. Closing while a long job runs prompts to cancel first.

## Closing the application

If a scan, organization, duplicate scan, rename, or history load is active, Junction cancels or asks before exit as appropriate.
