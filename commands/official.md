---
description: Download the official Gen 2 menu icons (one-time, network)
---

Tell the user this downloads Nintendo sprite assets (Gen 2 menu icons from the pret/pokecrystal disassembly + PokéSprite palettes) from GitHub into `~/.local/state/buddymon/packs/` — local only, never committed. If they confirm, run:

`uv run --with pillow --no-project python3 "${CLAUDE_PLUGIN_ROOT}/tools/fetch_official.py"`

and show the summary line. The statusline switches to the official icons automatically on the next render.
