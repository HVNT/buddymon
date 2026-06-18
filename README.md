# buddymon

A pixel-art pokémon buddy that lives in your Claude Code statusline. It earns
XP from the real tokens you burn, levels up, evolves, catches wild pokémon
while you work — and visibly reacts to your session: thinks when you think,
works when tools run, asks for you on permission prompts, and curls up asleep
when you go idle.

```
  ▄▀▀▀▀▀▀▄        ⚡ Pikachu Lv.12
 ▀▀█▀▀█▀▀▀▀      ▰▰▰▰▰▱▱▱▱▱ 312/660
 ▀▀▀▀▀▀▀▀▀ ▄     💤 zzz
   ▀▀▀▀▀  ▄▀     🔥4  ⚾9  📖7
  ▄▀▀▀▀▀▄        🎉 caught ✨🦊 Eevee (new!)
```

## Install

```
/plugin marketplace add /Users/hunt/buddymon
/plugin install buddymon@buddymon
```

Restart the session, then pick a starter:

```
/buddymon:choose pikachu     # or charmander, bulbasaur, squirtle, eevee
```

## How it plays

- **XP from tokens** — a Stop hook reads the turn's transcript usage:
  1 XP / 100 output · 1 / 1,000 input · 1 / 500 cache-write · 1 / 5,000 cache-read.
  A per-session anchor uuid guarantees turns are never double-counted, even
  across resume/compaction.
- **Levels & evolution** — quadratic curve to Lv.60. Starters evolve on the
  canonical levels (16/36, Pikachu 30, Eevee branches at 25). Evolution
  changes the sprite.
- **Wild encounters** — each XP-earning turn has an 18% spawn chance
  (70/20/8/2 rarity split, legendaries gated behind Lv.20, shinies 1/128).
  Catching consumes a ball; you earn 3 per level-up.
- **Streaks** — consecutive coding days multiply XP, +2%/day up to ×1.6.
- **Journal** — every catch, evolution, and level-up is appended permanently
  to `~/.local/state/buddymon/journal.jsonl`; browse with `/buddymon:history`
  (also the last few entries in the menu bar dropdown). Rare moments —
  evolutions, shinies, legendaries — fire a macOS notification so you never
  miss one.
- **Moods** — hooks record the latest session event; the statusline maps it:
  prompt → thinking · PreToolUse → ⚙️ tool name · Notification → ❗ needs you ·
  stop → resting, then 💤 asleep (dimmed sprite, closed eyes) after 90s.
  Context pressure shows 🥵/🆘 when the payload exposes usage.

## Official Gen 2 icons (optional, recommended)

One-time setup — downloads the authentic 16×16 two-frame party menu icons
(the smallest official Pokémon sprites ever made) from the
[pret/pokecrystal](https://github.com/pret/pokecrystal) disassembly and
colorizes them per species using palettes extracted from
[PokéSprite](https://github.com/msikma/pokesprite) box icons:

```
uv run --with pillow --no-project python3 tools/fetch_official.py
```

The statusline then plays the classic party-screen bounce (2-frame flip);
shiny buddies get shiny palettes. Assets land in
`~/.local/state/buddymon/packs/gen2.json` — **local only, never committed**
(they are Nintendo's sprites, preserved by the pret project). Without the
pack, buddymon falls back to its built-in hand-drawn chibi sprites
(archivable via `buddymon.py export-chibi` → `~/Pictures/buddymon/`).

## Cross-client: same pokédex everywhere

State lives in `~/.local/state/buddymon/state.json`, so every surface shares
one buddy and one dex. XP sources by client:

| Client | XP | How |
|---|---|---|
| Claude Code | ✅ live | Stop hook (per turn) |
| Codex | ✅ | `collect` parses `~/.codex/sessions` rollouts (cumulative-delta anchors) |
| Auggie | ✅ | `collect` parses `~/.augment/sessions` (timestamp anchors) |
| Gemini / Cursor | ➖ | no local token counters; commands still work |

`python3 buddymon.py collect` is incremental and idempotent — the first run
anchors existing logs without awarding (no history dump), after that only new
tokens count. A file lock serializes it with the Claude hook.
(Collector parsing approach adapted from agent-platform's token-usage workflow.)

### Keep the menu bar always alive (optional)

If SwiftBar quits (or you reboot), the buddy disappears until it's relaunched.
A KeepAlive LaunchAgent starts it at login and relaunches it if it ever exits:

```
cp extras/com.hunt.buddymon-swiftbar.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.hunt.buddymon-swiftbar.plist
```

Remove with `launchctl unload …` + `rm`. (Or just add SwiftBar to System
Settings → General → Login Items for start-at-login without auto-revive.)

### After upgrading buddymon

Most surfaces spawn fresh processes per render and pick up code/state changes
instantly. The exception is the SwiftBar menu bar plugin (long-running stream):
after pulling new buddymon code or a state-format migration, restart it —
`osascript -e 'quit app "SwiftBar"' && open -a SwiftBar` — or it may keep
stale logic in memory (symptom: 🥚 in the menu bar despite a live buddy).

### tmux status bar

`~/.tmux.conf` runs `buddymon.py tiny --collect` in `status-right` every 15s:
a plain-text buddy (`🦎 Charmander Lv.15 ▰▱▱▱▱▱ ⚙ ⚾51`) that also harvests
Codex/Auggie XP as a side effect. `prefix+B` opens the full pixel status card
in a popup. For collection without tmux, a launchd agent can run
`buddymon.py collect` every 5 min (see `extras/com.hunt.buddymon-collect.plist`;
load with `launchctl load ~/Library/LaunchAgents/...`, remove with
`launchctl unload` + `rm`).

## Commands

| Command | What |
|---|---|
| `/buddymon:choose <starter>` | pick your starter (once) |
| `/buddymon:status` | status card |
| `/buddymon:dex` | collection by rarity |
| `/buddymon:switch <name>` | make a caught pokémon active |
| `/buddymon:history [n]` | the buddy's journey journal |
| `/buddymon:official` | fetch the official Gen 2 icon pack (asks first) |
| `/buddymon:uninstall` | clean removal instructions |

## Design guarantees

- **Local-only.** No network calls of any kind.
- **Never touches `~/.claude/settings.json`.** The statusline is declared in
  the plugin manifest; uninstalling the plugin removes everything.
- **One state file**, atomic writes: `~/.local/state/buddymon/state.json`
  (XDG-aware). Per-session mood events live beside it and are pruned.
- **Deterministic engine** — all RNG is injected; `tests/` covers the curve,
  evolution chains, encounter accounting, and the transcript anchor.

Run tests: `uv run --with pytest --no-project python3 -m pytest tests/ -q`

Art QA: `python3 buddymon.py preview` renders every sprite.

## Credits

Game design ideas (token-XP, anchor pattern, statusline buddy) inspired by
[andriar/pokemon-buddy-claude](https://github.com/andriar/pokemon-buddy-claude);
state-reactive mascot concept inspired by
[TeXmeijin/claude-code-mascot-statusline](https://github.com/TeXmeijin/claude-code-mascot-statusline).
All code and pixel art here are original. MIT licensed.
