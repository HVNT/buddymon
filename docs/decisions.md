# Decisions

These are BuddyMon's current durable choices and the reasons behind them.
Implementation history belongs in the changelog and Git history; current game
numbers belong in code.

## Plugin wiring stays plugin-owned

**Decision:** Install through `.claude-plugin/plugin.json` and `hooks.json`.
Never rewrite a user's global Claude settings.

**Why:** Plugin installation should be reversible, reviewable, and isolated
from unrelated tool configuration.

## Personal data stays local and outside the repo

**Decision:** Store state, journal history, and optional packs under
`$XDG_STATE_HOME/buddymon`, defaulting to
`~/.local/state/buddymon`.

**Why:** Progress survives repository updates without leaking personal data or
generated assets into commits. Normal play reads local inputs and does not
upload game state.

Manual backups copy the entire active state directory to
`~/Documents/BuddyMon Backups` with a timestamped folder. Terminal Settings and
`python3 buddymon.py backup` call the same Python operation. It respects
`XDG_STATE_HOME` and does not modify live data.

## Python owns the game

**Decision:** Keep rules and persistence in Python. Statusline, terminal,
SwiftBar, tmux, and the macOS app are presentation shells over the same state.

**Why:** One rules engine prevents clients from drifting. The native app uses
stable JSON views and actions instead of parsing human-readable output.

## Token Usage reports only supported local AI tools

**Decision:** Token Usage recognizes Claude Code, Codex CLI, Auggie, and Gemini
CLI only. Unknown log shapes are ignored rather than grouped under a vague
catch-all source, and model names remain hidden until their local record format
provides them reliably.

**Why:** A dashboard should describe what BuddyMon actually supports. Guessing
at providers or models makes the product feel more capable than its local data
can prove.

## Python owns native-menu policy

**Decision:** Return the menu's compact structure, labels, ordering,
visibility, shortcuts, and stable action IDs from `app-status`. Swift renders
the model with native brand styles and routes only known action IDs.

**Why:** Menu product decisions stay beside the game state that determines
them, while AppKit remains responsible for native presentation, accessibility,
and safe local routing.

State changes hold one cross-process lock across fresh load, mutation, and save.
Interactive screens release it while waiting for input, then re-resolve the
selection before saving.

## The menu-bar buddy remains the primary native surface

**Decision:** Treat the status item as BuddyMon's first product surface, not a
launcher icon. Python owns its complete state catalog and timed pixel frames;
the thin Swift player queues stable sequence ids, respects Reduce Motion, and
renders them on the native status-bar button. Its contract and complete state
harness remain a required gate for compact-dropdown changes.

**Why:** BuddyMon began as a tiny companion that makes work a little brighter.
Resting, working, XP, level-up, encounter, catch, result, and evolution moments
must feel coherent at menu-bar scale before a larger interface can add value.
The developer harness makes the whole state machine visible without mutating
personal game state. The active buddy remains the status item's persistent
identity: a catch may show the wild Pokémon during its action, but its result
settles back on the buddy while the compact panel identifies the caught species.
The status item uses the same species-specific Gen 5 source as that panel when
available; shared legacy menu icons are fallback art, not buddy identity art.

## Native commands are asynchronous

**Decision:** Run Python app commands away from the main UI thread, drain both
output streams, and bound them with timeout and cancellation handling.

**Why:** Collection, image export, or a large JSON response must not freeze the
app or deadlock on a full process pipe.

## The friend app is menu-bar-only and self-contained

**Decision:** Ship the friend build with a private Python runtime. The app is an
accessory process with one visible home: the menu-bar buddy and its anchored
panel. It does not create a Dock icon or standalone product window.

**Why:** A nontechnical tester still gets one app to open without installing
Python or using Terminal, while everyday use stays faithful to BuddyMon's tiny
ambient-companion purpose. The tradeoff is a larger, currently unsigned app
bundle.

## The native app has one process per user

**Decision:** Allow only one running BuddyMon native app across development,
preview, and friend-build bundle copies.

**Why:** Each native process owns a menu-bar item, timers, and child
commands. A per-user advisory lock enforces the invariant even when a developer
runs an app executable directly or launches a copy from another bundle path.
The kernel remains the source of truth for ownership; the lock file does not
store or trust a process id supplied by another process. A later app launch
sends a local distributed notification so the running copy reopens its panel.

## Native state synchronization is event driven

**Decision:** Watch the local BuddyMon state directory for atomic `state.json`
replacements, filter events by the state file's signature, debounce save
bursts, and coalesce passive status reads. Opening the dropdown also requests a
fresh read. Keep the 30-second poll only as a recovery fallback.

**Why:** Terminal play, hooks, and the native app are separate local processes.
Polling alone can leave a new battle invisible for most of a polling interval,
while a one-second poll would repeatedly launch Python when nothing changed.
Directory observation survives the atomic rename used by state saves, exact
signature filtering ignores journal and lock writes, and menu-bar animation can
remain an independent presentation concern.

## Native brand styles have one source of truth

**Decision:** `BuddyMonBrand` is the sole source of visual truth for shipping
native UI. Field Guide is its compact-menu expression. `BrandStyle.swift` owns
colors, type, spacing, geometry, motion values, and shared component treatments.
Every native screen consumes those tokens; older Redline Mono explorations are
developer-preview history only.

**Why:** A living preview is useful only when it renders the same tokens as the
product. Central ownership prevents one-off palettes, spacing drift, and
component variations from quietly becoming competing systems. The older Style
Archive stays available as historical context but is explicitly non-normative.

Any new visual value starts in `BrandStyle.swift`, is demonstrated in
`BrandStylesPreview.swift` or the product-specific
`MenuPanelStateHarnessView.swift`, and is documented in `docs/brand.md` in the
same change. Deterministic Brand Styles and compact-panel PNG renders provide
visual-review evidence. The previews remain developer tooling and are not
reachable from the production panel.

Compact screens do not animate into place. Opening the panel, navigating, and
refreshing local data all render the complete view immediately, with the panel's
window animation disabled. Motion is reserved for Pokémon state playback and
small direct-control feedback that honors Reduce Motion; it must not gate page
content or make navigation cadence depend on row count.

## Optional art requires explicit consent

**Decision:** Built-in fallback art is always enough for readiness. Optional art
is installed or refreshed only after a confirmed user action, and a failed
operation preserves the last working pack.

**Why:** Normal play should remain local-only and dependable. Optional,
third-party-derived assets should not be bundled or downloaded silently.

The Trainer Card's 64-by-64 Red pose is one explicit exception requested by the
trainer. It is a fixed, source-recorded FireRed/LeafGreen UI asset bundled with
the native shell; there is no runtime fetch. If that resource cannot load, the
card falls back to its local monochrome figure.

## Scheduled collection has one gate

**Decision:** The app timer and optional LaunchAgent both use
`collect --scheduled`, with one locked five-minute due check. Manual
`collect` remains immediate.

**Why:** Multiple clients may be active at once. A single gate prevents
double-counting without making explicit diagnostics wait.

The LaunchAgent is generated from the current runtime, script path, and XDG
environment. It is installed only through `collector install` and has explicit
`status` and `uninstall` lifecycle commands.

## Token totals are visible; progress math stays internal

**Decision:** Show understandable token totals, while treating the weighted XP
formula as an implementation detail.

**Why:** People should be able to verify activity without optimizing their work
around a game formula. Cached, input, output, and reasoning activity can all
contribute, while thresholds keep ordinary sessions rewarding.

## Progression stays long-lived

**Decision:** Keep a high buddy level cap, a lower random-wild cap, stage-aware
wild levels, fixed special-Pokémon levels, and visible evolution moments.

**Why:** The active buddy should remain worth growing for months, while catches
stay varied and readable instead of immediately matching endgame progress.
Exact values live in the game data and engine.

## Encounter styles are explicit

**Decision:** Quick is the default. Safari and Battle are opt-in modes. Rare and
legendary moments remain interactive even when ordinary Quick encounters can
resolve automatically.

**Why:** The default should not interrupt work, while players who want more game
decisions can choose them without changing the underlying collection.

## Rich encounter art is native and on demand

**Decision:** Render one local pixel battle scene for each native encounter
view or resolved result. The status item may play short, bounded local frame
sequences for catches, battles, results, and evolution; it does not continuously
regenerate art while idle and SwiftBar keeps its bounded transient stream.

**Why:** Encounters retain their game-like visual identity without reviving the
memory and CPU costs of continuously replacing menu-bar images. The same local
sprite-pack fallback path keeps the feature available without network assets.

## Preferences are local and bounded

**Decision:** Store only validated values for encounter mode, notifications,
menu launcher, terminal menu replacement, terminal graphics, share reveal, and
share banner behavior.

**Why:** Settings should accept an explicit validated value from every client
and recover cleanly from old or invalid state.

## Showcase is curated and local

**Decision:** Start with empty podium slots, store only selected Pokémon ids,
and export a PNG to the user's machine on demand.

**Why:** A showcase should reflect deliberate choices, not duplicate Party or
favorites automatically. Local export makes sharing useful without adding
accounts, uploads, or persistent export history.

## Onboarding invites without interrupting work

**Decision:** Native first run starts with a quiet menu-bar egg. Clicking it opens
First Signal in the anchored panel: a five-starter local setup screen with one
simple first mission. It does not open a standalone window, download optional
art, or schedule prompts.

**Why:** BuddyMon should feel like a little game from the first click while
remaining a calm local companion. Delight belongs to the player's own work and
collection, not attention-harvesting loops.

## The current native experience is the compact dropdown

**Decision:** Clicking the buddy always opens the compact everyday dropdown. A
waiting wild becomes its first emphasized action instead of bypassing the
dropdown. The native shell retains only the compact root, encounter and result,
Token Usage, Trainer, Settings, and the small generic setup/loading/confirmation
host. Party, Box, Pokédex, Activity, and Showcase remain terminal-game
destinations; the deleted expanded native graph and its private JSON routes are
not dormant product surfaces. The root presents a square two-row grid of six
compact links: native Trainer and Settings destinations plus terminal handoffs
for Party, Box, Pokédex, and Activity. The old renderer remains recoverable from
Git history and the `archive/native-window-prototype-2026-07-16` tag rather than
being compiled into the current app.

The panel captures the status item's screen-space anchor once when it opens and
keeps that anchor through refreshes and drill-ins. Closing clears the snapshot,
so the next open follows the buddy's then-current position without allowing
variable-width animation frames to move an already-open panel.

**Why:** The product began as a tiny companion, not a desktop dashboard.
Finalizing one dependable dropdown keeps the current quality gate honest and
prevents historical experimental breadth from dictating the everyday product.

Opening or reopening the app resolves to the compact dropdown. Development
builds stay under `.build`; `--install` explicitly replaces the copy in
`/Applications` so Finder cannot keep launching a stale experience.

Optional terminal handoffs are compact adjuncts to that surface. They request
one roughly 760-by-520 footprint beside the open panel, clamp it to the current
screen, and do not dismiss the panel or its state. iTerm2 and Terminal.app use
exact scripted bounds. Ghostty starts one isolated process with its position,
88-by-30 grid, fixed BuddyMon title, disabled saved state, and non-fullscreen
state supplied before launch. Its initial process is the stable system shell,
and the safely quoted menu command arrives as startup input. This keeps the
app-bundled Python runtime out of Ghostty's file-open confirmation path. It does
not activate or resize an existing Ghostty window, create a provisional window,
or close a live terminal during fallback. The launcher tries another terminal
only when Ghostty rejects the launch request before accepting a window.

**Why:** A best-effort size is less disruptive than a pixel-perfect handshake
that briefly creates a second window or asks the trainer to confirm closing it.
The isolated process also gives replacement logic a precise BuddyMon-owned
target without touching unrelated Ghostty sessions.

## Developer previews never become trainer state

**Decision:** Menu-bar visual QA plays canonical Python-rendered sequences on
the real native status item through a temporary local payload and process
signal. Preview state is never written to `state.json` or the journey journal,
never opens the dropdown, and automatically returns to the newest live status.

**Why:** A fake preview window cannot prove the tiny real menu-bar surface, but
polluting a trainer's collection or event history would make visual review
unsafe. A bounded local-only playback channel tests the shipping renderer while
preserving the core's state and privacy boundaries.

The shipping native graph stops at the menu-bar state harness, compact
dropdown, its compact drill-ins, and generic first-run/result content. Terminal
screens do not require duplicate native renderers.

## The compact dropdown uses the Field Guide skin

**Decision:** The everyday dropdown uses a warm off-white, almost entirely
monochrome field-guide layout: one tonal buddy group, one borderless
game-dialogue signal, and a short action list. Dark terminal chrome, blue
structural chrome, repeated card borders, stat boxes, and ASCII-box decoration
are not the default native surface. Shared tokens and controls live under
`BuddyMonBrand.Menu`; Pokémon identity, rarity, and urgent alerts remain the
few semantic color accents.

Token Usage is the first compact drill-in. It summarizes Today, Last 7 Days,
prior-period trend, a proportional seven-day daily pulse, daily average, peak
day, active streak, and leading tools inside the same anchored panel. These are
the highest-value glanceable parts of the structured dashboard payload; there
is no separate wide native dashboard.
Its loading, success, and failure states all use the standard 304-by-210-point
Field Guide panel. The async view request never routes through a standalone
loading window, preventing a dark oversized frame during navigation.
The compact report is read-only, so it does not spend its bottom row explaining
arrow or Return selection that does not exist. Supported-tool share becomes the
bottom anchor; Back and Escape remain available through shared navigation.

Settings is the next compact drill-in. It presents every current preference
directly in one 304-by-210 Field Guide view with the shared back-chevron/title row.
Each row exposes every allowed value. Selecting an option sends that exact
validated Python preference immediately, then refreshes the list in place.
Preference options are compact text controls
rather than persistent filled buttons. Their resting state is transparent,
every option uses a pointing-hand cursor, hover is transient, and keyboard focus
retains a visible square outline. The active option is darker, bold, underlined,
and marked with a leading chevron so state is visible without relying on color.
Backup and optional-art setup remain explicit terminal or command flows because
they require operational feedback rather than a preference value.

The root panel exposes Tokens, Today, and Yesterday as one clickable,
backgroundless, right-aligned masthead line, with no separate token row or
visible Open copy. The buddy group ends after XP rather than using another line
for trainer totals. Refresh and Quit are
footer commands, not action cards, and follow macOS conventions as `⌘R` and
`⌘Q`. The masthead begins with the FireRed/LeafGreen-inspired bitmap wordmark;
it has no decorative leading icon. A steady semantic dot immediately after the
wordmark reports active, starting, or unavailable local status without reusing a
blinking cursor as decoration. Active describes app health, not whether a
starter has been chosen. That local bitmap face is used for major compact
labels and actions; SF Mono remains the supporting data face.
The root frame keeps a six-point content gutter, while the active-buddy group
breaks out to the full 288-point inner frame width. That row is square and uses
only subtle top and bottom rules; its single six-point inner padding layer keeps
the 54-point buddy sprite aligned with the three identity rows beside it.

Trainer opens a non-mutating 3:2 card inside the same compact panel. It reports
NAME, TOKENS, POKÉDEX, and CAUGHT; it never invents a trainer level or relabels
the active Pokémon's level. Badge eligibility is derived by Python from local
collection, Showcase, and journey evidence. The regular rail contains Bond,
Safari, Battle, Curator, Type, Shiny, Legend, National, and Shiny Legend.
Shiny National is omitted entirely until National is earned, then appears as a
locked or earned tenth badge. The four stars summarize core badge progress and
are not a level.
Badge controls explain their earned state or requirement in place. Selection
does not mutate progress or open another surface.

Waiting encounters use the same compact drill-in contract. The shell renders
the Python-supplied buddy, wild, HP, message, and action policy as two sprite
identities, one dialogue line, and one move row. Arrow/Return navigation is
shared across the compact root, Tokens, Trainer, encounter, and result panels.
Pokémon names and result titles remain neutral ink; a single adjacent rarity
code is their only rarity color, matching Last Catch.
Trainer, Tokens, encounter, and result also share one leading back-chevron and
display-title row; trailing context may follow, but a second Back or Return Home
action may not duplicate it.
The masthead or navigation row, Field Guide border, striped background,
surrounding canvas, and content rows all render immediately. The panel shell
disables window-level animation, and compact screens own no entrance timing or
transition exceptions.
On the root panel, Python supplies a complete waiting label and the shell folds
that label, the wild sprite, and the encounter shortcut into one dark action;
there is no duplicate field-message row.

**Why:** Terminal density is useful, but terminal imitation made a tiny native
menu feel like a developer console. A handheld field-guide structure keeps the
same compact information density while making the Pokémon and current moment
the obvious product center.
