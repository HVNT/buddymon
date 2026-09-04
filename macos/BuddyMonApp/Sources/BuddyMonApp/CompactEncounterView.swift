import AppKit
import Foundation
import QuartzCore

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
    private weak var messageIndicator: NSTextField?
    private weak var messageField: NSTextField?
    private var actionButtonsByID: [String: NSButton] = [:]

    init(
        view: [String: Any],
        message: String?,
        preferredActionID: String? = nil,
        target: AnyObject,
        action: Selector,
        backAction: Selector
    ) {
        let encounter = view["encounter"] as? [String: Any] ?? [:]
        var controls: [NSButton] = []
        var firstControl: NSView?
        var messageViews: (indicator: NSTextField, field: NSTextField)?
        var actionButtonsByID: [String: NSButton] = [:]
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
            let line = Self.messageLine(
                encounter["message"] as? String ?? "No wild Pokémon is waiting."
            )
            root.addArrangedSubview(line.view)
            messageViews = (line.indicator, line.field)
            controls = [back]
            firstControl = back
        } else {
            root.addArrangedSubview(Self.identityRow(encounter))
            let signal = message
                ?? encounter["message"] as? String
                ?? encounter["status"] as? String
                ?? "Choose your next move."
            let line = Self.messageLine(signal)
            root.addArrangedSubview(line.view)
            messageViews = (line.indicator, line.field)

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
                actionButtonsByID[identifier] = button
                actionRow.addArrangedSubview(button)
            }
            Self.sizeButtons(actionButtons, availableWidth: Layout.contentWidth)
            if !actionButtons.isEmpty {
                root.addArrangedSubview(actionRow)
            }
            controls = actionButtons + [back]
            firstControl = preferredActionID.flatMap { actionButtonsByID[$0] }
                ?? actionButtons.first
                ?? back
        }
        root.addArrangedSubview(Self.footer())

        let card = BuddyMonFieldGuideCardBackgroundView()
        card.addSubview(root)
        root.translatesAutoresizingMaskIntoConstraints = false

        super.init(frame: .zero)
        focusableControls = controls
        initialResponder = firstControl
        messageIndicator = messageViews?.indicator
        messageField = messageViews?.field
        self.actionButtonsByID = actionButtonsByID
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
        if message != nil {
            DispatchQueue.main.async { [weak self] in
                guard let indicator = self?.messageIndicator else { return }
                BuddyMonBrand.Motion.animateEncounterFeedback(indicator)
            }
        }
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    func beginAction(_ actionID: String) {
        let pendingMessage = Self.pendingMessage(for: actionID)
        messageField?.stringValue = pendingMessage
        messageField?.toolTip = pendingMessage
        messageField?.setAccessibilityLabel(pendingMessage)
        for (identifier, button) in actionButtonsByID {
            BuddyMonBrand.Menu.refreshActionButton(
                button,
                role: identifier == actionID ? .primary : .secondary,
                state: .loading
            )
            if identifier == actionID {
                button.setAccessibilityValue("In progress")
            }
        }
    }

    private static func pendingMessage(for actionID: String) -> String {
        switch actionID {
        case "attack", "fight": return "Your buddy attacks…"
        case "ball": return "Throwing a Ball…"
        case "rock": return "Throwing a Rock…"
        case "bait": return "Throwing Bait…"
        case "run": return "Getting away…"
        default: return "Making a move…"
        }
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

    private static func messageLine(
        _ message: String
    ) -> (view: NSView, indicator: NSTextField, field: NSTextField) {
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
        let indicator = text(
            "▶",
            color: BuddyMonBrand.Menu.ink,
            font: BuddyMonBrand.Font.strong(10)
        )
        let field = text(
            message,
            color: BuddyMonBrand.Menu.ink,
            font: BuddyMonBrand.Font.strong(10)
        )
        field.toolTip = message
        field.setAccessibilityLabel(message)
        field.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        row.addArrangedSubview(indicator)
        row.addArrangedSubview(field)
        return (row, indicator, field)
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
