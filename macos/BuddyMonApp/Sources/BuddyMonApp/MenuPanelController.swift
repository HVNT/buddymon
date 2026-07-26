import AppKit
import Foundation
import QuartzCore

// MARK: - Panel Shell

private final class BuddyMonMenuPanel: NSPanel {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { false }
}

@MainActor
final class MenuPanelController: NSObject {
    private struct OpenSessionAnchor {
        let statusItemFrame: NSRect
        let visibleScreenFrame: NSRect
    }

    enum DisplayMode: String {
        case menu
        case tokens
        case settings
        case trainer
        case encounter
        case encounterResult
        case setup
        case notice
    }

    private let panel: BuddyMonMenuPanel
    private weak var anchorButton: NSStatusBarButton?
    private var keyboardMonitor: Any?
    private var compactControls: [NSButton] = []
    private var globalMouseMonitor: Any?
    private var localMouseMonitor: Any?
    private var openSessionAnchor: OpenSessionAnchor?

    private(set) var displayMode: DisplayMode = .menu

    override init() {
        panel = BuddyMonMenuPanel(
            contentRect: NSRect(x: 0, y: 0, width: 372, height: 220),
            styleMask: [.borderless],
            backing: .buffered,
            defer: false
        )
        super.init()
        BuddyMonBrand.Menu.applyPanelShell(to: panel)
        panel.level = .popUpMenu
        panel.collectionBehavior = [
            .moveToActiveSpace,
            .fullScreenAuxiliary,
        ]
        panel.hidesOnDeactivate = false
        panel.isReleasedWhenClosed = false
    }

    var isVisible: Bool { panel.isVisible }

    func attach(to button: NSStatusBarButton?) {
        anchorButton = button
    }

    func close() {
        panel.orderOut(nil)
        openSessionAnchor = nil
        compactControls = []
        removeKeyboardMonitor()
        removeOutsideClickMonitors()
    }

    func prepareForTerminalHandoff() -> String? {
        guard panel.isVisible else { return nil }
        removeOutsideClickMonitors()
        let screen = panel.screen ?? anchorButton?.window?.screen ?? NSScreen.main
        guard let screen else { return nil }
        let visible = screen.visibleFrame
        let width = BuddyMonBrand.Menu.terminalWindowWidth
        let height = BuddyMonBrand.Menu.terminalWindowHeight
        let gap = BuddyMonBrand.Spacing.compact

        let leftX = panel.frame.minX - width - gap
        let rightX = panel.frame.maxX + gap
        let preferredX = leftX >= visible.minX + gap ? leftX : rightX
        let minX = visible.minX + gap
        let maxX = max(minX, visible.maxX - width - gap)
        let x = min(max(preferredX, minX), maxX)
        let preferredY = panel.frame.maxY - height
        let minY = visible.minY + gap
        let maxY = max(minY, visible.maxY - height - gap)
        let y = min(max(preferredY, minY), maxY)
        let desktopTop = NSScreen.screens.first?.frame.maxY ?? screen.frame.maxY
        let top = desktopTop - (y + height)

        return [x, top, width, height]
            .map { String(Int($0.rounded())) }
            .joined(separator: ",")
    }

    private func installKeyboardMonitor() {
        removeKeyboardMonitor()
        guard panel.isVisible else { return }
        keyboardMonitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) {
            [weak self] event in
            guard let self else { return event }
            switch event.keyCode {
            case 53:
                self.close()
                return nil
            case 123:
                self.moveCompactFocus(by: -1)
                return nil
            case 124:
                self.moveCompactFocus(by: 1)
                return nil
            case 126:
                self.moveCompactFocus(
                    by: self.displayMode == .setup
                        ? -BuddyMonBrand.Menu.starterChoiceColumns
                        : -1
                )
                return nil
            case 125:
                self.moveCompactFocus(
                    by: self.displayMode == .setup
                        ? BuddyMonBrand.Menu.starterChoiceColumns
                        : 1
                )
                return nil
            case 36, 49, 76:
                self.activateCompactFocus()
                return nil
            default:
                break
            }
            if self.displayMode == .setup {
                switch event.charactersIgnoringModifiers?.lowercased() {
                case "a":
                    self.moveCompactFocus(by: -1)
                    return nil
                case "d":
                    self.moveCompactFocus(by: 1)
                    return nil
                case "w":
                    self.moveCompactFocus(
                        by: -BuddyMonBrand.Menu.starterChoiceColumns
                    )
                    return nil
                case "s":
                    self.moveCompactFocus(
                        by: BuddyMonBrand.Menu.starterChoiceColumns
                    )
                    return nil
                default:
                    break
                }
            }
            return event
        }
    }

    func presentRoot(
        status: [String: Any],
        target: AnyObject,
        action: Selector
    ) {
        let content = BuddyMonCompactMenuView(
            status: status,
            target: target,
            action: action
        )
        compactControls = content.focusableControls
        displayMode = .menu
        install(content, preferredSize: content.preferredSize)
        panel.makeFirstResponder(content.initialResponder)
    }

    func presentStarterSetup(
        target: AnyObject,
        chooseAction: Selector
    ) {
        let content = BuddyMonCompactStarterSetupView(
            target: target,
            chooseAction: chooseAction
        )
        compactControls = content.focusableControls
        displayMode = .setup
        install(content, preferredSize: content.preferredSize)
        panel.makeFirstResponder(content.initialResponder)
    }

    func presentLoading(_ message: String) {
        presentNotice(message, kind: .loading)
    }

    func presentMessage(_ message: String) {
        presentNotice(message, kind: .error)
    }

    private func presentNotice(
        _ message: String,
        kind: BuddyMonCompactNoticeView.Kind
    ) {
        let content = BuddyMonCompactNoticeView(
            message: message,
            kind: kind
        )
        compactControls = content.focusableControls
        displayMode = .notice
        install(content, preferredSize: content.preferredSize)
    }

    func presentTokenUsage(
        view: [String: Any],
        target: AnyObject,
        backAction: Selector
    ) {
        let content = BuddyMonCompactTokensView(
            view: view,
            target: target,
            backAction: backAction
        )
        compactControls = content.focusableControls
        displayMode = .tokens
        install(content, preferredSize: content.preferredSize)
        panel.makeFirstResponder(content.initialResponder)
    }

    func presentSettings(
        view: [String: Any],
        target: AnyObject,
        backAction: Selector,
        selectionAction: Selector
    ) {
        let content = BuddyMonCompactSettingsView(
            view: view,
            target: target,
            backAction: backAction,
            selectionAction: selectionAction
        )
        compactControls = content.focusableControls
        displayMode = .settings
        install(content, preferredSize: content.preferredSize)
        panel.makeFirstResponder(content.initialResponder)
    }

    func presentTrainerCard(
        view: [String: Any],
        target: AnyObject,
        backAction: Selector
    ) {
        let content = BuddyMonCompactTrainerView(
            view: view,
            target: target,
            backAction: backAction
        )
        compactControls = content.focusableControls
        displayMode = .trainer
        install(content, preferredSize: content.preferredSize)
        panel.makeFirstResponder(content.initialResponder)
    }

    func presentEncounter(
        view: [String: Any],
        message: String? = nil,
        target: AnyObject,
        action: Selector,
        backAction: Selector
    ) {
        let content = BuddyMonCompactEncounterView(
            view: view,
            message: message,
            target: target,
            action: action,
            backAction: backAction
        )
        compactControls = content.focusableControls
        displayMode = .encounter
        install(content, preferredSize: content.preferredSize)
        panel.makeFirstResponder(content.initialResponder)
    }

    func presentEncounterResult(
        result: [String: Any],
        target: AnyObject,
        doneAction: Selector
    ) {
        let content = BuddyMonCompactEncounterResultView(
            result: result,
            target: target,
            doneAction: doneAction
        )
        compactControls = content.focusableControls
        displayMode = .encounterResult
        install(content, preferredSize: content.preferredSize)
        panel.makeFirstResponder(content.initialResponder)
    }

    private func moveCompactFocus(by offset: Int) {
        let enabled = compactControls.filter(\.isEnabled)
        guard !enabled.isEmpty else { return }
        let current = enabled.firstIndex { $0 === panel.firstResponder }
        let origin = current ?? (offset > 0 ? -1 : 0)
        let next = (origin + offset + enabled.count) % enabled.count
        panel.makeFirstResponder(enabled[next])
    }

    private func activateCompactFocus() {
        if let button = panel.firstResponder as? NSButton, button.isEnabled {
            button.performClick(nil)
        } else if let first = compactControls.first(where: \.isEnabled) {
            panel.makeFirstResponder(first)
            first.performClick(nil)
        }
    }

    private func install(_ content: NSView, preferredSize: NSSize) {
        let size = constrainedSize(preferredSize)
        content.frame = NSRect(origin: .zero, size: size)
        content.autoresizingMask = [.width, .height]
        panel.contentView = content
        panel.setContentSize(size)
        presentIfNeeded()
    }

    private func presentIfNeeded() {
        guard let anchorButton else { return }
        let sessionAnchor = openSessionAnchor
            ?? captureOpenSessionAnchor(relativeTo: anchorButton)
        guard let sessionAnchor else { return }
        openSessionAnchor = sessionAnchor
        NSApp.activate(ignoringOtherApps: true)
        positionPanel(relativeTo: sessionAnchor)
        panel.makeKeyAndOrderFront(nil)
        installOutsideClickMonitors()
        installKeyboardMonitor()
    }

    private func captureOpenSessionAnchor(
        relativeTo button: NSStatusBarButton
    ) -> OpenSessionAnchor? {
        guard let window = button.window else { return nil }
        let buttonInWindow = button.convert(button.bounds, to: nil)
        let statusItemFrame = window.convertToScreen(buttonInWindow)
        let screen = window.screen ?? NSScreen.main
        let visibleScreenFrame = screen?.visibleFrame
            ?? NSRect(x: 0, y: 0, width: 1280, height: 800)
        return OpenSessionAnchor(
            statusItemFrame: statusItemFrame,
            visibleScreenFrame: visibleScreenFrame
        )
    }

    private func positionPanel(relativeTo sessionAnchor: OpenSessionAnchor) {
        let anchor = sessionAnchor.statusItemFrame
        let visible = sessionAnchor.visibleScreenFrame
        let size = panel.frame.size
        let preferredX = anchor.midX - size.width / 2
        let x = min(
            max(preferredX, visible.minX + BuddyMonBrand.Spacing.compact),
            visible.maxX - size.width - BuddyMonBrand.Spacing.compact
        )
        var y = anchor.minY - size.height - BuddyMonBrand.Spacing.micro
        if y < visible.minY + BuddyMonBrand.Spacing.compact {
            y = anchor.maxY + BuddyMonBrand.Spacing.micro
        }
        panel.setFrameOrigin(NSPoint(x: x, y: y))
    }

    private func installOutsideClickMonitors() {
        removeOutsideClickMonitors()
        globalMouseMonitor = NSEvent.addGlobalMonitorForEvents(
            matching: [.leftMouseDown, .rightMouseDown]
        ) { [weak self] _ in
            Task { @MainActor in
                self?.close()
            }
        }
        localMouseMonitor = NSEvent.addLocalMonitorForEvents(
            matching: [.leftMouseDown, .rightMouseDown]
        ) { [weak self] event in
            guard let self else { return event }
            if event.window !== self.panel, event.window !== self.anchorButton?.window {
                self.close()
            }
            return event
        }
    }

    private func removeOutsideClickMonitors() {
        if let globalMouseMonitor {
            NSEvent.removeMonitor(globalMouseMonitor)
            self.globalMouseMonitor = nil
        }
        if let localMouseMonitor {
            NSEvent.removeMonitor(localMouseMonitor)
            self.localMouseMonitor = nil
        }
    }

    private func removeKeyboardMonitor() {
        guard let keyboardMonitor else { return }
        NSEvent.removeMonitor(keyboardMonitor)
        self.keyboardMonitor = nil
    }

    private func constrainedSize(_ preferred: NSSize) -> NSSize {
        let screen = anchorButton?.window?.screen ?? NSScreen.main
        let visible = openSessionAnchor?.visibleScreenFrame.size
            ?? screen?.visibleFrame.size
            ?? NSSize(width: 1280, height: 800)
        let minimumWidth = BuddyMonBrand.Menu.panelWidth
        let maximumWidth = max(minimumWidth, min(960, visible.width - 48))
        let maximumHeight = max(320, min(720, visible.height - 72))
        return NSSize(
            width: min(max(preferred.width, minimumWidth), maximumWidth),
            height: min(
                max(preferred.height, BuddyMonBrand.Menu.popoverMinimumHeight),
                maximumHeight
            )
        )
    }
}
