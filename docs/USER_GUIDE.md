# FileForge User Guide

This guide describes **Milestone 4**: the desktop shell, read-only Folder Scanner, preview-first Organizer, and read-only Duplicate Finder. Duplicate deletion, bulk renaming, and undo are not available yet.

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

## Duplicate Finder

The Duplicate Finder identifies files with **identical content** using a staged algorithm. It is strictly read-only: FileForge never deletes, quarantines, moves, or renames duplicates.

### How detection works

1. Inventory the selected folder with the same scanner used elsewhere (no symlink/junction follow).
2. Group files by size. Unique sizes are skipped (they cannot be content duplicates).
3. Hash remaining candidates with SHA-256 in bounded chunks (not loaded entirely into memory).
4. Group files only when full hashes match.
5. Hard-linked paths that share the same physical file are counted carefully so potential savings are not overstated.

File names are irrelevant: same name does not imply a duplicate, and different names do not imply uniqueness.

### How to scan

1. Open **Duplicate Finder** (Ctrl+4).
2. Click **Choose Folder…** and select a directory you own or are allowed to inspect.
3. Optionally uncheck **Include subfolders**.
4. Click **Start Scan**.
5. Watch progress counts (no invented percentages). Click **Cancel** to stop between hashing steps.

### Interpreting results

- **Duplicate groups** - each row is one content digest with two or more distinct physical copies.
- **Member table** - selecting a group lists every path in that group (relative path shown; full path in the tooltip).
- **SHA-256** - truncated in the table; full digest is available in the group tooltip.
- **Theoretical potential savings** - `(unique physical copies - 1) × file size`. This is not reclaimed space. Nothing is deleted.
- Identical content does **not** mean one copy is unnecessary or safe to remove.

### Privacy and safety

- No file names, hashes, or contents are transmitted over the network.
- Scan results stay in memory for the session; they are not written to the SQLite database.
- The **Delete Selected Duplicates** button remains disabled by design.
- Closing the app while a scan runs prompts to cancel and exit.

### Limitations

- Deletion, quarantine, and automatic cleanup are not implemented
- Very large trees keep results in memory
- Permission errors and files that change mid-hash are reported and excluded
- Potential savings is an estimate only

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

Bulk Renamer and Operation History remain placeholders. Settings stores display name, exit confirmation, and shows the database path.

## Closing the application

If a folder scan, organization job, or duplicate scan is running, FileForge asks before cancelling and exiting.
