import AppKit
import Foundation

struct RGBA: Equatable {
    let r: UInt8
    let g: UInt8
    let b: UInt8
    let a: UInt8

    init(_ r: UInt8, _ g: UInt8, _ b: UInt8, _ a: UInt8 = 255) {
        self.r = r
        self.g = g
        self.b = b
        self.a = a
    }
}

enum Palette {
    static let clear = RGBA(0, 0, 0, 0)
    static let canvas = RGBA(247, 241, 223)
    static let surface = RGBA(255, 249, 232)
    static let raised = RGBA(231, 223, 201)
    static let ink = RGBA(38, 34, 54)
    static let muted = RGBA(109, 102, 120)
    static let rule = RGBA(185, 174, 189)
    static let red = RGBA(217, 84, 98)
    static let water = RGBA(79, 143, 199)
    static let grass = RGBA(57, 137, 120)
    static let electric = RGBA(211, 154, 44)
    static let buddy = RGBA(114, 199, 169)
    static let buddyShadow = RGBA(59, 130, 111)
    static let buddyFace = RGBA(182, 228, 207)

    static let artColors: Set<String> = [
        clear, canvas, surface, raised, ink, muted, rule,
        red, water, grass, electric, buddy, buddyShadow, buddyFace,
    ].map { $0.key }.reduce(into: Set<String>()) { $0.insert($1) }
}

extension RGBA {
    var key: String { "\(r),\(g),\(b),\(a)" }
}

struct Point {
    let x: Int
    let y: Int
}

struct PixelCanvas {
    let width: Int
    let height: Int
    private(set) var pixels: [RGBA]

    init(width: Int, height: Int, fill: RGBA = Palette.clear) {
        self.width = width
        self.height = height
        self.pixels = Array(repeating: fill, count: width * height)
    }

    mutating func set(_ x: Int, _ y: Int, _ color: RGBA) {
        guard x >= 0, y >= 0, x < width, y < height else { return }
        pixels[y * width + x] = color
    }

    func colorAt(_ x: Int, _ y: Int) -> RGBA {
        pixels[y * width + x]
    }

    mutating func rect(_ x: Int, _ y: Int, _ w: Int, _ h: Int, _ color: RGBA) {
        guard w > 0, h > 0 else { return }
        for row in y..<(y + h) {
            for column in x..<(x + w) {
                set(column, row, color)
            }
        }
    }

    mutating func line(_ x1: Int, _ y1: Int, _ x2: Int, _ y2: Int, _ color: RGBA) {
        var x = x1
        var y = y1
        let dx = abs(x2 - x1)
        let sx = x1 < x2 ? 1 : -1
        let dy = -abs(y2 - y1)
        let sy = y1 < y2 ? 1 : -1
        var error = dx + dy
        while true {
            set(x, y, color)
            if x == x2 && y == y2 { break }
            let twice = 2 * error
            if twice >= dy {
                error += dy
                x += sx
            }
            if twice <= dx {
                error += dx
                y += sy
            }
        }
    }

    mutating func polygon(_ points: [Point], _ color: RGBA) {
        guard points.count >= 3 else { return }
        let minX = max(0, points.map(\.x).min() ?? 0)
        let maxX = min(width - 1, points.map(\.x).max() ?? 0)
        let minY = max(0, points.map(\.y).min() ?? 0)
        let maxY = min(height - 1, points.map(\.y).max() ?? 0)

        for y in minY...maxY {
            for x in minX...maxX {
                let px = Double(x) + 0.5
                let py = Double(y) + 0.5
                var inside = false
                var previous = points.count - 1
                for current in points.indices {
                    let a = points[current]
                    let b = points[previous]
                    let crosses = (Double(a.y) > py) != (Double(b.y) > py)
                    if crosses {
                        let edgeX = Double(b.x - a.x) * (py - Double(a.y))
                            / Double(b.y - a.y) + Double(a.x)
                        if px < edgeX { inside.toggle() }
                    }
                    previous = current
                }
                if inside { set(x, y, color) }
            }
        }
    }

    mutating func blit(_ source: PixelCanvas, x: Int, y: Int) {
        for sourceY in 0..<source.height {
            for sourceX in 0..<source.width {
                let color = source.colorAt(sourceX, sourceY)
                if color.a == 255 {
                    set(x + sourceX, y + sourceY, color)
                }
            }
        }
    }

    func resized(width targetWidth: Int, height targetHeight: Int) -> PixelCanvas {
        var target = PixelCanvas(width: targetWidth, height: targetHeight)
        for y in 0..<targetHeight {
            let sourceY = min(height - 1, y * height / targetHeight)
            for x in 0..<targetWidth {
                let sourceX = min(width - 1, x * width / targetWidth)
                target.set(x, y, colorAt(sourceX, sourceY))
            }
        }
        return target
    }

    func scaled(_ factor: Int) -> PixelCanvas {
        resized(width: width * factor, height: height * factor)
    }

    func pngData() throws -> Data {
        guard let rep = NSBitmapImageRep(
            bitmapDataPlanes: nil,
            pixelsWide: width,
            pixelsHigh: height,
            bitsPerSample: 8,
            samplesPerPixel: 4,
            hasAlpha: true,
            isPlanar: false,
            colorSpaceName: .deviceRGB,
            bitmapFormat: [],
            bytesPerRow: width * 4,
            bitsPerPixel: 32
        ), let data = rep.bitmapData else {
            throw NSError(domain: "BuddyMonConcepts", code: 1)
        }

        for (index, color) in pixels.enumerated() {
            let offset = index * 4
            data[offset] = color.r
            data[offset + 1] = color.g
            data[offset + 2] = color.b
            data[offset + 3] = color.a
        }
        guard let png = rep.representation(using: .png, properties: [:]) else {
            throw NSError(domain: "BuddyMonConcepts", code: 2)
        }
        return png
    }

    func write(to url: URL) throws {
        try pngData().write(to: url, options: .atomic)
    }
}

func writeICNS(_ entries: [(type: String, canvas: PixelCanvas)], to url: URL) throws {
    var body = Data()
    for entry in entries {
        let png = try entry.canvas.pngData()
        guard let type = entry.type.data(using: .ascii), type.count == 4 else {
            throw NSError(domain: "BuddyMonBrand", code: 5)
        }
        body.append(type)
        var chunkLength = UInt32(png.count + 8).bigEndian
        withUnsafeBytes(of: &chunkLength) { body.append(contentsOf: $0) }
        body.append(png)
    }

    var data = Data("icns".utf8)
    var totalLength = UInt32(body.count + 8).bigEndian
    withUnsafeBytes(of: &totalLength) { data.append(contentsOf: $0) }
    data.append(body)
    try data.write(to: url, options: .atomic)
}

enum PixelType {
    static let glyphs: [Character: [String]] = [
        " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
        "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
        "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
        "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
        "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
        "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
        "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
        "G": ["01111", "10000", "10000", "10111", "10001", "10001", "01111"],
        "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
        "I": ["01110", "00100", "00100", "00100", "00100", "00100", "01110"],
        "J": ["00111", "00010", "00010", "00010", "10010", "10010", "01100"],
        "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
        "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
        "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
        "N": ["10001", "11001", "10101", "10101", "10011", "10001", "10001"],
        "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
        "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
        "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
        "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
        "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
        "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
        "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
        "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
        "W": ["10001", "10001", "10001", "10101", "10101", "11011", "10001"],
        "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
        "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
        "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
        "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
        "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
        "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
        "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
        "/": ["00001", "00010", "00010", "00100", "01000", "01000", "10000"],
        "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    ]

    static func metrics(_ character: Character) -> (glyph: [String], leading: Int, width: Int) {
        let glyph = glyphs[character] ?? glyphs[" "]!
        if character == " " { return (glyph, 0, 3) }
        var first = 5
        var last = -1
        for row in glyph {
            for (column, bit) in row.enumerated() where bit == "1" {
                first = min(first, column)
                last = max(last, column)
            }
        }
        return last >= first ? (glyph, first, last - first + 1) : (glyph, 0, 3)
    }

    static func width(_ text: String, pixel: Int) -> Int {
        let characters = Array(text.uppercased())
        let glyphUnits = characters.reduce(0) { $0 + metrics($1).width }
        let tracking = max(0, characters.count - 1) * 3 * pixel / 2
        return glyphUnits * pixel + tracking
    }

    static func draw(
        _ text: String,
        on canvas: inout PixelCanvas,
        x: Int,
        y: Int,
        pixel: Int,
        color: RGBA,
        shadow: Bool = false
    ) {
        func paint(offsetX: Int, offsetY: Int, paint: RGBA) {
            var cursor = x
            for character in text.uppercased() {
                let glyphMetrics = metrics(character)
                for (rowIndex, row) in glyphMetrics.glyph.enumerated() {
                    for (columnIndex, bit) in row.enumerated() where bit == "1" {
                        canvas.rect(
                            cursor + (columnIndex - glyphMetrics.leading) * pixel + offsetX,
                            y + rowIndex * pixel + offsetY,
                            pixel,
                            pixel,
                            paint
                        )
                    }
                }
                cursor += glyphMetrics.width * pixel + 3 * pixel / 2
            }
        }
        if shadow { paint(offsetX: pixel, offsetY: pixel, paint: Palette.rule) }
        paint(offsetX: 0, offsetY: 0, paint: color)
    }
}

enum Direction: Int, CaseIterable {
    case signalPeek = 1
    case promptHatch = 2
    case firstSignal = 3

    var slug: String {
        switch self {
        case .signalPeek: return "signal-peek"
        case .promptHatch: return "prompt-hatch"
        case .firstSignal: return "first-signal"
        }
    }

    var title: String {
        switch self {
        case .signalPeek: return "SIGNAL PEEK"
        case .promptHatch: return "PROMPT HATCH"
        case .firstSignal: return "FIRST SIGNAL"
        }
    }
}

enum BuddyPose {
    case peeking
    case rising
    case greeting
}

func drawFrame(on canvas: inout PixelCanvas) {
    canvas.rect(0, 0, 128, 128, Palette.surface)
    canvas.polygon([
        Point(x: 7, y: 3), Point(x: 121, y: 3),
        Point(x: 125, y: 7), Point(x: 125, y: 121),
        Point(x: 121, y: 125), Point(x: 7, y: 125),
        Point(x: 3, y: 121), Point(x: 3, y: 7),
    ], Palette.ink)
    canvas.polygon([
        Point(x: 8, y: 7), Point(x: 120, y: 7),
        Point(x: 121, y: 8), Point(x: 121, y: 120),
        Point(x: 120, y: 121), Point(x: 8, y: 121),
        Point(x: 7, y: 120), Point(x: 7, y: 8),
    ], Palette.canvas)
    canvas.rect(10, 7, 38, 2, Palette.red)
    canvas.rect(7, 10, 2, 20, Palette.red)
    canvas.rect(80, 119, 38, 2, Palette.red)
    canvas.rect(119, 98, 2, 20, Palette.red)
    canvas.rect(12, 12, 104, 1, Palette.rule)
    canvas.rect(12, 115, 104, 1, Palette.rule)
    for x in stride(from: 15, through: 111, by: 8) {
        canvas.rect(x, 16, 1, 1, Palette.raised)
        canvas.rect(x + 3, 111, 1, 1, Palette.raised)
    }
}

func buddySprite(pose: BuddyPose) -> PixelCanvas {
    var sprite = PixelCanvas(width: 64, height: 64)

    // A tiny heart-shaped signal light keeps the tech cue friendly at 32 px.
    sprite.rect(31, 10, 3, 8, Palette.ink)
    sprite.rect(26, 0, 5, 3, Palette.ink)
    sprite.rect(34, 0, 5, 3, Palette.ink)
    sprite.rect(24, 2, 17, 5, Palette.ink)
    sprite.rect(26, 7, 13, 3, Palette.ink)
    sprite.rect(29, 10, 7, 3, Palette.ink)
    sprite.rect(27, 2, 4, 3, Palette.red)
    sprite.rect(34, 2, 4, 3, Palette.red)
    sprite.rect(26, 4, 13, 3, Palette.red)
    sprite.rect(28, 7, 9, 2, Palette.red)
    sprite.rect(31, 9, 3, 3, Palette.red)
    sprite.rect(27, 2, 2, 2, Palette.buddyFace)
    sprite.rect(42, 7, 4, 3, Palette.water)
    sprite.rect(47, 3, 3, 3, Palette.water)

    if pose != .peeking {
        sprite.polygon([
            Point(x: 21, y: 44), Point(x: 43, y: 44),
            Point(x: 49, y: 55), Point(x: 45, y: 63),
            Point(x: 19, y: 63), Point(x: 15, y: 55),
        ], Palette.ink)
        sprite.polygon([
            Point(x: 23, y: 46), Point(x: 41, y: 46),
            Point(x: 45, y: 55), Point(x: 42, y: 60),
            Point(x: 22, y: 60), Point(x: 19, y: 55),
        ], Palette.buddy)
        sprite.rect(26, 49, 12, 9, Palette.buddyFace)
        sprite.rect(23, 59, 8, 4, Palette.ink)
        sprite.rect(36, 59, 8, 4, Palette.ink)
    }

    // Original round companion silhouette with small side nubs and a soft chin.
    sprite.polygon([
        Point(x: 10, y: 27), Point(x: 5, y: 29),
        Point(x: 4, y: 36), Point(x: 9, y: 41),
        Point(x: 14, y: 38), Point(x: 14, y: 30),
    ], Palette.ink)
    sprite.polygon([
        Point(x: 9, y: 29), Point(x: 6, y: 31),
        Point(x: 6, y: 36), Point(x: 9, y: 39),
        Point(x: 12, y: 36), Point(x: 12, y: 31),
    ], Palette.buddyShadow)
    sprite.rect(8, 32, 3, 4, Palette.buddyFace)
    sprite.polygon([
        Point(x: 54, y: 27), Point(x: 59, y: 29),
        Point(x: 60, y: 36), Point(x: 55, y: 41),
        Point(x: 50, y: 38), Point(x: 50, y: 30),
    ], Palette.ink)
    sprite.polygon([
        Point(x: 55, y: 29), Point(x: 58, y: 31),
        Point(x: 58, y: 36), Point(x: 55, y: 39),
        Point(x: 52, y: 36), Point(x: 52, y: 31),
    ], Palette.buddyShadow)
    sprite.rect(53, 32, 3, 4, Palette.buddyFace)
    sprite.polygon([
        Point(x: 19, y: 14), Point(x: 43, y: 14),
        Point(x: 50, y: 18), Point(x: 55, y: 27),
        Point(x: 56, y: 39), Point(x: 51, y: 49),
        Point(x: 44, y: 54), Point(x: 20, y: 54),
        Point(x: 12, y: 49), Point(x: 8, y: 40),
        Point(x: 9, y: 27), Point(x: 14, y: 19),
    ], Palette.ink)
    sprite.polygon([
        Point(x: 20, y: 18), Point(x: 42, y: 18),
        Point(x: 47, y: 21), Point(x: 51, y: 29),
        Point(x: 52, y: 39), Point(x: 48, y: 45),
        Point(x: 42, y: 50), Point(x: 21, y: 50),
        Point(x: 16, y: 46), Point(x: 12, y: 39),
        Point(x: 13, y: 29), Point(x: 17, y: 22),
    ], Palette.buddy)
    sprite.rect(16, 36, 4, 8, Palette.buddyShadow)

    // A small sea-glass muzzle breaks up the mint face without turning the
    // companion into a pale porcelain mask.
    sprite.polygon([
        Point(x: 23, y: 34), Point(x: 41, y: 34),
        Point(x: 46, y: 39), Point(x: 43, y: 47),
        Point(x: 21, y: 47), Point(x: 18, y: 39),
    ], Palette.buddyFace)
    sprite.rect(23, 47, 18, 3, Palette.buddyShadow)

    // Chibi button eyes use stepped corners and two warm/blue glints.
    sprite.polygon([
        Point(x: 20, y: 24), Point(x: 27, y: 24),
        Point(x: 29, y: 27), Point(x: 29, y: 34),
        Point(x: 27, y: 37), Point(x: 20, y: 37),
        Point(x: 18, y: 34), Point(x: 18, y: 27),
    ], Palette.ink)
    sprite.polygon([
        Point(x: 38, y: 24), Point(x: 45, y: 24),
        Point(x: 47, y: 27), Point(x: 47, y: 34),
        Point(x: 45, y: 37), Point(x: 38, y: 37),
        Point(x: 36, y: 34), Point(x: 36, y: 27),
    ], Palette.ink)
    sprite.rect(20, 26, 3, 3, Palette.buddyFace)
    sprite.rect(38, 26, 3, 3, Palette.buddyFace)
    sprite.rect(25, 32, 2, 2, Palette.water)
    sprite.rect(43, 32, 2, 2, Palette.water)

    // Plump blush marks and a tiny cat-like smile.
    sprite.rect(14, 37, 5, 2, Palette.red)
    sprite.rect(15, 39, 3, 1, Palette.red)
    sprite.rect(47, 37, 5, 2, Palette.red)
    sprite.rect(48, 39, 3, 1, Palette.red)
    sprite.rect(31, 38, 3, 2, Palette.ink)
    sprite.rect(28, 40, 3, 1, Palette.ink)
    sprite.rect(34, 40, 3, 1, Palette.ink)
    sprite.rect(30, 41, 5, 1, Palette.ink)
    sprite.rect(31, 42, 3, 2, Palette.red)

    switch pose {
    case .peeking:
        sprite.polygon([
            Point(x: 13, y: 47), Point(x: 25, y: 47),
            Point(x: 28, y: 54), Point(x: 24, y: 60),
            Point(x: 14, y: 59), Point(x: 10, y: 53),
        ], Palette.ink)
        sprite.rect(14, 50, 10, 6, Palette.buddy)
        sprite.rect(17, 56, 5, 2, Palette.buddyShadow)
        sprite.polygon([
            Point(x: 39, y: 47), Point(x: 51, y: 47),
            Point(x: 54, y: 53), Point(x: 50, y: 59),
            Point(x: 40, y: 60), Point(x: 36, y: 54),
        ], Palette.ink)
        sprite.rect(40, 50, 10, 6, Palette.buddy)
        sprite.rect(42, 56, 5, 2, Palette.buddyShadow)
    case .rising:
        sprite.rect(8, 38, 5, 4, Palette.red)
        sprite.rect(3, 38, 3, 4, Palette.red)
    case .greeting:
        sprite.polygon([
            Point(x: 47, y: 43), Point(x: 57, y: 35),
            Point(x: 62, y: 39), Point(x: 53, y: 50),
        ], Palette.ink)
        sprite.polygon([
            Point(x: 49, y: 43), Point(x: 57, y: 38),
            Point(x: 59, y: 40), Point(x: 52, y: 47),
        ], Palette.buddy)
        sprite.rect(57, 38, 2, 2, Palette.buddyFace)
    }
    return sprite
}

func drawFrontTerminal(on canvas: inout PixelCanvas) {
    canvas.polygon([
        Point(x: 20, y: 69), Point(x: 108, y: 69),
        Point(x: 112, y: 73), Point(x: 112, y: 106),
        Point(x: 108, y: 110), Point(x: 20, y: 110),
        Point(x: 16, y: 106), Point(x: 16, y: 73),
    ], Palette.ink)
    canvas.rect(21, 74, 86, 30, Palette.muted)
    canvas.rect(26, 78, 64, 20, Palette.ink)
    canvas.rect(29, 82, 3, 3, Palette.water)
    canvas.rect(34, 84, 10, 3, Palette.water)
    canvas.rect(47, 84, 13, 3, Palette.rule)
    canvas.rect(29, 91, 18, 2, Palette.grass)
    canvas.rect(50, 91, 5, 2, Palette.surface)
    canvas.rect(96, 79, 5, 5, Palette.red)
    canvas.rect(101, 86, 3, 3, Palette.electric)
    canvas.rect(96, 92, 5, 3, Palette.water)
    canvas.rect(29, 103, 70, 3, Palette.raised)
    for x in stride(from: 31, through: 91, by: 6) {
        canvas.rect(x, 104, 3, 1, Palette.muted)
    }
    canvas.rect(28, 110, 72, 5, Palette.ink)
    canvas.rect(38, 110, 52, 2, Palette.rule)
    canvas.rect(22, 114, 9, 3, Palette.ink)
    canvas.rect(97, 114, 9, 3, Palette.ink)
}

func drawScene(_ direction: Direction, framed: Bool) -> PixelCanvas {
    var canvas = PixelCanvas(width: 128, height: 128)
    if framed { drawFrame(on: &canvas) }

    switch direction {
    case .signalPeek:
        canvas.blit(buddySprite(pose: .peeking), x: 32, y: 12)
        drawFrontTerminal(on: &canvas)
        canvas.rect(47, 67, 12, 5, Palette.ink)
        canvas.rect(49, 67, 8, 3, Palette.surface)
        canvas.rect(71, 67, 12, 5, Palette.ink)
        canvas.rect(73, 67, 8, 3, Palette.surface)

    case .promptHatch:
        canvas.polygon([
            Point(x: 17, y: 25), Point(x: 111, y: 25),
            Point(x: 115, y: 29), Point(x: 115, y: 101),
            Point(x: 111, y: 105), Point(x: 17, y: 105),
            Point(x: 13, y: 101), Point(x: 13, y: 29),
        ], Palette.ink)
        canvas.rect(18, 31, 92, 64, Palette.muted)
        canvas.rect(22, 35, 84, 56, Palette.raised)
        canvas.rect(26, 39, 76, 48, Palette.ink)
        for y in stride(from: 40, through: 80, by: 8) {
            canvas.rect(29, y, 5, 2, Palette.water)
            canvas.rect(36, y, 11 + (y % 3) * 3, 2, Palette.rule)
        }
        canvas.blit(buddySprite(pose: .rising), x: 32, y: 25)
        canvas.rect(19, 96, 4, 4, Palette.red)
        canvas.rect(26, 96, 4, 4, Palette.electric)
        canvas.rect(34, 97, 44, 2, Palette.rule)
        canvas.rect(82, 96, 22, 3, Palette.raised)
        canvas.rect(27, 104, 74, 5, Palette.ink)
        canvas.rect(38, 109, 52, 6, Palette.ink)
        canvas.rect(47, 109, 34, 2, Palette.rule)
        canvas.rect(98, 41, 3, 8, Palette.red)

    case .firstSignal:
        canvas.rect(24, 91, 80, 21, Palette.ink)
        canvas.rect(29, 95, 70, 10, Palette.muted)
        canvas.rect(37, 98, 54, 3, Palette.raised)
        canvas.polygon([
            Point(x: 17, y: 66), Point(x: 49, y: 56),
            Point(x: 54, y: 91), Point(x: 25, y: 100),
        ], Palette.ink)
        canvas.polygon([
            Point(x: 21, y: 69), Point(x: 46, y: 61),
            Point(x: 50, y: 87), Point(x: 28, y: 94),
        ], Palette.water)
        canvas.rect(27, 73, 14, 2, Palette.raised)
        canvas.rect(31, 79, 12, 2, Palette.surface)
        canvas.rect(34, 85, 10, 2, Palette.raised)
        canvas.polygon([
            Point(x: 79, y: 56), Point(x: 111, y: 66),
            Point(x: 103, y: 100), Point(x: 74, y: 91),
        ], Palette.ink)
        canvas.polygon([
            Point(x: 82, y: 61), Point(x: 107, y: 69),
            Point(x: 100, y: 94), Point(x: 78, y: 87),
        ], Palette.red)
        canvas.rect(87, 73, 14, 2, Palette.raised)
        canvas.rect(85, 79, 12, 2, Palette.surface)
        canvas.rect(84, 85, 10, 2, Palette.raised)
        canvas.rect(59, 70, 4, 4, Palette.electric)
        canvas.rect(66, 63, 4, 4, Palette.electric)
        canvas.rect(72, 72, 3, 3, Palette.electric)
        canvas.blit(buddySprite(pose: .greeting), x: 32, y: 22)
        canvas.rect(31, 112, 66, 5, Palette.ink)
        canvas.rect(45, 112, 38, 2, Palette.rule)
        canvas.rect(36, 117, 10, 2, Palette.ink)
        canvas.rect(82, 117, 10, 2, Palette.ink)
    }
    return canvas
}

func makeLockup(_ direction: Direction, dark: Bool) -> PixelCanvas {
    var canvas = PixelCanvas(width: 480, height: 112)
    let mark = drawScene(direction, framed: false).resized(width: 96, height: 96)
    canvas.blit(mark, x: 4, y: 8)
    let textColor = dark ? Palette.surface : Palette.ink
    PixelType.draw(
        "BUDDYMON",
        on: &canvas,
        x: 114,
        y: 30,
        pixel: 7,
        color: dark ? Palette.muted : Palette.rule
    )
    PixelType.draw(
        "BUDDYMON",
        on: &canvas,
        x: 112,
        y: 28,
        pixel: 7,
        color: textColor,
        shadow: false
    )
    canvas.rect(112, 88, 42, 4, Palette.red)
    canvas.rect(158, 88, 28, 4, Palette.water)
    canvas.rect(190, 88, 28, 4, Palette.grass)
    canvas.rect(222, 89, 244, 2, dark ? Palette.rule : Palette.muted)
    return canvas
}

func makeConceptBoard(_ direction: Direction) -> PixelCanvas {
    var board = PixelCanvas(width: 320, height: 328, fill: Palette.canvas)
    board.rect(0, 0, 320, 34, Palette.ink)
    PixelType.draw(
        "BUDDYMON / CONCEPT 0\(direction.rawValue)",
        on: &board,
        x: 12,
        y: 8,
        pixel: 2,
        color: Palette.surface
    )
    PixelType.draw(
        direction.title,
        on: &board,
        x: 12,
        y: 39,
        pixel: 2,
        color: Palette.red
    )

    let appIcon = drawScene(direction, framed: true)
    board.blit(appIcon, x: 12, y: 59)

    PixelType.draw("APP ICON", on: &board, x: 154, y: 61, pixel: 1, color: Palette.muted)
    let icon64 = appIcon.resized(width: 64, height: 64)
    let icon32 = appIcon.resized(width: 32, height: 32)
    board.blit(icon64, x: 154, y: 75)
    board.blit(icon32, x: 232, y: 96)
    PixelType.draw("64", on: &board, x: 174, y: 145, pixel: 1, color: Palette.ink)
    PixelType.draw("32", on: &board, x: 240, y: 134, pixel: 1, color: Palette.ink)

    PixelType.draw("MARK", on: &board, x: 272, y: 61, pixel: 1, color: Palette.muted)
    let mark = drawScene(direction, framed: false).resized(width: 40, height: 40)
    board.blit(mark, x: 272, y: 79)
    board.rect(271, 126, 42, 2, Palette.red)
    board.rect(271, 132, 42, 2, Palette.water)
    board.rect(271, 138, 42, 2, Palette.grass)
    board.rect(271, 144, 42, 2, Palette.electric)

    PixelType.draw("LIGHT LOCKUP", on: &board, x: 12, y: 195, pixel: 1, color: Palette.muted)
    board.rect(12, 207, 296, 52, Palette.surface)
    board.rect(12, 207, 296, 1, Palette.rule)
    board.rect(12, 258, 296, 1, Palette.rule)
    let lightLockup = makeLockup(direction, dark: false).resized(width: 282, height: 66)
    board.blit(lightLockup, x: 19, y: 200)

    PixelType.draw("DARK LOCKUP", on: &board, x: 12, y: 267, pixel: 1, color: Palette.muted)
    board.rect(12, 279, 296, 41, Palette.ink)
    let darkLockup = makeLockup(direction, dark: true).resized(width: 273, height: 64)
    board.blit(darkLockup, x: 20, y: 267)
    return board
}

func makeComparison(_ boards: [PixelCanvas]) -> PixelCanvas {
    var sheet = PixelCanvas(width: 780, height: 420, fill: Palette.surface)
    sheet.rect(0, 0, 780, 48, Palette.ink)
    PixelType.draw(
        "BUDDYMON / PIXEL BRAND CONCEPTS",
        on: &sheet,
        x: 20,
        y: 12,
        pixel: 3,
        color: Palette.surface
    )
    PixelType.draw(
        "ROUND SIGNAL BUDDY / MINT SIGNAL PALETTE / HAND PIXELED",
        on: &sheet,
        x: 20,
        y: 53,
        pixel: 1,
        color: Palette.muted
    )

    let previewSize = (width: 244, height: 250)
    for (index, board) in boards.enumerated() {
        let x = 12 + index * 256
        sheet.rect(x, 70, previewSize.width, previewSize.height, Palette.canvas)
        sheet.rect(x, 70, previewSize.width, 1, Palette.rule)
        sheet.rect(x, 319, previewSize.width, 1, Palette.rule)
        let preview = board.resized(width: previewSize.width, height: previewSize.height)
        sheet.blit(preview, x: x, y: 70)
    }

    PixelType.draw("PALETTE", on: &sheet, x: 20, y: 341, pixel: 1, color: Palette.muted)
    let colors = [
        Palette.canvas, Palette.surface, Palette.raised, Palette.ink,
        Palette.red, Palette.water, Palette.grass, Palette.electric,
        Palette.buddy, Palette.buddyShadow, Palette.buddyFace,
    ]
    for (index, color) in colors.enumerated() {
        let x = 20 + index * 40
        sheet.rect(x, 355, 32, 24, Palette.ink)
        sheet.rect(x + 2, 357, 28, 20, color)
    }
    PixelType.draw(
        "CONCEPT ONLY / NO SHIPPING ASSETS CHANGED",
        on: &sheet,
        x: 500,
        y: 358,
        pixel: 1,
        color: Palette.red
    )
    return sheet
}

enum SemanticIcon: String, CaseIterable {
    case brand
    case setup
    case activity
    case encounter
    case collection
    case nativeApp = "native-app"
    case privacy
    case development
}

func drawSemanticIcon(_ icon: SemanticIcon) -> PixelCanvas {
    var canvas = PixelCanvas(width: 16, height: 16)

    switch icon {
    case .brand:
        // Heart antenna, round signal face, and a tiny terminal ledge.
        canvas.rect(7, 1, 2, 2, Palette.red)
        canvas.set(6, 1, Palette.red)
        canvas.set(9, 1, Palette.red)
        canvas.set(7, 3, Palette.ink)
        canvas.set(8, 3, Palette.ink)
        canvas.rect(4, 4, 8, 1, Palette.ink)
        canvas.rect(3, 5, 10, 6, Palette.ink)
        canvas.rect(4, 5, 8, 6, Palette.buddy)
        canvas.rect(5, 7, 2, 2, Palette.ink)
        canvas.rect(9, 7, 2, 2, Palette.ink)
        canvas.set(5, 7, Palette.buddyFace)
        canvas.set(9, 7, Palette.buddyFace)
        canvas.rect(7, 9, 2, 1, Palette.red)
        canvas.rect(3, 12, 10, 3, Palette.ink)
        canvas.rect(4, 12, 8, 1, Palette.water)

    case .setup:
        // A welcoming prompt with the signal heart arriving above it.
        canvas.rect(2, 5, 12, 9, Palette.ink)
        canvas.rect(3, 6, 10, 6, Palette.surface)
        canvas.rect(4, 8, 2, 1, Palette.water)
        canvas.rect(6, 9, 2, 1, Palette.water)
        canvas.rect(9, 9, 3, 1, Palette.muted)
        canvas.rect(5, 13, 6, 2, Palette.ink)
        canvas.rect(7, 1, 2, 3, Palette.red)
        canvas.set(6, 1, Palette.red)
        canvas.set(9, 1, Palette.red)

    case .activity:
        // A local signal pulse growing into XP.
        canvas.rect(1, 8, 3, 2, Palette.muted)
        canvas.rect(4, 6, 2, 6, Palette.grass)
        canvas.rect(6, 3, 2, 11, Palette.buddy)
        canvas.rect(8, 6, 2, 6, Palette.water)
        canvas.rect(10, 8, 5, 2, Palette.muted)
        canvas.rect(11, 2, 3, 1, Palette.electric)
        canvas.rect(12, 1, 1, 3, Palette.electric)

    case .encounter:
        // Two signals meet around a compact capture core.
        canvas.line(2, 3, 7, 8, Palette.water)
        canvas.line(13, 3, 8, 8, Palette.red)
        canvas.rect(1, 2, 3, 3, Palette.ink)
        canvas.rect(12, 2, 3, 3, Palette.ink)
        canvas.rect(5, 6, 6, 6, Palette.ink)
        canvas.rect(6, 7, 4, 2, Palette.surface)
        canvas.rect(6, 9, 4, 2, Palette.buddy)
        canvas.rect(7, 8, 2, 1, Palette.electric)
        canvas.rect(7, 12, 2, 3, Palette.ink)

    case .collection:
        // A six-slot local box with one rare signal selected.
        canvas.rect(1, 2, 14, 12, Palette.ink)
        for row in 0..<2 {
            for column in 0..<3 {
                let x = 2 + column * 4
                let y = 3 + row * 5
                canvas.rect(x, y, 3, 4, Palette.surface)
            }
        }
        canvas.rect(6, 3, 3, 4, Palette.buddy)
        canvas.set(7, 4, Palette.ink)
        canvas.set(7, 5, Palette.red)
        canvas.rect(11, 9, 2, 2, Palette.water)

    case .nativeApp:
        // The menu-bar signal opening a compact Field Guide panel.
        canvas.rect(1, 2, 14, 2, Palette.ink)
        canvas.rect(11, 2, 2, 2, Palette.buddy)
        canvas.rect(3, 5, 10, 10, Palette.ink)
        canvas.rect(4, 6, 8, 7, Palette.surface)
        canvas.rect(5, 7, 2, 2, Palette.buddy)
        canvas.rect(8, 7, 3, 1, Palette.red)
        canvas.rect(8, 9, 3, 1, Palette.water)
        canvas.rect(5, 11, 6, 1, Palette.muted)

    case .privacy:
        // A local-only shield with a closed prompt lock.
        canvas.polygon([
            Point(x: 3, y: 3), Point(x: 8, y: 1), Point(x: 13, y: 3),
            Point(x: 12, y: 11), Point(x: 8, y: 15), Point(x: 4, y: 11),
        ], Palette.ink)
        canvas.polygon([
            Point(x: 5, y: 4), Point(x: 8, y: 3), Point(x: 11, y: 4),
            Point(x: 10, y: 10), Point(x: 8, y: 12), Point(x: 6, y: 10),
        ], Palette.buddy)
        canvas.rect(6, 7, 4, 4, Palette.ink)
        canvas.rect(7, 5, 2, 3, Palette.ink)
        canvas.set(8, 8, Palette.surface)

    case .development:
        // Code brackets around the same heart signal used by the mascot.
        canvas.line(5, 3, 2, 7, Palette.water)
        canvas.line(2, 7, 5, 11, Palette.water)
        canvas.line(11, 3, 14, 7, Palette.red)
        canvas.line(14, 7, 11, 11, Palette.red)
        canvas.line(9, 2, 7, 13, Palette.muted)
        canvas.rect(7, 6, 2, 3, Palette.buddy)
        canvas.set(6, 6, Palette.buddy)
        canvas.set(9, 6, Palette.buddy)
        canvas.set(7, 7, Palette.ink)
        canvas.set(8, 7, Palette.ink)
    }
    return canvas
}

func makeProductionLockup() -> PixelCanvas {
    var banner = PixelCanvas(width: 540, height: 136, fill: Palette.surface)
    banner.rect(0, 0, 540, 5, Palette.ink)
    banner.rect(0, 131, 540, 5, Palette.ink)
    banner.rect(0, 5, 5, 126, Palette.ink)
    banner.rect(535, 5, 5, 126, Palette.ink)
    banner.rect(10, 10, 118, 3, Palette.red)
    banner.rect(412, 123, 118, 3, Palette.water)
    banner.blit(makeLockup(.signalPeek, dark: false), x: 30, y: 12)
    return banner
}

func validate(_ canvas: PixelCanvas, name: String) throws {
    let invalidAlpha = canvas.pixels.contains { $0.a != 0 && $0.a != 255 }
    if invalidAlpha {
        throw NSError(
            domain: "BuddyMonConcepts",
            code: 3,
            userInfo: [NSLocalizedDescriptionKey: "\(name) contains partial alpha"]
        )
    }
    let invalidColor = canvas.pixels.contains { color in
        color.a == 255 && !Palette.artColors.contains(color.key)
    }
    if invalidColor {
        throw NSError(
            domain: "BuddyMonConcepts",
            code: 4,
            userInfo: [NSLocalizedDescriptionKey: "\(name) contains a non-brand color"]
        )
    }
}

guard CommandLine.arguments.count == 3 else {
    FileHandle.standardError.write(Data(
        "usage: render-brand-assets REPOSITORY_ROOT APP_ICONSET\n".utf8
    ))
    exit(2)
}

let repositoryRoot = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
let iconsetDirectory = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
let brandDirectory = repositoryRoot.appendingPathComponent("docs/assets/brand", isDirectory: true)
let iconDirectory = brandDirectory.appendingPathComponent("icons", isDirectory: true)
let appResourceDirectory = repositoryRoot.appendingPathComponent(
    "macos/BuddyMonApp/Resources",
    isDirectory: true
)
try FileManager.default.createDirectory(
    at: iconDirectory,
    withIntermediateDirectories: true
)
try FileManager.default.createDirectory(
    at: appResourceDirectory,
    withIntermediateDirectories: true
)
try FileManager.default.createDirectory(
    at: iconsetDirectory,
    withIntermediateDirectories: true
)

let appIcon = drawScene(.signalPeek, framed: true)
let mark = drawScene(.signalPeek, framed: false)
let lockup = makeProductionLockup()
try validate(appIcon, name: "app icon")
try validate(mark, name: "brand mark")
try validate(lockup, name: "brand lockup")

try appIcon.scaled(8).write(
    to: appResourceDirectory.appendingPathComponent("AppIcon.png")
)
try mark.scaled(2).write(
    to: brandDirectory.appendingPathComponent("buddymon-mark.png")
)
try lockup.scaled(2).write(
    to: brandDirectory.appendingPathComponent("buddymon-lockup.png")
)

for icon in SemanticIcon.allCases {
    let canvas = drawSemanticIcon(icon)
    try validate(canvas, name: icon.rawValue)
    try canvas.scaled(2).write(
        to: iconDirectory.appendingPathComponent("\(icon.rawValue).png")
    )
}

let iconsetSizes: [(String, Int)] = [
    ("icon_16x16.png", 16),
    ("icon_16x16@2x.png", 32),
    ("icon_32x32.png", 32),
    ("icon_32x32@2x.png", 64),
    ("icon_128x128.png", 128),
    ("icon_128x128@2x.png", 256),
    ("icon_256x256.png", 256),
    ("icon_256x256@2x.png", 512),
    ("icon_512x512.png", 512),
    ("icon_512x512@2x.png", 1024),
]
for (name, size) in iconsetSizes {
    try appIcon.resized(width: size, height: size).write(
        to: iconsetDirectory.appendingPathComponent(name)
    )
}

try writeICNS([
    ("icp4", appIcon.resized(width: 16, height: 16)),
    ("icp5", appIcon.resized(width: 32, height: 32)),
    ("icp6", appIcon.resized(width: 64, height: 64)),
    ("ic07", appIcon.resized(width: 128, height: 128)),
    ("ic08", appIcon.resized(width: 256, height: 256)),
    ("ic09", appIcon.resized(width: 512, height: 512)),
    ("ic10", appIcon.resized(width: 1024, height: 1024)),
], to: appResourceDirectory.appendingPathComponent("AppIcon.icns"))

print("Rendered BuddyMon production lockup, mark, app icon, and eight semantic icons.")
