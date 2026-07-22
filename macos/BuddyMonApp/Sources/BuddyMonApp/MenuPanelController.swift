import AppKit
import Foundation
import QuartzCore

// MARK: - Panel Shell

private final class BuddyMonMenuPanel: NSPanel {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { false }
}

private final class BuddyMonTokenHeaderButton: NSButton {
    override var acceptsFirstResponder: Bool { isEnabled }

    override func resetCursorRects() {
        super.resetCursorRects()
        if isEnabled {
            addCursorRect(bounds, cursor: .pointingHand)
        }
    }
}

private final class BuddyMonMenuFooterButton: NSButton {
    override func resetCursorRects() {
        super.resetCursorRects()
        if isEnabled {
            addCursorRect(bounds, cursor: .pointingHand)
        }
    }
}

private func compactNavigationHeader(
    title: String,
    identifier: String,
    target: AnyObject,
    action: Selector,
    contentWidth: CGFloat,
    backAccessibilityLabel: String = "Back to BuddyMon",
    trailing: NSView? = nil
) -> (view: NSView, back: NSButton) {
    let row = NSStackView()
    row.orientation = .horizontal
    row.alignment = .centerY
    row.spacing = BuddyMonBrand.Menu.headerGap
    let back = BuddyMonMenuFooterButton(
        title: "‹",
        target: target,
        action: action
    )
    back.identifier = NSUserInterfaceItemIdentifier(identifier)
    back.isBordered = false
    back.focusRingType = .none
    back.font = BuddyMonBrand.Font.strong(15)
    back.contentTintColor = BuddyMonBrand.Menu.ink
    back.setAccessibilityLabel(backAccessibilityLabel)
    row.addArrangedSubview(back)
    row.addArrangedSubview(BuddyMonBrand.Menu.makeDisplayLabel(
        title,
        color: BuddyMonBrand.Menu.ink,
        pixel: BuddyMonBrand.Menu.displayButtonPixel
    ))
    let spacer = NSView()
    spacer.setContentHuggingPriority(.defaultLow, for: .horizontal)
    spacer.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
    row.addArrangedSubview(spacer)
    if let trailing {
        row.addArrangedSubview(trailing)
    }
    row.widthAnchor.constraint(equalToConstant: contentWidth).isActive = true
    return (row, back)
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
        case expanded
    }

    private let panel: BuddyMonMenuPanel
    private weak var anchorButton: NSStatusBarButton?
    private var keyboardHandler: ((NSEvent) -> Bool)?
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

    func setKeyboardHandler(_ handler: ((NSEvent) -> Bool)?) {
        keyboardHandler = handler
        installKeyboardMonitor()
    }

    private func installKeyboardMonitor() {
        removeKeyboardMonitor()
        guard panel.isVisible else { return }
        keyboardMonitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) {
            [weak self] event in
            guard let self else { return event }
            if let keyboardHandler = self.keyboardHandler, keyboardHandler(event) {
                return nil
            }
            if self.displayMode != .expanded {
                switch event.keyCode {
                case 53:
                    self.close()
                    return nil
                case 123, 126:
                    self.moveCompactFocus(by: -1)
                    return nil
                case 124, 125:
                    self.moveCompactFocus(by: 1)
                    return nil
                case 36, 49, 76:
                    self.activateCompactFocus()
                    return nil
                default:
                    break
                }
            }
            return event
        }
    }

    func showCompact(
        status: [String: Any],
        target: AnyObject,
        action: Selector
    ) {
        setKeyboardHandler(nil)
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

    func showExpanded(content: NSView, preferredSize: NSSize) {
        compactControls = []
        displayMode = .expanded
        install(content, preferredSize: preferredSize)
    }

    func showCompactTokens(
        view: [String: Any],
        target: AnyObject,
        backAction: Selector
    ) {
        setKeyboardHandler(nil)
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

    func showCompactSettings(
        view: [String: Any],
        target: AnyObject,
        backAction: Selector,
        selectionAction: Selector
    ) {
        setKeyboardHandler(nil)
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

    func showCompactTrainer(
        view: [String: Any],
        target: AnyObject,
        backAction: Selector
    ) {
        setKeyboardHandler(nil)
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

    func showCompactEncounter(
        view: [String: Any],
        message: String? = nil,
        target: AnyObject,
        action: Selector,
        backAction: Selector
    ) {
        setKeyboardHandler(nil)
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

    func showCompactEncounterResult(
        result: [String: Any],
        target: AnyObject,
        doneAction: Selector
    ) {
        setKeyboardHandler(nil)
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

// MARK: - Trainer Card

private final class BuddyMonFieldGuideCardBackgroundView: NSView {
    override var isFlipped: Bool { true }

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        BuddyMonBrand.Menu.applyFieldGuideCardSurface(to: self)
    }

    required init?(coder: NSCoder) {
        nil
    }

    override func draw(_ dirtyRect: NSRect) {
        BuddyMonBrand.Menu.surface.setFill()
        bounds.fill()
        BuddyMonBrand.Menu.raised.withAlphaComponent(0.34).setFill()
        let step = BuddyMonBrand.Menu.trainerStripeHeight * 2
        for y in stride(from: CGFloat(0), to: bounds.height, by: step) {
            NSBezierPath(rect: NSRect(
                x: 0,
                y: y,
                width: bounds.width,
                height: BuddyMonBrand.Menu.trainerStripeHeight
            )).fill()
        }
    }
}

private final class BuddyMonTrainerPortraitView: NSView {
    override var isFlipped: Bool { true }

    private static let officialImage: NSImage? = {
        let bundled = Bundle.main.url(
            forResource: "TrainerRedFRLG",
            withExtension: "png"
        )
        let sourceResource = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .appendingPathComponent("Resources/TrainerRedFRLG.png")
        for url in [bundled, sourceResource].compactMap({ $0 }) {
            if let image = NSImage(contentsOf: url) {
                image.isTemplate = false
                return image
            }
        }
        return nil
    }()

    private static let grid = [
        "....KKKK....",
        "...KKKKKK...",
        "..KKMMMMK...",
        "..KMMMMMMK..",
        "...KMMMK....",
        "....KKK.....",
        "...KKMKK....",
        "..KKMMMKK...",
        ".KKMMMMMKK..",
        "..KMMMMMK...",
        "..KMMKMMK...",
        "..KMMMMMK...",
        "...KMMMK....",
        "...KK.KK....",
        "..KK...KK...",
        "..K.....K...",
        ".KK.....KK..",
        ".K.......K..",
        "KK.......KK.",
        "K.........K.",
    ]

    override var intrinsicContentSize: NSSize {
        NSSize(
            width: BuddyMonBrand.Menu.trainerPortraitWidth,
            height: BuddyMonBrand.Menu.trainerPortraitHeight
        )
    }

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        setAccessibilityElement(true)
        setAccessibilityRole(.image)
        setAccessibilityLabel("Red trainer sprite from Pokemon FireRed and LeafGreen")
    }

    required init?(coder: NSCoder) {
        nil
    }

    override func draw(_ dirtyRect: NSRect) {
        if let image = Self.officialImage {
            NSGraphicsContext.current?.imageInterpolation = .none
            image.draw(
                in: bounds,
                from: .zero,
                operation: .sourceOver,
                fraction: 1,
                respectFlipped: true,
                hints: nil
            )
            return
        }

        let pixel = BuddyMonBrand.Menu.trainerPortraitPixel
        let fallbackWidth = CGFloat(Self.grid.first?.count ?? 0) * pixel
        let fallbackHeight = CGFloat(Self.grid.count) * pixel
        let offsetX = (bounds.width - fallbackWidth) / 2
        let offsetY = (bounds.height - fallbackHeight) / 2
        for (rowIndex, row) in Self.grid.enumerated() {
            for (columnIndex, value) in row.enumerated() where value != "." {
                let color = value == "M"
                    ? BuddyMonBrand.Menu.mutedInk
                    : BuddyMonBrand.Menu.ink
                color.setFill()
                NSBezierPath(rect: NSRect(
                    x: offsetX + (CGFloat(columnIndex) * pixel),
                    y: offsetY + (CGFloat(rowIndex) * pixel),
                    width: pixel,
                    height: pixel
                )).fill()
            }
        }
    }
}

private final class BuddyMonTrainerBadgeView: NSButton {
    let badgeID: String
    private let earned: Bool
    private let rare: Bool
    private let animationIndex: Int
    private let badgeName: String
    private let requirement: String
    private let innerRing = CAShapeLayer()
    private var tracking: NSTrackingArea?
    private var hasAnimatedReveal = false
    private var isBadgeSelected = false

    init(
        badge: [String: Any],
        size: CGFloat,
        symbolSize: CGFloat,
        animationIndex: Int
    ) {
        let symbol = badge["symbol"] as? String ?? "·"
        badgeName = badge["label"] as? String ?? "Trainer Badge"
        requirement = badge["description"] as? String ?? "Keep exploring BuddyMon."
        earned = badge["earned"] as? Bool == true
        let identifier = badge["id"] as? String ?? "badge"
        badgeID = identifier
        rare = identifier.hasPrefix("shiny")
        self.animationIndex = animationIndex
        super.init(frame: .zero)
        title = ""
        isBordered = false
        focusRingType = .none

        let symbolLabel = NSTextField(labelWithString: symbol)
        symbolLabel.alignment = .center
        symbolLabel.font = BuddyMonBrand.Font.mono(symbolSize, weight: .bold)
        symbolLabel.textColor = BuddyMonBrand.Menu.trainerBadgeForeground(
            earned: earned,
            rare: rare
        )
        symbolLabel.setAccessibilityElement(false)
        symbolLabel.translatesAutoresizingMaskIntoConstraints = false

        innerRing.fillColor = NSColor.clear.cgColor
        innerRing.strokeColor = BuddyMonBrand.Menu.trainerBadgeRingColor(
            earned: earned,
            rare: rare
        ).cgColor
        innerRing.lineWidth = BuddyMonBrand.Geometry.borderWidth

        wantsLayer = true
        layer?.addSublayer(innerRing)
        addSubview(symbolLabel)
        NSLayoutConstraint.activate([
            symbolLabel.centerXAnchor.constraint(equalTo: centerXAnchor),
            symbolLabel.centerYAnchor.constraint(
                equalTo: centerYAnchor,
                constant: BuddyMonBrand.Menu.trainerBadgeSymbolOpticalLift
            ),
        ])

        toolTip = [
            badge["label"] as? String,
            badge["description"] as? String,
        ].compactMap { $0 }.joined(separator: " — ")
        setAccessibilityElement(true)
        setAccessibilityRole(.button)
        setAccessibilityLabel(badgeName)
        setAccessibilityValue(earned ? "Earned" : "Locked")
        BuddyMonBrand.Menu.applyTrainerBadge(
            to: self,
            size: size,
            earned: earned,
            rare: rare
        )
        widthAnchor.constraint(
            equalToConstant: size
        ).isActive = true
        heightAnchor.constraint(
            equalToConstant: size
        ).isActive = true
    }

    required init?(coder: NSCoder) {
        nil
    }

    override var acceptsFirstResponder: Bool { true }

    var selectionSummary: String {
        earned
            ? "\(badgeName.uppercased())  ·  EARNED"
            : requirement.uppercased()
    }

    override func resetCursorRects() {
        super.resetCursorRects()
        addCursorRect(bounds, cursor: .pointingHand)
    }

    override func becomeFirstResponder() -> Bool {
        let accepted = super.becomeFirstResponder()
        if accepted {
            refreshFocusRing(focused: true)
        }
        return accepted
    }

    override func resignFirstResponder() -> Bool {
        let resigned = super.resignFirstResponder()
        if resigned {
            refreshFocusRing(focused: isBadgeSelected)
        }
        return resigned
    }

    func setSelected(_ selected: Bool) {
        isBadgeSelected = selected
        refreshFocusRing(
            focused: selected || window?.firstResponder === self
        )
    }

    override func layout() {
        super.layout()
        innerRing.frame = bounds
        innerRing.path = CGPath(
            ellipseIn: bounds.insetBy(
                dx: BuddyMonBrand.Menu.trainerBadgeInnerInset,
                dy: BuddyMonBrand.Menu.trainerBadgeInnerInset
            ),
            transform: nil
        )
    }

    override func viewDidMoveToWindow() {
        super.viewDidMoveToWindow()
        guard window != nil else {
            layer?.removeAllAnimations()
            return
        }
        animateRevealIfNeeded()
        animateRareGlowIfNeeded()
    }

    override func updateTrackingAreas() {
        super.updateTrackingAreas()
        if let tracking {
            removeTrackingArea(tracking)
        }
        let next = NSTrackingArea(
            rect: .zero,
            options: [.mouseEnteredAndExited, .activeInKeyWindow, .inVisibleRect],
            owner: self,
            userInfo: nil
        )
        addTrackingArea(next)
        tracking = next
    }

    override func mouseEntered(with event: NSEvent) {
        animateHover(isHovered: true)
    }

    override func mouseExited(with event: NSEvent) {
        animateHover(isHovered: false)
    }

    private func refreshFocusRing(focused: Bool) {
        innerRing.lineWidth = focused
            ? BuddyMonBrand.Geometry.focusBorderWidth
            : BuddyMonBrand.Geometry.borderWidth
        innerRing.strokeColor = (
            focused
                ? BuddyMonBrand.Menu.ink
                : BuddyMonBrand.Menu.trainerBadgeRingColor(
                    earned: earned,
                    rare: rare
                )
        ).cgColor
    }

    private var reduceMotion: Bool {
        NSWorkspace.shared.accessibilityDisplayShouldReduceMotion
    }

    private func animateRevealIfNeeded() {
        guard !reduceMotion, !hasAnimatedReveal else { return }
        hasAnimatedReveal = true
        let beginTime = CACurrentMediaTime()
            + (Double(animationIndex) * BuddyMonBrand.Menu.trainerBadgeRevealStagger)

        let stamp = CAKeyframeAnimation(keyPath: "transform.scale")
        stamp.values = [
            BuddyMonBrand.Menu.trainerBadgeRevealScale,
            BuddyMonBrand.Menu.trainerBadgeRevealOvershoot,
            1,
        ]
        stamp.keyTimes = [0, 0.72, 1]
        stamp.duration = BuddyMonBrand.Menu.trainerBadgeRevealDuration
        stamp.beginTime = beginTime
        stamp.fillMode = .backwards
        stamp.timingFunctions = [
            CAMediaTimingFunction(name: .easeOut),
            CAMediaTimingFunction(name: .easeInEaseOut),
        ]
        layer?.add(stamp, forKey: "buddymon-trainer-badge-reveal")

        let fade = CABasicAnimation(keyPath: "opacity")
        fade.fromValue = earned ? 0.42 : 0.68
        fade.toValue = 1
        fade.duration = BuddyMonBrand.Menu.trainerBadgeRevealDuration
        fade.beginTime = beginTime
        fade.fillMode = .backwards
        fade.timingFunction = CAMediaTimingFunction(name: .easeOut)
        layer?.add(fade, forKey: "buddymon-trainer-badge-fade")
    }

    private func animateRareGlowIfNeeded() {
        guard !reduceMotion, earned, rare else { return }
        let glow = CABasicAnimation(keyPath: "shadowOpacity")
        glow.fromValue = BuddyMonBrand.Menu.trainerBadgeRareShadowOpacity
        glow.toValue = BuddyMonBrand.Menu.trainerBadgeGlowOpacity
        glow.duration = BuddyMonBrand.Menu.trainerBadgeGlowDuration
        glow.beginTime = CACurrentMediaTime()
            + BuddyMonBrand.Menu.trainerBadgeRevealDuration
            + (Double(animationIndex) * BuddyMonBrand.Menu.trainerBadgeRevealStagger)
        glow.autoreverses = true
        glow.repeatCount = .infinity
        glow.timingFunction = CAMediaTimingFunction(name: .easeInEaseOut)
        layer?.add(glow, forKey: "buddymon-trainer-badge-glow")
    }

    private func animateHover(isHovered: Bool) {
        guard !reduceMotion, let layer else { return }
        let targetScale = isHovered
            ? BuddyMonBrand.Menu.trainerBadgeHoverScale
            : 1
        let currentScale = layer.presentation()?.transform.m11 ?? layer.transform.m11
        let hover = CABasicAnimation(keyPath: "transform.scale")
        hover.fromValue = currentScale
        hover.toValue = targetScale
        hover.duration = BuddyMonBrand.Menu.trainerBadgeHoverDuration
        hover.timingFunction = CAMediaTimingFunction(name: .easeOut)
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        layer.transform = CATransform3DMakeScale(targetScale, targetScale, 1)
        CATransaction.commit()
        layer.add(hover, forKey: "buddymon-trainer-badge-hover")
    }
}

final class BuddyMonCompactTrainerView: NSView {
    private enum Layout {
        static let width = BuddyMonBrand.Menu.panelWidth
        static let cardWidth = BuddyMonBrand.Menu.trainerCardWidth
        static let cardHeight = BuddyMonBrand.Menu.trainerCardHeight
        static let cardContentWidth = cardWidth - (BuddyMonBrand.Menu.cardPadding * 2)
    }

    private(set) var preferredSize = NSSize(
        width: Layout.width,
        height: BuddyMonBrand.Menu.trainerPanelMinimumHeight
    )
    private(set) weak var initialResponder: NSView?
    private(set) var focusableControls: [NSButton] = []
    private var badgeDetailLabel: NSTextField?
    private weak var selectedBadge: BuddyMonTrainerBadgeView?

    init(
        view: [String: Any],
        target: AnyObject,
        backAction: Selector
    ) {
        let card = BuddyMonFieldGuideCardBackgroundView()
        let content = NSStackView()
        content.orientation = .vertical
        content.alignment = .leading
        content.spacing = BuddyMonBrand.Menu.sectionGap
        content.edgeInsets = NSEdgeInsets(
            top: BuddyMonBrand.Menu.cardPadding,
            left: BuddyMonBrand.Menu.cardPadding,
            bottom: BuddyMonBrand.Menu.cardPadding,
            right: BuddyMonBrand.Menu.cardPadding
        )

        let idLabel = Self.text(
            "IDNo.\(view["id_no"] as? String ?? "00000")",
            color: BuddyMonBrand.Menu.mutedInk,
            font: BuddyMonBrand.Font.mono(9, weight: .medium)
        )
        let idCapsule = NSStackView(views: [idLabel])
        idCapsule.edgeInsets = NSEdgeInsets(
            top: BuddyMonBrand.Menu.microGap,
            left: BuddyMonBrand.Menu.compactGap,
            bottom: BuddyMonBrand.Menu.microGap,
            right: BuddyMonBrand.Menu.compactGap
        )
        BuddyMonBrand.Menu.applySurface(to: idCapsule, raised: true, bordered: false)
        let navigation = compactNavigationHeader(
            title: "TRAINER CARD",
            identifier: "trainer_back",
            target: target,
            action: backAction,
            contentWidth: Layout.cardContentWidth,
            trailing: idCapsule
        )
        let back = navigation.back
        content.addArrangedSubview(navigation.view)

        let body = NSStackView()
        body.orientation = .horizontal
        body.alignment = .centerY
        body.spacing = BuddyMonBrand.Menu.compactGap
        let starCount = min(4, max(0, view["star_count"] as? Int ?? 0))
        body.addArrangedSubview(Self.factGrid(
            view["facts"] as? [[String: Any]] ?? [],
            starCount: starCount
        ))
        body.addArrangedSubview(Self.flexibleSpacer())

        if
            let encoded = view["portrait_base64"] as? String,
            let data = Data(base64Encoded: encoded),
            let image = NSImage(data: data)
        {
            let portrait = NSImageView()
            portrait.image = image
            portrait.imageScaling = .scaleProportionallyUpOrDown
            portrait.wantsLayer = true
            portrait.layer?.magnificationFilter = .nearest
            portrait.layer?.minificationFilter = .nearest
            portrait.widthAnchor.constraint(
                equalToConstant: BuddyMonBrand.Menu.trainerPortraitWidth
            ).isActive = true
            portrait.heightAnchor.constraint(
                equalToConstant: BuddyMonBrand.Menu.trainerPortraitHeight
            ).isActive = true
            body.addArrangedSubview(portrait)
        } else {
            body.addArrangedSubview(BuddyMonTrainerPortraitView())
        }
        body.widthAnchor.constraint(equalToConstant: Layout.cardContentWidth).isActive = true
        content.addArrangedSubview(body)

        let trainerStats = view["trainer_stats"] as? [[String: Any]] ?? []
        if trainerStats.isEmpty {
            content.addArrangedSubview(Self.flexibleVerticalSpacer())
        } else {
            content.addArrangedSubview(Self.fullBleedTrainerStatusRail(
                trainerStats
            ))
        }

        let badgeGroup = NSStackView()
        badgeGroup.orientation = .vertical
        badgeGroup.alignment = .leading
        badgeGroup.spacing = BuddyMonBrand.Menu.microGap
        let badgeHeader = NSStackView()
        badgeHeader.orientation = .horizontal
        badgeHeader.alignment = .centerY
        badgeHeader.spacing = BuddyMonBrand.Menu.tightGap
        badgeHeader.addArrangedSubview(Self.text(
            "BADGES",
            color: BuddyMonBrand.Menu.mutedInk,
            font: BuddyMonBrand.Font.mono(7, weight: .bold)
        ))
        badgeHeader.addArrangedSubview(Self.flexibleSpacer())
        let badgeDetail = Self.text(
            "SELECT A BADGE",
            color: BuddyMonBrand.Menu.mutedInk,
            font: BuddyMonBrand.Font.mono(7, weight: .medium)
        )
        badgeDetail.alignment = .right
        badgeHeader.addArrangedSubview(badgeDetail)
        badgeHeader.widthAnchor.constraint(
            equalToConstant: Layout.cardContentWidth
        ).isActive = true
        badgeGroup.addArrangedSubview(badgeHeader)
        let badgeRail = Self.badgeRail(
            view["badges"] as? [[String: Any]] ?? []
        )
        badgeGroup.addArrangedSubview(badgeRail.view)
        content.addArrangedSubview(badgeGroup)

        card.addSubview(content)
        content.translatesAutoresizingMaskIntoConstraints = false

        super.init(frame: .zero)
        badgeDetailLabel = badgeDetail
        for badge in badgeRail.buttons {
            badge.target = self
            badge.action = #selector(selectBadge(_:))
        }
        if
            let selectedID = view["selected_badge_id"] as? String,
            let selected = badgeRail.buttons.first(where: { $0.badgeID == selectedID })
        {
            badgeDetail.stringValue = selected.selectionSummary
            badgeDetail.textColor = BuddyMonBrand.Menu.ink
            selected.setSelected(true)
            selectedBadge = selected
        }
        focusableControls = [back] + badgeRail.buttons
        initialResponder = back
        wantsLayer = true
        layer?.backgroundColor = BuddyMonBrand.Menu.canvas.cgColor
        addSubview(card)
        card.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            widthAnchor.constraint(equalToConstant: Layout.width),
            card.widthAnchor.constraint(equalToConstant: Layout.cardWidth),
            card.heightAnchor.constraint(equalToConstant: Layout.cardHeight),
            card.centerXAnchor.constraint(equalTo: centerXAnchor),
            card.topAnchor.constraint(
                equalTo: topAnchor,
                constant: BuddyMonBrand.Menu.fieldGuideFrameInset
            ),
            card.bottomAnchor.constraint(
                equalTo: bottomAnchor,
                constant: -BuddyMonBrand.Menu.fieldGuideFrameInset
            ),
            content.leadingAnchor.constraint(equalTo: card.leadingAnchor),
            content.trailingAnchor.constraint(equalTo: card.trailingAnchor),
            content.topAnchor.constraint(equalTo: card.topAnchor),
            content.bottomAnchor.constraint(equalTo: card.bottomAnchor),
        ])
    }

    required init?(coder: NSCoder) {
        nil
    }

    @objc private func selectBadge(_ sender: BuddyMonTrainerBadgeView) {
        selectedBadge?.setSelected(false)
        sender.setSelected(true)
        selectedBadge = sender
        badgeDetailLabel?.stringValue = sender.selectionSummary
        badgeDetailLabel?.textColor = BuddyMonBrand.Menu.ink
    }

    private static func factLabel(_ fact: [String: Any]) -> NSView {
        let cell = NSStackView()
        cell.orientation = .horizontal
        cell.alignment = .centerY
        cell.spacing = BuddyMonBrand.Menu.microGap
        cell.addArrangedSubview(text(
            "○",
            color: BuddyMonBrand.Menu.rule,
            font: BuddyMonBrand.Font.mono(8)
        ))
        let label = text(
            fact["label"] as? String ?? "",
            color: BuddyMonBrand.Menu.mutedInk,
            font: BuddyMonBrand.Font.mono(9, weight: .medium)
        )
        label.widthAnchor.constraint(
            equalToConstant: BuddyMonBrand.Menu.trainerFactLabelWidth
        ).isActive = true
        cell.addArrangedSubview(label)
        return cell
    }

    private static func factValue(_ fact: [String: Any]) -> NSTextField {
        let value = text(
            fact["value"] as? String ?? "—",
            color: BuddyMonBrand.Menu.ink,
            font: BuddyMonBrand.Font.mono(10, weight: .medium)
        )
        value.alignment = .right
        value.widthAnchor.constraint(
            equalToConstant: BuddyMonBrand.Menu.trainerFactValueWidth
        ).isActive = true
        return value
    }

    private static func factGrid(
        _ facts: [[String: Any]],
        starCount: Int
    ) -> NSView {
        let grid = NSGridView()
        grid.rowSpacing = BuddyMonBrand.Menu.labelGap
        grid.columnSpacing = BuddyMonBrand.Menu.microGap
        for (index, fact) in facts.enumerated() {
            grid.addRow(with: [factLabel(fact), factValue(fact)])
            if index == 0 {
                let stars = text(
                    String(repeating: "★", count: starCount)
                        + String(repeating: "☆", count: 4 - starCount),
                    color: BuddyMonBrand.Menu.ink,
                    font: BuddyMonBrand.Font.mono(10, weight: .bold)
                )
                stars.alignment = .right
                stars.widthAnchor.constraint(
                    equalToConstant: BuddyMonBrand.Menu.trainerFactValueWidth
                ).isActive = true
                grid.addRow(with: [NSView(), stars])
            }
        }
        return grid
    }

    private static func fullBleedTrainerStatusRail(
        _ stats: [[String: Any]]
    ) -> NSView {
        let rail = BuddyMonBrand.Menu.makeTrainerStatusRail(
            stats.map { stat in
                (
                    label: stat["label"] as? String ?? "",
                    value: stat["value"] as? String ?? "—"
                )
            }
        )
        let container = NSView()
        container.addSubview(rail)
        rail.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            container.widthAnchor.constraint(
                equalToConstant: Layout.cardContentWidth
            ),
            container.heightAnchor.constraint(
                equalToConstant: BuddyMonBrand.Menu.trainerStatusRailHeight
            ),
            rail.widthAnchor.constraint(equalToConstant: Layout.cardWidth),
            rail.centerXAnchor.constraint(equalTo: container.centerXAnchor),
            rail.centerYAnchor.constraint(equalTo: container.centerYAnchor),
        ])
        return container
    }

    private static func badgeRail(
        _ badges: [[String: Any]]
    ) -> (view: NSView, buttons: [BuddyMonTrainerBadgeView]) {
        let isDense = badges.count > 9
        let badgeSize = isDense
            ? BuddyMonBrand.Menu.trainerBadgeDenseSize
            : BuddyMonBrand.Menu.trainerBadgeSize
        let symbolSize = isDense
            ? BuddyMonBrand.Menu.trainerBadgeDenseSymbolSize
            : BuddyMonBrand.Menu.trainerBadgeSymbolSize

        let rail = NSStackView()
        rail.orientation = .horizontal
        rail.alignment = .centerY
        rail.distribution = .fillEqually
        rail.spacing = BuddyMonBrand.Menu.flushInset
        var buttons: [BuddyMonTrainerBadgeView] = []
        for (index, badge) in badges.enumerated() {
            let medallion = BuddyMonTrainerBadgeView(
                badge: badge,
                size: badgeSize,
                symbolSize: symbolSize,
                animationIndex: index
            )
            medallion.translatesAutoresizingMaskIntoConstraints = false
            let slot = NSView()
            slot.addSubview(medallion)
            NSLayoutConstraint.activate([
                medallion.centerXAnchor.constraint(equalTo: slot.centerXAnchor),
                medallion.centerYAnchor.constraint(equalTo: slot.centerYAnchor),
            ])
            rail.addArrangedSubview(slot)
            buttons.append(medallion)
        }
        rail.widthAnchor.constraint(equalToConstant: Layout.cardContentWidth).isActive = true
        rail.heightAnchor.constraint(
            equalToConstant: BuddyMonBrand.Menu.trainerBadgeSize
        ).isActive = true
        return (rail, buttons)
    }

    private static func flexibleSpacer() -> NSView {
        let spacer = NSView()
        spacer.setContentHuggingPriority(.defaultLow, for: .horizontal)
        spacer.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        return spacer
    }

    private static func flexibleVerticalSpacer() -> NSView {
        let spacer = NSView()
        spacer.setContentHuggingPriority(.defaultLow, for: .vertical)
        spacer.setContentCompressionResistancePriority(.defaultLow, for: .vertical)
        return spacer
    }

    private static func text(
        _ value: String,
        color: NSColor,
        font: NSFont
    ) -> NSTextField {
        let field = NSTextField(labelWithString: value)
        field.textColor = color
        field.font = font
        field.lineBreakMode = .byTruncatingTail
        field.maximumNumberOfLines = 1
        return field
    }
}

// MARK: - Compact Menu

final class BuddyMonCompactMenuView: NSView {
    private enum Layout {
        static let width = BuddyMonBrand.Menu.panelWidth
        static let cardWidth = BuddyMonBrand.Menu.trainerCardWidth
        static let rootContentInset = BuddyMonBrand.Menu.compactGap
        static let buddyContentInset = BuddyMonBrand.Menu.compactGap
        static let contentWidth = cardWidth - (rootContentInset * 2)
        static let buddyRowWidth = cardWidth
        static let cardInnerWidth = buddyRowWidth - (buddyContentInset * 2)
        static let identityWidth = cardInnerWidth
            - BuddyMonBrand.Menu.buddySpriteSize
            - buddyContentInset
    }

    private(set) var preferredSize = NSSize(
        width: Layout.width,
        height: BuddyMonBrand.Menu.panelMinimumHeight
    )
    private(set) weak var initialResponder: NSView?
    private(set) var focusableControls: [NSButton] = []

    init(
        status: [String: Any],
        target: AnyObject,
        action: Selector
    ) {
        var firstAction: NSView?
        var controls: [NSButton] = []
        let root = NSStackView()
        root.orientation = .vertical
        root.alignment = .centerX
        root.spacing = BuddyMonBrand.Menu.sectionGap
        root.edgeInsets = NSEdgeInsets(
            top: Layout.rootContentInset,
            left: BuddyMonBrand.Menu.flushInset,
            bottom: Layout.rootContentInset,
            right: BuddyMonBrand.Menu.flushInset
        )

        let menu = status["native_menu"] as? [String: Any] ?? [:]
        let masthead = Self.header(
            status: status,
            menu: menu,
            target: target,
            action: action
        )
        root.addArrangedSubview(masthead.view)
        controls.append(masthead.button)
        if status["error"] != nil {
            root.addArrangedSubview(Self.emptyCard(
                title: "SIGNAL LOST",
                detail: "Reconnecting to your local BuddyMon data.",
                color: BuddyMonBrand.Menu.alert
            ))
        } else if let active = status["active"] as? [String: Any] {
            root.addArrangedSubview(Self.buddyCard(active: active))
        } else {
            root.addArrangedSubview(Self.emptyCard(
                title: "NO BUDDY YET",
                detail: "Choose a starter to begin.",
                color: BuddyMonBrand.Menu.chrome
            ))
        }
        if status["pending"] as? [String: Any] == nil {
            root.addArrangedSubview(Self.messageBox(status))
        }

        let primaryActions = NSStackView()
        primaryActions.orientation = .vertical
        primaryActions.alignment = .leading
        primaryActions.spacing = BuddyMonBrand.Menu.actionGap
        var utilityButtons: [NSButton] = []
        var fallbackAction: NSView? = masthead.button
        let descriptors = menu["items"] as? [[String: Any]] ?? []
        for descriptor in descriptors {
            guard
                let identifier = descriptor["id"] as? String,
                let rawLabel = descriptor["label"] as? String
            else { continue }
            let shortcut = descriptor["shortcut"] as? String ?? ""
            let label = rawLabel.replacingOccurrences(of: "Advanced: ", with: "")
                .replacingOccurrences(of: "Open Terminal", with: "Terminal")
            let isUtility = descriptor["presentation"] as? String == "utility"
                || identifier == "quit"
            let displayLabel = shortcut.isEmpty
                ? label.uppercased()
                : (
                    isUtility
                        ? "\(shortcut.uppercased()) \(label.uppercased())"
                        : "  \(shortcut.uppercased())  /  \(label.uppercased())"
                )
            let role: BuddyMonBrand.ButtonRole = descriptor["emphasis"] as? String == "primary"
                ? .primary
                : (isUtility ? .quiet : .secondary)
            let button: NSButton
            if isUtility {
                button = BuddyMonBrand.Menu.makeQuickLink(
                    displayLabel,
                    target: target,
                    action: action
                )
            } else {
                button = BuddyMonBrand.Menu.makeActionButton(
                    displayLabel,
                    target: target,
                    action: action,
                    role: role
                )
            }
            button.identifier = NSUserInterfaceItemIdentifier(identifier)
            button.keyEquivalent = shortcut
            button.keyEquivalentModifierMask = []
            controls.append(button)
            if
                let encoded = descriptor["image_base64"] as? String,
                let data = Data(base64Encoded: encoded),
                let image = NSImage(data: data)
            {
                image.size = NSSize(width: 24, height: 24)
                button.image = image
                button.imagePosition = .imageLeft
            }
            if firstAction == nil, !isUtility {
                firstAction = button
            }
            if fallbackAction == nil, identifier != "quit" {
                fallbackAction = button
            }
            if isUtility {
                utilityButtons.append(button)
            } else {
                button.widthAnchor.constraint(equalToConstant: Layout.contentWidth).isActive = true
                primaryActions.addArrangedSubview(button)
            }
        }
        if !primaryActions.arrangedSubviews.isEmpty {
            root.addArrangedSubview(primaryActions)
        }
        if !utilityButtons.isEmpty {
            root.addArrangedSubview(Self.quickLinkGrid(utilityButtons))
        }
        root.addArrangedSubview(Self.footer(
            menu: menu,
            target: target,
            action: action
        ))

        let card = BuddyMonFieldGuideCardBackgroundView()
        card.addSubview(root)
        root.translatesAutoresizingMaskIntoConstraints = false

        super.init(frame: .zero)
        focusableControls = controls
        initialResponder = firstAction ?? fallbackAction
        wantsLayer = true
        layer?.backgroundColor = BuddyMonBrand.Menu.canvas.cgColor
        addSubview(card)
        card.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            widthAnchor.constraint(equalToConstant: Layout.width),
            card.widthAnchor.constraint(equalToConstant: Layout.cardWidth),
            card.centerXAnchor.constraint(equalTo: centerXAnchor),
            card.topAnchor.constraint(
                equalTo: topAnchor,
                constant: BuddyMonBrand.Menu.fieldGuideFrameInset
            ),
            card.bottomAnchor.constraint(
                equalTo: bottomAnchor,
                constant: -BuddyMonBrand.Menu.fieldGuideFrameInset
            ),
            root.leadingAnchor.constraint(equalTo: card.leadingAnchor),
            root.trailingAnchor.constraint(equalTo: card.trailingAnchor),
            root.topAnchor.constraint(equalTo: card.topAnchor),
            root.bottomAnchor.constraint(equalTo: card.bottomAnchor),
        ])
        card.layoutSubtreeIfNeeded()
        preferredSize = NSSize(
            width: Layout.width,
            height: max(
                BuddyMonBrand.Menu.panelMinimumHeight,
                card.fittingSize.height + (BuddyMonBrand.Menu.fieldGuideFrameInset * 2)
            )
        )
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    private static func quickLinkGrid(_ buttons: [NSButton]) -> NSStackView {
        let grid = NSStackView()
        grid.orientation = .vertical
        grid.alignment = .leading
        grid.spacing = BuddyMonBrand.Menu.actionGap

        let columns = BuddyMonBrand.Menu.quickLinkColumns
        let gap = BuddyMonBrand.Menu.actionGap
        let linkWidth = (
            Layout.contentWidth - (gap * CGFloat(columns - 1))
        ) / CGFloat(columns)
        for start in stride(from: 0, to: buttons.count, by: columns) {
            let row = NSStackView()
            row.orientation = .horizontal
            row.alignment = .centerY
            row.spacing = gap
            for button in buttons[start..<min(start + columns, buttons.count)] {
                button.widthAnchor.constraint(equalToConstant: linkWidth).isActive = true
                row.addArrangedSubview(button)
            }
            row.widthAnchor.constraint(equalToConstant: Layout.contentWidth).isActive = true
            grid.addArrangedSubview(row)
        }
        grid.widthAnchor.constraint(equalToConstant: Layout.contentWidth).isActive = true
        return grid
    }

    private static func header(
        status: [String: Any],
        menu: [String: Any],
        target: AnyObject,
        action: Selector
    ) -> (view: NSView, button: NSButton) {
        let row = NSStackView()
        row.orientation = .horizontal
        row.alignment = .centerY
        row.spacing = BuddyMonBrand.Menu.headerGap
        row.addArrangedSubview(BuddyMonBrand.Menu.makeDisplayLabel(
            "BUDDYMON",
            color: BuddyMonBrand.Menu.ink,
            pixel: BuddyMonBrand.Menu.displayButtonPixel
        ))
        let appStatus: BuddyMonBrand.Menu.AppStatusState
        if status["error"] != nil {
            appStatus = .unavailable
        } else if status.isEmpty {
            appStatus = .idle
        } else {
            appStatus = .active
        }
        row.addArrangedSubview(BuddyMonBrand.Menu.makeStatusIndicator(appStatus))
        row.addArrangedSubview(flexibleSpacer())
        let tokens = headerTokenControl(
            status: status,
            menu: menu,
            target: target,
            action: action
        )
        row.addArrangedSubview(tokens.view)
        row.widthAnchor.constraint(equalToConstant: Layout.contentWidth).isActive = true
        return (row, tokens.button)
    }

    private static func buddyCard(active: [String: Any]) -> NSView {
        let card = BuddyMonBrand.Menu.makeActiveBuddyRow()
        card.orientation = .vertical
        card.alignment = .leading
        card.spacing = BuddyMonBrand.Menu.sectionGap
        card.edgeInsets = NSEdgeInsets(
            top: Layout.buddyContentInset,
            left: Layout.buddyContentInset,
            bottom: Layout.buddyContentInset,
            right: Layout.buddyContentInset
        )
        card.widthAnchor.constraint(equalToConstant: Layout.buddyRowWidth).isActive = true

        let hero = NSStackView()
        hero.orientation = .horizontal
        hero.alignment = .centerY
        hero.spacing = Layout.buddyContentInset
        hero.addArrangedSubview(buddySprite(active))

        let identity = NSStackView()
        identity.orientation = .vertical
        identity.alignment = .leading
        identity.spacing = BuddyMonBrand.Menu.actionGap
        let nameRow = NSStackView()
        nameRow.orientation = .horizontal
        nameRow.alignment = .centerY
        nameRow.spacing = BuddyMonBrand.Menu.compactGap
        let name = (active["name"] as? String ?? "Buddy").uppercased()
        nameRow.addArrangedSubview(BuddyMonBrand.Menu.makeDisplayLabel(
            name,
            color: BuddyMonBrand.Menu.pokemonColor(active),
            pixel: BuddyMonBrand.Menu.displayLabelPixel
        ))
        if active["shiny"] as? Bool == true {
            nameRow.addArrangedSubview(text(
                "✦",
                color: BuddyMonBrand.Menu.pokemonColor(active),
                font: BuddyMonBrand.Font.strong(9)
            ))
        }
        nameRow.addArrangedSubview(flexibleSpacer())
        nameRow.addArrangedSubview(text(
            "LVL. \(active["level"] as? Int ?? 1)",
            color: BuddyMonBrand.Menu.ink,
            font: BuddyMonBrand.Font.strong(11)
        ))
        nameRow.widthAnchor.constraint(equalToConstant: Layout.identityWidth).isActive = true
        identity.addArrangedSubview(nameRow)

        let type = (active["type"] as? String ?? "Normal").uppercased()
        let rarity = (active["rarity"] as? String ?? "buddy").uppercased()
        identity.addArrangedSubview(text(
            "\(type)  /  \(rarity)",
            color: BuddyMonBrand.Menu.mutedInk,
            font: BuddyMonBrand.Font.strong(10)
        ))

        let percent = levelPercent(active)
        let xpRow = NSStackView()
        xpRow.orientation = .horizontal
        xpRow.alignment = .centerY
        xpRow.spacing = BuddyMonBrand.Menu.compactGap
        let xpLabel = text(
            "XP",
            color: BuddyMonBrand.Menu.mutedInk,
            font: BuddyMonBrand.Font.strong(10)
        )
        xpLabel.setContentHuggingPriority(.required, for: .horizontal)
        xpRow.addArrangedSubview(xpLabel)
        let progress = BuddyMonMenuProgressView(percent: percent)
        let percentLabel = text(
            "\(percent)%",
            color: BuddyMonBrand.Menu.ink,
            font: BuddyMonBrand.Font.strong(10)
        )
        percentLabel.setContentHuggingPriority(.required, for: .horizontal)
        percentLabel.setContentCompressionResistancePriority(.required, for: .horizontal)
        let progressWidth = Layout.identityWidth
            - xpLabel.intrinsicContentSize.width
            - percentLabel.intrinsicContentSize.width
            - (BuddyMonBrand.Menu.compactGap * 2)
        progress.widthAnchor.constraint(equalToConstant: progressWidth).isActive = true
        progress.heightAnchor.constraint(equalToConstant: 8).isActive = true
        xpRow.addArrangedSubview(progress)
        xpRow.addArrangedSubview(percentLabel)
        xpRow.widthAnchor.constraint(equalToConstant: Layout.identityWidth).isActive = true
        identity.addArrangedSubview(xpRow)
        hero.addArrangedSubview(identity)
        card.addArrangedSubview(hero)

        return card
    }

    private static func buddySprite(_ active: [String: Any]) -> NSImageView {
        let sprite = NSImageView()
        sprite.translatesAutoresizingMaskIntoConstraints = false
        sprite.imageScaling = .scaleProportionallyUpOrDown
        sprite.wantsLayer = true
        sprite.layer?.magnificationFilter = .nearest
        if
            let encoded = active["sprite_base64"] as? String,
            let data = Data(base64Encoded: encoded)
        {
            sprite.image = NSImage(data: data)
        }
        animateSprite(sprite)
        NSLayoutConstraint.activate([
            sprite.widthAnchor.constraint(
                equalToConstant: BuddyMonBrand.Menu.buddySpriteSize
            ),
            sprite.heightAnchor.constraint(
                equalToConstant: BuddyMonBrand.Menu.buddySpriteSize
            ),
        ])
        return sprite
    }

    private static func emptyCard(title: String, detail: String, color: NSColor) -> NSView {
        let card = NSStackView()
        card.orientation = .vertical
        card.alignment = .leading
        card.spacing = BuddyMonBrand.Menu.tightGap
        card.edgeInsets = NSEdgeInsets(
            top: BuddyMonBrand.Menu.panelPadding,
            left: BuddyMonBrand.Menu.cardPadding,
            bottom: BuddyMonBrand.Menu.panelPadding,
            right: BuddyMonBrand.Menu.cardPadding
        )
        card.widthAnchor.constraint(equalToConstant: Layout.contentWidth).isActive = true
        card.addArrangedSubview(BuddyMonBrand.Menu.makeDisplayLabel(
            title,
            color: color,
            pixel: BuddyMonBrand.Menu.displayLabelPixel
        ))
        card.addArrangedSubview(text(
            detail,
            color: BuddyMonBrand.Menu.mutedInk,
            font: BuddyMonBrand.Font.regular(10)
        ))
        BuddyMonBrand.Menu.applySurface(to: card, raised: true, bordered: false)
        return card
    }

    private static func messageBox(_ status: [String: Any]) -> NSView {
        let message: String
        let color: NSColor
        var pokemon: [String: Any]?
        var pokemonName: String?
        if status["error"] != nil {
            message = "RETRYING IN THE BACKGROUND"
            color = BuddyMonBrand.Menu.alert
        } else if status["active"] as? [String: Any] == nil {
            message = "CHOOSE A STARTER TO BEGIN"
            color = BuddyMonBrand.Menu.chrome
        } else if
            let recent = (status["recent"] as? [[String: Any]])?.first,
            let name = recent["name"] as? String
        {
            message = "LAST CATCH"
            color = BuddyMonBrand.Menu.ink
            pokemon = recent
            pokemonName = name.uppercased()
        } else {
            message = "YOUR BUDDY IS HERE"
            color = BuddyMonBrand.Menu.chrome
        }

        let box = NSStackView()
        box.orientation = .horizontal
        box.alignment = .centerY
        box.spacing = BuddyMonBrand.Menu.tightGap
        box.edgeInsets = NSEdgeInsets(
            top: BuddyMonBrand.Menu.labelGap,
            left: BuddyMonBrand.Menu.flushInset,
            bottom: BuddyMonBrand.Menu.labelGap,
            right: BuddyMonBrand.Menu.microGap
        )
        box.widthAnchor.constraint(equalToConstant: Layout.contentWidth).isActive = true

        let chevron = BuddyMonBrand.Menu.makeDisplayLabel(
            "▶",
            color: color,
            pixel: BuddyMonBrand.Menu.displayButtonPixel
        )
        box.addArrangedSubview(chevron)
        if let pokemon {
            box.setCustomSpacing(BuddyMonBrand.Menu.labelGap, after: chevron)
            let sprite = signalSprite(pokemon)
            box.addArrangedSubview(sprite)
            box.setCustomSpacing(BuddyMonBrand.Menu.tightGap, after: sprite)
        }
        let messageLabel = BuddyMonBrand.Menu.makeDisplayLabel(
            message,
            color: color,
            pixel: BuddyMonBrand.Menu.displayButtonPixel
        )
        messageLabel.setContentHuggingPriority(.required, for: .horizontal)
        box.addArrangedSubview(messageLabel)
        if let pokemonName {
            box.setCustomSpacing(BuddyMonBrand.Menu.compactGap, after: messageLabel)
            let nameLabel = BuddyMonBrand.Menu.makeDisplayLabel(
                pokemonName,
                color: color,
                pixel: BuddyMonBrand.Menu.displayButtonPixel
            )
            nameLabel.setContentHuggingPriority(.required, for: .horizontal)
            box.addArrangedSubview(nameLabel)
            box.setCustomSpacing(BuddyMonBrand.Menu.labelGap, after: nameLabel)
        }
        if let rarity = pokemon?["rarity"] as? String {
            box.addArrangedSubview(BuddyMonBrand.Menu.makeRarityLabel(rarity))
        }
        box.addArrangedSubview(flexibleSpacer())
        return box
    }

    private static func signalSprite(_ pokemon: [String: Any]) -> NSImageView {
        let imageView = NSImageView()
        imageView.imageScaling = .scaleProportionallyUpOrDown
        imageView.imageAlignment = .alignCenter
        imageView.wantsLayer = true
        imageView.layer?.magnificationFilter = .nearest
        if
            let encoded = pokemon["sprite_base64"] as? String,
            let data = Data(base64Encoded: encoded)
        {
            imageView.image = NSImage(data: data)
        }
        imageView.widthAnchor.constraint(
            equalToConstant: BuddyMonBrand.Menu.signalSpriteSize
        ).isActive = true
        imageView.heightAnchor.constraint(
            equalToConstant: BuddyMonBrand.Menu.signalSpriteSize
        ).isActive = true
        return imageView
    }

    private static func headerTokenControl(
        status: [String: Any],
        menu: [String: Any],
        target: AnyObject,
        action: Selector
    ) -> (view: NSView, button: NSButton) {
        let tokens = status["tokens"] as? [String: Any] ?? [:]
        let today = tokens["today"] as? [String: Any] ?? [:]
        let yesterday = tokens["yesterday"] as? [String: Any] ?? [:]
        let tokenError = (tokens["error"] as? String)?.isEmpty == false
        let descriptor = menu["token_action"] as? [String: Any] ?? [
            "id": "tokens",
            "label": "Open token detail",
            "shortcut": "u",
        ]

        let row = NSStackView()
        row.orientation = .horizontal
        row.alignment = .centerY
        row.spacing = BuddyMonBrand.Menu.labelGap
        row.widthAnchor.constraint(
            equalToConstant: BuddyMonBrand.Menu.tokenHeaderWidth
        ).isActive = true
        row.addArrangedSubview(flexibleSpacer())
        row.addArrangedSubview(text(
            "TOKENS",
            color: BuddyMonBrand.Menu.mutedInk,
            font: BuddyMonBrand.Font.strong(7)
        ))
        row.addArrangedSubview(tokenMetric(
            label: today["label"] as? String ?? "Today",
            value: tokenError ? "—" : (today["compact"] as? String ?? "—")
        ))
        row.addArrangedSubview(text(
            "·",
            color: BuddyMonBrand.Menu.mutedInk,
            font: BuddyMonBrand.Font.regular(7)
        ))
        row.addArrangedSubview(tokenMetric(
            label: yesterday["label"] as? String ?? "Yesterday",
            value: tokenError ? "—" : (yesterday["compact"] as? String ?? "—")
        ))
        let shortcut = descriptor["shortcut"] as? String ?? "u"
        let button = BuddyMonTokenHeaderButton(
            title: "",
            target: target,
            action: action
        )
        button.identifier = NSUserInterfaceItemIdentifier(
            descriptor["id"] as? String ?? "tokens"
        )
        button.isBordered = false
        button.focusRingType = .none
        button.keyEquivalent = shortcut
        button.keyEquivalentModifierMask = []
        let todayValue = tokenError ? "unavailable" : (today["compact"] as? String ?? "zero")
        let yesterdayValue = tokenError
            ? "unavailable"
            : (yesterday["compact"] as? String ?? "zero")
        button.setAccessibilityLabel(
            "Token usage. Today \(todayValue). Yesterday \(yesterdayValue). Open details."
        )
        row.addSubview(button, positioned: .above, relativeTo: nil)
        button.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            button.leadingAnchor.constraint(equalTo: row.leadingAnchor),
            button.trailingAnchor.constraint(equalTo: row.trailingAnchor),
            button.topAnchor.constraint(equalTo: row.topAnchor),
            button.bottomAnchor.constraint(equalTo: row.bottomAnchor),
        ])
        return (row, button)
    }

    private static func tokenMetric(label: String, value: String) -> NSView {
        let metric = NSStackView()
        metric.orientation = .horizontal
        metric.alignment = .centerY
        metric.spacing = BuddyMonBrand.Menu.microGap
        metric.addArrangedSubview(text(
            label.uppercased(),
            color: BuddyMonBrand.Menu.mutedInk,
            font: BuddyMonBrand.Font.regular(7)
        ))
        metric.addArrangedSubview(text(
            value,
            color: BuddyMonBrand.Menu.ink,
            font: BuddyMonBrand.Font.strong(9)
        ))
        return metric
    }

    private static func footer(
        menu: [String: Any],
        target: AnyObject,
        action: Selector
    ) -> NSView {
        let row = NSStackView()
        row.orientation = .horizontal
        row.alignment = .centerY
        row.spacing = BuddyMonBrand.Menu.compactGap
        row.addArrangedSubview(text(
            "↑↓ MOVE  ·  ↵ SELECT  ·  ESC",
            color: BuddyMonBrand.Menu.mutedInk,
            font: BuddyMonBrand.Font.regular(7)
        ))
        row.addArrangedSubview(flexibleSpacer())
        var descriptors = menu["footer_items"] as? [[String: Any]] ?? []
        if descriptors.isEmpty {
            descriptors = [
                [
                    "id": "refresh",
                    "label": "Refresh",
                    "shortcut": "r",
                    "modifiers": ["command"],
                ],
                [
                    "id": "quit",
                    "label": "Quit",
                    "shortcut": "q",
                    "modifiers": ["command"],
                ],
            ]
        }
        for descriptor in descriptors {
            let shortcut = descriptor["shortcut"] as? String ?? ""
            let label = descriptor["label"] as? String ?? ""
            let modifiers = descriptor["modifiers"] as? [String] ?? []
            let prefix = modifiers.contains("command") ? "⌘" : ""
            let button = BuddyMonMenuFooterButton(
                title: "\(prefix)\(shortcut.uppercased())  \(label.uppercased())",
                target: target,
                action: action
            )
            button.identifier = NSUserInterfaceItemIdentifier(
                descriptor["id"] as? String ?? ""
            )
            button.isBordered = false
            button.focusRingType = .none
            button.font = BuddyMonBrand.Font.regular(7)
            button.contentTintColor = BuddyMonBrand.Menu.mutedInk
            button.keyEquivalent = shortcut
            button.keyEquivalentModifierMask = modifiers.contains("command")
                ? [.command]
                : []
            row.addArrangedSubview(button)
        }
        row.widthAnchor.constraint(equalToConstant: Layout.contentWidth).isActive = true
        return row
    }

    private static func levelPercent(_ active: [String: Any]) -> Int {
        let progress = active["level_progress"] as? [String: Any] ?? [:]
        return min(100, max(0, progress["percent"] as? Int ?? 0))
    }

    private static func flexibleSpacer() -> NSView {
        let spacer = NSView()
        spacer.setContentHuggingPriority(.defaultLow, for: .horizontal)
        spacer.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        return spacer
    }

    private static func text(
        _ value: String,
        color: NSColor = BuddyMonBrand.Menu.ink,
        font: NSFont = BuddyMonBrand.Font.mono(12)
    ) -> NSTextField {
        let field = NSTextField(labelWithString: value)
        field.textColor = color
        field.font = font
        field.lineBreakMode = .byTruncatingTail
        field.maximumNumberOfLines = 1
        return field
    }

    private static func animateSprite(_ imageView: NSImageView) {
        guard !NSWorkspace.shared.accessibilityDisplayShouldReduceMotion else { return }
        let bob = CABasicAnimation(keyPath: "transform.translation.y")
        bob.fromValue = 0.0
        bob.toValue = 2.0
        bob.duration = 1.65
        bob.autoreverses = true
        bob.repeatCount = .infinity
        bob.timingFunction = CAMediaTimingFunction(name: .easeInEaseOut)
        imageView.layer?.add(bob, forKey: "buddymon-menu-sprite-bob")
    }
}

// MARK: - Token Detail

final class BuddyMonCompactTokensView: NSView {
    private enum Layout {
        static let width = BuddyMonBrand.Menu.panelWidth
        static let cardWidth = BuddyMonBrand.Menu.trainerCardWidth
        static let contentWidth = cardWidth - (BuddyMonBrand.Menu.cardPadding * 2)
        static let summaryWidth = (
            contentWidth - (BuddyMonBrand.Menu.actionGap * 2)
        ) / 3
    }

    private(set) var preferredSize = NSSize(
        width: Layout.width,
        height: BuddyMonBrand.Menu.tokenPanelMinimumHeight
    )
    private(set) weak var initialResponder: NSView?
    private(set) var focusableControls: [NSButton] = []

    init(
        view: [String: Any],
        target: AnyObject,
        backAction: Selector
    ) {
        let root = NSStackView()
        root.orientation = .vertical
        root.alignment = .leading
        root.spacing = BuddyMonBrand.Menu.compactGap
        root.distribution = .fill
        root.edgeInsets = NSEdgeInsets(
            top: BuddyMonBrand.Menu.cardPadding,
            left: BuddyMonBrand.Menu.cardPadding,
            bottom: BuddyMonBrand.Menu.cardPadding,
            right: BuddyMonBrand.Menu.cardPadding
        )

        let navigation = compactNavigationHeader(
            title: "TOKEN USAGE",
            identifier: "tokens_back",
            target: target,
            action: backAction,
            contentWidth: Layout.contentWidth
        )
        let back = navigation.back
        root.addArrangedSubview(navigation.view)
        if view["loading"] as? Bool == true {
            root.addArrangedSubview(Self.message(
                "READING LOCAL TOKEN ACTIVITY…",
                color: BuddyMonBrand.Menu.mutedInk
            ))
        } else if let error = view["error"] as? String, !error.isEmpty {
            root.addArrangedSubview(Self.message(
                "TOKEN DATA UNAVAILABLE",
                color: BuddyMonBrand.Menu.alert
            ))
        } else {
            let summary = view["summary"] as? [[String: Any]] ?? []
            root.addArrangedSubview(Self.summaryRow(summary))
            root.addArrangedSubview(Self.dailyPulse(view))
            root.addArrangedSubview(Self.insightLine(view))
            root.addArrangedSubview(Self.flexibleVerticalSpacer())
            root.addArrangedSubview(Self.toolLine(view))
        }

        let card = BuddyMonFieldGuideCardBackgroundView()
        card.addSubview(root)
        root.translatesAutoresizingMaskIntoConstraints = false

        super.init(frame: .zero)
        focusableControls = [back]
        initialResponder = back
        wantsLayer = true
        layer?.backgroundColor = BuddyMonBrand.Menu.canvas.cgColor
        addSubview(card)
        card.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            widthAnchor.constraint(equalToConstant: Layout.width),
            card.widthAnchor.constraint(equalToConstant: Layout.cardWidth),
            card.centerXAnchor.constraint(equalTo: centerXAnchor),
            card.topAnchor.constraint(
                equalTo: topAnchor,
                constant: BuddyMonBrand.Menu.fieldGuideFrameInset
            ),
            card.bottomAnchor.constraint(
                equalTo: bottomAnchor,
                constant: -BuddyMonBrand.Menu.fieldGuideFrameInset
            ),
            root.leadingAnchor.constraint(equalTo: card.leadingAnchor),
            root.trailingAnchor.constraint(equalTo: card.trailingAnchor),
            root.topAnchor.constraint(equalTo: card.topAnchor),
            root.bottomAnchor.constraint(equalTo: card.bottomAnchor),
        ])
        preferredSize = NSSize(
            width: Layout.width,
            height: BuddyMonBrand.Menu.tokenPanelMinimumHeight
        )
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    private static func summaryRow(_ summary: [[String: Any]]) -> NSView {
        let row = NSStackView()
        row.orientation = .horizontal
        row.alignment = .top
        row.spacing = BuddyMonBrand.Menu.actionGap
        let ids = ["today", "last_7_days", "trend"]
        for id in ids {
            let item = summary.first { $0["id"] as? String == id } ?? [:]
            let label: String
            switch id {
            case "last_7_days": label = "7 DAYS"
            case "trend": label = "VS PRIOR"
            default: label = (item["label"] as? String ?? id).uppercased()
            }
            let cell = NSStackView()
            cell.orientation = .vertical
            cell.alignment = .leading
            cell.spacing = BuddyMonBrand.Menu.microGap
            cell.edgeInsets = NSEdgeInsets(
                top: BuddyMonBrand.Menu.compactGap,
                left: BuddyMonBrand.Menu.compactGap,
                bottom: BuddyMonBrand.Menu.compactGap,
                right: BuddyMonBrand.Menu.compactGap
            )
            cell.addArrangedSubview(text(
                label,
                color: BuddyMonBrand.Menu.mutedInk,
                font: BuddyMonBrand.Font.strong(8)
            ))
            cell.addArrangedSubview(text(
                item["compact"] as? String ?? "0",
                color: BuddyMonBrand.Menu.ink,
                font: BuddyMonBrand.Font.strong(14)
            ))
            cell.widthAnchor.constraint(equalToConstant: Layout.summaryWidth).isActive = true
            BuddyMonBrand.Menu.applySurface(to: cell, raised: true, bordered: false)
            row.addArrangedSubview(cell)
        }
        return row
    }

    private static func toolLine(_ view: [String: Any]) -> NSView {
        let dashboard = view["dashboard"] as? [String: Any] ?? [:]
        let clients = dashboard["clients"] as? [[String: Any]] ?? []
        let values = clients.prefix(3).map { client in
            let label = (client["label"] as? String ?? "Tool").uppercased()
            return "\(label) \(client["percent"] as? Int ?? 0)%"
        }
        let value = values.isEmpty
            ? "NO LOCAL ACTIVITY YET"
            : "BY TOOL  " + values.joined(separator: " · ")
        return message(value, color: BuddyMonBrand.Menu.mutedInk)
    }

    private static func dailyPulse(_ view: [String: Any]) -> NSView {
        let dashboard = view["dashboard"] as? [String: Any] ?? [:]
        let days = dashboard["daily"] as? [[String: Any]] ?? []
        let pulse = BuddyMonTokenDailyPulseView(days: Array(days.suffix(7)))
        pulse.widthAnchor.constraint(equalToConstant: Layout.contentWidth).isActive = true
        pulse.heightAnchor.constraint(
            equalToConstant: BuddyMonBrand.Menu.tokenDailyPulseHeight
        ).isActive = true
        return pulse
    }

    private static func insightLine(_ view: [String: Any]) -> NSView {
        let dashboard = view["dashboard"] as? [String: Any] ?? [:]
        let insights = dashboard["insights"] as? [[String: Any]] ?? []

        func insight(_ id: String) -> [String: Any] {
            insights.first { $0["id"] as? String == id } ?? [:]
        }

        let average = insight("average")["value"] as? String ?? "0"
        let peak = insight("peak")["value"] as? String ?? "NO USAGE"
        let rawStreak = insight("active_streak")["value"] as? String ?? "0 days"
        let streak = rawStreak
            .replacingOccurrences(of: " days", with: "D")
            .replacingOccurrences(of: " day", with: "D")
        return message(
            "AVG \(average)/D · PEAK \(peak.uppercased()) · STREAK \(streak.uppercased())",
            color: BuddyMonBrand.Menu.mutedInk
        )
    }

    private static func message(_ value: String, color: NSColor) -> NSView {
        let row = NSStackView()
        row.orientation = .horizontal
        row.alignment = .centerY
        row.edgeInsets = NSEdgeInsets(
            top: BuddyMonBrand.Menu.labelGap,
            left: BuddyMonBrand.Menu.microGap,
            bottom: BuddyMonBrand.Menu.labelGap,
            right: BuddyMonBrand.Menu.microGap
        )
        row.widthAnchor.constraint(equalToConstant: Layout.contentWidth).isActive = true
        row.addArrangedSubview(text(
            value,
            color: color,
            font: BuddyMonBrand.Font.strong(9)
        ))
        return row
    }

    private static func flexibleVerticalSpacer() -> NSView {
        let spacer = NSView()
        spacer.setContentHuggingPriority(.defaultLow, for: .vertical)
        spacer.setContentCompressionResistancePriority(.defaultLow, for: .vertical)
        return spacer
    }

    private static func text(
        _ value: String,
        color: NSColor,
        font: NSFont
    ) -> NSTextField {
        let field = NSTextField(labelWithString: value)
        field.textColor = color
        field.font = font
        field.lineBreakMode = .byTruncatingTail
        field.maximumNumberOfLines = 1
        return field
    }
}

private final class BuddyMonTokenDailyPulseView: NSView {
    private let days: [[String: Any]]

    init(days: [[String: Any]]) {
        self.days = days
        super.init(frame: .zero)
        let spokenDays = days.map { day in
            let label = day["date_label"] as? String ?? day["label"] as? String ?? "Day"
            let value = day["compact"] as? String ?? "0"
            return "\(label), \(value) tokens"
        }
        setAccessibilityElement(true)
        setAccessibilityRole(.group)
        setAccessibilityLabel("Seven-day token pulse. \(spokenDays.joined(separator: ", "))")
    }

    required init?(coder: NSCoder) {
        nil
    }

    override var isFlipped: Bool { true }

    override var intrinsicContentSize: NSSize {
        NSSize(
            width: NSView.noIntrinsicMetric,
            height: BuddyMonBrand.Menu.tokenDailyPulseHeight
        )
    }

    override func draw(_ dirtyRect: NSRect) {
        super.draw(dirtyRect)
        guard !days.isEmpty else {
            drawLabel(
                "NO DAILY ACTIVITY YET",
                in: bounds,
                color: BuddyMonBrand.Menu.mutedInk,
                font: BuddyMonBrand.Font.strong(8)
            )
            return
        }

        let maximum = max(1, days.compactMap { $0["tokens"] as? Int }.max() ?? 0)
        let columnWidth = bounds.width / CGFloat(days.count)
        let valueHeight = BuddyMonBrand.Menu.compactGap + BuddyMonBrand.Menu.tightGap
        let labelHeight = BuddyMonBrand.Menu.compactGap + BuddyMonBrand.Menu.headerGap
        let barHeight = bounds.height
            - valueHeight
            - labelHeight
            - (BuddyMonBrand.Menu.microGap * 2)

        for (index, day) in days.enumerated() {
            let x = CGFloat(index) * columnWidth
            let isToday = day["is_today"] as? Bool ?? false
            let ink = isToday ? BuddyMonBrand.Menu.ink : BuddyMonBrand.Menu.mutedInk
            drawLabel(
                day["compact"] as? String ?? "0",
                in: NSRect(x: x, y: 0, width: columnWidth, height: valueHeight),
                color: ink,
                font: BuddyMonBrand.Font.strong(7)
            )

            let track = NSRect(
                x: x + (BuddyMonBrand.Menu.compactGap / 2),
                y: valueHeight + BuddyMonBrand.Menu.microGap,
                width: columnWidth - BuddyMonBrand.Menu.compactGap,
                height: barHeight
            )
            BuddyMonBrand.Menu.dataTrack.setFill()
            NSBezierPath(
                roundedRect: track,
                xRadius: BuddyMonBrand.Menu.progressCornerRadius,
                yRadius: BuddyMonBrand.Menu.progressCornerRadius
            ).fill()

            let tokens = max(0, day["tokens"] as? Int ?? 0)
            if tokens > 0 {
                let ratio = CGFloat(tokens) / CGFloat(maximum)
                let fillHeight = max(BuddyMonBrand.Menu.microGap, barHeight * ratio)
                let fill = NSRect(
                    x: track.minX,
                    y: track.maxY - fillHeight,
                    width: track.width,
                    height: fillHeight
                )
                BuddyMonBrand.Menu.dataFill.setFill()
                NSBezierPath(
                    roundedRect: fill,
                    xRadius: BuddyMonBrand.Menu.progressCornerRadius,
                    yRadius: BuddyMonBrand.Menu.progressCornerRadius
                ).fill()
            }

            drawLabel(
                (day["label"] as? String ?? "-").uppercased(),
                in: NSRect(
                    x: x,
                    y: track.maxY + BuddyMonBrand.Menu.microGap,
                    width: columnWidth,
                    height: labelHeight
                ),
                color: ink,
                font: BuddyMonBrand.Font.regular(7)
            )
        }
    }

    private func drawLabel(
        _ value: String,
        in rect: NSRect,
        color: NSColor,
        font: NSFont
    ) {
        let style = NSMutableParagraphStyle()
        style.alignment = .center
        let attributes: [NSAttributedString.Key: Any] = [
            .foregroundColor: color,
            .font: font,
            .paragraphStyle: style,
        ]
        NSAttributedString(string: value, attributes: attributes).draw(in: rect)
    }
}

// MARK: - Settings

final class BuddyMonCompactSettingsView: NSView {
    private enum Layout {
        static let width = BuddyMonBrand.Menu.panelWidth
        static let cardWidth = BuddyMonBrand.Menu.trainerCardWidth
        static let contentWidth = cardWidth - (BuddyMonBrand.Menu.cardPadding * 2)
    }

    private(set) var preferredSize = NSSize(
        width: Layout.width,
        height: BuddyMonBrand.Menu.settingsPanelMinimumHeight
    )
    private(set) weak var initialResponder: NSView?
    private(set) var focusableControls: [NSButton] = []

    init(
        view: [String: Any],
        target: AnyObject,
        backAction: Selector,
        selectionAction: Selector
    ) {
        let root = NSStackView()
        root.orientation = .vertical
        root.alignment = .leading
        root.spacing = BuddyMonBrand.Menu.microGap
        root.distribution = .fill
        root.edgeInsets = NSEdgeInsets(
            top: BuddyMonBrand.Menu.cardPadding,
            left: BuddyMonBrand.Menu.cardPadding,
            bottom: BuddyMonBrand.Menu.cardPadding,
            right: BuddyMonBrand.Menu.cardPadding
        )

        let navigation = compactNavigationHeader(
            title: "SETTINGS",
            identifier: "settings_back",
            target: target,
            action: backAction,
            contentWidth: Layout.contentWidth
        )
        let back = navigation.back
        root.addArrangedSubview(navigation.view)
        var controls = [back]

        if view["loading"] as? Bool == true {
            root.addArrangedSubview(Self.message(
                "READING LOCAL SETTINGS…",
                color: BuddyMonBrand.Menu.mutedInk
            ))
        } else if let error = view["error"] as? String, !error.isEmpty {
            root.addArrangedSubview(Self.message(
                "SETTINGS UNAVAILABLE",
                color: BuddyMonBrand.Menu.alert
            ))
        } else {
            let rows = view["rows"] as? [[String: Any]] ?? []
            if rows.isEmpty {
                root.addArrangedSubview(Self.message(
                    "NO LOCAL SETTINGS FOUND",
                    color: BuddyMonBrand.Menu.mutedInk
                ))
            } else {
                for setting in rows {
                    let key = setting["key"] as? String ?? "setting"
                    let currentValue = setting["value"] as? String ?? ""
                    let allowedValues = setting["allowed_values"] as? [String] ?? [currentValue]
                    let allowedLabels = setting["allowed_display_values"] as? [String]
                        ?? allowedValues.map { $0.capitalized }
                    let options = allowedValues.enumerated().map { index, value in
                        BuddyMonBrand.Menu.SettingsOption(
                            value: value,
                            label: index < allowedLabels.count ? allowedLabels[index] : value,
                            isActive: value == currentValue
                        )
                    }
                    let row = BuddyMonBrand.Menu.makeSettingsRow(
                        label: setting["label"] as? String ?? key,
                        key: key,
                        detail: setting["help"] as? String ?? "",
                        options: options,
                        target: target,
                        action: selectionAction
                    )
                    row.widthAnchor.constraint(equalToConstant: Layout.contentWidth).isActive = true
                    controls.append(contentsOf: row.optionButtons)
                    root.addArrangedSubview(row)
                }
            }
        }

        root.addArrangedSubview(Self.flexibleVerticalSpacer())
        root.addArrangedSubview(Self.footer())

        let card = BuddyMonFieldGuideCardBackgroundView()
        card.addSubview(root)
        root.translatesAutoresizingMaskIntoConstraints = false

        super.init(frame: .zero)
        focusableControls = controls
        initialResponder = back
        wantsLayer = true
        layer?.backgroundColor = BuddyMonBrand.Menu.canvas.cgColor
        addSubview(card)
        card.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            widthAnchor.constraint(equalToConstant: Layout.width),
            card.widthAnchor.constraint(equalToConstant: Layout.cardWidth),
            card.centerXAnchor.constraint(equalTo: centerXAnchor),
            card.topAnchor.constraint(
                equalTo: topAnchor,
                constant: BuddyMonBrand.Menu.fieldGuideFrameInset
            ),
            card.bottomAnchor.constraint(
                equalTo: bottomAnchor,
                constant: -BuddyMonBrand.Menu.fieldGuideFrameInset
            ),
            root.leadingAnchor.constraint(equalTo: card.leadingAnchor),
            root.trailingAnchor.constraint(equalTo: card.trailingAnchor),
            root.topAnchor.constraint(equalTo: card.topAnchor),
            root.bottomAnchor.constraint(equalTo: card.bottomAnchor),
        ])
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    private static func message(_ value: String, color: NSColor) -> NSView {
        let field = NSTextField(labelWithString: value)
        field.textColor = color
        field.font = BuddyMonBrand.Font.strong(9)
        field.lineBreakMode = .byTruncatingTail
        field.maximumNumberOfLines = 1
        field.widthAnchor.constraint(equalToConstant: Layout.contentWidth).isActive = true
        return field
    }

    private static func flexibleVerticalSpacer() -> NSView {
        let spacer = NSView()
        spacer.setContentHuggingPriority(.defaultLow, for: .vertical)
        spacer.setContentCompressionResistancePriority(.defaultLow, for: .vertical)
        return spacer
    }

    private static func footer() -> NSView {
        let field = NSTextField(
            labelWithString: "ARROWS MOVE  ·  RETURN SETS  ·  ESC CLOSE"
        )
        field.textColor = BuddyMonBrand.Menu.mutedInk
        field.font = BuddyMonBrand.Font.strong(9)
        field.lineBreakMode = .byTruncatingTail
        field.maximumNumberOfLines = 1
        field.widthAnchor.constraint(equalToConstant: Layout.contentWidth).isActive = true
        return field
    }
}

// MARK: - Encounter

final class BuddyMonCompactEncounterView: NSView {
    private enum Layout {
        static let width = BuddyMonBrand.Menu.panelWidth
        static let cardWidth = BuddyMonBrand.Menu.trainerCardWidth
        static let contentWidth = cardWidth - (BuddyMonBrand.Menu.cardPadding * 2)
        static let identityWidth = (
            contentWidth - BuddyMonBrand.Menu.actionGap
        ) / 2
    }

    private(set) var preferredSize = NSSize(
        width: Layout.width,
        height: BuddyMonBrand.Menu.encounterPanelMinimumHeight
    )
    private(set) weak var initialResponder: NSView?
    private(set) var focusableControls: [NSButton] = []

    init(
        view: [String: Any],
        message: String?,
        target: AnyObject,
        action: Selector,
        backAction: Selector
    ) {
        let encounter = view["encounter"] as? [String: Any] ?? [:]
        var controls: [NSButton] = []
        var firstControl: NSView?
        let root = NSStackView()
        root.orientation = .vertical
        root.alignment = .leading
        root.spacing = BuddyMonBrand.Menu.sectionGap
        root.edgeInsets = NSEdgeInsets(
            top: BuddyMonBrand.Menu.cardPadding,
            left: BuddyMonBrand.Menu.cardPadding,
            bottom: BuddyMonBrand.Menu.cardPadding,
            right: BuddyMonBrand.Menu.cardPadding
        )

        let mode = (encounter["mode"] as? String ?? "encounter").uppercased()
        let navigation = compactNavigationHeader(
            title: "\(mode) / WILD SIGNAL",
            identifier: "encounter_back",
            target: target,
            action: backAction,
            contentWidth: Layout.contentWidth
        )
        let back = navigation.back
        root.addArrangedSubview(navigation.view)

        if encounter["state"] as? String == "empty" {
            root.addArrangedSubview(Self.messageLine(
                encounter["message"] as? String ?? "No wild Pokémon is waiting."
            ))
            controls = [back]
            firstControl = back
        } else {
            root.addArrangedSubview(Self.identityRow(encounter))
            let signal = message
                ?? encounter["message"] as? String
                ?? encounter["status"] as? String
                ?? "Choose your next move."
            root.addArrangedSubview(Self.messageLine(signal))

            let actionRow = NSStackView()
            actionRow.orientation = .horizontal
            actionRow.alignment = .centerY
            actionRow.spacing = BuddyMonBrand.Menu.actionGap
            let descriptors = encounter["actions"] as? [[String: Any]] ?? []
            var actionButtons: [NSButton] = []
            for descriptor in descriptors {
                guard let identifier = descriptor["id"] as? String else { continue }
                let shortcut = descriptor["shortcut"] as? String ?? ""
                let label = descriptor["compact_label"] as? String
                    ?? descriptor["label"] as? String
                    ?? identifier
                let display = shortcut.isEmpty
                    ? label.uppercased()
                    : "\(shortcut.uppercased())  \(label.uppercased())"
                let button = BuddyMonBrand.Menu.makeActionButton(
                    display,
                    target: target,
                    action: action,
                    role: .secondary
                )
                button.identifier = NSUserInterfaceItemIdentifier(identifier)
                button.keyEquivalent = shortcut
                button.keyEquivalentModifierMask = []
                actionButtons.append(button)
                actionRow.addArrangedSubview(button)
            }
            Self.sizeButtons(actionButtons, availableWidth: Layout.contentWidth)
            if !actionButtons.isEmpty {
                root.addArrangedSubview(actionRow)
            }
            controls = actionButtons + [back]
            firstControl = actionButtons.first ?? back
        }
        root.addArrangedSubview(Self.footer())

        let card = BuddyMonFieldGuideCardBackgroundView()
        card.addSubview(root)
        root.translatesAutoresizingMaskIntoConstraints = false

        super.init(frame: .zero)
        focusableControls = controls
        initialResponder = firstControl
        wantsLayer = true
        layer?.backgroundColor = BuddyMonBrand.Menu.canvas.cgColor
        addSubview(card)
        card.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            widthAnchor.constraint(equalToConstant: Layout.width),
            card.widthAnchor.constraint(equalToConstant: Layout.cardWidth),
            card.centerXAnchor.constraint(equalTo: centerXAnchor),
            card.topAnchor.constraint(
                equalTo: topAnchor,
                constant: BuddyMonBrand.Menu.fieldGuideFrameInset
            ),
            card.bottomAnchor.constraint(
                equalTo: bottomAnchor,
                constant: -BuddyMonBrand.Menu.fieldGuideFrameInset
            ),
            root.leadingAnchor.constraint(equalTo: card.leadingAnchor),
            root.trailingAnchor.constraint(equalTo: card.trailingAnchor),
            root.topAnchor.constraint(equalTo: card.topAnchor),
            root.bottomAnchor.constraint(equalTo: card.bottomAnchor),
        ])
        card.layoutSubtreeIfNeeded()
        preferredSize = NSSize(
            width: Layout.width,
            height: max(
                BuddyMonBrand.Menu.encounterPanelMinimumHeight,
                card.fittingSize.height + (BuddyMonBrand.Menu.fieldGuideFrameInset * 2)
            )
        )
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    private static func identityRow(_ encounter: [String: Any]) -> NSView {
        let hp = encounter["hp"] as? [String: Any] ?? [:]
        let row = NSStackView()
        row.orientation = .horizontal
        row.alignment = .top
        row.spacing = BuddyMonBrand.Menu.actionGap
        row.addArrangedSubview(identityCard(
            role: "BUDDY",
            pokemon: encounter["buddy"] as? [String: Any] ?? [:],
            levelKey: "level",
            hpPercent: hp["buddy_percent"] as? Int
        ))
        row.addArrangedSubview(identityCard(
            role: "WILD",
            pokemon: encounter["wild"] as? [String: Any] ?? [:],
            levelKey: "wild_level",
            hpPercent: hp["wild_percent"] as? Int
        ))
        return row
    }

    private static func identityCard(
        role: String,
        pokemon: [String: Any],
        levelKey: String,
        hpPercent: Int?
    ) -> NSView {
        let card = NSStackView()
        card.orientation = .vertical
        card.alignment = .leading
        card.spacing = BuddyMonBrand.Menu.tightGap
        card.edgeInsets = NSEdgeInsets(
            top: BuddyMonBrand.Menu.compactGap,
            left: BuddyMonBrand.Menu.compactGap,
            bottom: BuddyMonBrand.Menu.compactGap,
            right: BuddyMonBrand.Menu.compactGap
        )
        card.widthAnchor.constraint(equalToConstant: Layout.identityWidth).isActive = true
        card.addArrangedSubview(text(
            role,
            color: BuddyMonBrand.Menu.mutedInk,
            font: BuddyMonBrand.Font.strong(8)
        ))

        let identity = NSStackView()
        identity.orientation = .horizontal
        identity.alignment = .centerY
        identity.spacing = BuddyMonBrand.Menu.compactGap
        identity.addArrangedSubview(sprite(pokemon))
        let labels = NSStackView()
        labels.orientation = .vertical
        labels.alignment = .leading
        labels.spacing = BuddyMonBrand.Menu.microGap
        let nameRow = NSStackView()
        nameRow.orientation = .horizontal
        nameRow.alignment = .centerY
        nameRow.spacing = BuddyMonBrand.Menu.microGap
        nameRow.addArrangedSubview(BuddyMonBrand.Menu.makeDisplayLabel(
            (pokemon["name"] as? String ?? "Pokémon").uppercased(),
            color: BuddyMonBrand.Menu.ink,
            pixel: BuddyMonBrand.Menu.displayButtonPixel
        ))
        nameRow.addArrangedSubview(BuddyMonBrand.Menu.makeRarityLabel(
            pokemon["rarity"] as? String
        ))
        labels.addArrangedSubview(nameRow)
        let level = pokemon[levelKey] as? Int ?? pokemon["level"] as? Int ?? 1
        labels.addArrangedSubview(text(
            "LVL. \(level)",
            color: BuddyMonBrand.Menu.ink,
            font: BuddyMonBrand.Font.strong(9)
        ))
        if let hpPercent {
            let hpRow = NSStackView()
            hpRow.orientation = .horizontal
            hpRow.alignment = .centerY
            hpRow.spacing = BuddyMonBrand.Menu.tightGap
            hpRow.addArrangedSubview(text(
                "HP",
                color: BuddyMonBrand.Menu.mutedInk,
                font: BuddyMonBrand.Font.strong(8)
            ))
            let progress = BuddyMonMenuProgressView(percent: hpPercent)
            progress.widthAnchor.constraint(
                equalToConstant: BuddyMonBrand.Menu.compactProgressWidth
            ).isActive = true
            progress.heightAnchor.constraint(
                equalToConstant: BuddyMonBrand.Menu.compactProgressHeight
            ).isActive = true
            hpRow.addArrangedSubview(progress)
            labels.addArrangedSubview(hpRow)
        }
        identity.addArrangedSubview(labels)
        card.addArrangedSubview(identity)
        BuddyMonBrand.Menu.applySurface(to: card, raised: true, bordered: false)
        return card
    }

    fileprivate static func sprite(_ pokemon: [String: Any]) -> NSImageView {
        let imageView = NSImageView()
        imageView.imageScaling = .scaleProportionallyUpOrDown
        imageView.wantsLayer = true
        imageView.layer?.magnificationFilter = .nearest
        if
            let encoded = pokemon["sprite_base64"] as? String,
            let data = Data(base64Encoded: encoded)
        {
            imageView.image = NSImage(data: data)
        }
        imageView.widthAnchor.constraint(
            equalToConstant: BuddyMonBrand.Menu.encounterSpriteSize
        ).isActive = true
        imageView.heightAnchor.constraint(
            equalToConstant: BuddyMonBrand.Menu.encounterSpriteSize
        ).isActive = true
        return imageView
    }

    private static func messageLine(_ message: String) -> NSView {
        let row = NSStackView()
        row.orientation = .horizontal
        row.alignment = .centerY
        row.spacing = BuddyMonBrand.Menu.compactGap
        row.edgeInsets = NSEdgeInsets(
            top: BuddyMonBrand.Menu.labelGap,
            left: BuddyMonBrand.Menu.microGap,
            bottom: BuddyMonBrand.Menu.labelGap,
            right: BuddyMonBrand.Menu.microGap
        )
        row.widthAnchor.constraint(equalToConstant: Layout.contentWidth).isActive = true
        row.addArrangedSubview(text(
            "▶  \(message)",
            color: BuddyMonBrand.Menu.ink,
            font: BuddyMonBrand.Font.strong(10)
        ))
        return row
    }

    private static func sizeButtons(_ buttons: [NSButton], availableWidth: CGFloat) {
        guard !buttons.isEmpty else { return }
        let gaps = BuddyMonBrand.Menu.actionGap * CGFloat(max(0, buttons.count - 1))
        let width = availableWidth - gaps
        let weights = buttons.map { CGFloat(max(1, $0.title.count + 2)) }
        let total = weights.reduce(0, +)
        for (index, button) in buttons.enumerated() {
            button.widthAnchor.constraint(
                equalToConstant: width * (weights[index] / total)
            ).isActive = true
        }
    }

    private static func footer() -> NSView {
        let row = NSStackView()
        row.orientation = .horizontal
        row.alignment = .centerY
        row.widthAnchor.constraint(equalToConstant: Layout.contentWidth).isActive = true
        row.addArrangedSubview(text(
            "ARROWS MOVE  ·  RETURN SELECTS  ·  ESC CLOSE",
            color: BuddyMonBrand.Menu.mutedInk,
            font: BuddyMonBrand.Font.strong(9)
        ))
        return row
    }

    private static func text(
        _ value: String,
        color: NSColor,
        font: NSFont
    ) -> NSTextField {
        let field = NSTextField(labelWithString: value)
        field.textColor = color
        field.font = font
        field.lineBreakMode = .byTruncatingTail
        field.maximumNumberOfLines = 1
        return field
    }
}

// MARK: - Encounter Result

final class BuddyMonCompactEncounterResultView: NSView {
    private enum Layout {
        static let width = BuddyMonBrand.Menu.panelWidth
        static let cardWidth = BuddyMonBrand.Menu.trainerCardWidth
        static let contentWidth = cardWidth - (BuddyMonBrand.Menu.cardPadding * 2)
    }

    private(set) var preferredSize = NSSize(
        width: Layout.width,
        height: BuddyMonBrand.Menu.resultPanelMinimumHeight
    )
    private(set) weak var initialResponder: NSView?
    private(set) var focusableControls: [NSButton] = []

    init(result: [String: Any],
        target: AnyObject,
        doneAction: Selector
    ) {
        let root = NSStackView()
        root.orientation = .vertical
        root.alignment = .leading
        root.spacing = BuddyMonBrand.Menu.sectionGap
        root.edgeInsets = NSEdgeInsets(
            top: BuddyMonBrand.Menu.cardPadding,
            left: BuddyMonBrand.Menu.cardPadding,
            bottom: BuddyMonBrand.Menu.cardPadding,
            right: BuddyMonBrand.Menu.cardPadding
        )
        let navigation = compactNavigationHeader(
            title: "ENCOUNTER COMPLETE",
            identifier: "encounter_result_back",
            target: target,
            action: doneAction,
            contentWidth: Layout.contentWidth
        )
        let back = navigation.back
        root.addArrangedSubview(navigation.view)

        let resultRow = NSStackView()
        resultRow.orientation = .horizontal
        resultRow.alignment = .centerY
        resultRow.spacing = BuddyMonBrand.Menu.cardPadding
        resultRow.edgeInsets = NSEdgeInsets(
            top: BuddyMonBrand.Menu.compactGap,
            left: BuddyMonBrand.Menu.compactGap,
            bottom: BuddyMonBrand.Menu.compactGap,
            right: BuddyMonBrand.Menu.compactGap
        )
        resultRow.widthAnchor.constraint(equalToConstant: Layout.contentWidth).isActive = true
        let wild = result["wild"] as? [String: Any] ?? [:]
        resultRow.addArrangedSubview(BuddyMonCompactEncounterView.sprite(wild))
        let copy = NSStackView()
        copy.orientation = .vertical
        copy.alignment = .leading
        copy.spacing = BuddyMonBrand.Menu.tightGap
        let titleRow = NSStackView()
        titleRow.orientation = .horizontal
        titleRow.alignment = .centerY
        titleRow.spacing = BuddyMonBrand.Menu.microGap
        titleRow.addArrangedSubview(BuddyMonBrand.Menu.makeDisplayLabel(
            (result["title"] as? String ?? "Encounter complete").uppercased(),
            color: BuddyMonBrand.Menu.ink,
            pixel: BuddyMonBrand.Menu.displayButtonPixel
        ))
        titleRow.addArrangedSubview(BuddyMonBrand.Menu.makeRarityLabel(
            wild["rarity"] as? String
        ))
        copy.addArrangedSubview(titleRow)
        copy.addArrangedSubview(Self.text(
            result["message"] as? String ?? "Your journey continues.",
            color: BuddyMonBrand.Menu.mutedInk,
            font: BuddyMonBrand.Font.strong(9)
        ))
        resultRow.addArrangedSubview(copy)
        BuddyMonBrand.Menu.applySurface(to: resultRow, raised: true, bordered: false)
        root.addArrangedSubview(resultRow)

        root.addArrangedSubview(Self.footer())

        let card = BuddyMonFieldGuideCardBackgroundView()
        card.addSubview(root)
        root.translatesAutoresizingMaskIntoConstraints = false

        super.init(frame: .zero)
        focusableControls = [back]
        initialResponder = back
        wantsLayer = true
        layer?.backgroundColor = BuddyMonBrand.Menu.canvas.cgColor
        addSubview(card)
        card.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            widthAnchor.constraint(equalToConstant: Layout.width),
            card.widthAnchor.constraint(equalToConstant: Layout.cardWidth),
            card.centerXAnchor.constraint(equalTo: centerXAnchor),
            card.topAnchor.constraint(
                equalTo: topAnchor,
                constant: BuddyMonBrand.Menu.fieldGuideFrameInset
            ),
            card.bottomAnchor.constraint(
                equalTo: bottomAnchor,
                constant: -BuddyMonBrand.Menu.fieldGuideFrameInset
            ),
            root.leadingAnchor.constraint(equalTo: card.leadingAnchor),
            root.trailingAnchor.constraint(equalTo: card.trailingAnchor),
            root.topAnchor.constraint(equalTo: card.topAnchor),
            root.bottomAnchor.constraint(equalTo: card.bottomAnchor),
        ])
        card.layoutSubtreeIfNeeded()
        preferredSize = NSSize(
            width: Layout.width,
            height: max(
                BuddyMonBrand.Menu.resultPanelMinimumHeight,
                card.fittingSize.height + (BuddyMonBrand.Menu.fieldGuideFrameInset * 2)
            )
        )
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    private static func footer() -> NSView {
        let row = NSStackView()
        row.orientation = .horizontal
        row.alignment = .centerY
        row.widthAnchor.constraint(equalToConstant: Layout.contentWidth).isActive = true
        row.addArrangedSubview(text(
            "RETURN SELECTS  ·  ESC CLOSE",
            color: BuddyMonBrand.Menu.mutedInk,
            font: BuddyMonBrand.Font.strong(9)
        ))
        return row
    }

    private static func text(
        _ value: String,
        color: NSColor,
        font: NSFont
    ) -> NSTextField {
        let field = NSTextField(labelWithString: value)
        field.textColor = color
        field.font = font
        field.lineBreakMode = .byTruncatingTail
        field.maximumNumberOfLines = 1
        return field
    }
}

// MARK: - Shared Components

private final class BuddyMonMenuProgressView: NSView {
    private let percent: CGFloat
    private let fillLayer = CALayer()

    init(percent: Int) {
        self.percent = CGFloat(min(100, max(0, percent))) / 100
        super.init(frame: .zero)
        wantsLayer = true
        layer?.backgroundColor = BuddyMonBrand.Menu.xpTrack.cgColor
        layer?.cornerRadius = BuddyMonBrand.Menu.progressCornerRadius
        layer?.masksToBounds = true
        fillLayer.backgroundColor = BuddyMonBrand.Menu.xpFill.cgColor
        fillLayer.cornerRadius = BuddyMonBrand.Menu.progressCornerRadius
        layer?.addSublayer(fillLayer)
    }

    required init?(coder: NSCoder) {
        nil
    }

    override func layout() {
        super.layout()
        fillLayer.frame = NSRect(
            x: 0,
            y: 0,
            width: bounds.width * percent,
            height: bounds.height
        )
    }
}
