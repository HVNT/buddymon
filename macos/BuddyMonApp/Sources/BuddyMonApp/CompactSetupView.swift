import AppKit
import Foundation

// MARK: - First-Run Setup

final class BuddyMonCompactStarterSetupView: NSView {
    private enum Layout {
        static let width = BuddyMonBrand.Menu.panelWidth
        static let cardWidth = BuddyMonBrand.Menu.trainerCardWidth
        static let contentWidth = cardWidth - (BuddyMonBrand.Menu.cardPadding * 2)
        static let columns = BuddyMonBrand.Menu.starterChoiceColumns
        static let choiceWidth = (
            contentWidth
                - (BuddyMonBrand.Menu.actionGap * CGFloat(columns - 1))
        ) / CGFloat(columns)
    }

    let preferredSize = NSSize(
        width: Layout.width,
        height: BuddyMonBrand.Menu.starterPanelMinimumHeight
    )
    private(set) weak var initialResponder: NSView?
    private(set) var focusableControls: [NSButton] = []

    init(target: AnyObject?, chooseAction: Selector?) {
        let root = NSStackView()
        root.orientation = .vertical
        root.alignment = .leading
        root.spacing = BuddyMonBrand.Menu.compactGap
        root.edgeInsets = NSEdgeInsets(
            top: BuddyMonBrand.Menu.cardPadding,
            left: BuddyMonBrand.Menu.cardPadding,
            bottom: BuddyMonBrand.Menu.cardPadding,
            right: BuddyMonBrand.Menu.cardPadding
        )

        root.addArrangedSubview(BuddyMonBrand.Menu.makeDisplayLabel(
            "FIRST SIGNAL",
            color: BuddyMonBrand.Menu.ink
        ))
        root.addArrangedSubview(Self.text(
            "A tiny local companion is looking for a trainer.",
            color: BuddyMonBrand.Menu.mutedInk,
            font: BuddyMonBrand.Font.regular(9)
        ))

        let starters: [(id: String, name: String, color: NSColor)] = [
            ("pikachu", "PIKACHU", BuddyMonBrand.Menu.pokemonElectric),
            ("charmander", "CHARMANDER", BuddyMonBrand.Menu.pokemonFire),
            ("bulbasaur", "BULBASAUR", BuddyMonBrand.Menu.pokemonGrass),
            ("squirtle", "SQUIRTLE", BuddyMonBrand.Menu.pokemonWater),
            ("eevee", "EEVEE", BuddyMonBrand.Menu.ink),
        ]
        var buttons: [NSButton] = []
        let grid = NSStackView()
        grid.orientation = .vertical
        grid.alignment = .leading
        grid.spacing = BuddyMonBrand.Menu.actionGap
        for start in stride(from: 0, to: starters.count, by: Layout.columns) {
            let row = NSStackView()
            row.orientation = .horizontal
            row.alignment = .centerY
            row.spacing = BuddyMonBrand.Menu.actionGap
            for starter in starters[start..<min(start + Layout.columns, starters.count)] {
                let button = BuddyMonBrand.Menu.makeStarterChoice(
                    starter.name,
                    identityColor: starter.color,
                    target: target,
                    action: chooseAction
                )
                button.identifier = NSUserInterfaceItemIdentifier(starter.id)
                button.setAccessibilityLabel(
                    "Choose \(starter.name) as your BuddyMon starter"
                )
                button.widthAnchor.constraint(
                    equalToConstant: Layout.choiceWidth
                ).isActive = true
                row.addArrangedSubview(button)
                buttons.append(button)
            }
            while row.arrangedSubviews.count < Layout.columns {
                let spacer = NSView()
                spacer.widthAnchor.constraint(
                    equalToConstant: Layout.choiceWidth
                ).isActive = true
                row.addArrangedSubview(spacer)
            }
            row.widthAnchor.constraint(equalToConstant: Layout.contentWidth).isActive = true
            grid.addArrangedSubview(row)
        }
        grid.widthAnchor.constraint(equalToConstant: Layout.contentWidth).isActive = true
        root.addArrangedSubview(grid)

        root.addArrangedSubview(Self.text(
            "FIRST MISSION  /  DO A LITTLE WORK, THEN CHECK BACK.",
            color: BuddyMonBrand.Menu.ink,
            font: BuddyMonBrand.Font.strong(8)
        ))
        root.addArrangedSubview(Self.flexibleVerticalSpacer())
        root.addArrangedSubview(Self.text(
            "ARROWS MOVE  ·  RETURN CHOOSE  ·  ESC CLOSE",
            color: BuddyMonBrand.Menu.mutedInk,
            font: BuddyMonBrand.Font.regular(7)
        ))

        let card = BuddyMonFieldGuideCardBackgroundView()
        card.addSubview(root)
        root.translatesAutoresizingMaskIntoConstraints = false

        super.init(frame: .zero)
        focusableControls = buttons
        initialResponder = buttons.first
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
        field.widthAnchor.constraint(equalToConstant: Layout.contentWidth).isActive = true
        return field
    }

    private static func flexibleVerticalSpacer() -> NSView {
        let spacer = NSView()
        spacer.setContentHuggingPriority(.defaultLow, for: .vertical)
        spacer.setContentCompressionResistancePriority(.defaultLow, for: .vertical)
        return spacer
    }
}

// MARK: - Compact Flow Notice

final class BuddyMonCompactNoticeView: NSView {
    enum Kind {
        case loading
        case error
    }

    private enum Layout {
        static let width = BuddyMonBrand.Menu.panelWidth
        static let cardWidth = BuddyMonBrand.Menu.trainerCardWidth
        static let contentWidth = cardWidth - (BuddyMonBrand.Menu.cardPadding * 2)
    }

    let preferredSize = NSSize(
        width: Layout.width,
        height: BuddyMonBrand.Menu.noticePanelMinimumHeight
    )
    let focusableControls: [NSButton] = []
    let initialResponder: NSView? = nil

    init(message: String, kind: Kind) {
        let root = NSStackView()
        root.orientation = .vertical
        root.alignment = .leading
        root.spacing = BuddyMonBrand.Menu.compactGap
        root.edgeInsets = NSEdgeInsets(
            top: BuddyMonBrand.Menu.cardPadding,
            left: BuddyMonBrand.Menu.cardPadding,
            bottom: BuddyMonBrand.Menu.cardPadding,
            right: BuddyMonBrand.Menu.cardPadding
        )

        root.addArrangedSubview(BuddyMonBrand.Menu.makeDisplayLabel(
            kind == .loading ? "WORKING" : "SIGNAL LOST",
            color: kind == .loading
                ? BuddyMonBrand.Menu.ink
                : BuddyMonBrand.Menu.alert
        ))
        root.addArrangedSubview(Self.messageView(message))
        root.addArrangedSubview(Self.flexibleVerticalSpacer())
        root.addArrangedSubview(Self.footer())

        let card = BuddyMonFieldGuideCardBackgroundView()
        card.addSubview(root)
        root.translatesAutoresizingMaskIntoConstraints = false

        super.init(frame: .zero)
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

    private static func messageView(_ message: String) -> NSTextField {
        let field = NSTextField(wrappingLabelWithString: message)
        field.font = BuddyMonBrand.Font.regular(9)
        field.textColor = BuddyMonBrand.Menu.ink
        field.lineBreakMode = .byWordWrapping
        field.maximumNumberOfLines = 7
        field.toolTip = message
        field.setAccessibilityLabel(message)
        field.widthAnchor.constraint(equalToConstant: Layout.contentWidth).isActive = true
        field.setContentHuggingPriority(.defaultLow, for: .vertical)
        field.setContentCompressionResistancePriority(.defaultLow, for: .vertical)
        return field
    }

    private static func footer() -> NSTextField {
        let field = NSTextField(labelWithString: "ESC  CLOSE")
        field.textColor = BuddyMonBrand.Menu.mutedInk
        field.font = BuddyMonBrand.Font.regular(7)
        return field
    }

    private static func flexibleVerticalSpacer() -> NSView {
        let spacer = NSView()
        spacer.setContentHuggingPriority(.defaultLow, for: .vertical)
        spacer.setContentCompressionResistancePriority(.defaultLow, for: .vertical)
        return spacer
    }
}
