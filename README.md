# buddymon

A pixel-art pokémon buddy that lives in your Claude Code statusline and menu
bar, with a full terminal menu for party management, encounters, collection
browsing, and token reports. It earns progress from the real tokens you burn,
levels up, evolves, catches wild pokémon while you work — and visibly reacts to
your session: thinks when you think, works when tools run, asks for you on
permission prompts, and curls up asleep when you go idle.

```
  ▄▀▀▀▀▀▀▄        ⚡ Pikachu Lv.12
 ▀▀█▀▀█▀▀▀▀      ▰▰▰▰▰▱▱▱▱▱ 312/660
 ▀▀▀▀▀▀▀▀▀ ▄     💤 zzz
   ▀▀▀▀▀  ▄▀     🔥4  ⚾9  📖7  🪙1.2M
  ▄▀▀▀▀▀▄        🎉 caught ✨🦊 Eevee (new!)
```

## Install

```
/plugin marketplace add /Users/hunt/buddymon
/plugin install buddymon@buddymon
```

For a new checkout:

```
git clone https://github.com/HVNT/buddymon.git /Users/hunt/buddymon
```

Restart the session, then pick a starter:

```
/buddymon:choose pikachu     # or charmander, bulbasaur, squirtle, eevee
```

## How it plays

- **Tokens feed progress** — a Stop hook reads the turn's transcript usage and
  the UI shows raw tracked tokens. The hidden level score uses weights:
  1 point / 75 output · 1 / 500 input · 1 / 250 cache-write · 1 / 1,000 cache-read.
  A per-session anchor uuid guarantees turns are never double-counted, even
  across resume/compaction.
- **Levels & evolution** — cubic curve to Lv.60. Evolution is table-driven
  across the dex; if a pokemon has multiple eligible evolutions, one is picked.
- **Wild encounters** — each progress-earning turn has a 35% spawn chance
  (70/20/8/2 rarity split, legendaries gated behind Lv.20, shinies 1/128).
  Wild levels are sampled from each species' evolution-stage range, so evolved
  forms never appear below their evolution level. In Auto Mode,
  commons/uncommons auto-resolve (one ball, caught or fled).
- **Safari Zone** — rare and legendary spawns *wait* for you and become an
  interactive Gen 1 Safari minigame in the menu bar dropdown: **🪨 Rock**
  (doubles catch rate but angers it → 2× flee), **🍖 Bait** (halves catch rate
  but it eats → ¼ flee), **⚾ Ball**, **🏃 Run**. Angry/eating are mutually
  exclusive and tick down each turn; when anger wears off the catch boost
  resets — so it's a race. The wild waits indefinitely until you act and never
  flees on your first move — you always get to start the fight.
- **Battle Mode** — optional weaken-then-catch battles for every wild spawn.
  Toggle it from the menu bar or with `/buddymon:mode battle`.
- **Party, Box, and favorites** — the terminal menu has a Party view for your
  active team and a Box view for every caught individual, including duplicates.
  Press `f` in Party or Box to star favorites; favorites stay easy to switch to
  from the SwiftBar dropdown.
- **Token Usage** — the terminal menu and `python3 buddymon.py tokens` show
  local usage summaries for today, yesterday, this week, this month, last
  month, and a cached daily timeline by client.
- **Streaks** — consecutive coding days multiply progress, +2%/day up to ×1.6.
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
one buddy and one dex. Token sources by client:

| Client | Tokens | How |
|---|---|---|
| Claude Code | ✅ live | Stop hook (per turn) |
| Codex | ✅ | `collect` parses `~/.codex/sessions` rollouts (cumulative-delta anchors) |
| Auggie | ✅ | `collect` parses `~/.augment/sessions` (timestamp anchors) |
| Gemini / Cursor | ➖ | no local token counters; commands still work |

`python3 buddymon.py collect` is incremental and idempotent — the first run
anchors existing logs without counting them (no history dump), after that only
new tokens count. A file lock serializes it with the Claude hook.
(Collector parsing approach adapted from agent-platform's token-usage workflow.)

## Terminal menu

Open the full menu directly:

```
python3 buddymon.py menu          # main menu
python3 buddymon.py menu tokens   # jump to Token Usage
python3 buddymon.py menu party    # jump to Party
```

The SwiftBar dropdown's **Open menu**, encounter, Party overflow, and Token
Usage actions use the same launcher. It prefers Ghostty for inline PNG sprites,
then iTerm2, then Terminal.app. Ghostty launches first close only Ghostty
processes explicitly running this checkout's `buddymon.py menu`, so repeated
clicks do not grow Dock icons or touch unrelated Ghostty windows.

The terminal menu includes Party, Pokédex, Journal, Status, Box, Token Usage,
Settings, and any waiting encounter. Ghostty and iTerm2 render real inline
images; plain terminals fall back to terminal-safe pixel art.

### Keep the menu bar always alive (optional)

If SwiftBar quits (or you reboot), the buddy disappears until it's relaunched.
A KeepAlive LaunchAgent starts it at login and relaunches it if it ever exits:

```
cp extras/com.hunt.buddymon-swiftbar.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.hunt.buddymon-swiftbar.plist
```

Remove with `launchctl unload …` + `rm`. (Or just add SwiftBar to System
Settings → General → Login Items for start-at-login without auto-revive.)

### Hide SwiftBar's own menu bar icon

By default SwiftBar shows its own "SwiftBar" item next to your buddy. Enable
Stealth Mode so it stays hidden whenever a plugin is active (it only reappears
if you disable all plugins, so you're never locked out — SwiftBar's Preferences
also remain reachable from the buddy's dropdown footer):

```
defaults write com.ameba.SwiftBar StealthMode -bool YES
osascript -e 'quit app "SwiftBar"' && open -a SwiftBar
```

Now only the buddy shows. (Fallback: hold ⌘ and drag the SwiftBar icon out of
the menu bar.)

### After upgrading buddymon

Most surfaces spawn fresh processes per render and pick up code/state changes
instantly. The exception is the SwiftBar menu bar plugin (long-running stream):
after pulling new buddymon code or a state-format migration, restart it —
`osascript -e 'quit app "SwiftBar"' && open -a SwiftBar` — or it may keep
stale logic in memory (symptom: 🥚 in the menu bar despite a live buddy).

### tmux status bar

`~/.tmux.conf` runs `buddymon.py tiny --collect` in `status-right` every 15s:
a plain-text buddy (`🦎 Charmander Lv.15 ▰▱▱▱▱▱ ⚙ ⚾51 🪙1.2M`) that also harvests
Codex/Auggie tokens as a side effect. `prefix+B` opens the full pixel status
card in a popup. For collection without tmux, a launchd agent can run
`buddymon.py collect` every 5 min (see `extras/com.hunt.buddymon-collect.plist`;
load with `launchctl load ~/Library/LaunchAgents/...`, remove with
`launchctl unload` + `rm`).

## Commands

| Command | What |
|---|---|
| `/buddymon:choose <starter>` | pick your starter (once) |
| `/buddymon:status` | compact status summary |
| `/buddymon:dex` | collection by rarity |
| `/buddymon:switch <name>` | make a caught pokémon active |
| `/buddymon:history [n]` | the buddy's journey journal |
| `/buddymon:safari <action>` | play a Safari turn |
| `/buddymon:battle <action>` | play a Battle Mode turn |
| `/buddymon:mode [auto\|battle]` | toggle encounter mode |
| `/buddymon:official` | fetch the official Gen 2 icon pack (asks first) |
| `/buddymon:uninstall` | clean removal instructions |

Direct CLI helpers:

| Command | What |
|---|---|
| `python3 buddymon.py menu [screen]` | open the interactive terminal menu |
| `python3 buddymon.py tokens` | local token usage report |
| `python3 buddymon.py collect` | collect Codex/Auggie token progress |
| `python3 buddymon.py preview` | render every sprite for art QA |

## More docs

- [docs/decisions.md](docs/decisions.md) — why it works this way
- [docs/architecture.md](docs/architecture.md) — simple system map
- [docs/development.md](docs/development.md) — local dev commands
- [docs/troubleshooting.md](docs/troubleshooting.md) — common fixes
- [docs/assets.md](docs/assets.md) — sprite asset rules
- [CHANGELOG.md](CHANGELOG.md) — human release notes

## Design guarantees

- **Runtime local-only.** Normal play reads local files only. Optional asset
  fetch tools use the network only when you run them.
- **Never touches `~/.claude/settings.json`.** The statusline is declared in
  the plugin manifest; uninstalling the plugin removes everything.
- **One state file**, atomic writes: `~/.local/state/buddymon/state.json`
  (XDG-aware). Per-session mood events live beside it and are pruned.
- **Deterministic engine** — all RNG is injected; `tests/` covers the curve,
  evolution chains, encounter accounting, and the transcript anchor.

Run tests: `uv run --with pytest --with pillow --no-project python3 -m pytest tests/ -q`

Art QA: `python3 buddymon.py preview` renders every sprite.

## Credits

Game design ideas (token progress, anchor pattern, statusline buddy) inspired by
[andriar/pokemon-buddy-claude](https://github.com/andriar/pokemon-buddy-claude);
state-reactive mascot concept inspired by
[TeXmeijin/claude-code-mascot-statusline](https://github.com/TeXmeijin/claude-code-mascot-statusline).
All code and pixel art here are original. MIT licensed.
