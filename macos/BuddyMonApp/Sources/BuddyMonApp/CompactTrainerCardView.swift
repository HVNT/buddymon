import AppKit
import Foundation
import QuartzCore

// MARK: - Trainer Card

private final class BuddyMonTrainerPortraitView: NSView {
    override var isFlipped: Bool { true }

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
        setAccessibilityLabel("BuddyMon trainer silhouette")
    }

    required init?(coder: NSCoder) {
        nil
    }

    override func draw(_ dirtyRect: NSRect) {
        let pixel = BuddyMonBrand.Menu.trainerPortraitPixel
        let portraitWidth = CGFloat(Self.grid.first?.count ?? 0) * pixel
        let portraitHeight = CGFloat(Self.grid.count) * pixel
        let offsetX = (bounds.width - portraitWidth) / 2
        let offsetY = (bounds.height - portraitHeight) / 2
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

    var selectionLabel: String { badgeName.uppercased() }

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
    private var badgeTitleLabel: NSTextField?
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
            view["facts"] as? [[String: Any]] ?? []
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
        let badgeTitle = Self.text(
            "BADGES",
            color: BuddyMonBrand.Menu.mutedInk,
            font: BuddyMonBrand.Font.mono(7, weight: .bold)
        )
        badgeHeader.addArrangedSubview(badgeTitle)
        badgeHeader.addArrangedSubview(Self.flexibleSpacer())
        let rankStars = String(repeating: "★", count: starCount)
            + String(repeating: "☆", count: 4 - starCount)
        let rank = Self.text(
            "RANK \(rankStars)",
            color: BuddyMonBrand.Menu.mutedInk,
            font: BuddyMonBrand.Font.mono(7, weight: .bold)
        )
        rank.toolTip = "Trainer rank: \(starCount) of 4. Earn one rank for every two core badges."
        rank.setAccessibilityLabel("Trainer badge rank")
        rank.setAccessibilityValue("\(starCount) of 4")
        badgeHeader.addArrangedSubview(rank)
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
        badgeTitleLabel = badgeTitle
        for badge in badgeRail.buttons {
            badge.target = self
            badge.action = #selector(selectBadge(_:))
        }
        if
            let selectedID = view["selected_badge_id"] as? String,
            let selected = badgeRail.buttons.first(where: { $0.badgeID == selectedID })
        {
            badgeTitle.stringValue = selected.selectionLabel
            badgeTitle.textColor = BuddyMonBrand.Menu.ink
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
        badgeTitleLabel?.stringValue = sender.selectionLabel
        badgeTitleLabel?.textColor = BuddyMonBrand.Menu.ink
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

    private static func factGrid(_ facts: [[String: Any]]) -> NSView {
        let grid = NSGridView()
        grid.rowSpacing = BuddyMonBrand.Menu.labelGap
        grid.columnSpacing = BuddyMonBrand.Menu.microGap
        for fact in facts {
            grid.addRow(with: [factLabel(fact), factValue(fact)])
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
