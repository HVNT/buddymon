import AppKit
import Foundation
import QuartzCore

// MARK: - Token Detail

final class BuddyMonCompactTokensView: NSView {
    private enum Layout {
        static let width = BuddyMonBrand.Menu.panelWidth
        static let cardWidth = BuddyMonBrand.Menu.trainerCardWidth
        static let contentWidth = cardWidth - (BuddyMonBrand.Menu.cardPadding * 2)
        static let summaryWidth = (
            contentWidth - BuddyMonBrand.Menu.actionGap
        ) / 2
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
        let ids = ["day", "week"]
        for id in ids {
            let item = summary.first { $0["id"] as? String == id } ?? [:]
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

            let heading = NSStackView()
            heading.orientation = .horizontal
            heading.alignment = .firstBaseline
            heading.spacing = BuddyMonBrand.Menu.tightGap
            heading.addArrangedSubview(text(
                (item["label"] as? String ?? id).uppercased(),
                color: BuddyMonBrand.Menu.mutedInk,
                font: BuddyMonBrand.Font.strong(8)
            ))
            let headingSpacer = NSView()
            headingSpacer.setContentHuggingPriority(.defaultLow, for: .horizontal)
            heading.addArrangedSubview(headingSpacer)
            heading.addArrangedSubview(text(
                item["change"] as? String ?? "0%",
                color: BuddyMonBrand.Menu.ink,
                font: BuddyMonBrand.Font.strong(8)
            ))
            heading.widthAnchor.constraint(
                equalToConstant: Layout.summaryWidth
                    - (BuddyMonBrand.Menu.compactGap * 2)
            ).isActive = true
            cell.addArrangedSubview(heading)
            cell.addArrangedSubview(text(
                item["compact"] as? String ?? "0",
                color: BuddyMonBrand.Menu.ink,
                font: BuddyMonBrand.Font.strong(14)
            ))
            let comparisonLabel = (
                item["comparison_label"] as? String ?? "Previous"
            ).uppercased()
            let comparisonValue = item["comparison_compact"] as? String ?? "0"
            cell.addArrangedSubview(text(
                "\(comparisonLabel)  \(comparisonValue)",
                color: BuddyMonBrand.Menu.mutedInk,
                font: BuddyMonBrand.Font.strong(7)
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
