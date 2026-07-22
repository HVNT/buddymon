---
description: Download the nicer local sprite packs (one-time, network)
---

Tell the user this downloads Nintendo sprite assets from GitHub into BuddyMon's
local XDG state directory (normally `~/.local/state/buddymon/packs/`) and never
commits them. If they confirm, run:

`python3 "${CLAUDE_PLUGIN_ROOT}/buddymon.py" install-assets`

and show the summary lines. This installs only missing packs. Use `--refresh`
only when the user explicitly asks to refresh every pack; `--force` is a
compatibility alias. BuddyMon switches to the nicer local art automatically on
the next render.
