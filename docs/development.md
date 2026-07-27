# Development

BuddyMon keeps its normal runtime stdlib-only where practical. Tests add pytest
and Pillow:

```bash
uv run --with pytest --with pillow --no-project python3 -m pytest tests/ -q
```

Pillow covers image import, export, and sprite-pack tooling.

## Useful Commands

```bash
python3 buddymon.py app-status --pretty
python3 buddymon.py app-menu-bar-harness --pretty
python3 buddymon.py app-menu-panel-harness --pretty
python3 buddymon.py app-view encounter
python3 buddymon.py app-view tokens
python3 buddymon.py app-view trainer
python3 buddymon.py app-view settings
python3 buddymon.py app-action preference mode quick
python3 buddymon.py install-assets --json
python3 buddymon.py menu
python3 buddymon.py tokens
python3 buddymon.py collect
python3 buddymon.py status
python3 buddymon.py dex --list
python3 buddymon.py preview
python3 buddymon.py tiny --collect
```

`app-status`, the four listed `app-view` routes, and the `encounter` and
`preference` `app-action` routes are the stable native JSON boundary. Python
owns game rules and state mutations. Party, Box, Pokédex, Activity, and
Showcase are terminal screens, not native bridge views.

## macOS App

For the user flow, see [BuddyMon.app, ELI5](macos-app.md).

```bash
# Developer build: uses this Mac's /usr/bin/python3
scripts/build-macos-app.sh

# Self-contained build
scripts/build-macos-app.sh --friend

# Replace /Applications/BuddyMon.app and open that installed copy
scripts/build-macos-app.sh --friend --install --open
```

`--install` first asks any running BuddyMon process to quit, then replaces the
bundle. This prevents `--open` from signaling an old in-memory build after its
files have been updated.

The self-contained build uses `BUDDYMON_PYTHON_RUNTIME` or `--runtime-dir` when
provided. Otherwise it creates a managed standalone CPython runtime under
`.build/python-runtime`, installs Pillow, validates the runtime, and copies it
into the app. Default runtime inputs come only from
`scripts/runtime-lock.json`: exact Python archives and architecture-specific
Pillow wheels are verified by SHA-256 before extraction or installation. A
managed runtime is reused only when its metadata and imported Python/Pillow
versions still match that lock.
Custom `--url` or `--tarball` inputs require an explicit `--sha256`.

```bash
scripts/build-macos-app.sh --friend --force-runtime
scripts/build-macos-app.sh --friend --python-version 3.12.13
BUDDYMON_PYTHON_RUNTIME=/path/to/runtime scripts/build-macos-app.sh --friend
scripts/capture-brand-styles.sh
scripts/menu-bar-state-harness.sh
scripts/capture-menu-bar-states.sh
scripts/capture-menu-panel.sh
scripts/capture-menu-panel-states.sh
```

An external development runtime must be named explicitly and paired with
`--allow-unlocked-runtime`. That escape hatch performs import checks but is not
used by CI or the release packager:

```bash
scripts/build-macos-app.sh \
  --friend \
  --runtime-dir /path/to/development-runtime \
  --allow-unlocked-runtime
```

### Watch menu-bar states and user stories

Build and launch the current native app once, then drive its real menu-bar
buddy from the Python demo runner:

```bash
scripts/build-macos-app.sh
open .build/macos/BuddyMon.app

scripts/menu-bar-demo.py list
scripts/menu-bar-demo.py play evolving
scripts/menu-bar-demo.py story evolution
scripts/menu-bar-demo.py story interactive-retry
scripts/menu-bar-demo.py story all-stories --speed 2
scripts/menu-bar-demo.py story all-states --speed 2
scripts/menu-bar-demo.py reset
```

The fixtures assume Charmander is the starter and Eevee is the wild Pokémon.
`play` reserves the menu-bar icon just long enough to show one state. `story`
runs its steps in order and prints the active user-story beat in the terminal.
`all-stories` is the complete narrative QA pass; `all-states` is the shorter
catalog pass with each visual shown exactly once.
Both use the production frame renderer and installed local art, never mutate
trainer state, never open the dropdown, and restore the newest live status when
playback ends. Quit and relaunch BuddyMon after rebuilding so the running app
has the current preview receiver.

The builder never rewrites an unmarked external runtime. BuddyMon-managed
runtimes carry `buddymon-runtime.json`; replacements are validated in staging
before the previous runtime is changed.

`VERSION` is the canonical product version. The plugin manifest, marketplace
metadata, generated app plist, and runtime lock are checked with:

```bash
python3 scripts/validate-release-metadata.py
python3 scripts/validate-release-metadata.py --app .build/macos/BuddyMon.app
```

### Signed release archive

The release packager rebuilds the embedded runtime from the lock, verifies it,
enforces the production bundle id and canonical version/build before signing
and again before archiving, signs every Mach-O payload and the app with Hardened
Runtime, submits the archive for notarization, staples and assesses the app,
and writes a SHA-256 file whose entry uses the archive basename, so the two
downloaded files verify together in any directory. It never discovers
credentials. Configure an existing Developer ID identity and `notarytool`
keychain profile through Apple's supported tools, then run:

```bash
BUDDYMON_CODESIGN_IDENTITY="Developer ID Application: ..." \
BUDDYMON_NOTARY_PROFILE="buddymon-notary" \
scripts/package-macos-release.sh
```

The output is `.build/release/BuddyMon-macOS-ARCH.zip` plus its checksum. The
stable asset name supports the README's `/releases/latest/download/` link while
the app bundle keeps the canonical version in its metadata. Build on each
architecture you intend to publish; do not label one archive universal.

Before changing native UI, read [Brand Styles](brand.md) and use
`BuddyMonBrand`. `BrandStylesPreview.swift` is the living reference for the
shared system. `MenuPanelStateHarnessView.swift` renders the shipping compact
components, including first-run setup, loading/error notices, and both Trainer
Card badge counts. `StyleArchivePreview.swift` keeps three older directions as
non-normative history. These developer/snapshot sources are excluded from the
self-contained build.

New colors, type, spacing, geometry, or control treatments start in
`BrandStyle.swift`, then appear in the Brand Styles preview with all relevant
states in the same change. Shipping views must not define local visual themes.
The capture commands write the full scrollable reference to
`.build/brand-styles.png`, the complete menu-bar state inventory to
`.build/menu-bar-state-harness.png`, the shipping compact panel to
`.build/menu-panel.png`, and all compact product states to
`.build/menu-panel-states.png` for visual review. Run
`scripts/menu-bar-state-harness.sh` without arguments to open the interactive,
scrollable harness; use Play, Pause, and Restart to inspect the shipping frame
scheduler.

Native Python commands run asynchronously through `ProcessExecutor`. It drains
stdout and stderr while the process runs and applies timeout and cancellation
handling so large payloads or a slow child process cannot freeze the app.

## Collection Service

The app timer and optional LaunchAgent both call:

```bash
python3 buddymon.py collect --scheduled
```

That path uses one locked five-minute gate, so overlapping clients do not award
the same activity twice. `python3 buddymon.py collect` is an immediate manual
run and bypasses the schedule gate.

Manage the per-user service with:

```bash
python3 buddymon.py collector install
python3 buddymon.py collector status
python3 buddymon.py collector uninstall
```

Install generates
`~/Library/LaunchAgents/io.github.hvnt.buddymon.collector.plist` from the
current script path and active Python runtime. It also preserves
`XDG_STATE_HOME` when set. Do not install the real service in tests; use a
temporary home and the injected command runner.

## Optional Assets

Generated packs belong under `$XDG_STATE_HOME/buddymon/packs`, or
`~/.local/state/buddymon/packs` by default. Do not commit them.

```bash
python3 buddymon.py install-assets
python3 buddymon.py install-assets --refresh
uv run --with pillow --no-project python3 tools/fetch_official.py
uv run --with pillow --no-project python3 tools/fetch_box.py
uv run --with pillow --no-project python3 tools/fetch_gen5.py
```

See [Assets](assets.md) for sources, validation, and fallback behavior.

## Before Pushing

```bash
python3 -m pip install --requirement requirements-test.txt
python3 -m pytest tests/ -q
python3 scripts/validate-release-metadata.py
scripts/build-macos-app.sh
git diff --check
git status --short
```

Keep generated packs, personal state, and unrelated worktree changes out of the
commit.

The same test/build/metadata gate runs on macOS for every pull request and
`main` push through `.github/workflows/ci.yml`.
