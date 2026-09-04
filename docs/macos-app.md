# <img src="assets/brand/icons/native-app.png" width="28" height="28" alt=""> BuddyMon.app, ELI5

BuddyMon.app is a tiny menu-bar companion. The Python game inside it is the
brain; the native app is a very thin shell around that shared core.

The self-contained build carries a private Python runtime, so the user does not
need Homebrew, Terminal setup, Ghostty, or their own Python install.

## <img src="assets/brand/icons/setup.png" width="22" height="22" alt=""> Open It

BuddyMon `0.2.0` is not published as a downloadable GitHub Release yet. To try
the current macOS app from source, clone the repository and build the local
self-contained app:

```bash
scripts/build-macos-app.sh --friend --install --open
```

Published archives will use the signed and notarized release path documented in
[Development](development.md); the README will link the downloadable archive
only after that release exists.

BuddyMon appears only in the menu bar. It does not create a Dock icon or open a
standalone product window. Opening the app again signals the existing copy to
open its panel instead of creating a duplicate buddy.

## <img src="assets/brand/icons/native-app.png" width="22" height="22" alt=""> The Menu-Bar Buddy

The buddy itself is the first product surface. Its Python-owned state model
covers startup, no-starter, idle, working, resting, shiny, XP, level-up,
evolution, encounter attention, automatic battle, catching, every encounter
result, and unavailable fallbacks. Swift only plays the supplied frames and
routes clicks.

Short moments play once even if status polling discovers them late. Waiting
encounters remain visible without constantly moving, and baseline idle motion
does not regenerate image files. Reduce Motion selects one representative frame
instead of playing the sequence.

Terminal play and the native app stay in sync through local state-change
notifications. A terminal-started battle should reach the buddy and an open
dropdown within a fraction of a second; it does not wait for the current
menu-bar animation to finish. Opening the dropdown also requests a fresh read,
while a slower timer remains as recovery if a filesystem event is missed.

Click the menu-bar sprite for the compact view. It shows the active Pokémon,
level, visual XP meter, latest signal, and only the essential
actions:

- handle a waiting encounter
- inspect compact token usage
- inspect the native Trainer Card
- change every local preference in native Settings
- open Party, Box, Pokédex, or Activity in the optional terminal experience
- refresh local status
- quit BuddyMon

The compact panel uses the light Field Guide brand skin: warm Pokémon
off-white, charcoal ink, a compact trainer-card buddy group, and a one-line
game-dialogue signal. Color is reserved for Pokémon identity, rarity, and
urgent alerts. It uses actual local sprite art and quiet cursor/sprite motion.
Motion respects macOS Reduce Motion. The latest-catch signal includes that
Pokémon's small pixel sprite,
neutral brand copy, and one colored rarity letter immediately after its name.
Arrow keys move focus, Return or Space selects, Escape closes, and visible
letter shortcuts activate actions. A click always lands here instead of
skipping directly into an encounter.
The buddy group ends after the XP meter instead of spending a row on trainer
totals. The masthead's clickable far-right control shows Tokens, Today, and
Yesterday on one right-aligned baseline without a card background; there is no
second token row or visible Open affordance. Root navigation is a square 3-by-2
grid of six compact links: Trainer, Party, Box, Pokédex, Activity, and Settings.
Trainer and Settings stay native; the other four are explicit terminal
handoffs, with Activity opening the terminal journey log. Refresh and Quit are
quiet footer commands—`⌘R` and `⌘Q`—rather than primary buttons.
The root card uses a tighter outer inset, and its smaller buddy sprite aligns
with the name, type, and XP rows beside it.

The masthead is intentionally tiny: it begins directly with the
FireRed/LeafGreen-style pixel `BUDDYMON` wordmark and a steady semantic status
dot. Green means active, neutral means starting, and red means unavailable.
Major labels and actions use the same local bitmap face;
small stats and supporting copy remain SF Mono.
Every clickable compact control uses the macOS pointing-hand cursor; passive
labels, sprites, and status rows retain the normal arrow.

Tokens opens a second compact Field Guide panel. Two equal cards compare Today
with Yesterday and This Week with the same elapsed weekdays from last week,
with each percentage kept inside its own card. The prior-week label names its
cutoff until Sunday. The seven-day bars and leading local tools remain below. Its back
chevron shares the title row, matching Trainer, Battle, and Battle Result. Back
returns to the buddy dropdown; it never opens a standalone dashboard.

Trainer opens a 3:2 Field Guide card in the same panel. It shows NAME, TOKENS,
POKÉDEX, and CAUGHT beside an explicitly installed local Trainer Red portrait,
or BuddyMon's original two-tone trainer silhouette when that pack is absent. A
compact status rail adds the current encounter mode, activity streak, available
balls, and owned shiny count without changing the card size. Battle mode shows
unlimited balls because Battle throws do not consume Safari inventory. There is
no Trainer Level: levels belong to Pokémon. The four-star badge rank awards one
star for every two of the eight core badges and sits in the badge header. The
status rail alone spans the
full card width and meets the border; the rest of the content keeps its normal
inset. The badge rail recognizes Bond,
Safari, Battle, Curator, Type, Shiny, Legend, National, and Shiny Legend
achievements from local collection, Showcase, and journey evidence. Shiny
National is not shown at all until the National Badge is complete; it then
appears locked until every National Pokédex species has a shiny copy.
Badges are pointer- and keyboard-selectable; choosing one replaces the badge
heading with its name. Medallion styling carries earned or locked state, and
the tooltip retains the unlock requirement.
Large circular medallions use equal-width slots so every symbol is centered.
They stamp in sequentially when the card opens, lift gently on hover, and give
earned shiny achievements a slow glow; Reduce Motion keeps them static.

A waiting wild opens a minimal Field Guide battle panel in the same dropdown.
On the root dropdown, the waiting message is part of the dark encounter action
itself rather than a duplicate line above it.
It shows the buddy and wild sprites, levels, battle HP when relevant, one status
line, and only the available move buttons. Resolving the encounter shows one
small result panel, then returns to the root dropdown. No wide encounter
renderer remains in the native app.
Battle names and caught, fled, or ran-away result titles use neutral ink. One
colored rarity letter immediately after the copy carries the rarity signal.

## <img src="assets/brand/icons/setup.png" width="22" height="22" alt=""> First Run

After BuddyMon gets one confirmed local status showing that no buddy exists,
first run automatically opens **First Signal** in the anchored panel:

1. Choose a starter.
2. BuddyMon is ready immediately with built-in fallback art.
3. Do a little work and return for the next signal.
4. Install optional art later with `/buddymon:official` or `install-assets` only
   if you want it.

BuddyMon never downloads optional art automatically, and missing art never
blocks setup. First Signal, its working state, and any setup error all use the
same 304-by-210 Field Guide panel as the everyday dropdown. There is no dark
console-style setup window. A failed refresh keeps the last working copy.

## <img src="assets/brand/icons/native-app.png" width="22" height="22" alt=""> Compact Dropdown

Compact is the complete native product surface. A waiting encounter is exposed
as the first compact action; choosing it, taking every move, and seeing its
result all stay inside the anchored dropdown. Party, Box, Pokédex, Activity,
and Showcase remain in the Python terminal game, but do not have duplicate
native renderers or private native bridge routes.

Settings presents all seven preferences directly in one
304-by-210 panel. Every allowed value is visible; the active value is marked,
and selecting another option applies that exact validated value immediately.
Backup and optional-art setup remain explicit terminal or command flows rather
than masquerading as native preferences.

Click outside to close the panel and keep BuddyMon running. Click the menu-bar
buddy again to toggle compact mode. No normal product destination opens a
separate BuddyMon window.
While the panel remains open, it keeps the screen position captured at that
closed-to-open transition. Menu-bar animation and refreshes cannot shift it;
closing and reopening captures the buddy's current position again.

## <img src="assets/brand/icons/development.png" width="22" height="22" alt=""> Terminal Is Optional

Party, Box, Pokédex, and Activity launch the existing terminal client at that
exact destination using the saved launcher preference. Trainer and Settings
stay in the native panel. The terminal path keeps the compact emoji/ASCII experience and Ghostty
PNG experience available for power users. New users never need to choose
between “coder” and “simple” during onboarding; native is the default.
Each handoff chooses the largest safe footprint for the current display:
`1040-by-680`, `920-by-600`, or the compact `760-by-520` fallback. It prefers to
sit beside the menu-bar panel and leaves that panel visible while the terminal
is in use. The origin is clamped to the panel's current display. iTerm2 and
Terminal.app use exact scripted bounds. Ghostty maps those footprints to
`112-by-38`, `100-by-34`, and `88-by-30` grids with saved state, fullscreen,
maximize, and close confirmation disabled. Its first process is the stable
system shell, which receives the safely quoted BuddyMon command as startup
input; the bundled Python runtime is never handed to Ghostty as a file to open.
It never creates a provisional Ghostty window or closes one during frame
verification, so a single handoff cannot fan out into an alert plus a second
terminal. Ghostty's pixel dimensions may vary slightly with font metrics.

## <img src="assets/brand/icons/privacy.png" width="22" height="22" alt=""> Local and Shared

The app calls the same Python boundaries as every other BuddyMon client:

- `app-status` for current state and compact action policy
- `app-view encounter|tokens|trainer|settings` for native screen data
- `app-action encounter|preference` for native mutations
- `open-menu <screen>` for explicit terminal handoffs such as Party, Box,
  Pokédex, and Activity

Python owns game rules, progression, state, and encounter logic. Swift owns the
status item, anchored panel, native rendering, and safe routing. Collection, setup,
sharing, and game commands run asynchronously so they do not freeze the panel.
Claude Code progress comes from its plugin hooks. The app's collection path reads
Codex CLI and Auggie activity; Gemini CLI stays in the read-only Token Usage
report.

## <img src="assets/brand/icons/collection.png" width="22" height="22" alt=""> Where Data Lives

Progress, journal history, and optional packs live under
`$XDG_STATE_HOME/buddymon`, or `~/.local/state/buddymon` when
`XDG_STATE_HOME` is unset. The app does not rewrite Claude, Codex, Auggie, or
Gemini settings.

Use **Back up my data** in Terminal Settings, or run
`python3 buddymon.py backup`, to create a timestamped local copy in
`~/Documents/BuddyMon Backups`.

If existing state is corrupt, unreadable, structurally invalid, or from a newer
BuddyMon release, every normal mutation stops and the original `state.json`
remains untouched. The compact panel shows **State Needs Care** instead of
mistaking the file for a new game. Valid older state is migrated only after a
copy is preserved under the local `recovery/` directory.

Local builds may require first-open approval. Published archives use the
explicit signing and notarization path in [Development](development.md). For
common problems, see [Troubleshooting](troubleshooting.md).
