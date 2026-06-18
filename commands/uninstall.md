---
description: How to remove buddymon cleanly
---

Tell the user:

1. `/plugin uninstall buddymon` removes the plugin (hooks + statusline). buddymon never edits `~/.claude/settings.json`, so there is nothing to restore.
2. Trainer state lives at `~/.local/state/buddymon/`. Ask whether they want to keep it (reinstalling later picks the buddy back up) or wipe it with `rm -rf ~/.local/state/buddymon`. Do not delete it without their explicit confirmation.
