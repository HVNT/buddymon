import AppKit
import Foundation
import QuartzCore

// MARK: - Compact Menu

private final class BuddyMonTokenHeaderButton: NSButton {
    override var acceptsFirstResponder: Bool { isEnabled }

    override func resetCursorRects() {
        super.resetCursorRects()
        if isEnabled {
            addCursorRect(bounds, cursor: .pointingHand)
        }
    }
}

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
        let recoveryRequired = status["recovery_required"] as? Bool == true
        if status["error"] != nil {
            root.addArrangedSubview(Self.emptyCard(
                title: recoveryRequired ? "STATE NEEDS CARE" : "SIGNAL LOST",
                detail: recoveryRequired
                    ? (
                        status["recovery_summary"] as? String
                            ?? "File untouched. Restore or update BuddyMon."
                    )
                    : "Reconnecting to your local BuddyMon data.",
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
        if status["pending"] as? [String: Any] == nil && !recoveryRequired {
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
