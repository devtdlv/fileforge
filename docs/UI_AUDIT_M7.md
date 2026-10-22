# Milestone 7 UI audit checklist (internal)

Captured against the app (then branded FileForge) at commit `6358a55` before polish work.
Product branding for this milestone is **Junction**.

| Page | Findings (priority) |
|------|---------------------|
| Dashboard | Outdated “later milestones” copy; only Scanner CTA; no journal-backed recent ops or real batch stats |
| Bulk Renamer | File/preview tables cramped vertically; preview summary repeats full rule order |
| Operation History | Source/destination heavily truncated; entry pane too short; need clearer status distinction |
| Folder Scanner | Modified date column can clip; long folder paths hard to read; completion messaging may duplicate |
| Organizer | Generally solid post-3.1; tighten summary/status consistency |
| Duplicate Finder | Group/member panes need practical min heights / splitter |
| Settings | Hint still sounds unfinished; Save should match Secondary/Primary styling consistency |
| Shared | Standardize table min heights, splitter handles, status colors, QGroupBox/QSpinBox, focus rings |

Priority order: Renamer tables → History tables/paths → Dashboard → Scanner dates/paths → Dup/Organizer polish → Theme → Docs/README.

## Resolution notes (Milestone 7)

| Area | Change |
|------|--------|
| Dashboard | Journal-backed stats, recent batches, feature shortcuts |
| Bulk Renamer | Vertical splitter min heights, concise preview summary |
| Operation History | Path abbreviations + tooltips, taller splitter panes, status colors |
| Folder Scanner | Modified column width, path tooltip, less redundant completion text |
| Organizer / Dup Finder | Table min heights; Dup splitter non-collapsible |
| Settings | Accurate copy; Primary Save button |
| Shared | `table_utils.configure_result_table`, theme status/stat/shortcut tokens |
| Screenshots | Authentic PNGs captured under `docs/screenshots/` via `tools/capture_portfolio_screenshots.py`; README embeds those paths |
| Branding | Visible product name Junction; package/module `fileforge` and `%LOCALAPPDATA%\\FileForge` paths preserved |
