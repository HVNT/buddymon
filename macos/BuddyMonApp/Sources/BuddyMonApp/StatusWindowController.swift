import AppKit
import Foundation

private final class KeyboardWindow: NSWindow {
    var keyHandler: ((NSEvent) -> Bool)?

    override func keyDown(with event: NSEvent) {
        if keyHandler?(event) == true {
            return
        }
        super.keyDown(with: event)
    }
}

final class StatusWindowController: NSWindowController {
    var contentHandler: ((NSView, NSSize) -> Void)?
    var keyboardHandlerChanged: (((NSEvent) -> Bool)?) -> Void = { _ in }

    init() {
        let window = KeyboardWindow(
            contentRect: NSRect(x: 0, y: 0, width: 560, height: 520),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = "BuddyMon — local console"
        window.backgroundColor = BuddyMonBrand.canvas
        window.appearance = NSAppearance(named: .darkAqua)
        window.isOpaque = true
        super.init(window: window)
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    func show(text: String) {
        let textView = NSTextView()
        textView.isEditable = false
        textView.isSelectable = true
        textView.isRichText = false
        textView.font = BuddyMonBrand.Font.mono(12)
        textView.textColor = BuddyMonBrand.textPrimary
        textView.backgroundColor = BuddyMonBrand.canvas
        textView.textContainerInset = NSSize(
            width: BuddyMonBrand.Spacing.panelPadding,
            height: BuddyMonBrand.Spacing.panelPadding
        )
        textView.string = text

        clearKeyboardControls()

        let scroll = NSScrollView(frame: window?.contentView?.bounds ?? .zero)
        scroll.autoresizingMask = [.width, .height]
        scroll.hasVerticalScroller = true
        scroll.autohidesScrollers = true
        scroll.drawsBackground = true
        scroll.backgroundColor = BuddyMonBrand.canvas
        textView.frame = scroll.contentView.bounds
        textView.minSize = NSSize(width: 0, height: scroll.contentSize.height)
        textView.maxSize = NSSize(
            width: CGFloat.greatestFiniteMagnitude,
            height: CGFloat.greatestFiniteMagnitude
        )
        textView.isVerticallyResizable = true
        textView.isHorizontallyResizable = false
        textView.autoresizingMask = [.width]
        textView.textContainer?.containerSize = NSSize(
            width: scroll.contentSize.width,
            height: CGFloat.greatestFiniteMagnitude
        )
        textView.textContainer?.widthTracksTextView = true
        scroll.documentView = textView
        window?.setContentSize(NSSize(width: 640, height: 460))
        window?.contentView = scroll
        present()
        resetScrollPosition(scroll)
    }

    func showLoading(_ title: String) {
        let root = NSStackView()
        root.orientation = .vertical
        root.alignment = .leading
        root.spacing = BuddyMonBrand.Spacing.small
        root.edgeInsets = NSEdgeInsets(
            top: BuddyMonBrand.Spacing.pageVertical,
            left: BuddyMonBrand.Spacing.pageHorizontal,
            bottom: BuddyMonBrand.Spacing.pageVertical,
            right: BuddyMonBrand.Spacing.pageHorizontal
        )

        let progress = NSProgressIndicator()
        progress.style = .spinning
        progress.controlSize = .large
        progress.startAnimation(nil)
        root.addArrangedSubview(progress)
        root.addArrangedSubview(label(
            title,
            color: BuddyMonBrand.textSecondary,
            font: BuddyMonBrand.Font.mono(15, weight: .medium)
        ))

        clearKeyboardControls()
        console(root)
        window?.setContentSize(NSSize(width: 420, height: 220))
        window?.contentView = root
        present()
    }

    func showConfirmation(
        title: String,
        message: String,
        confirmTitle: String,
        target: AnyObject,
        confirmSelector: Selector,
        cancelSelector: Selector
    ) {
        let root = NSStackView()
        root.orientation = .vertical
        root.alignment = .leading
        root.spacing = BuddyMonBrand.Spacing.medium
        root.edgeInsets = NSEdgeInsets(
            top: BuddyMonBrand.Spacing.pageVertical,
            left: BuddyMonBrand.Spacing.pageHorizontal,
            bottom: BuddyMonBrand.Spacing.pageVertical,
            right: BuddyMonBrand.Spacing.pageHorizontal
        )
        root.addArrangedSubview(label(
            "[ CONFIRM NETWORK ACTION ]",
            color: BuddyMonBrand.brand,
            font: BuddyMonBrand.Font.mono(11, weight: .bold)
        ))
        root.addArrangedSubview(label(
            title.uppercased(),
            font: BuddyMonBrand.Font.mono(20, weight: .bold)
        ))
        let detail = label(message, color: BuddyMonBrand.textSecondary)
        detail.maximumNumberOfLines = 0
        detail.lineBreakMode = .byWordWrapping
        detail.preferredMaxLayoutWidth = 480
        root.addArrangedSubview(detail)

        let actions = NSStackView()
        actions.orientation = .horizontal
        actions.alignment = .centerY
        actions.spacing = BuddyMonBrand.Spacing.controlGap
        let confirm = button(
            "[ \(confirmTitle.uppercased()) ]",
            target: target,
            action: confirmSelector,
            emphasized: true
        )
        let cancel = button(
            "[ CANCEL ]",
            target: target,
            action: cancelSelector
        )
        actions.addArrangedSubview(confirm)
        actions.addArrangedSubview(cancel)
        root.addArrangedSubview(actions)

        clearKeyboardControls()
        console(root)
        window?.setContentSize(NSSize(width: 560, height: 300))
        window?.contentView = root
        present()
        enableKeyboardControls(in: root, initial: confirm, escape: cancel)
    }

    func showStarterSetup(target: AnyObject, chooseSelector: Selector) {
        let root = NSStackView()
        root.orientation = .vertical
        root.alignment = .leading
        root.spacing = BuddyMonBrand.Spacing.screenGap
        root.edgeInsets = NSEdgeInsets(
            top: BuddyMonBrand.Spacing.pageVertical,
            left: BuddyMonBrand.Spacing.pageHorizontal,
            bottom: BuddyMonBrand.Spacing.pageVertical,
            right: BuddyMonBrand.Spacing.pageHorizontal
        )

        root.addArrangedSubview(label(
            "[ FIRST SIGNAL ]",
            color: BuddyMonBrand.brand,
            font: BuddyMonBrand.Font.mono(18, weight: .bold)
        ))
        root.addArrangedSubview(label(
            "A tiny local companion is looking for a trainer.",
            font: BuddyMonBrand.Font.mono(22, weight: .bold)
        ))
        root.addArrangedSubview(label(
            "Pick one. Do a little work. Come back for the next signal. Nothing leaves your Mac.",
            color: BuddyMonBrand.textSecondary
        ))

        let choices = NSStackView()
        choices.orientation = .horizontal
        choices.alignment = .top
        choices.spacing = BuddyMonBrand.Spacing.compact
        let starters: [(String, String, String, NSColor)] = [
            ("pikachu", "PIKACHU", "⚡", BuddyMonBrand.pikachu),
            ("charmander", "CHARMANDER", "🔥", BuddyMonBrand.brand),
            ("bulbasaur", "BULBASAUR", "🌿", BuddyMonBrand.starterGrass),
            ("squirtle", "SQUIRTLE", "💧", BuddyMonBrand.starterWater),
            ("eevee", "EEVEE", "✦", BuddyMonBrand.textPrimary),
        ]
        var firstButton: NSButton?
        for (id, name, mark, color) in starters {
            let card = NSStackView()
            card.orientation = .vertical
            card.alignment = .leading
            card.spacing = BuddyMonBrand.Spacing.compact
            card.addArrangedSubview(label(
                mark,
                color: color,
                font: BuddyMonBrand.Font.mono(30, weight: .bold)
            ))
            card.addArrangedSubview(label(
                name,
                color: color,
                font: BuddyMonBrand.Font.mono(11, weight: .bold)
            ))
            let choose = button(
                "Choose",
                target: target,
                action: chooseSelector,
                emphasized: id == "pikachu"
            )
            choose.identifier = NSUserInterfaceItemIdentifier(id)
            choose.setAccessibilityLabel("Choose \(name) as your BuddyMon starter")
            card.addArrangedSubview(choose)
            let surface = panel(card, padding: BuddyMonBrand.Spacing.panelPadding)
            NSLayoutConstraint.activate([
                surface.widthAnchor.constraint(equalToConstant: 126),
            ])
            choices.addArrangedSubview(surface)
            firstButton = firstButton ?? choose
        }
        root.addArrangedSubview(choices)
        root.addArrangedSubview(label(
            "FIRST MISSION  //  work normally for a few minutes, then check back.",
            color: BuddyMonBrand.textSecondary,
            font: BuddyMonBrand.Font.mono(11, weight: .medium)
        ))

        clearKeyboardControls()
        console(root)
        window?.setContentSize(NSSize(width: 760, height: 480))
        window?.contentView = root
        present()
        if let firstButton {
            enableKeyboardControls(in: root, initial: firstButton)
        }
    }

    private func present() {
        guard
            let contentHandler,
            let window,
            let content = window.contentView
        else { return }
        let size = window.contentLayoutRect.size
        window.contentView = NSView(frame: NSRect(origin: .zero, size: size))
        contentHandler(content, size)
    }

    private func label(
        _ text: String,
        color: NSColor = BuddyMonBrand.textPrimary,
        font: NSFont = BuddyMonBrand.Font.mono(13)
    ) -> NSTextField {
        let field = NSTextField(labelWithString: text)
        field.textColor = color
        field.font = font
        field.lineBreakMode = .byWordWrapping
        field.maximumNumberOfLines = 0
        return field
    }

    private func button(
        _ title: String,
        target: AnyObject,
        action: Selector,
        emphasized: Bool = false,
        state: BuddyMonBrand.ControlState = .normal
    ) -> NSButton {
        BuddyMonBrand.makeButton(
            title,
            target: target,
            action: action,
            role: emphasized ? .primary : .secondary,
            state: state
        )
    }

    private func clearKeyboardControls() {
        (window as? KeyboardWindow)?.keyHandler = nil
        keyboardHandlerChanged(nil)
    }

    private func enableKeyboardControls(
        in root: NSView,
        initial: NSButton? = nil,
        escape: NSButton? = nil
    ) {
        guard let window = window as? KeyboardWindow else { return }
        let controls = keyboardButtons(in: root).filter(\.isEnabled)
        guard !controls.isEmpty else {
            window.keyHandler = nil
            keyboardHandlerChanged(nil)
            return
        }

        var selectedIndex = controls.firstIndex { $0 === initial } ?? 0
        window.initialFirstResponder = controls[selectedIndex]
        controls[selectedIndex].window?.makeFirstResponder(controls[selectedIndex])
        DispatchQueue.main.async { [weak initialControl = controls[selectedIndex]] in
            initialControl?.window?.makeFirstResponder(initialControl)
        }

        let handler: (NSEvent) -> Bool = { event in
            guard event.modifierFlags.intersection([.command, .control, .option]).isEmpty else {
                return false
            }
            let character = event.charactersIgnoringModifiers?.lowercased()
            switch (event.keyCode, character) {
            case (126, _), (123, _), (_, "w"), (_, "a"):
                selectedIndex = (selectedIndex - 1 + controls.count) % controls.count
                controls[selectedIndex].window?.makeFirstResponder(controls[selectedIndex])
                return true
            case (125, _), (124, _), (_, "s"), (_, "d"):
                selectedIndex = (selectedIndex + 1) % controls.count
                controls[selectedIndex].window?.makeFirstResponder(controls[selectedIndex])
                return true
            case (36, _), (76, _), (49, _):
                controls[selectedIndex].performClick(nil)
                return true
            case (53, _):
                escape?.performClick(nil)
                return escape != nil
            default:
                return false
            }
        }
        window.keyHandler = handler
        keyboardHandlerChanged(handler)
    }

    private func keyboardButtons(in view: NSView) -> [NSButton] {
        let current = (view as? NSButton).map { [$0] } ?? []
        return current + view.subviews.flatMap(keyboardButtons(in:))
    }

    private func console(_ stack: NSStackView) {
        stack.wantsLayer = true
        stack.layer?.backgroundColor = BuddyMonBrand.canvas.cgColor
    }

    private func resetScrollPosition(_ scroll: NSScrollView) {
        let scrollToTop = { [weak scroll] in
            guard let scroll else { return }
            scroll.documentView?.layoutSubtreeIfNeeded()
            scroll.layoutSubtreeIfNeeded()
            scroll.contentView.scroll(to: .zero)
            scroll.reflectScrolledClipView(scroll.contentView)
        }
        scrollToTop()
        DispatchQueue.main.async(execute: scrollToTop)
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.05, execute: scrollToTop)
    }

    private func panel(
        _ content: NSView,
        padding: CGFloat = BuddyMonBrand.Spacing.panelPadding
    ) -> NSView {
        let frame = BuddyMonBrand.makeSurface()
        frame.addSubview(content)
        content.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            content.leadingAnchor.constraint(equalTo: frame.leadingAnchor, constant: padding),
            content.trailingAnchor.constraint(equalTo: frame.trailingAnchor, constant: -padding),
            content.topAnchor.constraint(equalTo: frame.topAnchor, constant: padding),
            content.bottomAnchor.constraint(equalTo: frame.bottomAnchor, constant: -padding),
        ])
        return frame
    }
}
