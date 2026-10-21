# FileForge User Guide

This guide describes the **Milestone 2** application: the desktop shell plus the read-only Folder Scanner. Organizing, renaming, duplicate removal, and undo are not available yet.

## Starting FileForge

From the project root in Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m fileforge
```

On first launch, FileForge creates a local SQLite database under your Windows local application data folder (typically `%LOCALAPPDATA%\FileForge\fileforge.db`). Source files in the project tree are never used as the live database.

If the database cannot be created (for example, the folder is not writable), FileForge shows an error dialog and exits cleanly.

## Main window

The window has:

- A **sidebar** with FileForge branding and navigation
- A **content area** for the selected page
- A **status bar** showing the application version and useful status text

Minimum recommended size is 1024×640. The layout resizes within normal desktop constraints. The full SQLite database path is shown on the Settings page, not in the status bar.

## Navigation

Use the sidebar or keyboard shortcuts:

| Shortcut | Page |
|----------|------|
| Ctrl+1 | Dashboard |
| Ctrl+2 | Folder Scanner |
| Ctrl+3 | Organizer |
| Ctrl+4 | Duplicate Finder |
| Ctrl+5 | Bulk Renamer |
| Ctrl+6 | Operation History |
| Ctrl+7 | Settings |

The sidebar list is keyboard-focusable. Selected items use a clear highlight; focused items show a visible focus ring.

## Pages

### Dashboard

Explains what FileForge is for, summarizes the safety approach, and offers a primary **Open Folder Scanner** action (also available via Ctrl+2). After you complete a scan in the current session, a short summary can appear on the Dashboard. That summary is not persisted across restarts. No fabricated metrics are shown.

### Folder Scanner

The Folder Scanner builds a **read-only inventory** of a folder you explicitly choose.

#### Choose a folder

1. Click **Choose Folder…**
2. Select a directory in the native Windows picker

FileForge does not automatically scan your home directory or other personal locations.

#### Run a scan

1. Optionally toggle **Include subfolders** (on by default for recursive scanning)
2. Click **Start Scan**
3. Watch the status line for live counts of files, folders, and issues

Progress is indeterminate while the total is unknown. FileForge does not invent a completion percentage.

#### Review results

The results table lists name, type, extension, size, modified time, and relative path. Columns are resizable and sortable. Use:

- The search box to match file names or relative paths
- The type filter for all types, files only, folders only, or a specific extension

A summary line shows total files, folders, skipped link/junction entries, total file size, and scan issues.

#### Cancel a scan

Click **Cancel** while a scan is running. The status changes to cancelled and cooperative cancellation stops further traversal.

#### What scanning does not do

- It does not follow symbolic links or directory junctions by default
- It does not read file contents (metadata only)
- It does not move, rename, overwrite, or delete files
- It does not write into the scanned folder
- Results are kept in memory for the current session only

Completed, cancelled, and partially failed scans are labeled clearly. Permission problems and disappearing files are recorded as issues without crashing the whole scan.

### Organizer

Placeholder for preview-first organization plans. **Apply Organization Plan** is disabled.

### Duplicate Finder

Placeholder for duplicate review. **Delete Selected Duplicates** is disabled. Automatic deletion will never be the default behavior.

### Bulk Renamer

Placeholder for rename previews. **Apply Rename Plan** is disabled.

### Operation History

Shows that the operation journal foundation exists in the database. **Undo Last Operation** is disabled. Undo is not implemented and will only appear when it is safe and verifiable.

### Settings

Lets you:

- Set an optional **display name** for this installation
- Toggle **confirm before exiting**
- View the **database path** (read-only)

**Save Settings** writes values to the local SQLite database. These preferences never leave your machine.

## What FileForge does not do yet

- It does not organize, rename, or delete files.
- It does not undo filesystem changes.
- It does not upload data or call remote APIs.
- It does not persist scan inventories between sessions.

## Closing the application

If a scan is running, FileForge asks whether to cancel it and exit. If exit confirmation is enabled (default), FileForge also asks before closing. You can turn exit confirmation off in Settings.

## Getting help during development

See `README.md` for install, test, and lint commands, and `docs/ARCHITECTURE.md` for how the code is organized.
