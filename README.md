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
- **Moods** — hooks record the latest session event; the statusline maps it:
  prompt → thinking · PreToolUse → ⚙️ tool name · Notification → ❗ needs you ·
  stop → resting, then 💤 asleep (dimmed sprite, closed eyes) after 90s.
  Context pressure shows 🥵/🆘 when the payload exposes usage.

## Commands

| Command | What |
|---|---|
| `/buddymon:choose <starter>` | pick your starter (once) |
| `/buddymon:status` | status card |
| `/buddymon:dex` | collection by rarity |
| `/buddymon:switch <name>` | make a caught pokémon active |
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
