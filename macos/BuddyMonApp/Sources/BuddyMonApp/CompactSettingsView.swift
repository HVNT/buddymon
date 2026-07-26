import AppKit
import Foundation
import QuartzCore

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
