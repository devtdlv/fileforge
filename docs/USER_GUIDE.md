# FileForge User Guide

This guide describes **Milestone 3**: the desktop shell, read-only Folder Scanner, and preview-first Organizer. Duplicate removal, bulk renaming, and undo are not available yet.

## Starting FileForge

```powershell
.\.venv\Scripts\python.exe -m fileforge
```

On first launch, FileForge creates a local SQLite database under `%LOCALAPPDATA%\FileForge\fileforge.db`.

## Navigation

| Shortcut | Page |
|----------|------|
| Ctrl+1 | Dashboard |
| Ctrl+2 | Folder Scanner |
| Ctrl+3 | Organizer |
| Ctrl+4 | Duplicate Finder |
| Ctrl+5 | Bulk Renamer |
| Ctrl+6 | Operation History |
| Ctrl+7 | Settings |

## Folder Scanner

Choose a folder, optionally include subfolders, and start a **read-only** metadata scan. Search and filter results. Cancel stops further traversal. Scanning never moves or deletes files.

## Organizer

The Organizer relocates files using a preview-first workflow.

### Modes

- **By file extension** - for example `Destination\jpg\photo.jpg`
- **By file category** - Images, Documents, Videos, Audio, Archives, Other
- **By modified year/month** - `Destination\YYYY\MM\filename`

### Workflow

1. Choose **Source Folder…** and **Destination Folder…**
2. Select a mode and whether to include subfolders
3. Click **Preview Plan**
4. Review every proposed move in the table (relative source/destination paths,
   rule, notes). Hover a path cell for the full absolute path.
5. If conflicts exist, Apply stays disabled
6. Click **Apply Organization Plan** and confirm the dialog
7. Watch progress; click **Cancel** to stop between remaining moves

### Safety protections

- Preview never modifies the filesystem
- Apply requires an explicit confirmation dialog
- Existing destination files are never overwritten
- Case-insensitive destination collisions block Apply
- Files that change after preview are rejected at execution time
- Symbolic links and directory junctions are not followed
- Cross-filesystem moves are refused (no copy-and-delete fallback)
- Successful and failed moves are written to the SQLite journal

### Journal behavior

Each apply creates a batch with per-file entries (`pending` → `success`/`failed`). Undo is **not** implemented in this milestone. If journaling cannot start, FileForge refuses to move files.

### Limitations

- Only files are moved; empty source folders are left in place
- Undo / reverse is not available yet
- Operation History UI does not yet list journal batches
- Very large trees keep the plan in memory

## Other pages

Duplicate Finder, Bulk Renamer, and undo remain placeholders with disabled actions. Settings still stores display name, exit confirmation, and shows the database path.

## Closing the application

If a scan or organization job is running, FileForge asks before cancelling and exiting.
