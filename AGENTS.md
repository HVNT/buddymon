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
- Native UI must always use `BuddyMonBrand` from `BrandStyle.swift`. Do not add
  local palettes, theme enums, direct font choices, one-off corner radii, or a
  second spacing system. Read `docs/brand.md` before changing native UI and add
  every new component or state to the Brand Styles preview in the same change.
- Brand Styles preview components must use the same `BuddyMonBrand` factories
  as shipping UI. Run `scripts/capture-brand-styles.sh` and
  `scripts/capture-menu-panel.sh`; run the menu panel and menu-bar state
  harness captures when their shipping states change. Inspect the relevant
  PNGs whenever native visual behavior changes.
- `StyleArchivePreview.swift` is historical and non-normative. Never copy its
  local values into shipping UI.
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
- Update `docs/brand.md` whenever a native visual token, semantic color use,
  shared treatment, component, or state changes.
- Use local ignored `plans/` for scoped implementation gameplans that are likely
  to be built. Use local ignored `ideas/` for exploratory or optional product
  notes that should be kept out of the public tree until explicitly promoted.
- Do not edit the gameplay journal at `~/.local/state/buddymon/journal.jsonl`
  as documentation.

## Git Hygiene

- Check `git status --short --branch` before edits.
- Stage explicit paths only.
- If pushing, target `origin` at `https://github.com/HVNT/buddymon.git`.
