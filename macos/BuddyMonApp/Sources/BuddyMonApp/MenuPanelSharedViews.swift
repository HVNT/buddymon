import AppKit
import Foundation
import QuartzCore

// MARK: - Shared Components

final class BuddyMonMenuFooterButton: NSButton {
    override func resetCursorRects() {
        super.resetCursorRects()
        if isEnabled {
            addCursorRect(bounds, cursor: .pointingHand)
        }
    }
}

func compactNavigationHeader(
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

final class BuddyMonFieldGuideCardBackgroundView: NSView {
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

final class BuddyMonMenuProgressView: NSView {
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
