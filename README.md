# BuddyMon

A tiny pixel buddy for your AI coding sessions.

BuddyMon tracks your local coding activity, levels up, evolves, and catches
wild Pokemon while you work.

![BuddyMon preview](docs/screenshots/buddymon-main.png)

## ⚡ Install

Clone BuddyMon:

```sh
git clone https://github.com/HVNT/buddymon.git ~/buddymon
```

Install it:

```sh
/plugin marketplace add ~/buddymon
/plugin install buddymon@buddymon
```

Restart your coding app, then choose a starter:

```sh
/buddymon:choose pikachu
```

Other starters:

```sh
/buddymon:choose charmander
/buddymon:choose bulbasaur
/buddymon:choose squirtle
/buddymon:choose eevee
```

That is it. Your buddy is now alive.

## ✨ What It Does

- 🐣 Gives you a starter Pokemon
- 📈 Levels up as you work
- 🌱 Evolves over time
- 🐾 Finds wild Pokemon
- ⭐ Lets you favorite and switch buddies
- 📦 Keeps every Pokemon you catch
- 📖 Saves your journey history
- 🪙 Shows local token usage
- 💤 Reacts when you are idle
- ⚔️ Has optional Battle Mode

## 🖼 Screenshots

### Statusline

![Statusline](docs/screenshots/statusline.png)

### Menu Bar

![Menu bar](docs/screenshots/menu-bar.png)

### Terminal Menu

![Terminal menu](docs/screenshots/terminal-menu.png)

### Wild Encounter

![Wild encounter](docs/screenshots/encounter.png)

### Token Report

![Token report](docs/screenshots/token-report.png)

## 🧩 Works With

| App | Supported |
|---|---|
| Claude Code | Yes |
| Codex | Yes |
| Auggie | Yes |
| Gemini | Limited |
| Cursor | Limited |

## 🔒 Privacy

**BuddyMon does not edit your AI tool settings.**

**BuddyMon does not send your game state anywhere.**

**BuddyMon only uses the network if you manually run the optional sprite download command.**

BuddyMon installs through its own plugin files and saves its game data locally.

## 🎮 Common Commands

| Command | What it does |
|---|---|
| `/buddymon:status` | Show your buddy |
| `/buddymon:dex` | Show your Pokedex |
| `/buddymon:history` | Show recent catches and evolutions |
| `/buddymon:switch pikachu` | Switch active buddy |
| `/buddymon:mode battle` | Turn on Battle Mode |
| `/buddymon:official` | Download optional official-style sprites |

## 🧭 Full Menu

Open the full BuddyMon menu:

```sh
python3 buddymon.py menu
```

Open the token report:

```sh
python3 buddymon.py tokens
```

The full menu includes your party, box, Pokedex, journal, settings, token
reports, and any waiting encounter. It looks best in Ghostty because Ghostty can
render real inline images. iTerm2 is also supported. Plain terminals fall back
to text-safe pixel art.

## 🎨 Optional Sprite Pack

BuddyMon works out of the box.

For nicer official-style icons:

```sh
/buddymon:official
```

These assets are saved locally and are not committed to the repo.

## 🧰 Details

BuddyMon saves your game locally here:

```sh
~/.local/state/buddymon/state.json
```

Journey history is saved here:

```sh
~/.local/state/buddymon/journal.jsonl
```

State is shared across supported local tools, so one buddy follows your local
AI coding sessions.

More docs:

- [docs/architecture.md](docs/architecture.md)
- [docs/development.md](docs/development.md)
- [docs/assets.md](docs/assets.md)
- [docs/troubleshooting.md](docs/troubleshooting.md)
- [docs/decisions.md](docs/decisions.md)
- [CHANGELOG.md](CHANGELOG.md)

## 🧪 Development

Run tests:

```sh
uv run --with pytest --with pillow --no-project python3 -m pytest tests/ -q
```

Art QA:

```sh
python3 buddymon.py preview
```

## License

MIT licensed.
