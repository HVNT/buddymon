import AppKit
import Foundation

/// Developer-only archive of the three visual directions that preceded
/// BuddyMonBrand. These values are historical evidence, never reusable tokens.
final class StyleArchiveView {
    let view: NSStackView

    private let void = ArchivedStyle(
        name: "A / VOID GRID", background: hex("070908"), panel: hex("0D1511"),
        ink: hex("E8FFE8"), muted: hex("7D9A83"), accent: hex("C7FF38"), hot: hex("FF5C35"),
        line: hex("314A36"), radius: 0, density: 10
    )
    private let night = ArchivedStyle(
        name: "B / NIGHTSHIFT", background: hex("090A13"), panel: hex("11152A"),
        ink: hex("F6F3FF"), muted: hex("9EA5C7"), accent: hex("5EEBFF"), hot: hex("B878FF"),
        line: hex("404B85"), radius: 12, density: 16
    )
    private let burn = ArchivedStyle(
        name: "C / AFTERBURN", background: hex("0B0A09"), panel: hex("18130F"),
        ink: hex("FFF7ED"), muted: hex("C2A997"), accent: hex("FF8A3D"), hot: hex("FFE36B"),
        line: hex("6D4630"), radius: 4, density: 22
    )

    init() {
        let root = NSStackView()
        root.orientation = .vertical
        root.alignment = .leading
        root.spacing = 32
        root.edgeInsets = NSEdgeInsets(top: 28, left: 28, bottom: 38, right: 28)
        root.wantsLayer = true
        root.layer?.backgroundColor = hex("050605").cgColor
        view = root

        root.addArrangedSubview(titleBlock())
        root.addArrangedSubview(section("01 / CANVAS + SURFACES", "How much atmosphere sits behind the game.", [
            surface(void), surface(night), surface(burn),
        ]))
        root.addArrangedSubview(section("02 / SPACING + DENSITY", "The same signal, with three physical rhythms.", [
            spacing(void, values: "04  08  12  16  24"), spacing(night, values: "04  08  14  20  28"), spacing(burn, values: "06  12  18  28  40"),
        ]))
        root.addArrangedSubview(section("03 / TYPOGRAPHY", "Read like an instrument panel, not an admin dashboard.", [
            typography(void, title: "PIKACHU//24", titleFont: BuddyMonBrand.Font.mono(18, weight: .bold), bodyFont: BuddyMonBrand.Font.mono(11)),
            typography(night, title: "PIKACHU // 24", titleFont: BuddyMonBrand.Font.mono(21, weight: .bold), bodyFont: BuddyMonBrand.Font.mono(11)),
            typography(burn, title: "PIKACHU // 24", titleFont: BuddyMonBrand.Font.mono(17, weight: .bold), bodyFont: BuddyMonBrand.Font.mono(12, weight: .medium)),
        ]))
        root.addArrangedSubview(section("04 / SECTION CHROME", "Three ways to make a screen feel like a destination.", [
            chrome(void, heading: "~/BUDDYMON $ PARTY"), chrome(night, heading: "PARTY / ACTIVE"), chrome(burn, heading: "party.bm"),
        ]))
        root.addArrangedSubview(section("05 / COMMAND CONTROLS", "Native buttons with a physical command-line edge.", [
            command(void, title: "[ ↵ CATCH ]"), command(night, title: "CATCH  ↵"), command(burn, title: "EXECUTE  ›"),
        ]))
        root.addArrangedSubview(section("06 / DATA + SPRITE FRAMES", "The active BuddyMon as a compact piece of hardware.", [
            record(void), record(night), record(burn),
        ]))
        root.addArrangedSubview(label("⌘⇧L  STYLE ARCHIVE   //   REFERENCE ONLY   //   NO GAME STATE CHANGED", color: hex("68806D"), font: BuddyMonBrand.Font.mono(10, weight: .medium)))
    }

    private func titleBlock() -> NSView {
        let stack = NSStackView()
        stack.orientation = .vertical; stack.alignment = .leading; stack.spacing = 7
        stack.addArrangedSubview(label("BUDDYMON", color: hex("F2FFF2"), font: BuddyMonBrand.Font.mono(34, weight: .bold)))
        stack.addArrangedSubview(label("ARCHIVED VISUAL EXPLORATIONS // NON-NORMATIVE", color: void.accent, font: BuddyMonBrand.Font.mono(12, weight: .bold)))
        stack.addArrangedSubview(label("Historical directions kept for reference. New work always follows BuddyMonBrand.", color: hex("8EA392"), font: BuddyMonBrand.Font.mono(11)))
        return stack
    }

    private func section(_ title: String, _ detail: String, _ samples: [NSView]) -> NSView {
        let stack = NSStackView(); stack.orientation = .vertical; stack.alignment = .leading; stack.spacing = 10
        stack.addArrangedSubview(label(title, color: hex("F0FFF0"), font: BuddyMonBrand.Font.mono(13, weight: .bold)))
        stack.addArrangedSubview(label(detail, color: hex("829287"), font: BuddyMonBrand.Font.mono(11)))
        let row = NSStackView(views: samples); row.orientation = .horizontal; row.alignment = .top; row.spacing = 14
        stack.addArrangedSubview(row)
        return stack
    }

    private func surface(_ style: ArchivedStyle) -> NSView {
        let card = canvas(style, height: 154)
        let grid = SignalGridView(style: style); card.addSubview(grid)
        grid.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([grid.leadingAnchor.constraint(equalTo: card.leadingAnchor), grid.trailingAnchor.constraint(equalTo: card.trailingAnchor), grid.topAnchor.constraint(equalTo: card.topAnchor), grid.bottomAnchor.constraint(equalTo: card.bottomAnchor)])
        let copy = vertical([label(style.name, color: style.accent, font: BuddyMonBrand.Font.mono(10, weight: .bold)), label("LOCAL / LIVE / UNCOMPLICATED", color: style.ink, font: BuddyMonBrand.Font.mono(12, weight: .bold)), label("black glass with a real pulse", color: style.muted, font: BuddyMonBrand.Font.mono(10))], spacing: 5)
        card.addSubview(copy); pin(copy, in: card, inset: 14)
        let mark = PixelMarkView(color: style.hot); card.addSubview(mark)
        mark.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([mark.trailingAnchor.constraint(equalTo: card.trailingAnchor, constant: -16), mark.bottomAnchor.constraint(equalTo: card.bottomAnchor, constant: -14), mark.widthAnchor.constraint(equalToConstant: 38), mark.heightAnchor.constraint(equalToConstant: 44)])
        return card
    }

    private func spacing(_ style: ArchivedStyle, values: String) -> NSView {
        let card = canvas(style, height: 132)
        let stack = vertical([label(style.name, color: style.accent, font: BuddyMonBrand.Font.mono(10, weight: .bold)), label(values, color: style.ink, font: BuddyMonBrand.Font.mono(11, weight: .medium)), bar(style, width: 184), label("PIKACHU   LV.24", color: style.ink, font: BuddyMonBrand.Font.mono(12, weight: .bold)), label("ELECTRIC // ACTIVE", color: style.muted, font: BuddyMonBrand.Font.mono(10))], spacing: style.density / 3)
        card.addSubview(stack); pin(stack, in: card, inset: style.density)
        return card
    }

    private func typography(_ style: ArchivedStyle, title: String, titleFont: NSFont, bodyFont: NSFont) -> NSView {
        let card = canvas(style, height: 132)
        let stack = vertical([label(style.name, color: style.accent, font: BuddyMonBrand.Font.mono(10, weight: .bold)), label(title, color: style.ink, font: titleFont), label("12,480 TOKENS  ·  ELECTRIC  ·  TODAY", color: style.muted, font: bodyFont), label("█████████░  92% CHARGED", color: style.hot, font: BuddyMonBrand.Font.mono(10, weight: .medium))], spacing: 7)
        card.addSubview(stack); pin(stack, in: card, inset: 14)
        return card
    }

    private func chrome(_ style: ArchivedStyle, heading: String) -> NSView {
        let card = canvas(style, height: 120)
        let stripe = NSView(); stripe.wantsLayer = true; stripe.layer?.backgroundColor = style.accent.cgColor
        card.addSubview(stripe); stripe.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([stripe.leadingAnchor.constraint(equalTo: card.leadingAnchor), stripe.topAnchor.constraint(equalTo: card.topAnchor), stripe.bottomAnchor.constraint(equalTo: card.bottomAnchor), stripe.widthAnchor.constraint(equalToConstant: style === night ? 5 : 2)])
        let stack = vertical([label(style.name, color: style.muted, font: BuddyMonBrand.Font.mono(10, weight: .bold)), label(heading, color: style.accent, font: BuddyMonBrand.Font.mono(15, weight: .bold)), bar(style, width: 192), label("06 CAUGHT  //  04 SPECIES  //  01 FAVORITE", color: style.ink, font: BuddyMonBrand.Font.mono(10))], spacing: 7)
        card.addSubview(stack); stack.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([stack.leadingAnchor.constraint(equalTo: card.leadingAnchor, constant: 16), stack.topAnchor.constraint(equalTo: card.topAnchor, constant: 14)])
        return card
    }

    private func command(_ style: ArchivedStyle, title: String) -> NSView {
        let card = canvas(style, height: 120)
        let stack = vertical([label(style.name, color: style.muted, font: BuddyMonBrand.Font.mono(10, weight: .bold))], spacing: 10)
        let button = NSButton(title: title, target: nil, action: nil)
        button.font = BuddyMonBrand.Font.mono(12, weight: .bold); button.contentTintColor = style.accent
        button.bezelStyle = .regularSquare; button.wantsLayer = true
        button.layer?.backgroundColor = style.background.cgColor; button.layer?.borderColor = style.accent.cgColor; button.layer?.borderWidth = 1; button.layer?.cornerRadius = style.radius
        stack.addArrangedSubview(button)
        stack.addArrangedSubview(label("ESC  CANCEL     ⌘↵  CONFIRM", color: style.muted, font: BuddyMonBrand.Font.mono(10)))
        card.addSubview(stack); pin(stack, in: card, inset: 14)
        return card
    }

    private func record(_ style: ArchivedStyle) -> NSView {
        let card = canvas(style, height: 138)
        let row = NSStackView(); row.orientation = .horizontal; row.alignment = .centerY; row.spacing = 12
        let mark = PixelMarkView(color: style.hot); NSLayoutConstraint.activate([mark.widthAnchor.constraint(equalToConstant: 42), mark.heightAnchor.constraint(equalToConstant: 52)])
        row.addArrangedSubview(mark)
        row.addArrangedSubview(vertical([label(style.name, color: style.accent, font: BuddyMonBrand.Font.mono(10, weight: .bold)), label("PIKACHU // LV.24", color: style.ink, font: BuddyMonBrand.Font.mono(12, weight: .bold)), label("ELECTRIC  ·  ★ ACTIVE", color: style.muted, font: BuddyMonBrand.Font.mono(10)), label("HP  092 / 100", color: style.hot, font: BuddyMonBrand.Font.mono(10, weight: .medium))], spacing: 5))
        card.addSubview(row); pin(row, in: card, inset: 14)
        return card
    }

    private func canvas(_ style: ArchivedStyle, height: CGFloat) -> NSView {
        let card = NSView(); card.wantsLayer = true
        card.layer?.backgroundColor = style.panel.cgColor; card.layer?.borderColor = style.line.cgColor; card.layer?.borderWidth = 1; card.layer?.cornerRadius = style.radius
        card.layer?.shadowColor = style.accent.cgColor; card.layer?.shadowOpacity = 0.12; card.layer?.shadowRadius = 14; card.layer?.shadowOffset = .zero
        NSLayoutConstraint.activate([card.widthAnchor.constraint(equalToConstant: 252), card.heightAnchor.constraint(equalToConstant: height)])
        return card
    }

    private func vertical(_ views: [NSView], spacing: CGFloat) -> NSStackView {
        let stack = NSStackView(views: views); stack.orientation = .vertical; stack.alignment = .leading; stack.spacing = spacing; return stack
    }
    private func bar(_ style: ArchivedStyle, width: CGFloat) -> NSView {
        let bar = NSView(); bar.wantsLayer = true; bar.layer?.backgroundColor = style.accent.cgColor
        NSLayoutConstraint.activate([bar.widthAnchor.constraint(equalToConstant: width), bar.heightAnchor.constraint(equalToConstant: 2)]); return bar
    }
    private func pin(_ child: NSView, in parent: NSView, inset: CGFloat) {
        child.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([child.leadingAnchor.constraint(equalTo: parent.leadingAnchor, constant: inset), child.topAnchor.constraint(equalTo: parent.topAnchor, constant: inset)])
    }
    private func label(_ string: String, color: NSColor, font: NSFont) -> NSTextField {
        let value = NSTextField(labelWithString: string); value.textColor = color; value.font = font; value.lineBreakMode = .byTruncatingTail; return value
    }
}

private final class ArchivedStyle {
    let name: String; let background: NSColor; let panel: NSColor; let ink: NSColor; let muted: NSColor; let accent: NSColor; let hot: NSColor; let line: NSColor; let radius: CGFloat; let density: CGFloat
    init(name: String, background: NSColor, panel: NSColor, ink: NSColor, muted: NSColor, accent: NSColor, hot: NSColor, line: NSColor, radius: CGFloat, density: CGFloat) {
        self.name = name; self.background = background; self.panel = panel; self.ink = ink; self.muted = muted; self.accent = accent; self.hot = hot; self.line = line; self.radius = radius; self.density = density
    }
}

private final class SignalGridView: NSView {
    private let style: ArchivedStyle
    init(style: ArchivedStyle) { self.style = style; super.init(frame: .zero); wantsLayer = true }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
    override func draw(_ dirtyRect: NSRect) {
        super.draw(dirtyRect)
        style.line.withAlphaComponent(0.38).setStroke()
        let grid = NSBezierPath(); let gap: CGFloat = 18
        stride(from: CGFloat(0), through: bounds.width, by: gap).forEach { grid.move(to: NSPoint(x: $0, y: 0)); grid.line(to: NSPoint(x: $0, y: bounds.height)) }
        stride(from: CGFloat(0), through: bounds.height, by: gap).forEach { grid.move(to: NSPoint(x: 0, y: $0)); grid.line(to: NSPoint(x: bounds.width, y: $0)) }
        grid.lineWidth = 0.5; grid.stroke()
    }
}

private final class PixelMarkView: NSView {
    private let color: NSColor
    init(color: NSColor) { self.color = color; super.init(frame: .zero); wantsLayer = true; layer?.shadowColor = color.cgColor; layer?.shadowOpacity = 0.65; layer?.shadowRadius = 7 }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
    override func draw(_ dirtyRect: NSRect) {
        super.draw(dirtyRect); color.setFill()
        let bolt = NSBezierPath(); let w = bounds.width; let h = bounds.height
        bolt.move(to: NSPoint(x: w * 0.58, y: h)); bolt.line(to: NSPoint(x: w * 0.12, y: h * 0.48)); bolt.line(to: NSPoint(x: w * 0.43, y: h * 0.48)); bolt.line(to: NSPoint(x: w * 0.28, y: 0)); bolt.line(to: NSPoint(x: w * 0.88, y: h * 0.62)); bolt.line(to: NSPoint(x: w * 0.58, y: h * 0.62)); bolt.close(); bolt.fill()
    }
}

private func hex(_ input: String) -> NSColor {
    let value = input.hasPrefix("#") ? String(input.dropFirst()) : input
    let number = Int(value, radix: 16) ?? 0
    return NSColor(calibratedRed: CGFloat((number >> 16) & 0xff) / 255, green: CGFloat((number >> 8) & 0xff) / 255, blue: CGFloat(number & 0xff) / 255, alpha: 1)
}
