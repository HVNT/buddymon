import os
import re
import struct
import subprocess

from tests.native_test_support import (
    MENU_PANEL_SWIFT_NAMES,
    ROOT,
    SWIFT_DIR,
    contrast_ratio,
    pytestmark as pytestmark,
    read_menu_panel_sources,
    swift_brand_color,
    swift_function_body,
)


def test_style_archive_is_developer_only_and_non_normative():
    app_source = (
        SWIFT_DIR / "AppDelegate.swift"
    ).read_text(encoding="utf-8")
    archive_source = (
        SWIFT_DIR / "StyleArchivePreview.swift"
    ).read_text(encoding="utf-8")
    build_source = (ROOT / "scripts" / "build-macos-app.sh").read_text(
        encoding="utf-8"
    )

    assert 'title: "Style Archive"' not in app_source
    assert "showStyleArchive" not in app_source
    assert "ARCHIVED VISUAL EXPLORATIONS // NON-NORMATIVE" in archive_source
    assert "New work always follows BuddyMonBrand." in archive_source
    assert "ConsoleLab" not in app_source
    assert "ConsoleLab" not in archive_source
    assert "LabStyle" not in archive_source
    assert "ArchivedStyle" in archive_source
    assert "SWIFTC_ARGS+=(-D BUDDYMON_DEVELOPMENT)" in build_source
    assert 'if [[ "${REQUIRE_RUNTIME}" != "1" ]]' in build_source
    development_sources = build_source.split(
        'if [[ "${REQUIRE_RUNTIME}" != "1" ]]', 1
    )[1]
    assert "StyleArchivePreview.swift" in development_sources
    assert "BrandStylesPreview.swift" in development_sources
    setup_source = (SWIFT_DIR / "CompactSetupView.swift").read_text(
        encoding="utf-8"
    )
    assert "NSFont.systemFont" not in archive_source
    assert "NSFont.systemFont" not in setup_source
    for title in [
        "01 / CANVAS + SURFACES",
        "02 / SPACING + DENSITY",
        "03 / TYPOGRAPHY",
        "04 / SECTION CHROME",
        "05 / COMMAND CONTROLS",
        "06 / DATA + SPRITE FRAMES",
    ]:
        assert title in archive_source
    for title in [
        "A / VOID GRID",
        "B / NIGHTSHIFT",
        "C / AFTERBURN",
    ]:
        assert title in archive_source


def test_brand_styles_are_the_canonical_native_visual_system():
    app_source = (SWIFT_DIR / "AppDelegate.swift").read_text(encoding="utf-8")
    setup_source = (SWIFT_DIR / "CompactSetupView.swift").read_text(
        encoding="utf-8"
    )
    brand_source = (SWIFT_DIR / "BrandStyle.swift").read_text(encoding="utf-8")
    preview_source = (SWIFT_DIR / "BrandStylesPreview.swift").read_text(
        encoding="utf-8"
    )
    panel_source = read_menu_panel_sources()
    brand_docs = (ROOT / "docs" / "brand.md").read_text(encoding="utf-8")
    agent_rules = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    capture_script = (ROOT / "scripts" / "capture-brand-styles.sh").read_text(
        encoding="utf-8"
    )
    menu_capture_script = (ROOT / "scripts" / "capture-menu-panel.sh").read_text(
        encoding="utf-8"
    )

    assert not (SWIFT_DIR / "ASCIILab.swift").exists()
    assert not (SWIFT_DIR / "ConsoleLab.swift").exists()
    assert 'title: "Brand Styles"' not in app_source
    assert "BrandStylesWindowController.shared.present()" not in app_source
    assert "#if BUDDYMON_DEVELOPMENT" in preview_source
    assert "BuddyMonBrand" in preview_source
    assert 'static let systemName = "Redline Mono"' in brand_source
    assert "static let section: CGFloat = 72" in brand_source
    assert "static let contentWidth: CGFloat = 880" in brand_source
    assert "static func applySurface" in brand_source
    assert "static func applyButton" in brand_source
    assert "static func makeButton" in brand_source
    assert "static func makeField" in brand_source
    assert "static func makeControlLabel" in brand_source
    assert "static func pokemonColor" in brand_source
    assert "static func makeDisplayLabel" in brand_source
    assert "static func makeRarityLabel" in brand_source
    for rarity, code in [
        ("common", "C"),
        ("uncommon", "U"),
        ("rare", "R"),
        ("legendary", "L"),
        ("mythic", "M"),
        ("starter", "S"),
    ]:
        assert f'case "{rarity}": return "{code}"' in brand_source
    menu_brand_source = brand_source.split("enum Menu {", 1)[1]
    menu_surface_color = swift_brand_color(menu_brand_source, "surface")
    for token in [
        "mutedInk",
        "pokemonGrass",
        "pokemonWater",
        "pokemonRare",
        "rarityLegendary",
        "rarityStarter",
    ]:
        assert contrast_ratio(
            swift_brand_color(menu_brand_source, token),
            menu_surface_color,
        ) >= 4.5, f"{token} must pass normal-text contrast on the menu surface"
    assert "enum FireRedDisplay" in brand_source
    assert "inspired by the FireRed/LeafGreen UI" in brand_source
    assert "static let glyphTracking: CGFloat = 1.5" in brand_source
    assert "private static func metrics(" in brand_source
    assert "glyphWeightExpansion" not in brand_source
    assert "BuddyMonTokenHeaderButton" in panel_source
    assert "headerTokenControl(" in panel_source
    assert '"U OPEN"' not in panel_source
    token_button = swift_function_body(
        panel_source,
        "private final class BuddyMonTokenHeaderButton",
    )
    assert "borderWidth" not in token_button
    assert "focusSurface" not in token_button
    assert "cursor: .pointingHand" in token_button
    footer_button = swift_function_body(
        panel_source,
        "final class BuddyMonMenuFooterButton",
    )
    assert "cursor: .pointingHand" in footer_button
    assert "BuddyMonMenuFooterButton(" in panel_source
    menu_button = swift_function_body(
        brand_source,
        "private final class BuddyMonMenuActionButton",
    )
    assert "cursor: .pointingHand" in menu_button
    assert "BuddyMonBrand.Motion.animateQuickLinkHover" in menu_button
    assert "static let panelWidth: CGFloat = 304" in brand_source
    assert "static let actionLabelPixel: CGFloat = 0.92" in brand_source
    assert "static let quickLinkHeight: CGFloat = 22" in brand_source
    assert "static let quickLinkColumns = 3" in brand_source
    assert "static let quickLinkHoverLift: CGFloat = 1" in brand_source
    assert "static func makeQuickLink(" in brand_source
    assert "Self.quickLinkGrid(utilityButtons)" in panel_source
    assert "BuddyMonBrand.Menu.quickLinkColumns" in panel_source
    quick_link = swift_function_body(
        brand_source,
        "private static func refreshQuickLink",
    )
    assert "subtleRule" in quick_link
    assert "Geometry.borderWidth" in quick_link
    assert "Geometry.cornerRadius" in quick_link
    quick_link_motion = swift_function_body(
        brand_source,
        "static func animateQuickLinkHover",
    )
    assert "accessibilityDisplayShouldReduceMotion" in quick_link_motion
    assert 'CABasicAnimation(keyPath: "transform.translation.y")' in quick_link_motion
    assert "quickLinkHoverDuration" in quick_link_motion
    encounter_feedback = swift_function_body(
        brand_source,
        "static func animateEncounterFeedback",
    )
    assert "accessibilityDisplayShouldReduceMotion" in encounter_feedback
    assert 'CAKeyframeAnimation(keyPath: "transform.translation.x")' in (
        encounter_feedback
    )
    assert "encounterFeedbackDuration" in encounter_feedback
    assert "fieldGuideQuickLinkSample()" in preview_source
    assert "BuddyMonBrand.Menu.makeQuickLink(" in preview_source
    assert "no separate Open label" in brand_docs
    assert "Encounter moves are single-flight" in brand_docs
    assert "ACTION PENDING" in preview_source
    for token in [
        "canvas",
        "surface",
        "textPrimary",
        "textSecondary",
        "brand",
        "pokemonBlue",
        "rarity",
        "starterWater",
        "starterGrass",
        "pikachu",
        "xpProgress",
        "dataProgress",
    ]:
        assert f"static let {token}" in brand_source

    surface_color = swift_brand_color(brand_source, "surface")
    for token in [
        "textPrimary",
        "textSecondary",
        "brand",
        "rarity",
        "starterWater",
        "starterGrass",
        "pikachu",
    ]:
        assert contrast_ratio(
            swift_brand_color(brand_source, token),
            surface_color,
        ) >= 4.5, f"{token} must pass normal-text contrast on the brand surface"
    assert contrast_ratio(
        swift_brand_color(brand_source, "pokemonBlue"),
        surface_color,
    ) >= 3.0, "pokemonBlue must pass large-identity contrast on the brand surface"

    shipping_source = app_source + panel_source
    assert "BuddyMonBrand" in panel_source
    assert "BuddyMonBrand" in setup_source
    assert "ConsoleTheme" not in shipping_source
    assert "ASCIILab" not in shipping_source
    assert "NSColor(calibratedRed:" not in shipping_source
    assert "NSFont.monospacedSystemFont" not in shipping_source
    assert ".spacing = 14" not in setup_source
    assert ".spacing = 18" not in setup_source
    assert "root.alignment = .centerX" not in setup_source
    assert "BuddyMonBrand.Menu.makeStarterChoice" in setup_source
    assert "BuddyMonBrand.makeButton" in preview_source
    assert "BuddyMonBrand.makeField" in preview_source

    allowed_literal_sources = {"BrandStyle.swift", "StyleArchivePreview.swift"}
    literal_patterns = [
        r"NSColor\(calibratedRed:",
        r"NSFont\.systemFont",
        r"NSFont\.monospacedSystemFont",
        r"\.spacing\s*=\s*\d",
        r"\.borderWidth\s*=\s*\d",
        r"\.cornerRadius\s*=\s*\d",
    ]
    for source_path in SWIFT_DIR.glob("*.swift"):
        if source_path.name in allowed_literal_sources:
            continue
        source = source_path.read_text(encoding="utf-8")
        for pattern in literal_patterns:
            assert re.search(pattern, source) is None, (
                f"{source_path.name} bypasses BuddyMonBrand with {pattern}"
            )
        if (
            source_path.name != "AppDelegate.swift"
            and any(
                name in source
                for name in ["NSView", "NSWindow", "NSButton", "NSTextField"]
            )
        ):
            assert "BuddyMonBrand" in source, (
                f"{source_path.name} defines native UI without BuddyMonBrand"
            )

    assert "spacing rhythm 04 / 08 / 12 / 20 / 32 / 48 / 72" in preview_source
    assert "stack.alignment = .leading" in preview_source
    assert "alignment = .width" not in preview_source
    assert "distribution = .fillEqually" not in preview_source
    assert "BUDDYMON / REDLINE MONO" in preview_source
    assert "BuddyMonBrand.pikachu" in preview_source
    assert "BuddyMonBrand.starterWater" in preview_source
    assert "BuddyMonBrand.starterGrass" in preview_source
    assert "BuddyMonBrand.rarity" in preview_source
    assert "BuddyMonBrand.pokemonBlue" in preview_source
    assert "[⌘1] PARTY" in preview_source
    assert "[F1]" not in preview_source
    assert 'stringValue = "█"' in preview_source
    assert 'forKey: "brand-cursor-blink"' in preview_source
    assert "accessibilityDisplayShouldReduceMotion" in preview_source
    assert "scroll.contentView.scroll(to: .zero)" in preview_source
    assert "static let contentWidth = BuddyMonBrand.Geometry.contentWidth" in preview_source
    assert "interactive: false" in preview_source
    assert "field.refusesFirstResponder = !interactive" in brand_source
    assert "STORIES::COMMON_CONTEXT" in preview_source
    assert "ONE BUDDY MOMENT / THREE SURFACES" in preview_source
    assert "EMOJI STATUSLINE" in preview_source
    assert "MACOS MENU BAR + DROPDOWN" in preview_source
    assert '"PIXEL FELLOW"' in preview_source
    assert '"OFFICIAL PNG"' in preview_source
    assert 'appendingPathComponent("buddymon/packs/gen5"' in preview_source
    assert "bitmap.representation(using: .png" in preview_source
    assert "magnificationFilter = .nearest" in preview_source
    for marker in [
        "WORK SESSION / LEVEL PROGRESS",
        "WILD SIGNAL / DECISION REQUIRED",
        "CATCH RESULT / COLLECTION FOLLOW-THROUGH",
        "01::ACTIVE_BUDDY",
        "02::LIVE_SIGNAL",
        "03::TAIL /journey.log",
        "hunt@buddymon:~$",
        "TYPE SYSTEM",
        "COMMAND CONTROLS",
        "FIELDS + SETTINGS",
        "NAVIGATION + COMMAND PALETTE",
        "COLLECTION ROWS + SPRITE FRAMES",
        "ENCOUNTER STATES",
        "SHOWCASE SLOTS",
        "STATUS + RARITY",
        "PROGRESS + LOADING",
        "DIALOGS + CONFIRMATION",
        "TOKEN SUMMARY + REPORT",
        "DOCTOR + DIAGNOSTIC OUTPUT",
        "BUDDY HEADER + TRAINER STATS",
        "BATTLE HUD + ACTION GRID",
        "BATTLE LOG ROWS",
        "SELECTED-BUDDY SUMMARY",
        "COLLECTION TOOLBAR + FILTERS",
        "POKEDEX CELLS + COMPLETION",
        "JOURNAL FILTERS + EVENT ROWS",
        "STARTER + SOURCE + ART + REPAIR",
        "TOKEN EDGE STATES",
        "KEYBOARD + ACCESSIBILITY",
    ]:
        assert marker in preview_source

    assert "single source of truth" in brand_docs
    assert "BrandStyle.swift" in brand_docs
    assert "StyleArchivePreview.swift" in brand_docs
    assert "scripts/capture-brand-styles.sh" in brand_docs
    assert "Native UI must always use `BuddyMonBrand`" in agent_rules
    assert "Read `docs/brand.md` before changing native UI" in agent_rules
    assert "BrandStyle.swift" in capture_script
    assert "BrandStylesPreview.swift" in capture_script
    assert "BrandStylesSnapshot.swift" in capture_script
    assert "BrandStyle.swift" in menu_capture_script
    for source_name in MENU_PANEL_SWIFT_NAMES:
        assert source_name in menu_capture_script
    assert "MenuPanelSnapshot.swift" in menu_capture_script


def test_brand_styles_full_page_snapshot_is_deterministic(
    brand_snapshot_harness,
    tmp_path,
):
    state_home = tmp_path / "state"
    state_home.mkdir()
    first = tmp_path / "brand-styles-first.png"
    second = tmp_path / "brand-styles-second.png"
    env = os.environ.copy()
    env["XDG_STATE_HOME"] = str(state_home)

    for output in [first, second]:
        result = subprocess.run(
            [str(brand_snapshot_harness), str(output)],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    first_png = first.read_bytes()
    assert first_png == second.read_bytes()
    assert first_png.startswith(b"\x89PNG\r\n\x1a\n")
    width, height = struct.unpack(">II", first_png[16:24])
    assert width >= 944
    assert height >= 8_000
    assert len(first_png) >= 500_000
