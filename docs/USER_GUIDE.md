# FileForge User Guide

This guide describes **Milestone 5**: the desktop shell, Folder Scanner, Organizer, Duplicate Finder, and preview-first Bulk Renamer. Undo and Operation History browsing are not available yet.

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

## Bulk Renamer

Rename many files safely with a mandatory preview.

### Supported rules

| Rule | Behavior |
|------|----------|
| Prefix | Inserted at the start of the stem |
| Suffix | Inserted at the end of the stem (before the extension) |
| Search / replace | Literal text replacement on the stem only (no regular expressions) |
| Sequential numbering | Appends a padded number with a configurable separator |
| Case | Lower / upper / title case applied to the **stem only** |

### Rule application order

1. Search / replace
2. Prefix
3. Suffix
4. Sequential numbering
5. Case transformation (stem only)

Example: `IMG_001.JPG` with replace `IMG`→`Holiday`, suffix `_edited`, lowercase stem → `holiday_001_edited.JPG`.

### Extension policy

Extensions are preserved by default, including their original casing (`photo.JPG` stays `.JPG`). Multi-dot names use Python’s final-suffix rule (`archive.tar.gz` → stem `archive.tar`, ext `.gz`). Extensionless files and dotfiles are supported.

Invalid Windows names (illegal characters, reserved device names, trailing dots/spaces, empty names, excessive length) are shown as **Invalid** in the preview. FileForge does not silently sanitize names into something unexpected.

### How to select files

1. Choose a folder and optionally include subfolders.
2. Click **Load Files**.
3. Check individual files, or use **Select All** / **Clear Selection**.
4. The selection count updates as you change checkboxes.
5. Directories are never renamed. Symbolic links are skipped.

### How to preview

Click **Preview Renames**. The table shows original name, proposed name, relative folder, status, and notes. Hover a row for absolute paths. Changing rules or selection invalidates the preview; regenerate before applying.

Statuses include Ready, Unchanged, Conflict, Invalid, Missing, and (at execution) Stale / Success / Failed / Cancelled.

### Interpreting conflicts

Conflicts appear when:

- Two selected files would share the same target name
- The target already exists and is not being renamed away
- Case-insensitive collisions would overwrite another file
- The proposed name is illegal on Windows

FileForge never auto-appends `(1)` or similar to “fix” collisions.

### How to apply safely

1. Ensure the preview status is ready (Apply enabled).
2. Click **Apply Renames** and confirm the dialog.
3. Watch progress; **Cancel** stops between safe boundaries.
4. Outcomes are written to the SQLite operation journal (`bulk_rename`).

Undo is **not** implemented. Renames are not claimed to be atomic across the whole batch. Chains and case-only renames use temporary names in the same folder, then finalize; leftover temps should not remain after a successful run.

### Limitations

- No undo / reverse from FileForge
- No regular expressions
- No intentional extension-changing mode
- Directories are not renamed
- Global rules apply to every selected file (per-file rule sets are not offered)

## Folder Scanner

Choose a folder, optionally include subfolders, and start a **read-only** metadata scan. Search and filter results. Cancel stops further traversal. Scanning never moves or deletes files.

## Duplicate Finder

Identifies files with identical content using size filtering and SHA-256. Strictly read-only: no delete, quarantine, move, or rename. Potential savings are theoretical. Completion status and statistics are shown as separate lines (status above, counts below).

## Organizer

Preview-first file moves by extension, category, or modified year/month. Apply requires confirmation. Overwrites are refused. Moves are journaled. Undo is not available.

## Other pages

Operation History remains a placeholder. Settings stores display name, exit confirmation, and shows the database path.

## Closing the application

If a folder scan, organization job, duplicate scan, or rename job is running, FileForge asks before cancelling and exiting.
