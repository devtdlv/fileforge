# FileForge User Guide

This guide describes the **Milestone 1 application shell**. File scanning, organizing, renaming, duplicate removal, and undo are not available yet.

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
- A **status bar** showing the version and database path

Minimum recommended size is 1024×640. The layout resizes within normal desktop constraints.

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

Explains what FileForge is for and lists the safety principles. Use **Open Folder Scanner** to jump to the Folder Scanner page. No fake storage metrics are shown.

### Folder Scanner

Placeholder for future read-only folder inventory. **Choose Folder…** is disabled until scanning is implemented. No personal folders are scanned in this milestone.

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

- It does not scan your Documents, Desktop, or other personal folders.
- It does not move, copy, rename, or delete files.
- It does not undo filesystem changes.
- It does not upload data or call remote APIs.

## Closing the application

If exit confirmation is enabled (default), FileForge asks before closing. You can turn that off in Settings.

## Getting help during development

See `README.md` for install, test, and lint commands, and `docs/ARCHITECTURE.md` for how the code is organized.
