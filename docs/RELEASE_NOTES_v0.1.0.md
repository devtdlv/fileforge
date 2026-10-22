# Junction v0.1.0 — Initial Windows Release

Introducing **Junction**, a local-first Windows desktop toolkit for scanning, organizing, finding duplicates, and renaming files.

Junction is designed around a preview-first workflow, helping you understand proposed file changes before applying them.

## Features

- **Dashboard:** Overview of recorded file operations and quick access to tools.
- **Folder Scanner:** Inspect files and folders without modifying them.
- **Smart Organizer:** Preview and organize files using configurable rules.
- **Duplicate Finder:** Identify identical files using SHA-256 hashing. Read-only by design.
- **Bulk Renamer:** Preview filename transformations and detect conflicts before renaming.
- **Operation History:** Review recorded operations stored locally in SQLite.
- **Settings:** Configure supported application preferences.

## Download and installation

1. Download `Junction-v0.1.0-windows-x64.zip` from the Assets section below.
2. Extract the complete ZIP archive.
3. Open the extracted `Junction` folder.
4. Double-click `Junction.exe`.

**Python is not required.**

Keep the executable and its accompanying `_internal` folder together.

## Privacy and safety

Junction operates locally and does not require a cloud account.

The Folder Scanner and Duplicate Finder are read-only. Organizer and Bulk Renamer provide previews and confirmation steps before applying changes.

Operation history is stored locally at:

`%LOCALAPPDATA%\FileForge\fileforge.db`

The legacy application-data path is intentionally retained for compatibility.

## Known limitations

- Windows executable is unsigned, so Microsoft SmartScreen may display a warning.
- No installer is included; this release uses a portable ZIP distribution.
- Duplicate deletion and operation undo are not implemented.
- The application is intended for Windows.

## Verify your download

A SHA-256 checksum file is included in the release assets.

**SHA-256:**

`31c938b6cdc96d6d48923d1c6a4b82b26916ff54937b944a3726942ab5184019`

## Source code

https://github.com/devtdlv/junction

**Release:** v0.1.0
