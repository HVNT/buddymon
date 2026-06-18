# Decision Log

Short notes on why BuddyMon works this way.

## 2026-06-15 — Use the plugin manifest, not `settings.json`

**Decision:** declare hooks and the statusline in `.claude-plugin/plugin.json`.

**Why:** installing and uninstalling the plugin should be reversible. BuddyMon
should not edit a user's global Claude settings.

**Cost:** BuddyMon depends on Claude Code plugin support.

## 2026-06-15 — Keep state outside the repo

**Decision:** store play state under `~/.local/state/buddymon/`.

**Why:** the repo is code. The user's buddy, journal, and downloaded art are
personal runtime data.

**Cost:** a fresh clone starts empty unless the same state folder is present.

## 2026-06-15 — Runtime is local-only

**Decision:** normal play reads local transcripts, local state, and local sprite
packs. Network is only used by explicit asset-fetch tools.

**Why:** hooks run often and should be fast, private, and predictable.

**Cost:** optional sprite packs need a manual fetch step.

## 2026-06-15 — Do not commit Nintendo-derived sprite packs

**Decision:** generated Gen 2, box, and Gen 5 packs live in local state, not git.

**Why:** the code is original, but those pixels come from external game/art
sources.

**Cost:** visual setup is one extra local step.

## 2026-06-15 — Make the game slow enough to keep

**Decision:** use a cubic level curve, streak bonuses, milestone balls, and
dex-wide evolution data.

**Why:** BuddyMon is meant to run for months, not finish in a weekend.

**Cost:** tuning matters; big changes should be noted here.

## 2026-06-15 — Keep rare spawns interactive

**Decision:** Auto Mode resolves common spawns quickly, while rare and legendary
spawns wait for Safari actions. Battle Mode is opt-in for people who want more
gameplay.

**Why:** common events should not interrupt work; rare events should feel worth
clicking.

**Cost:** the menu bar dropdown carries real game UI state.

## 2026-06-15 — Scale wild battle sprites down

**Decision:** draw wild pokemon at `87.5%` size in dropdown battle scenes.

**Why:** BuddyMon mirrors front sprites for the buddy. The GBA games used
separate close-up back sprites, with front sprites about `87.5%` as wide by
median, so shrinking the wild sprite restores that depth.

**Cost:** tiny wilds get a little smaller.

## 2026-06-15 — Show tokens, keep progress internal

**Decision:** show raw tracked tokens in BuddyMon UI, while keeping the weighted
progress score internal.

**Why:** users understand tokens. The game still needs a weighted score because
output, input, cache-write, and cache-read tokens should not all level the buddy
at the same rate.

**Cost:** old installs start token totals from this change forward.

## 2026-06-17 — Count more token types toward progress

**Decision:** make progress less stingy: output `75`, input `500`,
cache-write `250`, and cache-read `1,000` tokens per point.

**Why:** the cubic level curve is already slow. The previous cache-read and
input weights made real coding sessions feel under-rewarded.

**Cost:** leveling is faster, especially during cache-heavy work.

## 2026-06-17 — Keep evolution moments visible

**Decision:** after the 16-second evolution animation, keep a menu-bar
celebration for 2 hours and a dropdown notice for 6 hours.

**Why:** evolutions are rare and can happen from background hooks while the user
is not looking at SwiftBar.

**Cost:** the menu bar can show a celebratory label for a while after evolution,
unless an active encounter needs the space.

## 2026-06-17 — Keep dropdown notices readable

**Decision:** use dark accent colors for SwiftBar notice rows instead of pastel
colors.

**Why:** SwiftBar dropdowns can sit on a light gray background, where pale text
is hard to read.

**Cost:** accents are less soft, but the text stays readable.

## 2026-06-17 — Normalize terminal pokédex sprites

**Decision:** keep unique box-art sprites for the terminal pokédex, but use
compact cells and scale any larger sprite before padding it into the grid.

**Why:** local box packs include species wider than the old fixed cell, which
made evolved forms like Charizard clip in the TUI.

**Cost:** large species shrink slightly so the grid stays aligned and scannable.

## 2026-06-17 — Make encounters happen more often

**Decision:** raise the wild encounter chance from 18% to 35% per
progress-earning turn while keeping the rarity split unchanged.

**Why:** the game felt too quiet during normal coding. Raising the base chance
roughly doubles all encounter cadence without making rare and legendary pokemon
disproportionately common.

**Cost:** common auto-resolves and rare/legendary waits will show up more often.
