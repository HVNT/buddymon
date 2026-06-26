# Agent Notes

## Project Shape

BuddyMon is a local Claude Code plugin. It turns local token/activity data into
a small pokemon-style statusline/menu-bar game.

## Non-Negotiables

- Do not edit or rewrite `~/.claude/settings.json`; plugin wiring belongs in
  `.claude-plugin/plugin.json` and `hooks.json`.
- Keep runtime local-only. Normal play should read local transcripts, local
  state, and local sprite packs.
- Do not commit personal runtime state or generated sprite packs from
  `~/.local/state/buddymon/`.
- Do not fetch network assets unless the user explicitly asks for an asset
  setup command such as `/buddymon:official`.
- Do not stage unrelated dirty files. This repo often has small local polish
  changes in progress.

## State And Assets

- Code lives in this repo.
- Personal state lives in `~/.local/state/buddymon/state.json`.
- Journey history lives in `~/.local/state/buddymon/journal.jsonl`.
- Optional asset packs live in `~/.local/state/buddymon/packs/`.

## Development

- Runtime should stay stdlib-only where practical.
- Tests use pytest and Pillow:
  `uv run --with pytest --with pillow --no-project python3 -m pytest tests/ -q`
- Prefer focused tests near changed behavior.
- Keep docs short, plain, and non-redundant.

## Documentation Upkeep

- When code changes behavior, update the matching markdown in the same change.
- Update `docs/decisions.md` when the "why" changes: architecture, state, assets,
  game balance, install shape, privacy, or runtime boundaries.
- Update `CHANGELOG.md` as the project journal for user-visible changes.
- Update `README.md` only for current install, commands, core behavior, and doc
  links; keep deep detail in the smaller docs.
- Update `docs/architecture.md`, `docs/development.md`,
  `docs/troubleshooting.md`, `docs/assets.md`, or `commands/*.md` when code
  changes make those docs stale.
- Use local ignored `plans/` for scoped implementation gameplans that are likely
  to be built. Use local ignored `ideas/` for exploratory or optional product
  notes that should be kept out of the public tree until explicitly promoted.
- Do not edit the gameplay journal at `~/.local/state/buddymon/journal.jsonl`
  as documentation.

## Git Hygiene

- Check `git status --short --branch` before edits.
- Stage explicit paths only.
- If pushing, target `origin` at `https://github.com/HVNT/buddymon.git`.
