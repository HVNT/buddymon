import json
import os
import re
import struct
import subprocess
import sys

from PIL import Image

from tests.native_test_support import (
    ROOT,
    SWIFT_DIR,
    pytestmark as pytestmark,
    read_menu_panel_sources,
    swift_function_body,
)


def test_native_menu_bar_uses_a_short_pokemon_style_menu():
    app_source = (SWIFT_DIR / "AppDelegate.swift").read_text(encoding="utf-8")
    buddy_source = (SWIFT_DIR / "MenuBarBuddy.swift").read_text(encoding="utf-8")
    panel_source = read_menu_panel_sources()
    brand_source = (SWIFT_DIR / "BrandStyle.swift").read_text(encoding="utf-8")

    for value in [
        "BuddyMonMenuPanel",
        "BuddyMonCompactMenuView",
        "BuddyMonCompactTokensView",
        "BuddyMonCompactSettingsView",
        "BuddyMonCompactTrainerView",
        "BuddyMonFieldGuideCardBackgroundView",
        "BuddyMonTrainerBadgeView",
        "BuddyMonCompactEncounterView",
        "BuddyMonCompactEncounterResultView",
        'status["native_menu"]',
        'descriptor["image_base64"]',
        "levelPercent(active)",
        'message = "LAST CATCH"',
        '"BUDDYMON"',
        '"LVL. \\(active["level"] as? Int ?? 1)"',
        "BuddyMonMenuProgressView",
        "ARROWS MOVE  ·  RETURN SELECTS  ·  ESC CLOSE",
        "signalSprite(pokemon)",
        "signalSpriteSize",
        "BuddyMonBrand.Menu.makeStatusIndicator(appStatus)",
        "BuddyMonBrand.Menu.AppStatusState",
        'status["tokens"]',
        'menu["token_action"]',
        'menu["footer_items"]',
        "BuddyMonTokenHeaderButton",
        "headerTokenControl(",
        "BuddyMonBrand.Menu.makeDisplayLabel",
        '"↑↓ MOVE  ·  ↵ SELECT  ·  ESC"',
        'modifiers.contains("command")',
        'button.keyEquivalentModifierMask = modifiers.contains("command")',
        'replacingOccurrences(of: "Advanced: ", with: "")',
        "initialResponder",
        "buddymon-menu-sprite-bob",
    ]:
        assert value in panel_source
    assert "BuddyMonMenuStatusIndicatorView" in brand_source

    compact_home = panel_source.split("// MARK: - Compact Menu", 1)[1].split(
        "// MARK: - Token Detail", 1
    )[0]
    assert panel_source.count("BuddyMonFieldGuideCardBackgroundView()") == 8
    assert "func compactNavigationHeader(" in panel_source
    assert panel_source.count("compactNavigationHeader(") == 6
    assert "let card = BuddyMonFieldGuideCardBackgroundView()" in compact_home
    assert "card.addSubview(root)" in compact_home
    assert "static let cardWidth = BuddyMonBrand.Menu.trainerCardWidth" in compact_home
    assert "BuddyMonBrand.Menu.fieldGuideFrameInset" in compact_home
    assert "static let fieldGuideFrameInset: CGFloat = 8" in brand_source
    assert "static func applyFieldGuideCardSurface" in brand_source
    assert "static let buddySpriteSize: CGFloat = 54" in brand_source
    assert (
        "static let activeBuddyRowHeight: CGFloat = "
        "buddySpriteSize + (compactGap * 2)"
    ) in brand_source
    assert "static let rootContentInset = BuddyMonBrand.Menu.compactGap" in compact_home
    assert "static let buddyContentInset = BuddyMonBrand.Menu.compactGap" in compact_home
    assert "top: Layout.rootContentInset" in compact_home
    assert "root.alignment = .centerX" in compact_home
    assert "left: BuddyMonBrand.Menu.flushInset" in compact_home
    assert "right: BuddyMonBrand.Menu.flushInset" in compact_home
    assert "static let buddyRowWidth = cardWidth" in compact_home
    assert "static let subtleRule = rule.withAlphaComponent(0.28)" in brand_source
    assert "static func makeActiveBuddyRow() -> NSStackView" in brand_source
    assert "private final class BuddyMonMenuActiveRowView" in brand_source
    assert "static let statusIndicatorSize: CGFloat = 6" in brand_source
    assert "static func makeStatusIndicator(_ state: AppStatusState)" in brand_source
    assert "private final class BuddyMonMenuStatusIndicatorView" in brand_source
    assert 'case .active: return "BuddyMon active"' in brand_source
    assert 'case .idle: return "BuddyMon starting"' in brand_source

    header_layout = swift_function_body(panel_source, "private static func header")
    assert "status.isEmpty" in header_layout
    assert "appStatus = .unavailable" in header_layout
    assert "appStatus = .idle" in header_layout
    assert "appStatus = .active" in header_layout
    assert "brandMark(status)" not in header_layout
    assert "private static func brandMark" not in compact_home
    assert "buddymon-menu-cursor" not in compact_home
    assert "brandMarkSize" not in brand_source

    buddy_card_layout = swift_function_body(
        panel_source,
        "private static func buddyCard",
    )
    for edge in ["top", "left", "bottom", "right"]:
        assert f"{edge}: Layout.buddyContentInset" in buddy_card_layout
    assert "hero.spacing = Layout.buddyContentInset" in buddy_card_layout
    assert "BuddyMonBrand.Menu.makeActiveBuddyRow()" in buddy_card_layout
    assert "Layout.buddyRowWidth" in buddy_card_layout
    active_buddy_factory = swift_function_body(
        brand_source,
        "static func makeActiveBuddyRow() -> NSStackView",
    )
    assert "activeBuddyRowHeight" in active_buddy_factory
    assert "applySurface(to: card" not in buddy_card_layout
    assert "xpBarWidth" not in panel_source
    assert "xpRow.widthAnchor.constraint(equalToConstant: Layout.identityWidth)" in buddy_card_layout
    assert "let progressWidth = Layout.identityWidth" in buddy_card_layout
    assert "xpLabel.intrinsicContentSize.width" in buddy_card_layout
    assert "percentLabel.intrinsicContentSize.width" in buddy_card_layout
    assert "progress.widthAnchor.constraint(equalToConstant: progressWidth)" in buddy_card_layout
    assert "percentLabel.setContentHuggingPriority(.required" in buddy_card_layout
    assert "hero.addArrangedSubview(buddySprite(active))" in buddy_card_layout
    assert "spriteWell(active)" not in buddy_card_layout
    buddy_sprite = swift_function_body(
        panel_source,
        "private static func buddySprite",
    )
    assert "let sprite = NSImageView()" in buddy_sprite
    assert "backgroundColor" not in buddy_sprite
    assert "cornerRadius" not in buddy_sprite
    assert "BuddyMonBrand.Menu.tightGap" not in buddy_sprite
    assert "sprite.widthAnchor.constraint" in buddy_sprite
    assert "sprite.heightAnchor.constraint" in buddy_sprite
    assert "BuddyMonBrand.Menu.buddySpriteSize" in buddy_sprite

    assert '"U  OPEN"' not in panel_source
    assert '"U OPEN"' not in panel_source
    assert "root.addArrangedSubview(tokenSection" not in panel_source
    assert 'if status["pending"] as? [String: Any] == nil' in panel_source
    message_box = swift_function_body(
        panel_source,
        "private static func messageBox",
    )
    assert "IS WAITING" not in message_box
    assert "let lead = NSStackView()" not in message_box
    assert "box.spacing = BuddyMonBrand.Menu.tightGap" in message_box
    assert "left: BuddyMonBrand.Menu.flushInset" in message_box
    assert "color = BuddyMonBrand.Menu.ink" in message_box
    assert "BuddyMonBrand.Menu.pokemonColor(recent)" not in message_box
    chevron_index = message_box.index('"▶"')
    signal_index = message_box.index("let sprite = signalSprite(pokemon)")
    label_index = message_box.index("box.addArrangedSubview(messageLabel)")
    name_index = message_box.index("box.addArrangedSubview(nameLabel)")
    rarity_index = message_box.index("BuddyMonBrand.Menu.makeRarityLabel(rarity)")
    spacer_index = message_box.index("box.addArrangedSubview(flexibleSpacer())")
    assert chevron_index < signal_index < label_index < name_index < rarity_index < spacer_index
    assert "box.setCustomSpacing(BuddyMonBrand.Menu.labelGap, after: chevron)" in message_box
    assert "box.setCustomSpacing(BuddyMonBrand.Menu.tightGap, after: sprite)" in message_box
    assert "box.setCustomSpacing(BuddyMonBrand.Menu.compactGap, after: messageLabel)" in message_box
    buddy_card = swift_function_body(
        panel_source,
        "private static func buddyCard",
    )
    assert '"CAUGHT' not in buddy_card
    token_control = swift_function_body(
        panel_source,
        "private static func headerTokenControl",
    )
    assert "row.addArrangedSubview(flexibleSpacer())" in token_control
    assert "applySurface(to: row" not in token_control
    token_metric = swift_function_body(
        panel_source,
        "private static func tokenMetric",
    )
    assert "metric.orientation = .horizontal" in token_metric
    assert "font: BuddyMonBrand.Font.strong(9)" in token_metric

    for value in [
        "handleNativeMenuAction",
        'case "encounter"',
        'case "tokens"',
        'case "trainer"',
        'case "terminal_party"',
        'case "terminal_box"',
        'case "terminal_dex"',
        'case "terminal_activity"',
        'case "settings"',
        'case "refresh"',
        'case "quit"',
        "handleStatusItemClick",
        'var arguments = ["open-menu"]',
        'openTerminalExperience(screen: "party")',
        'openTerminalExperience(screen: "box")',
        'openTerminalExperience(screen: "dex")',
        'openTerminalExperience(screen: "journal")',
        "openSettings()",
    ]:
        assert value in app_source
    assert 'case "open_details"' not in app_source
    terminal_handoff = swift_function_body(
        app_source,
        "private func openTerminalExperience",
    )
    assert "menuPanelController.close()" not in terminal_handoff
    assert "menuPanelController.prepareForTerminalHandoff()" in terminal_handoff
    assert 'arguments.append("--window-frame=\\(windowFrame)")' in terminal_handoff
    assert "func prepareForTerminalHandoff()" in panel_source
    assert "removeOutsideClickMonitors()" in panel_source
    assert "BuddyMonBrand.Menu.terminalWindowWidth" in panel_source
    assert "BuddyMonBrand.Menu.terminalWindowHeight" in panel_source
    assert "static let terminalWindowWidth: CGFloat = 760" in brand_source
    assert "static let terminalWindowHeight: CGFloat = 520" in brand_source
    assert "statusItem.menu = menu" not in app_source
    assert "statusMenu?.popUp" not in app_source
    assert "BuddyMonMenuDashboard" not in app_source
    assert "NSEvent.addLocalMonitorForEvents" not in app_source

    for legacy_copy in ["COMMAND DECK", "COLLECTION  //  TERMINAL", "PRIORITY SIGNAL DETECTED"]:
        assert legacy_copy not in panel_source

    for token in [
        "BuddyMonBrand.Menu.canvas",
        "BuddyMonBrand.Menu.pokemonColor",
        "BuddyMonBrand.Menu.makeActionButton",
    ]:
        assert token in panel_source
    for token in [
        "static let pokemonBlue",
        "static let pikachu",
        "static let xpProgress",
        "static let dataProgress",
        "enum Menu",
        "static let spriteWell",
        "static let xpFill",
        "enum FireRedDisplay",
        "final class BuddyMonFireRedLabel",
        "static let tokenHeaderWidth",
        'case "fire":',
    ]:
        assert token in brand_source
    assert "MenuBarBuddyController" in app_source
    assert "menuBarBuddyController.showBooting()" in app_source
    assert "menuBarBuddyController.apply(status: status)" in app_source
    assert "menuBarBuddyController.showUnavailable()" in app_source
    assert "updateStatusButton" not in app_source
    for token in [
        "MenuBarBuddyPayload",
        "MenuBarBuddyPreviewEnvelope",
        "momentQueue",
        "seenSequenceIDSet",
        "isPreviewing",
        "func preview(",
        'button.title = frame.title.isEmpty ? "" : " \\(frame.title)"',
        "accessibilityDisplayShouldReduceMotion",
        "BuddyMonBrand.Geometry.menuBarIconHeight",
    ]:
        assert token in buddy_source
    assert buddy_source.count(") { [weak self] _ in") == 2
    assert buddy_source.count("Task { @MainActor [weak self] in") == 2
    for token in [
        "installMenuBarPreviewSignal()",
        "DispatchSource.makeSignalSource(signal: SIGWINCH",
        "consumeMenuBarPreview()",
        "menuBarBuddyController.preview(envelope)",
    ]:
        assert token in app_source
    assert "presentStarterSetup" in app_source
    assert '["backup"]' not in app_source
    status_click = swift_function_body(
        app_source,
        "@objc private func handleStatusItemClick",
    )
    assert "menuPanelController.close()" in status_click
    assert "presentRootPanel()" in status_click
    default_panel = swift_function_body(
        app_source,
        "private func presentRootPanel()",
    )
    assert "presentRoot(" in default_panel
    assert "openEncounter()" not in default_panel
    reopen = swift_function_body(
        app_source,
        "func applicationShouldHandleReopen",
    )
    assert "presentRootPanel()" in reopen
    assert "openBuddyMon" not in app_source
    assert "showHome" not in app_source


def test_native_panel_locks_its_anchor_for_each_open_session():
    panel_source = read_menu_panel_sources()

    assert "private struct OpenSessionAnchor" in panel_source
    assert "private var openSessionAnchor: OpenSessionAnchor?" in panel_source

    present = swift_function_body(panel_source, "private func presentIfNeeded()")
    assert "openSessionAnchor" in present
    assert "captureOpenSessionAnchor(relativeTo: anchorButton)" in present
    assert "openSessionAnchor = sessionAnchor" in present
    assert "positionPanel(relativeTo: sessionAnchor)" in present

    capture = swift_function_body(
        panel_source,
        "private func captureOpenSessionAnchor",
    )
    assert "window.convertToScreen(buttonInWindow)" in capture
    assert "visibleScreenFrame" in capture

    close = swift_function_body(panel_source, "func close()")
    assert "openSessionAnchor = nil" in close


def test_native_compact_views_render_without_entrance_motion():
    panel_source = read_menu_panel_sources()
    brand_source = (SWIFT_DIR / "BrandStyle.swift").read_text(encoding="utf-8")
    preview_source = (SWIFT_DIR / "BrandStylesPreview.swift").read_text(
        encoding="utf-8"
    )
    brand_docs = (ROOT / "docs" / "brand.md").read_text(encoding="utf-8")

    for token in [
        "struct SectionRevealStyle",
        "static let quickSectionReveal",
        'static let sectionRevealAnimationKey = "buddymon-brand-section-reveal"',
        "static func revealSections",
    ]:
        assert token not in brand_source
    assert "BuddyMonCompactScreenRevealStackView" not in brand_source
    assert "BuddyMonSectionRevealStackView" not in brand_source
    assert "revealsSectionsOnAppearance" not in panel_source
    assert "shouldRevealSections" not in panel_source
    assert "BuddyMonBrand.Menu.applyPanelShell(to: panel)" in panel_source
    panel_shell = swift_function_body(
        brand_source,
        "static func applyPanelShell",
    )
    assert "panel.animationBehavior = .none" in panel_shell
    assert "motionSection()" not in preview_source
    assert '"MOTION + ENTRANCE"' not in preview_source
    assert "fieldGuideActiveRowSample()" in preview_source
    assert "BuddyMonBrand.Menu.makeActiveBuddyRow()" in preview_source
    assert "fieldGuideStatusSample()" in preview_source
    assert "BuddyMonBrand.Menu.makeStatusIndicator(state)" in preview_source
    assert (
        "Compact screens and drill-ins render completely and immediately"
        in brand_docs
    )
    assert "entrance fades" in brand_docs
    assert "private static func animateSprite" in panel_source
    assert 'forKey: "buddymon-menu-sprite-bob"' in panel_source


def test_native_first_signal_onboarding_is_present():
    app_source = (SWIFT_DIR / "AppDelegate.swift").read_text(encoding="utf-8")
    setup_source = (SWIFT_DIR / "CompactSetupView.swift").read_text(
        encoding="utf-8"
    )
    panel_source = read_menu_panel_sources()
    brand_source = (SWIFT_DIR / "BrandStyle.swift").read_text(encoding="utf-8")
    harness_source = (SWIFT_DIR / "MenuPanelStateHarnessView.swift").read_text(
        encoding="utf-8"
    )

    assert '"FIRST SIGNAL"' in setup_source
    assert "A tiny local companion is looking for a trainer." in setup_source
    assert "BuddyMonBrand.Menu.makeStarterChoice" in setup_source
    assert "NSUserInterfaceItemIdentifier(starter.id)" in setup_source
    assert "static let width = BuddyMonBrand.Menu.panelWidth" in setup_source
    assert "height: BuddyMonBrand.Menu.starterPanelMinimumHeight" in setup_source
    assert "static let starterPanelMinimumHeight = panelMinimumHeight" in brand_source
    assert "760" not in setup_source
    assert "BuddyMonCompactStarterSetupView" in panel_source
    assert '"starter_setup"' in harness_source
    assert "chooseStarterFromWelcome" in app_source
    first_setup = swift_function_body(
        app_source,
        "private func presentStarterSetupIfNeeded()",
    )
    assert "guard hasConfirmedStatus" in first_setup
    assert 'latestStatus["recovery_required"]' in first_setup
    assert 'latestStatus["active"] as? [String: Any] == nil' in first_setup
    assert 'setup["needs_starter"] as? Bool == true' in first_setup


def test_native_token_action_uses_compact_drill_in_and_preserves_dashboard():
    app_source = (
        SWIFT_DIR / "AppDelegate.swift"
    ).read_text(encoding="utf-8")
    panel_source = read_menu_panel_sources()
    brand_source = (SWIFT_DIR / "BrandStyle.swift").read_text(encoding="utf-8")

    token_menu = swift_function_body(
        app_source,
        "@objc private func openTokenUsage()",
    )
    assert "loadTokenUsage()" in token_menu
    assert 'presentTokenUsage(["loading": true])' in token_menu
    assert "flowController.presentLoading" not in token_menu
    assert 'runner.appView(\n                "tokens"' in app_source
    assert "menuPanelController.presentTokenUsage(" in app_source
    assert "backAction: #selector(openRootPanel)" in app_source

    compact_tokens = panel_source.split("// MARK: - Token Detail", 1)[1].split(
        "// MARK: - Settings", 1
    )[0]
    assert "let card = BuddyMonFieldGuideCardBackgroundView()" in compact_tokens
    assert "static let cardWidth = BuddyMonBrand.Menu.trainerCardWidth" in compact_tokens
    assert "BuddyMonBrand.Menu.fieldGuideFrameInset" in compact_tokens
    assert '"TOKEN USAGE"' in compact_tokens
    assert 'view["loading"] as? Bool == true' in compact_tokens
    assert '"READING LOCAL TOKEN ACTIVITY…"' in compact_tokens
    assert "static let tokenPanelMinimumHeight = panelMinimumHeight" in brand_source
    assert "static let tokenDailyPulseHeight: CGFloat = 52" in brand_source
    assert "static let dataTrack = raised" in brand_source
    assert "static let dataFill = ink" in brand_source
    assert "private final class BuddyMonTokenDailyPulseView" in compact_tokens
    assert 'let ids = ["day", "week"]' in compact_tokens
    assert 'item["comparison_label"]' in compact_tokens
    assert 'item["comparison_compact"]' in compact_tokens
    assert 'item["change"]' in compact_tokens
    assert "contentWidth - BuddyMonBrand.Menu.actionGap" in compact_tokens
    assert 'let ids = ["today", "last_7_days", "trend"]' not in compact_tokens
    assert 'dashboard["daily"] as? [[String: Any]]' in compact_tokens
    assert 'dashboard["insights"] as? [[String: Any]]' in compact_tokens
    for label in ["AVG", "PEAK", "STREAK", "BY TOOL"]:
        assert label in compact_tokens
    assert "root.addArrangedSubview(Self.flexibleVerticalSpacer())" in compact_tokens
    assert "ARROWS MOVE" not in compact_tokens
    assert "RETURN SELECTS" not in compact_tokens
    assert "height: BuddyMonBrand.Menu.tokenPanelMinimumHeight" in compact_tokens
    assert "card.fittingSize.height" not in compact_tokens
    navigation_header = swift_function_body(
        panel_source,
        "func compactNavigationHeader",
    )
    assert "pixel: BuddyMonBrand.Menu.displayButtonPixel" in navigation_header
    assert 'values.joined(separator: " · ")' in compact_tokens
    assert "compactNavigationHeader(" in compact_tokens
    assert 'identifier: "tokens_back"' in compact_tokens
    assert '"B  BACK"' not in compact_tokens


def test_native_settings_show_all_preferences_and_apply_immediately():
    app_source = (SWIFT_DIR / "AppDelegate.swift").read_text(encoding="utf-8")
    panel_source = read_menu_panel_sources()
    brand_source = (SWIFT_DIR / "BrandStyle.swift").read_text(encoding="utf-8")
    preview_source = (SWIFT_DIR / "BrandStylesPreview.swift").read_text(
        encoding="utf-8"
    )
    harness_source = (SWIFT_DIR / "MenuPanelStateHarnessView.swift").read_text(
        encoding="utf-8"
    )
    menu_policy = (ROOT / "lib" / "menu_panel.py").read_text(encoding="utf-8")

    open_settings = swift_function_body(
        app_source,
        "@objc private func openSettings()",
    )
    assert 'presentSettings(["loading": true])' in open_settings
    assert "loadSettings()" in open_settings
    assert "loadNativeScreen" not in open_settings

    present = swift_function_body(app_source, "private func presentSettings(")
    assert "menuPanelController.presentSettings(" in present
    assert "#selector(openRootPanel)" in present
    assert "#selector(handleCompactSettingsAction(_:))" in present

    selection = swift_function_body(
        app_source,
        "@objc private func handleCompactSettingsAction",
    )
    assert 'let preferencePrefix = "settings_preference:"' in selection
    assert "maxSplits: 1" in selection
    assert "guard selection.count == 2" in selection
    assert "let value = String(selection[1])" in selection
    assert 'runner.appAction(\n                    "preference"' in selection
    assert "[key, value]" in selection
    assert 'response["view"] as? [String: Any]' in selection
    assert "presentSettings(view)" in selection
    assert "await refreshStatus()" in selection

    compact_settings = panel_source.split("// MARK: - Settings", 1)[1].split(
        "// MARK: - Encounter", 1
    )[0]
    for token in [
        "final class BuddyMonCompactSettingsView",
        'view["loading"] as? Bool == true',
        '"READING LOCAL SETTINGS…"',
        '"SETTINGS UNAVAILABLE"',
        '"NO LOCAL SETTINGS FOUND"',
        '"ARROWS MOVE  ·  RETURN SETS  ·  ESC CLOSE"',
        "for setting in rows",
        'setting["allowed_values"] as? [String]',
        'setting["allowed_display_values"] as? [String]',
        "BuddyMonBrand.Menu.SettingsOption(",
        "controls.append(contentsOf: row.optionButtons)",
        "BuddyMonBrand.Menu.makeSettingsRow(",
        "BuddyMonBrand.Menu.settingsPanelMinimumHeight",
    ]:
        assert token in compact_settings
    assert "card.fittingSize.height" not in compact_settings

    navigation = swift_function_body(panel_source, "func compactNavigationHeader")
    assert 'backAccessibilityLabel: String = "Back to BuddyMon"' in panel_source
    assert "back.setAccessibilityLabel(backAccessibilityLabel)" in navigation
    assert 'back.keyEquivalent = "b"' not in navigation
    assert '"Back to Settings"' not in compact_settings

    for token in [
        "static let settingsPanelMinimumHeight = panelMinimumHeight",
        "static let settingsRowHeight: CGFloat = 18",
        "static let settingsRowBackground = NSColor.clear",
        "static let settingsRowHover = raised.withAlphaComponent(0.55)",
        "static let settingsOptionFontSize: CGFloat = 7.5",
        "struct SettingsOption",
        "static func makeSettingsRow(",
        "static func applySettingsOption(",
        "final class BuddyMonMenuSettingsRowView",
        "private final class BuddyMonMenuSettingsOptionButton",
        '"settings_preference:\\(key):\\(option.value)"',
        'activeOption ? "› \\(optionLabel)" : optionLabel',
        "attributes[.underlineStyle] = NSUnderlineStyle.single.rawValue",
        "addCursorRect(bounds, cursor: .pointingHand)",
        "override func cursorUpdate(with event: NSEvent)",
    ]:
        assert token in brand_source
    option_button = brand_source.split(
        "private final class BuddyMonMenuSettingsOptionButton",
        1,
    )[1].split("final class BuddyMonFireRedLabel", 1)[0]
    assert "override func mouseDown" not in option_button
    assert 'fieldGuideControlSample("FIELD GUIDE / HOVER", hoveredRow)' in preview_source
    assert 'fieldGuideControlSample("FIELD GUIDE / FOCUS", focusedRow)' in preview_source
    assert "BuddyMonBrand.Menu.surface.cgColor" in preview_source
    assert "applySettingsOption(" in preview_source
    assert "settingsCard()" in harness_source
    assert "settingsCard(loading: true)" in harness_source
    assert "setupCard()" in harness_source
    assert "noticeCard(kind: .loading)" in harness_source
    assert "noticeCard(kind: .error)" in harness_source
    assert '"SETTINGS / ALL PREFERENCES"' in harness_source
    assert '"allowed_values": ["auto", "ghostty", "iterm", "terminal"]' in harness_source

    settings_definition = menu_policy.split('"id": "settings"', 1)[1].split("},", 1)[0]
    assert '"presentation": "utility"' in settings_definition
    assert "terminal_screen" not in settings_definition


def test_native_trainer_action_uses_read_only_compact_card():
    app_source = (SWIFT_DIR / "AppDelegate.swift").read_text(encoding="utf-8")
    panel_source = read_menu_panel_sources()
    brand_source = (SWIFT_DIR / "BrandStyle.swift").read_text(encoding="utf-8")
    brand_preview_source = (SWIFT_DIR / "BrandStylesPreview.swift").read_text(
        encoding="utf-8"
    )
    harness_source = (SWIFT_DIR / "MenuPanelStateHarnessView.swift").read_text(
        encoding="utf-8"
    )

    trainer_action = swift_function_body(
        app_source,
        "@objc private func openTrainerCard()",
    )
    assert "loadTrainerCard()" in trainer_action
    assert 'runner.appView(\n                "trainer"' in app_source
    assert "menuPanelController.presentTrainerCard(" in app_source
    assert "backAction: #selector(openRootPanel)" in app_source

    trainer_section = panel_source.split("// MARK: - Trainer Card", 1)[1].split(
        "// MARK: - Compact Menu", 1
    )[0]
    for token in [
        'view["facts"]',
        'view["trainer_stats"]',
        'view["badges"]',
        'view["star_count"]',
        'view["portrait_base64"]',
        '"TRAINER CARD"',
        "BuddyMonBrand.Menu.applyTrainerBadge",
        "BuddyMonBrand.Menu.makeTrainerStatusRail",
        "fullBleedTrainerStatusRail",
        "rail.widthAnchor.constraint(equalToConstant: Layout.cardWidth)",
        "rail.centerXAnchor.constraint(equalTo: container.centerXAnchor)",
        "BuddyMonBrand.Menu.trainerBadgeForeground",
        "BuddyMonBrand.Menu.trainerBadgeRingColor",
        "BuddyMonBrand.Menu.trainerBadgeSymbolOpticalLift",
        "BuddyMon trainer silhouette",
        "selectionLabel",
        "selectBadge(_:)",
        'view["selected_badge_id"]',
        "setSelected(true)",
        '"RANK \\(rankStars)"',
        "cursor: .pointingHand",
        "rail.distribution = .fillEqually",
        "medallion.centerXAnchor.constraint(equalTo: slot.centerXAnchor)",
        "medallion.centerYAnchor.constraint(equalTo: slot.centerYAnchor)",
        "accessibilityDisplayShouldReduceMotion",
        'forKey: "buddymon-trainer-badge-reveal"',
        'forKey: "buddymon-trainer-badge-glow"',
        'forKey: "buddymon-trainer-badge-hover"',
    ]:
        assert token in trainer_section
    assert "BuddyMonBrand.Menu.applyFieldGuideCardSurface" in panel_source
    assert 'view["level"]' not in trainer_section
    assert 'view["total_xp"]' not in trainer_section
    assert "BuddyMonTrainerBadgeView: NSButton" in trainer_section
    assert "BuddyMonTrainerBadgeView: NSTextField" not in trainer_section
    assert "setAccessibilityRole(.button)" in trainer_section
    assert "focusableControls = [back] + badgeRail.buttons" in trainer_section
    assert "badgeRail.distribution = .equalSpacing" not in trainer_section
    assert "compactNavigationHeader(" in trainer_section
    assert 'identifier: "trainer_back"' in trainer_section
    assert "trailing: idCapsule" in trainer_section

    assert "static let trainerCardWidth: CGFloat = 288" in brand_source
    assert "static let trainerCardHeight: CGFloat = 192" in brand_source
    assert "static let trainerBadgeSize: CGFloat = 28" in brand_source
    assert "static let trainerBadgeDenseSize: CGFloat = 25" in brand_source
    assert "static let trainerBadgeSymbolOpticalLift: CGFloat = 0" in brand_source
    assert "static let trainerPortraitWidth: CGFloat = 64" in brand_source
    assert "static let trainerPortraitHeight: CGFloat = 64" in brand_source
    assert "static let trainerStatusRailHeight: CGFloat = 26" in brand_source
    assert "static func applyFieldGuideCardSurface" in brand_source
    assert "static func applyTrainerBadge" in brand_source
    assert "static func makeTrainerStatusRail" in brand_source
    assert "BuddyMonMenuTrainerStatusRailView" in brand_source
    assert "BuddyMonBrand.Menu.makeTrainerStatusRail" in brand_preview_source
    trainer_status_preview = swift_function_body(
        brand_preview_source,
        "private func fieldGuideTrainerStatusRailSample()",
    )
    assert "BuddyMonBrand.Menu.trainerCardWidth" in trainer_status_preview
    assert "BuddyMonBrand.Menu.cardPadding" not in trainer_status_preview
    assert '"trainer_local_portrait_fixture"' in harness_source
    assert '"trainer_national_complete"' in harness_source
    assert '"portrait_base64"' in harness_source
    assert '"trainer_stats"' in harness_source
    assert '("shiny_legend", "Shiny Legend Badge"' in harness_source
    assert '"id": "shiny_national"' in harness_source


def test_native_encounter_action_stays_in_the_compact_dropdown():
    app_source = (SWIFT_DIR / "AppDelegate.swift").read_text(encoding="utf-8")
    panel_source = read_menu_panel_sources()

    open_encounter = swift_function_body(
        app_source,
        "@objc private func openEncounter()",
    )
    encounter = swift_function_body(
        app_source,
        "private func loadEncounter(message: String? = nil)",
    )
    action = swift_function_body(
        app_source,
        "@objc private func handleEncounterAction(_ sender: NSButton)",
    )

    assert "flowController.presentLoading" not in open_encounter
    assert "loadEncounter()" in open_encounter
    assert "menuPanelController.presentEncounter(" in encounter
    assert "flowController.presentEncounter(" not in encounter
    assert "menuPanelController.presentEncounterResult(" in action
    assert "menuPanelController.presentEncounter(" in action
    assert "flowController.presentEncounterResult(" not in action
    assert 'descriptor["compact_label"]' in panel_source
    assert 'descriptor["shortcut"]' in panel_source
    assert 'descriptor["emoji"]' not in swift_function_body(
        panel_source,
        "init(\n        view: [String: Any],",
    )

    compact_encounter = panel_source.split("// MARK: - Encounter\n", 1)[1].split(
        "// MARK: - Encounter Result", 1
    )[0]
    encounter_result = panel_source.split("// MARK: - Encounter Result", 1)[1]
    for section in [compact_encounter, encounter_result]:
        assert "let card = BuddyMonFieldGuideCardBackgroundView()" in section
        assert "static let cardWidth = BuddyMonBrand.Menu.trainerCardWidth" in section
        assert "BuddyMonBrand.Menu.fieldGuideFrameInset" in section
        assert "compactNavigationHeader(" in section
    assert "pixel: BuddyMonBrand.Menu.displayButtonPixel" in compact_encounter
    assert "pixel: BuddyMonBrand.Menu.displayButtonPixel" in encounter_result
    assert 'identifier: "encounter_back"' in compact_encounter
    assert 'identifier: "encounter_result_back"' in encounter_result
    assert '"H  HOME"' not in compact_encounter
    assert '"RETURN  HOME"' not in encounter_result
    assert '"B BACK' not in encounter_result

    encounter_identity = swift_function_body(
        panel_source,
        "private static func identityCard(",
    )
    assert "color: BuddyMonBrand.Menu.ink" in encounter_identity
    assert "BuddyMonBrand.Menu.makeRarityLabel(" in encounter_identity
    assert "BuddyMonBrand.Menu.pokemonColor(pokemon)" not in encounter_identity

    result_view = swift_function_body(
        panel_source,
        "init(result: [String: Any]",
    )
    assert "color: BuddyMonBrand.Menu.ink" in result_view
    assert "BuddyMonBrand.Menu.makeRarityLabel(" in result_view
    assert "BuddyMonBrand.Menu.pokemonColor(wild)" not in result_view


def test_native_destinations_follow_the_compact_and_terminal_policy():
    app_source = (SWIFT_DIR / "AppDelegate.swift").read_text(encoding="utf-8")
    panel_source = read_menu_panel_sources()

    menu_action = swift_function_body(
        app_source,
        "@objc private func handleNativeMenuAction",
    )
    for action_id, screen in [
        ("terminal_party", "party"),
        ("terminal_box", "box"),
        ("terminal_dex", "dex"),
        ("terminal_activity", "journal"),
    ]:
        assert f'case "{action_id}": openTerminalExperience(screen: "{screen}")' in (
            menu_action
        )
    assert 'case "trainer": openTrainerCard()' in menu_action
    assert 'case "tokens": openTokenUsage()' in menu_action
    assert 'case "settings": openSettings()' in menu_action

    open_settings = swift_function_body(
        app_source,
        "@objc private func openSettings()",
    )
    assert "presentSettings" in open_settings
    assert "loadSettings" in open_settings
    assert "menuPanelController.presentSettings(" in app_source
    assert "NSPopUpButton" not in app_source
    assert 'alert.messageText = "Choose Showcase Pokemon"' not in app_source
    assert 'var arguments = ["open-menu"]' in app_source
    assert "presentStarterSetup(" in panel_source
    assert "presentLoading(" in panel_source
    assert "presentMessage(" in panel_source
    assert "presentFlowContent" not in panel_source
    assert "MenuPanelFlowController" not in app_source
    for removed in [
        "openBuddyMon",
        "showHome",
        "showLibrary",
        "showShowcase",
        "openParty",
        "openBox",
        "openPokedex",
        "openJournal",
    ]:
        assert removed not in app_source


def test_native_keyboard_controls_support_wasd_arrows_and_selection():
    panel_source = read_menu_panel_sources()

    assert not (SWIFT_DIR / "MenuPanelFlowController.swift").exists()
    assert "NSEvent.addLocalMonitorForEvents(matching: .keyDown)" in panel_source
    assert "case 53:" in panel_source
    assert "panel.makeFirstResponder(content.initialResponder)" in panel_source
    assert 'status["active"] as? [String: Any] == nil' in panel_source
    for key_code in [123, 124, 125, 126]:
        assert f"case {key_code}:" in panel_source
    assert "case 36, 49, 76:" in panel_source
    for character in ["a", "d", "w", "s"]:
        assert f'case "{character}":' in panel_source
    assert "displayMode == .setup" in panel_source
    assert "BuddyMonBrand.Menu.starterChoiceColumns" in panel_source
    assert "moveCompactFocus(by: -1)" in panel_source
    assert "moveCompactFocus(by: 1)" in panel_source
    assert "activateCompactFocus()" in panel_source
    assert "focusableControls" in panel_source


def test_native_compact_menu_panel_snapshot_is_deterministic(
    menu_panel_snapshot_harness,
    tmp_path,
):
    preview_source = (SWIFT_DIR / "BrandStylesPreview.swift").read_text(
        encoding="utf-8"
    )
    sprite_match = re.search(r'"PIKACHU": "([^"]+)"', preview_source)
    assert sprite_match is not None
    status = {
        "active": {
            "name": "Charizard",
            "type": "Fire",
            "rarity": "starter",
            "level": 78,
            "shiny": False,
            "level_progress": {"percent": 58},
            "sprite_base64": sprite_match.group(1),
        },
        "trainer": {
            "caught_count": 768,
            "species_count": 328,
            "streak": 3,
        },
        "recent": [
            {
                "name": "Palpitoad",
                "type": "Water",
                "sprite_base64": sprite_match.group(1),
            }
        ],
        "tokens": {
            "today": {"label": "Today", "compact": "148K"},
            "yesterday": {"label": "Yesterday", "compact": "102K"},
        },
        "brand_mark_base64": sprite_match.group(1),
        "native_menu": {
            "layout": "compact",
            "token_action": {
                "id": "tokens",
                "label": "Open token detail",
                "shortcut": "u",
            },
            "items": [
                {
                    "id": "trainer",
                    "label": "Trainer",
                    "shortcut": "t",
                    "presentation": "utility",
                },
                {
                    "id": "terminal_party",
                    "label": "Party",
                    "shortcut": "p",
                    "terminal_screen": "party",
                    "presentation": "utility",
                },
                {
                    "id": "terminal_box",
                    "label": "Box",
                    "shortcut": "b",
                    "terminal_screen": "box",
                    "presentation": "utility",
                },
                {
                    "id": "terminal_dex",
                    "label": "Pokedex",
                    "shortcut": "d",
                    "terminal_screen": "dex",
                    "presentation": "utility",
                },
                {
                    "id": "terminal_activity",
                    "label": "Activity",
                    "shortcut": "a",
                    "terminal_screen": "journal",
                    "presentation": "utility",
                },
                {
                    "id": "settings",
                    "label": "Settings",
                    "shortcut": "s",
                    "presentation": "utility",
                },
            ],
            "footer_items": [
                {
                    "id": "refresh",
                    "label": "Refresh",
                    "shortcut": "r",
                    "modifiers": ["command"],
                },
                {
                    "id": "quit",
                    "label": "Quit",
                    "shortcut": "q",
                    "modifiers": ["command"],
                },
            ],
        },
    }
    first = tmp_path / "menu-panel-first.png"
    second = tmp_path / "menu-panel-second.png"

    for output in [first, second]:
        result = subprocess.run(
            [str(menu_panel_snapshot_harness), str(output)],
            cwd=ROOT,
            input=json.dumps(status),
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
    assert width == 304
    assert 210 <= height <= 300
    assert len(first_png) >= 10_000


def test_compact_menu_panel_state_harness_is_complete_and_deterministic(
    menu_panel_state_snapshot_harness,
    tmp_path,
):
    harness_source = (SWIFT_DIR / "MenuPanelStateHarnessView.swift").read_text(
        encoding="utf-8"
    )
    assert "rarityLegend()" in harness_source
    assert "BuddyMonBrand.Menu.makeRarityLabel(rarity)" in harness_source
    assert 'stateID: "encounter_result_caught"' in harness_source
    assert 'stateID: "encounter_result_ran"' in harness_source
    assert 'loading ? "tokens_loading" : "tokens"' in harness_source
    assert '"daily": [' in harness_source
    assert '"active_streak"' in harness_source
    assert "settingsCard()" in harness_source
    assert "settingsCard(loading: true)" in harness_source

    env = os.environ.copy()
    env["XDG_STATE_HOME"] = str(tmp_path / "state")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    payload = subprocess.run(
        [sys.executable, str(ROOT / "buddymon.py"), "app-menu-panel-harness"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert payload.returncode == 0, payload.stderr
    decoded = json.loads(payload.stdout)
    assert len(decoded["fixtures"]) == 8
    assert "recovery_required" in {
        fixture["id"] for fixture in decoded["fixtures"]
    }

    first = tmp_path / "menu-panel-states-first.png"
    second = tmp_path / "menu-panel-states-second.png"
    for output in (first, second):
        result = subprocess.run(
            [str(menu_panel_state_snapshot_harness), str(output)],
            cwd=ROOT,
            input=payload.stdout,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    first_png = first.read_bytes()
    with Image.open(first) as first_image, Image.open(second) as second_image:
        assert first_image.mode == second_image.mode
        assert first_image.size == second_image.size
        assert first_image.convert("RGBA").tobytes() == second_image.convert(
            "RGBA"
        ).tobytes()
    assert first_png.startswith(b"\x89PNG\r\n\x1a\n")
    width, height = struct.unpack(">II", first_png[16:24])
    assert width == 944
    assert 1_500 <= height <= 4_200
    assert len(first_png) >= 100_000
