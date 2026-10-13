# <img src="assets/brand/icons/setup.png" width="28" height="28" alt=""> Public Release QA

Use this checklist for every public BuddyMon.app archive. It supplements unit,
native-harness, and CI coverage with the real prompts a new macOS user sees.

## <img src="assets/brand/icons/native-app.png" width="22" height="22" alt=""> Release artifact

Replace the version's `unreleased` changelog marker with its publication date
before packaging. Both the packager and standalone archive verifier reject an
undated public release; the packager checks before rebuilding the runtime.

On the authorized release Mac, package the app with the existing Developer ID
identity and notary profile:

    BUDDYMON_CODESIGN_IDENTITY="Developer ID Application: ..." \
    BUDDYMON_NOTARY_PROFILE="buddymon-notary" \
    scripts/package-macos-release.sh

Before upload, verify the exact archive and checksum that will be attached:

    python3 scripts/verify-release-archive.py \
      .build/release/BuddyMon-macOS.dmg \
      .build/release/BuddyMon-macOS.dmg.sha256

The verifier checks the checksum, archive layout, release metadata, embedded
runtime locks for both architectures, code signature, stapled DMG, Gatekeeper assessment, and a disposable-state
app-status run from the embedded Python runtime.

## <img src="assets/brand/icons/setup.png" width="22" height="22" alt=""> Fresh-user acceptance

Use a clean, non-admin macOS 13-or-newer Apple-silicon user account or VM. Do
not copy BuddyMon state, optional packs, a LaunchAgent, or a Claude profile
into it. Record macOS version, archive checksum, and screenshots of every
system dialog.

1. Download the GitHub Release DMG and its checksum, verify it, open it, drag
   **BuddyMon.app** to Applications, and open it.
   Compare the local result with the matching checksum file:

       shasum -a 256 BuddyMon-macOS.dmg

2. Expected baseline: no unidentified-developer warning and no privacy,
   Automation, notification, or network-art prompt before First Signal.
   BuddyMon appears only in the menu bar.
3. Confirm First Signal appears after local status resolves. Choose a starter,
   confirm built-in art works immediately, quit, reopen, and verify the chosen
   starter persists without replaying setup.
   Open Token Usage during the first scan: loading must stay responsive and
   totals must appear automatically. Go Back or close the panel while it scans;
   completion must not change screens or reopen the panel.
4. Confirm artwork downloads while play stays available. Disconnect during a
   download, verify Retry appears, reconnect and retry. Quit mid-download and
   verify the next launch resumes completed progress. No LaunchAgent is created.
   Include a failed shiny request after regular art succeeds: the regular sprite
   must remain visible, Retry must fetch the missing shiny, and setup must not
   claim completion early. An older regular-only pack must repair automatically.
5. From a clean Claude Code profile without the plugin, complete new activity
   after BuddyMon's first scan. Verify collection and progress while the app is
   open. Add the optional plugin and verify the same activity is not counted twice.
6. Repeat startup and collection on an Intel Mac. An Intel runtime probe through
   Rosetta on Apple Silicon is useful evidence but does not replace native Intel QA.

## <img src="assets/brand/icons/activity.png" width="22" height="22" alt=""> Optional actions and expected prompts

Exercise each action deliberately. A denied or cancelled system dialog must
leave BuddyMon usable and must not lose state.

| Action | Expected behavior to record |
| --- | --- |
| /buddymon:official or install-assets | Explicit plugin/CLI setup or refresh; app onboarding downloads missing packs automatically. No pack is bundled. |
| collector install, then collector uninstall | Creates and removes only the per-user BuddyMon LaunchAgent. Record whether macOS presents any service-related prompt. |
| Turn notifications on with terminal-notifier available | Record the Notification Center consent dialog or confirm no dialog appears; then verify disabling notifications stops delivery. |
| Open a terminal handoff through Ghostty, iTerm2, and Terminal.app where installed | Record any macOS Automation consent dialog. Test both Allow and Do Not Allow, then confirm BuddyMon remains usable. |
| Export and reveal a Showcase | Record any Desktop/Finder permission dialog and verify cancellation leaves the game state intact. |

## <img src="assets/brand/icons/privacy.png" width="22" height="22" alt=""> Publish gate

Publish only when the artifact verifier, clean-user checklist, and PR CI are
all recorded as passing. Attach the universal DMG and matching .sha256 file
to vMAJOR.MINOR.PATCH, then confirm the README's stable download URL serves
that exact archive.

Record the release version, commit, macOS version, archive checksum, each
observed dialog, and the final Allow/Do Not Allow result with the release notes.
