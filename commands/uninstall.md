---
description: How to remove buddymon cleanly
---

Tell the user:

1. `/plugin uninstall buddymon` removes the plugin (hooks + statusline). buddymon never edits `~/.claude/settings.json`, so there is nothing to restore.
2. Trainer state lives at `$XDG_STATE_HOME/buddymon/` when `XDG_STATE_HOME` is set, otherwise at `~/.local/state/buddymon/`. Ask whether they want to keep it (reinstalling later picks the buddy back up) or remove the resolved BuddyMon state directory. Show the exact resolved path and get explicit confirmation before deleting it.
