import AppKit
import Foundation
import QuartzCore

#if BUDDYMON_DEVELOPMENT
private enum BrandPreviewMetric {
    static let contentWidth = BuddyMonBrand.Geometry.contentWidth
    static let contentInset = BuddyMonBrand.Spacing.large
    static let terminalInnerWidth = contentWidth - (BuddyMonBrand.Spacing.medium * 2)
}

/// Offline preview fixtures generated from BuddyMon's built-in `lib/sprites.py`
/// pixel art. The production views continue to consume runtime `sprite_base64`
/// payloads; these keep the style guide deterministic when no personal art pack
/// is installed.
private enum BrandPreviewSpriteData {
    static let base64: [String: String] = [
        "PIKACHU": "iVBORw0KGgoAAAANSUhEUgAAAGAAAABICAYAAAAJZ/BjAAAA60lEQVR42u3auw2AMAwFwMzCBNSsxHJswyL0sAAfBWFi0Fl6bRT5mshOKQ9V1w1rTda5T5Xa+5dsBQAAAAAAAABoVNkaGh0AAAAAAAAAAAAAAAAAAAAAAAAAFTmox4Z3wecDAAAAAAAAAADcA4heYUafDwAAAAAAAAAAcAEwjvvJNmCrvCcAAAAAAAAAAMA7q8pW39/L1wsAAAAAAAAA4CNX00anAwYAAAAAAAAAZANYptgEN+L701MAAAAAAAAAAIBfNBoAAAAAAAAAAOCVZygAAAAAAAAAAMBFo4NXhj5mAQAAAAAAAABOawPSDZCM4/jv4AAAAABJRU5ErkJggg==",
        "BULBASAUR": "iVBORw0KGgoAAAANSUhEUgAAAGAAAABICAYAAAAJZ/BjAAAA4ElEQVR42u3bsQmAMBAF0MziGIKj2DmY4Bz2juAYbqALGIvgqZh38NsI/zXBJCm9NMMy7mfppj40ue+m2gYAAAAAAAAA8NOiwQAAAAAAAAAA3i36rwEAAAAAAAAAACgDyE3TtKf52voAAAAAAAAAAABlALki7iooen0AAAAAAAAAAAA/4wAAAAAAAAAANQNEw0RvK6u7GQcAAAAAAAAAsG31ShIAAAAAAAAA8AGAeVtDAwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADAM0VHHxk6qgQAAAAAAAAAXM4Bxvxxfv2KPPAAAAAASUVORK5CYII=",
        "SQUIRTLE": "iVBORw0KGgoAAAANSUhEUgAAAGAAAABICAYAAAAJZ/BjAAAA60lEQVR42u3awQ2EIBAFUGqxDE9bxpayJXm0BMuxC7YBPWiYCM77yVwhzLtMgFIeynfZa09VsgUAAAAAAAAAkKzR6WAAAAAAAAAAABr9bhgAAAAAAAAAwCAAZ5mm+bB6Wx8AAAAAAAAAAOAewFkjWjUoen0AAAAAAAAAAACXcQAAAAAAAAAA/4XiYKLHSj/jAAAAAAAAAAA5x9aSLQAAAAAAAACARll/n3pUVwHqvoXWVYBW5wIAAAAAAAAAAHgHQHdjLgAAAAAAAAAAwKNjqMs4AAAAAAAAIBtA9NPjKPsCAAAAAAAAAAYB+APy7cg909ZTpQAAAABJRU5ErkJggg==",
    ]
}

/// Living visual reference for BuddyMonBrand. Shipping views and this guide use
/// the same tokens; Style Archive remains only as a non-normative comparison.
final class BrandStylesWindowController: NSWindowController {
    static let shared = BrandStylesWindowController()

    private var didPositionWindow = false
    private weak var previewScrollView: NSScrollView?
    private var officialSpriteCache: [String: NSImage] = [:]

    private init() {
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 980, height: 760),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = "BuddyMon // Brand Styles"
        window.backgroundColor = BuddyMonBrand.canvas
        window.appearance = NSAppearance(named: .darkAqua)
        window.contentMinSize = NSSize(
            width: BrandPreviewMetric.contentWidth + (BrandPreviewMetric.contentInset * 2),
            height: 560
        )
        super.init(window: window)
        window.contentView = makeScreen()
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    func present() {
        if !didPositionWindow {
            window?.center()
            didPositionWindow = true
        }
        showWindow(nil)
        window?.makeKeyAndOrderFront(nil)
        window?.makeFirstResponder(nil)
        NSApp.activate(ignoringOtherApps: true)
        for delay in [0.0, 0.05, 0.20] {
            DispatchQueue.main.asyncAfter(deadline: .now() + delay) { [weak self] in
                self?.scrollToTop()
            }
        }
    }

    /// Renders the entire scroll document at a stable 1x scale for visual QA.
    /// Tests point XDG_STATE_HOME at an empty directory so optional personal
    /// sprites cannot make the reference image machine-dependent.
    func writeSnapshot(to url: URL) throws {
        guard
            let scroll = previewScrollView,
            let document = scroll.documentView
        else {
            throw BrandSnapshotError.missingDocument
        }

        window?.contentView?.layoutSubtreeIfNeeded()
        scroll.layoutSubtreeIfNeeded()
        document.layoutSubtreeIfNeeded()

        let fitting = document.fittingSize
        let width = max(
            BrandPreviewMetric.contentWidth + (BrandPreviewMetric.contentInset * 2),
            fitting.width
        )
        let height = max(scroll.contentSize.height, fitting.height)
        guard width > 0, height > 0 else {
            throw BrandSnapshotError.invalidSize
        }

        document.setFrameSize(NSSize(width: width, height: height))
        document.layoutSubtreeIfNeeded()
        freezeAnimations(in: document)
        let bounds = NSRect(origin: .zero, size: document.frame.size)
        guard let bitmap = NSBitmapImageRep(
            bitmapDataPlanes: nil,
            pixelsWide: Int(ceil(bounds.width)),
            pixelsHigh: Int(ceil(bounds.height)),
            bitsPerSample: 8,
            samplesPerPixel: 4,
            hasAlpha: true,
            isPlanar: false,
            colorSpaceName: .deviceRGB,
            bytesPerRow: 0,
            bitsPerPixel: 0
        ) else {
            throw BrandSnapshotError.cannotCreateBitmap
        }
        bitmap.size = bounds.size
        document.cacheDisplay(in: bounds, to: bitmap)
        guard let png = bitmap.representation(using: .png, properties: [:]) else {
            throw BrandSnapshotError.cannotEncodePNG
        }
        try png.write(to: url, options: .atomic)
    }

    private func freezeAnimations(in view: NSView) {
        view.layer?.removeAllAnimations()
        for subview in view.subviews {
            freezeAnimations(in: subview)
        }
    }

    private func makeScreen() -> NSView {
        let scroll = NSScrollView(frame: NSRect(x: 0, y: 0, width: 980, height: 760))
        scroll.autoresizingMask = [.width, .height]
        scroll.hasVerticalScroller = true
        scroll.autohidesScrollers = true
        scroll.drawsBackground = true
        scroll.backgroundColor = BuddyMonBrand.canvas
        previewScrollView = scroll

        let document = BrandPreviewFlippedDocumentView()
        document.translatesAutoresizingMaskIntoConstraints = false
        scroll.documentView = document

        let root = vertical(spacing: BuddyMonBrand.Spacing.large)
        root.alignment = .leading
        root.edgeInsets = NSEdgeInsets(
            top: BrandPreviewMetric.contentInset,
            left: BrandPreviewMetric.contentInset,
            bottom: BuddyMonBrand.Spacing.xlarge,
            right: BrandPreviewMetric.contentInset
        )
        document.addSubview(root)
        root.translatesAutoresizingMaskIntoConstraints = false

        let mastheadView = masthead()
        let terminalView = terminal()
        let storyView = sharedContextStories()
        let workbenchView = componentWorkbench()
        let footnoteView = footnote()
        for view in [mastheadView, terminalView, storyView, workbenchView, footnoteView] {
            root.addArrangedSubview(view)
            view.widthAnchor.constraint(equalToConstant: BrandPreviewMetric.contentWidth).isActive = true
        }
        root.setCustomSpacing(BuddyMonBrand.Spacing.section, after: terminalView)
        root.setCustomSpacing(BuddyMonBrand.Spacing.section, after: storyView)
        root.setCustomSpacing(BuddyMonBrand.Spacing.section, after: workbenchView)

        NSLayoutConstraint.activate([
            document.widthAnchor.constraint(equalTo: scroll.contentView.widthAnchor),
            root.leadingAnchor.constraint(equalTo: document.leadingAnchor),
            root.trailingAnchor.constraint(equalTo: document.trailingAnchor),
            root.topAnchor.constraint(equalTo: document.topAnchor),
            root.bottomAnchor.constraint(equalTo: document.bottomAnchor),
        ])
        return scroll
    }

    private func scrollToTop() {
        guard let scroll = previewScrollView else { return }
        scroll.documentView?.layoutSubtreeIfNeeded()
        scroll.layoutSubtreeIfNeeded()
        scroll.contentView.scroll(to: .zero)
        scroll.reflectScrolledClipView(scroll.contentView)
    }

    private func masthead() -> NSView {
        let stack = vertical(spacing: BuddyMonBrand.Spacing.compact)
        stack.addArrangedSubview(text(
            "B U D D Y M O N  / /  B R A N D  S Y S T E M",
            color: BuddyMonBrand.textPrimary,
            font: BuddyMonBrand.Font.strong(24)
        ))
        stack.addArrangedSubview(text(
            "REDLINE MONO // color belongs to Pokemon, rarity, and signal—not interface furniture.",
            color: BuddyMonBrand.textSecondary,
            font: BuddyMonBrand.Font.regular(11)
        ))
        stack.addArrangedSubview(text(
            "================================================================================================================",
            color: BuddyMonBrand.brand,
            font: BuddyMonBrand.Font.regular(10)
        ))
        return stack
    }

    private func terminal() -> NSView {
        let surface = BuddyMonBrand.makeSurface()

        let content = vertical(spacing: BuddyMonBrand.Spacing.medium)
        content.alignment = .leading
        content.edgeInsets = NSEdgeInsets(
            top: BuddyMonBrand.Spacing.medium,
            left: BuddyMonBrand.Spacing.medium,
            bottom: BuddyMonBrand.Spacing.medium,
            right: BuddyMonBrand.Spacing.medium
        )
        surface.addSubview(content)
        content.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            content.leadingAnchor.constraint(equalTo: surface.leadingAnchor),
            content.trailingAnchor.constraint(equalTo: surface.trailingAnchor),
            content.topAnchor.constraint(equalTo: surface.topAnchor),
            content.bottomAnchor.constraint(equalTo: surface.bottomAnchor),
        ])

        let header = terminalHeader()
        content.addArrangedSubview(header)
        header.widthAnchor.constraint(equalToConstant: BrandPreviewMetric.terminalInnerWidth).isActive = true
        content.addArrangedSubview(text(
            "--------------------------------------------------------------------------------------------------------------",
            color: BuddyMonBrand.rule,
            font: BuddyMonBrand.Font.regular(10)
        ))
        content.addArrangedSubview(bootSequence())
        let readout = twoColumnReadout()
        content.addArrangedSubview(readout)
        readout.widthAnchor.constraint(equalToConstant: BrandPreviewMetric.terminalInnerWidth).isActive = true
        content.addArrangedSubview(activityLog())
        let commands = commandLine()
        content.addArrangedSubview(commands)
        commands.widthAnchor.constraint(equalToConstant: BrandPreviewMetric.terminalInnerWidth).isActive = true
        return surface
    }

    private func terminalHeader() -> NSView {
        let row = horizontal(spacing: BuddyMonBrand.Spacing.small)
        row.alignment = .centerY
        row.addArrangedSubview(text("[::]", color: BuddyMonBrand.brand, font: BuddyMonBrand.Font.strong(11)))
        row.addArrangedSubview(text("tty.buddymon.local", color: BuddyMonBrand.textPrimary, font: BuddyMonBrand.Font.strong(11)))
        row.addArrangedSubview(flexibleSpace())
        row.addArrangedSubview(text("PID 025", color: BuddyMonBrand.textSecondary, font: BuddyMonBrand.Font.regular(10)))
        row.addArrangedSubview(text("LOCAL_ONLY", color: BuddyMonBrand.textPrimary, font: BuddyMonBrand.Font.strong(10)))
        return row
    }

    private func bootSequence() -> NSView {
        let stack = vertical(spacing: BuddyMonBrand.Spacing.micro)
        stack.addArrangedSubview(text("$ buddymon --attach local", color: BuddyMonBrand.textPrimary, font: BuddyMonBrand.Font.strong(12)))
        stack.addArrangedSubview(text("[ok] state mounted     [ok] journal linked     [ok] sprite channel ready", color: BuddyMonBrand.textPrimary, font: BuddyMonBrand.Font.regular(11)))
        stack.addArrangedSubview(text("session resumed in 0.018s", color: BuddyMonBrand.textSecondary, font: BuddyMonBrand.Font.regular(10)))
        return stack
    }

    private func twoColumnReadout() -> NSView {
        let left = terminalBlock(
            title: "01::ACTIVE_BUDDY",
            body: """
            +---------------------------------------+
            | ID       025                          |
            | HANDLE   PIKACHU                      |
            | CLASS    ELECTRIC / ACTIVE            |
            | LEVEL    24                           |
            | XP       [#############.......]  64%  |
            | STATUS   READY                        |
            +---------------------------------------+
            """,
            highlights: [
                "PIKACHU": BuddyMonBrand.pikachu,
                "ELECTRIC": BuddyMonBrand.pikachu,
            ]
        )
        let right = terminalBlock(
            title: "02::LIVE_SIGNAL",
            body: """
            +---------------------------------------+
            | TOKENS   012,480                      |
            | TODAY    +003,942                     |
            | STREAK   07 DAYS                      |
            | SOURCE   CODEX / ATTACHED             |
            | ROSTER   BULBASAUR SQUIRTLE PIKACHU   |
            | PULSE    [||||||||||..........]  50%  |
            +---------------------------------------+
            """,
            highlights: [
                "BULBASAUR": BuddyMonBrand.starterGrass,
                "SQUIRTLE": BuddyMonBrand.starterWater,
                "PIKACHU": BuddyMonBrand.pikachu,
            ]
        )

        let row = horizontal(spacing: BuddyMonBrand.Spacing.medium)
        row.alignment = .top
        row.distribution = .fill
        row.addArrangedSubview(left)
        row.addArrangedSubview(right)
        left.widthAnchor.constraint(equalTo: right.widthAnchor).isActive = true
        return row
    }

    private func terminalBlock(
        title: String,
        body: String,
        highlights: [String: NSColor] = [:]
    ) -> NSView {
        let stack = vertical(spacing: BuddyMonBrand.Spacing.compact)
        stack.addArrangedSubview(text(title, color: BuddyMonBrand.textPrimary, font: BuddyMonBrand.Font.strong(10)))
        stack.addArrangedSubview(highlightedText(
            body,
            font: BuddyMonBrand.Font.regular(11),
            highlights: highlights,
            lineSpacing: 3
        ))
        return stack
    }

    private func activityLog() -> NSView {
        let stack = vertical(spacing: BuddyMonBrand.Spacing.compact)
        stack.addArrangedSubview(text("03::TAIL /journey.log", color: BuddyMonBrand.textPrimary, font: BuddyMonBrand.Font.strong(10)))
        stack.addArrangedSubview(highlightedText(
            """
            14:02:11  +280 xp    prompt completed                 source=codex
            14:06:43  +910 xp    tool chain resolved              streak=07
            14:09:02  ★ RARE     a faint signal moved nearby      zone=local
            """,
            font: BuddyMonBrand.Font.regular(11),
            highlights: ["★ RARE": BuddyMonBrand.rarity],
            lineSpacing: 5
        ))
        return stack
    }

    private func commandLine() -> NSView {
        let stack = vertical(spacing: BuddyMonBrand.Spacing.small)
        stack.addArrangedSubview(text(
            "[⌘1] PARTY    [⌘2] BOX    [⌘3] DEX    [⌘4] JOURNAL    [⌘K] COMMANDS    [?] HELP",
            color: BuddyMonBrand.textSecondary,
            font: BuddyMonBrand.Font.strong(10)
        ))

        let prompt = horizontal(spacing: BuddyMonBrand.Spacing.compact)
        prompt.alignment = .centerY
        prompt.addArrangedSubview(text("hunt@buddymon:~$", color: BuddyMonBrand.textPrimary, font: BuddyMonBrand.Font.strong(12)))
        prompt.addArrangedSubview(text("open party --active", color: BuddyMonBrand.textPrimary, font: BuddyMonBrand.Font.regular(12)))
        prompt.addArrangedSubview(BrandBlockCursor())
        prompt.addArrangedSubview(flexibleSpace())
        stack.addArrangedSubview(prompt)
        return stack
    }

    private func sharedContextStories() -> NSView {
        let stack = vertical(spacing: BuddyMonBrand.Spacing.xlarge)
        stack.alignment = .leading

        let intro = vertical(spacing: BuddyMonBrand.Spacing.compact)
        intro.addArrangedSubview(text(
            "STORIES::COMMON_CONTEXT",
            color: BuddyMonBrand.brand,
            font: BuddyMonBrand.Font.strong(11)
        ))
        intro.addArrangedSubview(text(
            "ONE BUDDY MOMENT / THREE SURFACES",
            color: BuddyMonBrand.textPrimary,
            font: BuddyMonBrand.Font.strong(18)
        ))
        intro.addArrangedSubview(text(
            "Each scenario keeps the same Pokemon, state, language, and next action across the emoji statusline, macOS menu bar, and native app.",
            color: BuddyMonBrand.textSecondary,
            font: BuddyMonBrand.Font.regular(10),
            lineSpacing: 2
        ))
        stack.addArrangedSubview(intro)

        stack.addArrangedSubview(contextStory(
            code: "A",
            title: "WORK SESSION / LEVEL PROGRESS",
            species: "PIKACHU",
            speciesColor: BuddyMonBrand.pikachu,
            statusline: "⚡ PIKACHU · Lv.24 · [█████████████.......] 64% · ⚙ · 🔥7 · ⚾12 · 🪙12.4k",
            menuTitle: "⚡ PIKACHU  Lv.24",
            menuDetail: """
            WORK SESSION ACTIVE
            +280 XP from latest prompt
            > Open BuddyMon                         [↵]
              Party                                [⌘1]
            """,
            nativeTitle: "PIKACHU / ACTIVE BUDDY",
            nativeMeta: "ELECTRIC · LV 24 · READY\nXP [#############.......] 64%\nLatest activity +280 XP",
            nativeAction: "[ OPEN PARTY ]"
        ))
        stack.addArrangedSubview(contextStory(
            code: "B",
            title: "WILD SIGNAL / DECISION REQUIRED",
            species: "SQUIRTLE",
            speciesColor: BuddyMonBrand.starterWater,
            statusline: "❗💧 A wild SQUIRTLE is waiting · safari odds: good · ⚾12",
            menuTitle: "❗ WILD SQUIRTLE",
            menuDetail: """
            ★ RARE SIGNAL / SAFARI
            Good catch odds · 12 balls ready
            > Open encounter                       [↵]
              Keep working                         [ESC]
            """,
            nativeTitle: "WILD SQUIRTLE / ★ RARE",
            nativeMeta: "WATER · LV 08 · WAITING\nCatch odds: GOOD\nChoose a ball or leave it journaled.",
            nativeAction: "[ ↵ CATCH ]   ESC  RUN"
        ))
        stack.addArrangedSubview(contextStory(
            code: "C",
            title: "CATCH RESULT / COLLECTION FOLLOW-THROUGH",
            species: "BULBASAUR",
            speciesColor: BuddyMonBrand.starterGrass,
            statusline: "🎉 Caught 🌱 BULBASAUR! · +1,240 XP · dex 001 registered",
            menuTitle: "🎉 BULBASAUR CAUGHT",
            menuDetail: """
            COLLECTION UPDATED
            +1,240 XP · Pokedex 001 registered
            > View new catch                       [↵]
              Add to Showcase                      [S]
            """,
            nativeTitle: "BULBASAUR / NEW CATCH",
            nativeMeta: "GRASS · LV 12 · CAUGHT\nDex 001 · Copy 01\nReady for Party or Showcase.",
            nativeAction: "[ ADD TO SHOWCASE ]   [ VIEW DEX ]"
        ))
        return stack
    }

    private func contextStory(
        code: String,
        title: String,
        species: String,
        speciesColor: NSColor,
        statusline: String,
        menuTitle: String,
        menuDetail: String,
        nativeTitle: String,
        nativeMeta: String,
        nativeAction: String
    ) -> NSView {
        let stack = vertical(spacing: BuddyMonBrand.Spacing.medium)
        stack.alignment = .leading

        let heading = horizontal(spacing: BuddyMonBrand.Spacing.compact)
        heading.addArrangedSubview(text("STORY \(code)::", color: BuddyMonBrand.brand, font: BuddyMonBrand.Font.strong(11)))
        heading.addArrangedSubview(text(title, color: BuddyMonBrand.textPrimary, font: BuddyMonBrand.Font.strong(13)))
        stack.addArrangedSubview(heading)

        stack.addArrangedSubview(storySurface(
            "EMOJI STATUSLINE",
            highlightedText(
                statusline,
                font: BuddyMonBrand.Font.strong(11),
                highlights: [species: speciesColor],
                lineSpacing: 0
            )
        ))
        stack.addArrangedSubview(storySurface(
            "MACOS MENU BAR + DROPDOWN",
            menuBarStory(
                species: species,
                speciesColor: speciesColor,
                title: menuTitle,
                detail: menuDetail
            )
        ))
        stack.addArrangedSubview(storySurface(
            "NATIVE APP",
            nativeAppStory(
                species: species,
                speciesColor: speciesColor,
                title: nativeTitle,
                meta: nativeMeta,
                action: nativeAction
            )
        ))
        return stack
    }

    private func storySurface(_ label: String, _ content: NSView) -> NSView {
        let stack = vertical(spacing: BuddyMonBrand.Spacing.compact)
        stack.alignment = .leading
        stack.addArrangedSubview(text(label, color: BuddyMonBrand.textSecondary, font: BuddyMonBrand.Font.strong(9)))

        let surface = BuddyMonBrand.makeSurface()
        surface.addSubview(content)
        content.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            surface.widthAnchor.constraint(equalToConstant: BrandPreviewMetric.contentWidth),
            content.leadingAnchor.constraint(equalTo: surface.leadingAnchor, constant: BuddyMonBrand.Spacing.medium),
            content.trailingAnchor.constraint(lessThanOrEqualTo: surface.trailingAnchor, constant: -BuddyMonBrand.Spacing.medium),
            content.topAnchor.constraint(equalTo: surface.topAnchor, constant: BuddyMonBrand.Spacing.small),
            content.bottomAnchor.constraint(equalTo: surface.bottomAnchor, constant: -BuddyMonBrand.Spacing.small),
        ])
        stack.addArrangedSubview(surface)
        return stack
    }

    private func menuBarStory(
        species: String,
        speciesColor: NSColor,
        title: String,
        detail: String
    ) -> NSView {
        let stack = vertical(spacing: BuddyMonBrand.Spacing.small)
        stack.alignment = .leading

        let titleRow = horizontal(spacing: BuddyMonBrand.Spacing.compact)
        titleRow.alignment = .centerY
        titleRow.addArrangedSubview(pokemonImageView(species, size: NSSize(width: 32, height: 24)))
        titleRow.addArrangedSubview(highlightedText(
            title,
            font: BuddyMonBrand.Font.strong(11),
            highlights: [species: speciesColor],
            lineSpacing: 0
        ))
        stack.addArrangedSubview(titleRow)
        stack.addArrangedSubview(text(
            "------------------------------------------------------------------------------------------",
            color: BuddyMonBrand.rule,
            font: BuddyMonBrand.Font.regular(9)
        ))
        stack.addArrangedSubview(highlightedText(
            detail,
            font: BuddyMonBrand.Font.regular(10),
            highlights: [
                species: speciesColor,
                "★ RARE": BuddyMonBrand.rarity,
            ],
            lineSpacing: 4
        ))
        return stack
    }

    private func nativeAppStory(
        species: String,
        speciesColor: NSColor,
        title: String,
        meta: String,
        action: String
    ) -> NSView {
        let row = horizontal(spacing: BuddyMonBrand.Spacing.medium)
        row.alignment = .centerY

        let art = horizontal(spacing: BuddyMonBrand.Spacing.small)
        art.alignment = .top
        art.addArrangedSubview(artPreview(
            "PIXEL FELLOW",
            pokemonImageView(species, size: NSSize(width: 80, height: 60))
        ))
        art.addArrangedSubview(artPreview(
            "OFFICIAL PNG",
            officialPokemonImageView(species, size: NSSize(width: 128, height: 104))
        ))
        row.addArrangedSubview(art)

        let copy = vertical(spacing: BuddyMonBrand.Spacing.compact)
        copy.alignment = .leading
        copy.addArrangedSubview(highlightedText(
            title,
            font: BuddyMonBrand.Font.strong(14),
            highlights: [
                species: speciesColor,
                "★ RARE": BuddyMonBrand.rarity,
            ],
            lineSpacing: 0
        ))
        copy.addArrangedSubview(text(meta, color: BuddyMonBrand.textPrimary, font: BuddyMonBrand.Font.regular(10), lineSpacing: 4))
        copy.addArrangedSubview(text(action, color: BuddyMonBrand.textPrimary, font: BuddyMonBrand.Font.strong(10)))
        row.addArrangedSubview(copy)
        return row
    }

    private func artPreview(_ label: String, _ image: NSView) -> NSView {
        let stack = vertical(spacing: BuddyMonBrand.Spacing.compact)
        stack.alignment = .leading
        stack.addArrangedSubview(text(label, color: BuddyMonBrand.textSecondary, font: BuddyMonBrand.Font.strong(8)))
        stack.addArrangedSubview(image)
        return stack
    }

    private func pokemonImageView(_ species: String, size: NSSize) -> NSView {
        guard
            let encoded = BrandPreviewSpriteData.base64[species],
            let data = Data(base64Encoded: encoded),
            let image = NSImage(data: data)
        else {
            return text("[ NO SPRITE ]", color: BuddyMonBrand.textSecondary, font: BuddyMonBrand.Font.strong(9))
        }

        image.isTemplate = false
        let imageView = NSImageView()
        imageView.image = image
        imageView.imageScaling = .scaleProportionallyUpOrDown
        imageView.wantsLayer = true
        imageView.layer?.magnificationFilter = .nearest
        imageView.layer?.minificationFilter = .nearest
        imageView.setAccessibilityLabel("\(species.capitalized) pixel sprite")
        NSLayoutConstraint.activate([
            imageView.widthAnchor.constraint(equalToConstant: size.width),
            imageView.heightAnchor.constraint(equalToConstant: size.height),
        ])
        return imageView
    }

    private func officialPokemonImageView(_ species: String, size: NSSize) -> NSView {
        guard let image = officialPokemonImage(species) else {
            let fallback = vertical(spacing: BuddyMonBrand.Spacing.compact)
            fallback.addArrangedSubview(pokemonImageView(species, size: size))
            fallback.addArrangedSubview(text(
                "LOCAL PACK FALLBACK",
                color: BuddyMonBrand.textSecondary,
                font: BuddyMonBrand.Font.strong(8)
            ))
            return fallback
        }

        let imageView = NSImageView()
        imageView.image = image
        imageView.imageScaling = .scaleProportionallyUpOrDown
        imageView.wantsLayer = true
        imageView.layer?.magnificationFilter = .nearest
        imageView.layer?.minificationFilter = .nearest
        imageView.setAccessibilityLabel("\(species.capitalized) official pixel sprite PNG")
        NSLayoutConstraint.activate([
            imageView.widthAnchor.constraint(equalToConstant: size.width),
            imageView.heightAnchor.constraint(equalToConstant: size.height),
        ])
        return imageView
    }

    private func officialPokemonImage(_ species: String) -> NSImage? {
        if let cached = officialSpriteCache[species] {
            return cached
        }

        let environment = ProcessInfo.processInfo.environment
        let stateRoot: URL
        if let xdg = environment["XDG_STATE_HOME"], !xdg.isEmpty {
            stateRoot = URL(fileURLWithPath: xdg, isDirectory: true)
        } else {
            stateRoot = FileManager.default.homeDirectoryForCurrentUser
                .appendingPathComponent(".local/state", isDirectory: true)
        }
        let slug = species.lowercased().replacingOccurrences(of: " ", with: "-")
        let source = stateRoot
            .appendingPathComponent("buddymon/packs/gen5", isDirectory: true)
            .appendingPathComponent("\(slug).json")
        guard
            let data = try? Data(contentsOf: source),
            let object = try? JSONSerialization.jsonObject(with: data),
            let entry = object as? [String: Any],
            let frames = entry["frames"] as? [Any],
            let frame = frames.first as? [Any],
            frame.count == 2,
            let grid = frame[0] as? [String],
            let palette = frame[1] as? [String: String],
            let image = pngImage(grid: grid, palette: palette, scale: 2)
        else {
            return nil
        }
        officialSpriteCache[species] = image
        return image
    }

    private func pngImage(
        grid: [String],
        palette: [String: String],
        scale: Int
    ) -> NSImage? {
        guard let first = grid.first, !first.isEmpty, scale > 0 else { return nil }
        let sourceWidth = first.count
        guard grid.allSatisfy({ $0.count == sourceWidth }) else { return nil }

        let width = sourceWidth * scale
        let height = grid.count * scale
        guard let bitmap = NSBitmapImageRep(
            bitmapDataPlanes: nil,
            pixelsWide: width,
            pixelsHigh: height,
            bitsPerSample: 8,
            samplesPerPixel: 4,
            hasAlpha: true,
            isPlanar: false,
            colorSpaceName: .deviceRGB,
            bytesPerRow: width * 4,
            bitsPerPixel: 32
        ), let pixels = bitmap.bitmapData else {
            return nil
        }
        pixels.initialize(repeating: 0, count: height * bitmap.bytesPerRow)

        for (sourceY, row) in grid.enumerated() {
            for (sourceX, cell) in row.enumerated() {
                guard
                    let hex = palette[String(cell)],
                    let color = rgba(hex)
                else { continue }
                for offsetY in 0..<scale {
                    for offsetX in 0..<scale {
                        let x = (sourceX * scale) + offsetX
                        let y = (sourceY * scale) + offsetY
                        let offset = (y * bitmap.bytesPerRow) + (x * 4)
                        pixels[offset] = color.0
                        pixels[offset + 1] = color.1
                        pixels[offset + 2] = color.2
                        pixels[offset + 3] = 255
                    }
                }
            }
        }

        guard
            let png = bitmap.representation(using: .png, properties: [:]),
            let image = NSImage(data: png)
        else { return nil }
        image.isTemplate = false
        return image
    }

    private func rgba(_ hex: String) -> (UInt8, UInt8, UInt8)? {
        let value = hex.trimmingCharacters(in: CharacterSet(charactersIn: "#"))
        guard value.count == 6, let number = UInt32(value, radix: 16) else { return nil }
        return (
            UInt8((number >> 16) & 0xff),
            UInt8((number >> 8) & 0xff),
            UInt8(number & 0xff)
        )
    }

    private func componentWorkbench() -> NSView {
        let stack = vertical(spacing: BuddyMonBrand.Spacing.section)
        stack.alignment = .leading

        let sections = [
            typographySection(),
            surfaceSection(),
            commandControlSection(),
            formControlSection(),
            navigationSection(),
            collectionSection(),
            encounterSection(),
            showcaseSection(),
            statusSection(),
            progressSection(),
            feedbackSection(),
            dialogSection(),
            notificationSection(),
            tokenSection(),
            doctorSection(),
            buddyHeaderSection(),
            battleHUDSection(),
            battleLogSection(),
            profileSummarySection(),
            collectionToolbarSection(),
            dexComponentSection(),
            journalComponentSection(),
            setupComponentSection(),
            tokenEdgeSection(),
            accessibilitySection(),
        ]
        for section in sections {
            stack.addArrangedSubview(section)
            section.widthAnchor.constraint(equalToConstant: BrandPreviewMetric.contentWidth).isActive = true
        }
        return stack
    }

    private func typographySection() -> NSView {
        let left = vertical(spacing: BuddyMonBrand.Spacing.compact)
        left.addArrangedSubview(text("DISPLAY / 28 / HEAVY", color: BuddyMonBrand.textPrimary, font: BuddyMonBrand.Font.strong(28)))
        left.addArrangedSubview(text("SCREEN TITLE / 18 / HEAVY", color: BuddyMonBrand.textPrimary, font: BuddyMonBrand.Font.strong(18)))
        left.addArrangedSubview(text("SECTION LABEL / 11 / HEAVY", color: BuddyMonBrand.textPrimary, font: BuddyMonBrand.Font.strong(11)))
        left.addArrangedSubview(text("Body copy stays compact, readable, and code-shaped.", color: BuddyMonBrand.textPrimary, font: BuddyMonBrand.Font.regular(12)))
        left.addArrangedSubview(text("Muted metadata / timestamps / explanatory copy", color: BuddyMonBrand.textSecondary, font: BuddyMonBrand.Font.regular(10)))

        let right = vertical(spacing: BuddyMonBrand.Spacing.compact)
        right.addArrangedSubview(highlightedText(
            "POKEMON RED  POKEMON BLUE\nPIKACHU  BULBASAUR  SQUIRTLE  ★ RARE",
            font: BuddyMonBrand.Font.strong(14),
            highlights: [
                "POKEMON RED": BuddyMonBrand.brand,
                "POKEMON BLUE": BuddyMonBrand.pokemonBlue,
                "PIKACHU": BuddyMonBrand.pikachu,
                "BULBASAUR": BuddyMonBrand.starterGrass,
                "SQUIRTLE": BuddyMonBrand.starterWater,
                "★ RARE": BuddyMonBrand.rarity,
            ],
            lineSpacing: 0
        ))
        right.addArrangedSubview(text("012,480 TOKENS", color: BuddyMonBrand.textPrimary, font: BuddyMonBrand.Font.strong(22)))
        right.addArrangedSubview(text("ID 025  /  LV 24  /  14:09:02", color: BuddyMonBrand.textSecondary, font: BuddyMonBrand.Font.regular(11)))
        right.addArrangedSubview(text("Long content wraps deliberately instead of shrinking into illegibility.", color: BuddyMonBrand.textPrimary, font: BuddyMonBrand.Font.regular(11), lineSpacing: 3))

        return specimenSection(
            "04",
            "TYPE SYSTEM",
            "One code-family voice. Weight, scale, spacing, and color—not font switching—create hierarchy.",
            sampleRow([left, right])
        )
    }

    private func surfaceSection() -> NSView {
        let samples = sampleRow([
            surfaceSample("CANVAS", detail: "page / window / deepest plane", level: 0),
            surfaceSample("TERMINAL", detail: "primary working surface", level: 1),
            surfaceSample("INSET", detail: "logs / reports / code output", level: 2),
            surfaceSample("FOCUS", detail: "one red rule; never a glow cloud", level: 3),
        ])
        let content = vertical(spacing: BuddyMonBrand.Spacing.medium)
        content.addArrangedSubview(samples)
        content.addArrangedSubview(fieldGuideActiveRowSample())
        content.addArrangedSubview(fieldGuideStatusSample())
        content.addArrangedSubview(fieldGuideQuickLinkSample())
        content.addArrangedSubview(fieldGuideTrainerStatusRailSample())
        return specimenSection(
            "05",
            "SURFACES + RULES",
            "Square geometry, one-pixel rules, no decorative rounding, and no nesting without information value. Field Guide's active-buddy row and Trainer status rail use only subtle top and bottom rules.",
            content
        )
    }

    private func fieldGuideActiveRowSample() -> NSView {
        let row = BuddyMonBrand.Menu.makeActiveBuddyRow()
        row.orientation = .horizontal
        row.alignment = .centerY
        row.spacing = BuddyMonBrand.Menu.compactGap
        row.edgeInsets = NSEdgeInsets(
            top: BuddyMonBrand.Menu.compactGap,
            left: BuddyMonBrand.Menu.compactGap,
            bottom: BuddyMonBrand.Menu.compactGap,
            right: BuddyMonBrand.Menu.compactGap
        )
        row.widthAnchor.constraint(
            equalToConstant: BrandPreviewMetric.contentWidth
        ).isActive = true
        row.addArrangedSubview(BuddyMonBrand.Menu.makeDisplayLabel(
            "ACTIVE BUDDY ROW",
            color: BuddyMonBrand.Menu.ink
        ))
        row.addArrangedSubview(flexibleSpace())
        row.addArrangedSubview(text(
            "FULL BLEED  ·  TOP / BOTTOM RULES",
            color: BuddyMonBrand.Menu.mutedInk,
            font: BuddyMonBrand.Font.strong(9)
        ))
        return row
    }

    private func fieldGuideStatusSample() -> NSView {
        let row = horizontal(spacing: BuddyMonBrand.Spacing.large)
        for (label, state) in [
            ("ACTIVE", BuddyMonBrand.Menu.AppStatusState.active),
            ("STARTING", BuddyMonBrand.Menu.AppStatusState.idle),
            ("UNAVAILABLE", BuddyMonBrand.Menu.AppStatusState.unavailable),
        ] {
            let item = horizontal(spacing: BuddyMonBrand.Menu.compactGap)
            item.addArrangedSubview(BuddyMonBrand.Menu.makeStatusIndicator(state))
            item.addArrangedSubview(text(
                label,
                color: BuddyMonBrand.Menu.ink,
                font: BuddyMonBrand.Font.strong(9)
            ))
            row.addArrangedSubview(item)
        }
        return row
    }

    private func fieldGuideQuickLinkSample() -> NSView {
        let samples: [(String, BuddyMonBrand.ControlState)] = [
            ("N NORMAL", .normal),
            ("H HOVER", .hovered),
            ("F FOCUS", .focused),
            ("P PRESS", .pressed),
            ("D DISABLED", .disabled),
            ("L LOADING", .loading),
        ]
        let row = NSStackView()
        row.orientation = .horizontal
        row.alignment = .centerY
        row.spacing = BuddyMonBrand.Menu.actionGap
        let linkWidth = (
            BrandPreviewMetric.contentWidth
                - BuddyMonBrand.Menu.actionGap * CGFloat(samples.count - 1)
        ) / CGFloat(samples.count)
        for (label, state) in samples {
            let link = BuddyMonBrand.Menu.makeQuickLink(
                label,
                target: nil,
                action: nil
            )
            BuddyMonBrand.Menu.refreshActionButton(
                link,
                role: .quiet,
                state: state
            )
            link.widthAnchor.constraint(equalToConstant: linkWidth).isActive = true
            row.addArrangedSubview(link)
        }
        row.widthAnchor.constraint(
            equalToConstant: BrandPreviewMetric.contentWidth
        ).isActive = true
        return row
    }

    private func fieldGuideTrainerStatusRailSample() -> NSView {
        let rail = BuddyMonBrand.Menu.makeTrainerStatusRail([
            (label: "MODE", value: "QUICK"),
            (label: "STREAK", value: "7D"),
            (label: "BALLS", value: "84"),
            (label: "SHINY", value: "3"),
        ])
        rail.widthAnchor.constraint(
            equalToConstant: BuddyMonBrand.Menu.trainerCardWidth
        ).isActive = true
        return controlSample("FIELD GUIDE / TRAINER STATUS", rail)
    }

    private func commandControlSection() -> NSView {
        let controls = sampleRow([
            controlSample("DEFAULT", brandButton("[ OPEN ]")),
            controlSample("HOVER", brandButton("[ OPEN ]", state: .hovered)),
            controlSample("FOCUS", brandButton("[ OPEN ]", state: .focused)),
            controlSample("PRESSED", brandButton("[ OPEN ]", state: .pressed)),
            controlSample("DISABLED", brandButton("[ OPEN ]", state: .disabled)),
            controlSample("LOADING", brandButton("[.. OPENING ]", state: .loading)),
        ])

        let actions = sampleRow([
            controlSample("PRIMARY", brandButton("[ ↵ CATCH ]", role: .primary, state: .focused)),
            controlSample("SECONDARY", brandButton("[ S SHARE ]")),
            controlSample("QUIET", brandButton("ESC  CANCEL", role: .quiet)),
            controlSample("DESTRUCTIVE", brandButton("[ ! RELEASE ]", role: .destructive)),
        ])

        let stack = vertical(spacing: BuddyMonBrand.Spacing.medium)
        stack.alignment = .leading
        stack.addArrangedSubview(controls)
        stack.addArrangedSubview(actions)
        return specimenSection(
            "06",
            "COMMAND CONTROLS",
            "Every action reads as a command. Focus is explicit; destructive actions require language, not color alone.",
            stack
        )
    }

    private func formControlSection() -> NSView {
        let fields = sampleRow([
            controlSample("EMPTY", brandField("", placeholder: "search Pokemon")),
            controlSample("FILLED", brandField("pika", placeholder: "")),
            controlSample("FOCUS", brandField("electric", placeholder: "", state: .focused)),
            controlSample("ERROR", brandField("???", placeholder: "", state: .error)),
            controlSample("DISABLED", brandField("local only", placeholder: "", state: .disabled)),
        ])

        let settings = sampleRow([
            controlSample("CHECKBOX", brandToggle("[ ] NOTIFICATIONS", color: BuddyMonBrand.textPrimary)),
            controlSample("CHECKED", brandToggle("[x] NOTIFICATIONS", color: BuddyMonBrand.textPrimary)),
            controlSample("MIXED", brandToggle("[-] SOURCES", color: BuddyMonBrand.textSecondary)),
            controlSample("RADIO", brandToggle("(o) APP   ( ) TERMINAL", color: BuddyMonBrand.textPrimary)),
            controlSample("SELECT", brandToggle("DISPLAY  < APP       v >", color: BuddyMonBrand.textPrimary)),
            controlSample("LOCAL ACTION", brandButton("[ BACK UP DATA ]", role: .secondary)),
        ])

        let stack = vertical(spacing: BuddyMonBrand.Spacing.medium)
        stack.alignment = .leading
        stack.addArrangedSubview(fields)
        stack.addArrangedSubview(settings)
        let preferenceRow = BuddyMonBrand.Menu.makeSettingsRow(
            label: "Encounter mode",
            key: "mode",
            detail: "Changes apply immediately.",
            options: [
                .init(value: "auto", label: "Quick", isActive: true),
                .init(value: "safari", label: "Safari", isActive: false),
                .init(value: "battle", label: "Battle", isActive: false),
            ],
            target: nil,
            action: nil
        )
        preferenceRow.widthAnchor.constraint(equalToConstant: 320).isActive = true
        let secondaryPreferenceRow = BuddyMonBrand.Menu.makeSettingsRow(
            label: "Terminal graphics",
            key: "terminal_graphics",
            detail: "Changes apply immediately.",
            options: [
                .init(value: "auto", label: "Auto", isActive: true),
                .init(value: "off", label: "Off", isActive: false),
            ],
            target: nil,
            action: nil
        )
        secondaryPreferenceRow.widthAnchor.constraint(equalToConstant: 320).isActive = true
        let compactSettings = sampleRow([
            fieldGuideControlSample(
                "FIELD GUIDE / PREFERENCE",
                preferenceRow
            ),
            fieldGuideControlSample(
                "FIELD GUIDE / PREFERENCE 2",
                secondaryPreferenceRow
            ),
        ])
        stack.addArrangedSubview(compactSettings)
        let hoveredRow = BuddyMonBrand.Menu.makeSettingsRow(
            label: "Notifications",
            key: "notifications",
            detail: "Changes apply immediately.",
            options: [
                .init(value: "on", label: "On", isActive: true),
                .init(value: "silent", label: "Silent", isActive: false),
                .init(value: "off", label: "Off", isActive: false),
            ],
            target: nil,
            action: nil
        )
        BuddyMonBrand.Menu.applySettingsOption(
            to: hoveredRow.optionButtons[2],
            state: .hovered
        )
        hoveredRow.widthAnchor.constraint(equalToConstant: 320).isActive = true
        let focusedRow = BuddyMonBrand.Menu.makeSettingsRow(
            label: "Share banners",
            key: "share_banner",
            detail: "Changes apply immediately.",
            options: [
                .init(value: "on", label: "On", isActive: true),
                .init(value: "off", label: "Off", isActive: false),
            ],
            target: nil,
            action: nil
        )
        BuddyMonBrand.Menu.applySettingsOption(
            to: focusedRow.optionButtons[1],
            state: .focused
        )
        focusedRow.widthAnchor.constraint(equalToConstant: 320).isActive = true
        stack.addArrangedSubview(sampleRow([
            fieldGuideControlSample("FIELD GUIDE / HOVER", hoveredRow),
            fieldGuideControlSample("FIELD GUIDE / FOCUS", focusedRow),
        ]))
        return specimenSection(
            "07",
            "FIELDS + SETTINGS",
            "Text input, search, validation, checks, radio choices, and immediate compact preferences without generic form chrome.",
            stack
        )
    }

    private func navigationSection() -> NSView {
        let navigation = highlightedText(
            """
              01  HOME                 default
            > 02  PARTY                selected
            * 03  BOX                  unread / 04
              04  POKEDEX              hover
            - 05  JOURNAL              disabled
              06  TOKEN USAGE          default
            """,
            font: BuddyMonBrand.Font.regular(11),
            highlights: ["> 02": BuddyMonBrand.brand],
            lineSpacing: 5
        )
        let palette = highlightedText(
            """
            / COMMANDS________________________________
            > open party                         [⌘1]
              search box                         [⌘K]
              collect local activity             [⌘R]
              open full terminal                 [⌘T]
              settings                           [⌘,]
            """,
            font: BuddyMonBrand.Font.regular(11),
            highlights: ["> open party": BuddyMonBrand.brand],
            lineSpacing: 5
        )
        return specimenSection(
            "08",
            "NAVIGATION + COMMAND PALETTE",
            "Selected, hover, unread, disabled, shortcuts, and fuzzy-command results use position and symbols before color.",
            sampleRow([navigation, palette])
        )
    }

    private func collectionSection() -> NSView {
        let rows = highlightedText(
            """
              025  PIKACHU      LV 24  ELECTRIC   active
            > 001  BULBASAUR    LV 12  GRASS      selected
              007  SQUIRTLE     LV 08  WATER      favorite ★
              ???  ----------   -- --  UNKNOWN    uncaught
            - 004  CHARMANDER   LV 06  FIRE       unavailable
            """,
            font: BuddyMonBrand.Font.regular(11),
            highlights: [
                "PIKACHU": BuddyMonBrand.pikachu,
                "BULBASAUR": BuddyMonBrand.starterGrass,
                "SQUIRTLE": BuddyMonBrand.starterWater,
                "> 001": BuddyMonBrand.brand,
            ],
            lineSpacing: 6
        )

        let frames = sampleRow([
            spriteFrame("DEFAULT", name: "PIKACHU", color: BuddyMonBrand.pikachu, edge: "+"),
            spriteFrame("SELECTED", name: "BULBASAUR", color: BuddyMonBrand.starterGrass, edge: "#"),
            spriteFrame("SHINY / RARE", name: "★ SIGNAL", color: BuddyMonBrand.rarity, edge: "*"),
            spriteFrame("UNCAUGHT", name: "???", color: BuddyMonBrand.textSecondary, edge: "."),
            spriteFrame("MISSING ART", name: "[ NO IMAGE ]", color: BuddyMonBrand.textSecondary, edge: "-"),
        ])

        let stack = vertical(spacing: BuddyMonBrand.Spacing.medium)
        stack.alignment = .leading
        stack.addArrangedSubview(rows)
        stack.addArrangedSubview(frames)
        return specimenSection(
            "09",
            "COLLECTION ROWS + SPRITE FRAMES",
            "Party, Box, and Dex states: default, hover/selected, active, favorite, shiny/rare, uncaught, unavailable, and missing art.",
            stack
        )
    }

    private func encounterSection() -> NSView {
        let waiting = stateBlock(
            "WAITING",
            """
            signal: faint
            wild:   unresolved
            action: [ KEEP WORKING ]
            """,
            color: BuddyMonBrand.textPrimary
        )
        let active = stateBlock(
            "ACTIVE",
            """
            wild:   PIKACHU
            odds:   72%
            action: [ ↵ CATCH ]
            """,
            color: BuddyMonBrand.pikachu
        )
        let caught = stateBlock(
            "CAUGHT",
            """
            result: success
            xp:     +1,240
            action: [ S SHARE ]
            """,
            color: BuddyMonBrand.textPrimary
        )
        let escaped = stateBlock(
            "ESCAPED",
            """
            result: no catch
            state:  journaled
            action: [ ↵ CONTINUE ]
            """,
            color: BuddyMonBrand.brand
        )
        return specimenSection(
            "10",
            "ENCOUNTER STATES",
            "Waiting, active, catching/loading, caught, escaped, and action affordances use the same command language.",
            sampleRow([waiting, active, caught, escaped])
        )
    }

    private func showcaseSection() -> NSView {
        let slots = sampleRow([
            showcaseSlot("01", state: "FILLED", name: "PIKACHU", color: BuddyMonBrand.pikachu),
            showcaseSlot("02", state: "SELECTED", name: "BULBASAUR", color: BuddyMonBrand.starterGrass),
            showcaseSlot("03", state: "EMPTY", name: "+ ADD", color: BuddyMonBrand.textPrimary),
            showcaseSlot("04", state: "LOCKED", name: "-----", color: BuddyMonBrand.textSecondary),
            showcaseSlot("05", state: "SHARING..", name: "[..]", color: BuddyMonBrand.textPrimary),
            showcaseSlot("06", state: "RARE", name: "★ SHINY", color: BuddyMonBrand.rarity),
        ])
        return specimenSection(
            "11",
            "SHOWCASE SLOTS",
            "Filled, hover/selected, empty, locked, sharing, and rare podium states stay compact and scannable.",
            slots
        )
    }

    private func statusSection() -> NSView {
        let chips = sampleRow([
            controlSample("READY", brandToggle("[+] READY", color: BuddyMonBrand.textPrimary)),
            controlSample("ACTIVE", brandToggle("[*] ACTIVE", color: BuddyMonBrand.textPrimary)),
            controlSample("SYNCING", brandToggle("[..] SYNCING", color: BuddyMonBrand.textPrimary)),
            controlSample("WAITING", brandToggle("[ ] WAITING", color: BuddyMonBrand.textSecondary)),
            controlSample("WARNING", brandToggle("[!] SETUP", color: BuddyMonBrand.textPrimary)),
            controlSample("ERROR", brandToggle("[x] ERROR", color: BuddyMonBrand.brand)),
            controlSample("RARE", brandToggle("[★] RARE", color: BuddyMonBrand.rarity)),
        ])
        return specimenSection(
            "12",
            "STATUS + RARITY",
            "Text and symbols always carry meaning. Color reinforces only brand, Pokémon identity, and exceptional states.",
            chips
        )
    }

    private func progressSection() -> NSView {
        let states = highlightedText(
            """
            XP / DETERMINATE    [############........]  60%
            TOKEN / COMPLETE    [####################] 100%  done
            COLLECT / LOADING   [..|..|..|..|..|..|..]       scanning
            ASSET / PAUSED      [########............]  40%  waiting
            RETRY / FAILED      [xxxx................]  20%  retry 2/3
            SKELETON            [========]  [============]  [=====]
            """,
            font: BuddyMonBrand.Font.regular(11),
            highlights: ["FAILED": BuddyMonBrand.brand],
            lineSpacing: 7
        )
        return specimenSection(
            "13",
            "PROGRESS + LOADING",
            "Determinate, indeterminate, complete, paused, failed/retrying, and skeleton states without ornamental spinners.",
            states
        )
    }

    private func feedbackSection() -> NSView {
        let states = sampleRow([
            stateBlock("EMPTY", "No Pokemon here yet.\n[ OPEN DEX ]", color: BuddyMonBrand.textSecondary),
            stateBlock("SUCCESS", "Collection complete.\n+04 species", color: BuddyMonBrand.textPrimary),
            stateBlock("WARNING", "Optional art absent.\nBuilt-in art remains active.", color: BuddyMonBrand.textPrimary),
            stateBlock("ERROR", "Collector did not answer.\n[ RETRY ]  [ DETAILS ]", color: BuddyMonBrand.brand),
        ])
        return specimenSection(
            "14",
            "EMPTY + SUCCESS + WARNING + ERROR",
            "Every feedback state says what happened and offers one obvious next action when action is possible.",
            states
        )
    }

    private func dialogSection() -> NSView {
        let confirm = brandDialog(
            "CONFIRM SWITCH",
            body: "Make BULBASAUR your active buddy?",
            actions: "[ ESC CANCEL ]    [ ↵ SWITCH ]",
            highlight: "BULBASAUR",
            highlightColor: BuddyMonBrand.starterGrass
        )
        let destructive = brandDialog(
            "RELEASE POKEMON",
            body: "This cannot be undone. Type RELEASE.",
            actions: "[ CANCEL ]    [ ! RELEASE ]",
            highlight: "RELEASE",
            highlightColor: BuddyMonBrand.brand
        )
        return specimenSection(
            "15",
            "DIALOGS + CONFIRMATION",
            "Default confirmation, destructive confirmation, keyboard escape, and explicit irreversible-language patterns.",
            sampleRow([confirm, destructive])
        )
    }

    private func notificationSection() -> NSView {
        let messages = vertical(spacing: BuddyMonBrand.Spacing.small)
        messages.addArrangedSubview(notificationLine("INFO", "Local collection finished.", action: "OPEN"))
        messages.addArrangedSubview(notificationLine("SUCCESS", "Pikachu reached Lv.25.", action: "VIEW"))
        messages.addArrangedSubview(notificationLine("WARNING", "Optional art needs attention.", action: "FIX"))
        messages.addArrangedSubview(notificationLine("ERROR", "Collector stopped after 3 retries.", action: "DETAILS"))
        messages.addArrangedSubview(highlightedText(
            "[★ RARE]  A rare signal appeared nearby.                            [ CATCH ]",
            font: BuddyMonBrand.Font.strong(11),
            highlights: ["★ RARE": BuddyMonBrand.rarity],
            lineSpacing: 0
        ))
        return specimenSection(
            "16",
            "BANNERS + NOTIFICATIONS",
            "Inline banners, transient notices, actionable failures, and rare-event alerts share one message grammar.",
            messages
        )
    }

    private func tokenSection() -> NSView {
        let summary = highlightedText(
            """
            TODAY       012,480    [#############.......]  +18%
            THIS WEEK   084,922    [################....]  +09%
            CODEX CLI   060,102    primary
            CLAUDE CODE 024,820    secondary
            RHYTHM      [##][  ][##][##][  ][##][##]
            28-DAY      [##][##][  ][##][##][##][  ] ...
            """,
            font: BuddyMonBrand.Font.regular(11),
            highlights: ["012,480": BuddyMonBrand.pikachu],
            lineSpacing: 7
        )
        let report = text(
            """
            DATE        INPUT       OUTPUT      TOTAL
            07/15       009,830     002,650     012,480
            07/14       011,104     003,118     014,222
            07/13       008,442     001,904     010,346
            ------------------------------------------
            """,
            color: BuddyMonBrand.textPrimary,
            font: BuddyMonBrand.Font.regular(11),
            lineSpacing: 6
        )
        return specimenSection(
            "17",
            "TOKEN SUMMARY + REPORT",
            "Summary values, supported-tool rhythm, 28-day trend bars, source splits, dense tables, zero-data, and overflow/report patterns.",
            sampleRow([summary, report])
        )
    }

    private func doctorSection() -> NSView {
        let output = highlightedText(
            """
            $ buddymon doctor --local
            [ok] app bridge           responsive
            [ok] state store          writable
            [ok] codex collector      attached
            [--] optional art         not installed
            [!!] launch at login      needs approval
            [xx] notification helper  unavailable
            """,
            font: BuddyMonBrand.Font.regular(11),
            highlights: [
                "[!!]": BuddyMonBrand.brand,
                "[xx]": BuddyMonBrand.brand,
            ],
            lineSpacing: 6
        )
        let actions = vertical(spacing: BuddyMonBrand.Spacing.small)
        actions.addArrangedSubview(brandButton("[ R RETRY CHECKS ]"))
        actions.addArrangedSubview(brandButton("[ C COPY REPORT ]"))
        actions.addArrangedSubview(brandButton("[ O OPEN SETTINGS ]", role: .primary, state: .focused))
        actions.addArrangedSubview(text("Sensitive values are redacted by default.", color: BuddyMonBrand.textSecondary, font: BuddyMonBrand.Font.regular(10)))
        let recovery = stateBlock(
            "STATE NEEDS CARE",
            "File untouched.\nRestore or update BuddyMon.",
            color: BuddyMonBrand.brand
        )
        return specimenSection(
            "18",
            "DOCTOR + DIAGNOSTIC OUTPUT",
            "Healthy, optional, blocked, recovery-required, warning, failure, retry, and copy-report states stay readable like real command output.",
            sampleRow([output, actions, recovery])
        )
    }

    private func buddyHeaderSection() -> NSView {
        let heroes = sampleRow([
            buddyHero(
                state: "ACTIVE",
                name: "PIKACHU",
                detail: "LV 24 / ELECTRIC / COMMON",
                meter: "XP [#############.......] 64%",
                color: BuddyMonBrand.pikachu
            ),
            buddyHero(
                state: "SHINY / RARE",
                name: "★ BULBASAUR",
                detail: "LV 31 / GRASS / SHINY",
                meter: "XP [#################...] 86%",
                color: BuddyMonBrand.rarity
            ),
            buddyHero(
                state: "NO STARTER",
                name: "----------",
                detail: "Choose a buddy to begin.",
                meter: "XP [....................]  0%",
                color: BuddyMonBrand.textSecondary
            ),
        ])

        let stats = highlightedText(
            """
            CATCHES 048    SPECIES 032    STREAK 07d    BALLS 012    TOKENS 012,480
            NARROW:  CATCHES 048 / SPECIES 032 / STREAK 07d
                     BALLS 012  / TOKENS 012,480
            EMPTY:   CATCHES --  / SPECIES --  / STREAK --
            """,
            font: BuddyMonBrand.Font.regular(11),
            highlights: ["012,480": BuddyMonBrand.pikachu],
            lineSpacing: 6
        )

        let stack = vertical(spacing: BuddyMonBrand.Spacing.medium)
        stack.alignment = .leading
        stack.addArrangedSubview(heroes)
        stack.addArrangedSubview(stats)
        return specimenSection(
            "19",
            "BUDDY HEADER + TRAINER STATS",
            "Composed hero states plus the responsive catches/species/streak/Balls/tokens strip used across Home and Status.",
            stack
        )
    }

    private func battleHUDSection() -> NSView {
        let defaultHUD = battlePlate(
            title: "DEFAULT",
            buddy: "PIKACHU",
            buddyHP: "[##############......] 72/100",
            wild: "SQUIRTLE",
            wildHP: "[################....] 84/100",
            status: "TURN 02 / YOUR MOVE"
        )
        let dangerHUD = battlePlate(
            title: "LOW HP + STATUS",
            buddy: "PIKACHU / PAR",
            buddyHP: "[####................] 19/100",
            wild: "BULBASAUR",
            wildHP: "[##########..........] 51/100",
            status: "WARNING / SPEED REDUCED"
        )

        let commands = vertical(spacing: BuddyMonBrand.Spacing.small)
        commands.alignment = .leading
        commands.addArrangedSubview(sampleRow([
            brandButton("[ 1 FIGHT ]", role: .primary, state: .focused),
            brandButton("[ 2 BALL  ]"),
            brandButton("[ 3 RUN   ]"),
        ]))
        commands.addArrangedSubview(sampleRow([
            brandButton("[.. THROWING ]", state: .loading),
            brandButton("[ 0 BALLS ]", state: .disabled),
            brandButton("[ ! CANNOT RUN ]", state: .disabled),
        ]))

        let stack = vertical(spacing: BuddyMonBrand.Spacing.medium)
        stack.alignment = .leading
        stack.addArrangedSubview(sampleRow([defaultHUD, dangerHUD]))
        stack.addArrangedSubview(commands)
        return specimenSection(
            "20",
            "BATTLE HUD + ACTION GRID",
            "Buddy/wild plates, HP, status, turn ownership, Fight/Ball/Run, disabled inventory, loading, and blocked-action states.",
            stack
        )
    }

    private func battleLogSection() -> NSView {
        let log = highlightedText(
            """
            00:00  APPEARED    Wild SQUIRTLE entered the signal.
            00:03  ATTACK      PIKACHU used THUNDER SHOCK.              -24 hp
            00:06  STATUS      Wild SQUIRTLE is PARALYZED.
            00:09  BALL        Ball thrown...                           shake 1/3
            00:12  CAUGHT      Gotcha! SQUIRTLE was caught.             +1,240 xp
            00:14  LEVEL UP    PIKACHU reached Lv.25.
            00:17  EVOLUTION   BULBASAUR is ready to evolve.
            00:20  RAN         You escaped safely.
            00:23  FAILED      The Pokemon broke free.
            """,
            font: BuddyMonBrand.Font.regular(11),
            highlights: [
                "SQUIRTLE": BuddyMonBrand.starterWater,
                "PIKACHU": BuddyMonBrand.pikachu,
                "BULBASAUR": BuddyMonBrand.starterGrass,
                "FAILED": BuddyMonBrand.brand,
            ],
            lineSpacing: 7
        )
        return specimenSection(
            "21",
            "BATTLE LOG ROWS",
            "Appeared, attack, damage, status, throw/shake, catch, level-up, evolution, run, and failed-result messages.",
            log
        )
    }

    private func profileSummarySection() -> NSView {
        let selected = profileSummary(
            state: "SELECTED",
            name: "PIKACHU",
            identity: "#025 / ELECTRIC / COMMON",
            details: "LV 24   XP 64%   CAUGHT 07/12   FAVORITE yes",
            action: "[ ↵ MAKE ACTIVE ]   [ ★ UNFAVORITE ]",
            color: BuddyMonBrand.pikachu
        )
        let active = profileSummary(
            state: "ACTIVE + COPIES",
            name: "SQUIRTLE x03",
            identity: "#007 / WATER / STARTER",
            details: "LV 18   XP 42%   BEST COPY 02   FAVORITE no",
            action: "[ 1 PREV ] [ 2 NEXT ] [ S SWITCH ]",
            color: BuddyMonBrand.starterWater
        )
        let none = profileSummary(
            state: "NO SELECTION",
            name: "----------",
            identity: "Choose a roster row for details.",
            details: "LV --   XP --   CAUGHT --   FAVORITE --",
            action: "[ ACTIONS DISABLED ]",
            color: BuddyMonBrand.textSecondary
        )
        return specimenSection(
            "22",
            "SELECTED-BUDDY SUMMARY",
            "Composed profile cards for selected, active, duplicate-copy browsing, favorite, and no-selection states.",
            sampleRow([selected, active, none])
        )
    }

    private func collectionToolbarSection() -> NSView {
        let controls = sampleRow([
            controlSample("SEARCH", brandField("pika", placeholder: "find Pokemon", state: .focused)),
            controlSample("SORT", brandToggle("SORT < NEWEST v >", color: BuddyMonBrand.textPrimary)),
            controlSample("FILTER", brandToggle("TYPE < ELECTRIC v >", color: BuddyMonBrand.textPrimary)),
            controlSample("COUNT", brandToggle("04 / 151 RESULTS", color: BuddyMonBrand.textSecondary)),
            controlSample("CLEAR", brandButton("[ x CLEAR ]", role: .quiet)),
        ])
        let filters = highlightedText(
            """
            FILTERS   [ ALL ]  [* ELECTRIC ]  [ SHINY ]  [ FAVORITES ]  [ UNCAUGHT ]
            APPLIED   type:electric  +  favorites:true                    [ CLEAR ALL ]
            EMPTY     0 results for "missingno"                          [ RESET ]
            OVERFLOW  [ TYPE ] [ RARITY ] [ SHINY ] [ FAVORITE ] [ MORE +3 ]
            """,
            font: BuddyMonBrand.Font.regular(10),
            highlights: ["* ELECTRIC": BuddyMonBrand.pikachu],
            lineSpacing: 7
        )
        let stack = vertical(spacing: BuddyMonBrand.Spacing.medium)
        stack.alignment = .leading
        stack.addArrangedSubview(controls)
        stack.addArrangedSubview(filters)
        return specimenSection(
            "23",
            "COLLECTION TOOLBAR + FILTERS",
            "Search, sort, type/rarity filters, counts, applied chips, clear/reset, no results, and filter-overflow states.",
            stack
        )
    }

    private func dexComponentSection() -> NSView {
        let cells = sampleRow([
            dexCell("#001", name: "BULBASAUR", state: "CAUGHT", color: BuddyMonBrand.starterGrass),
            dexCell("#007", name: "SQUIRTLE", state: "SELECTED", color: BuddyMonBrand.starterWater),
            dexCell("#025", name: "PIKACHU", state: "FAVORITE ★", color: BuddyMonBrand.pikachu),
            dexCell("#004", name: "?????", state: "UNCAUGHT", color: BuddyMonBrand.textSecondary),
            dexCell("#133", name: "★ SHINY", state: "RARE", color: BuddyMonBrand.rarity),
            dexCell("#151", name: "NO ART", state: "FALLBACK", color: BuddyMonBrand.textSecondary),
        ])
        let completion = text(
            "DEX COMPLETION  [############........]  093 / 151  (61%)     SEEN 118     SHINY 004",
            color: BuddyMonBrand.textPrimary,
            font: BuddyMonBrand.Font.strong(10)
        )
        let stack = vertical(spacing: BuddyMonBrand.Spacing.medium)
        stack.alignment = .leading
        stack.addArrangedSubview(cells)
        stack.addArrangedSubview(completion)
        return specimenSection(
            "24",
            "POKEDEX CELLS + COMPLETION",
            "Numbered caught, selected, favorite, silhouette/uncaught, shiny/rare, missing-art, and completion states.",
            stack
        )
    }

    private func journalComponentSection() -> NSView {
        let filters = text(
            "[ ALL ]  [ CATCHES ]  [ RARES ]  [ SHINIES ]  [ EVOLUTIONS ]  [ LEVEL UPS ]",
            color: BuddyMonBrand.textSecondary,
            font: BuddyMonBrand.Font.strong(10)
        )
        let events = highlightedText(
            """
            07/15 14:12  CATCH       SQUIRTLE joined your Box.              +1,240 xp
            07/15 14:09  ★ RARE      A rare signal appeared nearby.
            07/14 19:44  ★ SHINY     BULBASAUR revealed a shiny form.
            07/14 18:02  EVOLUTION   BULBASAUR can evolve into IVYSAUR.
            07/13 11:38  LEVEL UP    PIKACHU reached Lv.25.
            07/12 09:10  ESCAPED     Wild encounter ended safely.
            """,
            font: BuddyMonBrand.Font.regular(11),
            highlights: [
                "SQUIRTLE": BuddyMonBrand.starterWater,
                "★ RARE": BuddyMonBrand.rarity,
                "★ SHINY": BuddyMonBrand.rarity,
                "BULBASAUR": BuddyMonBrand.starterGrass,
                "IVYSAUR": BuddyMonBrand.starterGrass,
                "PIKACHU": BuddyMonBrand.pikachu,
            ],
            lineSpacing: 7
        )
        let stack = vertical(spacing: BuddyMonBrand.Spacing.medium)
        stack.alignment = .leading
        stack.addArrangedSubview(filters)
        stack.addArrangedSubview(events)
        stack.addArrangedSubview(text("EMPTY FILTER: No shiny events yet.  [ SHOW ALL ]", color: BuddyMonBrand.textSecondary, font: BuddyMonBrand.Font.regular(10)))
        return specimenSection(
            "25",
            "JOURNAL FILTERS + EVENT ROWS",
            "Catch, rare, shiny, evolution, level-up, escaped, filtered-empty, and show-all patterns.",
            stack
        )
    }

    private func setupComponentSection() -> NSView {
        let compactSetup = BuddyMonCompactStarterSetupView(
            target: nil,
            chooseAction: nil
        )
        compactSetup.heightAnchor.constraint(
            equalToConstant: compactSetup.preferredSize.height
        ).isActive = true
        let compactLoading = BuddyMonCompactNoticeView(
            message: "Choosing your starter…",
            kind: .loading
        )
        compactLoading.heightAnchor.constraint(
            equalToConstant: compactLoading.preferredSize.height
        ).isActive = true
        let compactError = BuddyMonCompactNoticeView(
            message: "BuddyMon could not finish setup.\nYour local state was not changed.",
            kind: .error
        )
        compactError.heightAnchor.constraint(
            equalToConstant: compactError.preferredSize.height
        ).isActive = true
        let compactFlows = vertical(spacing: BuddyMonBrand.Spacing.medium)
        compactFlows.addArrangedSubview(sampleRow([compactSetup, compactLoading]))
        compactFlows.addArrangedSubview(compactError)

        let starters = sampleRow([
            starterChoice("PIKACHU", state: "SELECTED", color: BuddyMonBrand.pikachu),
            starterChoice("BULBASAUR", state: "DEFAULT", color: BuddyMonBrand.starterGrass),
            starterChoice("SQUIRTLE", state: "HOVER", color: BuddyMonBrand.starterWater),
            starterChoice("CHARMANDER", state: "DISABLED", color: BuddyMonBrand.brand),
        ])
        let setup = highlightedText(
            """
            SOURCE / CODEX       [ok] attached               [ DISCONNECT ]
            SOURCE / CLAUDE      [!!] permission needed      [ ENABLE ]
            SOURCE / AUGGIE      [--] not detected           [ LEARN MORE ]
            ART / BUILT-IN       [ok] active                 local
            ART / OPTIONAL       [..] installing             [########....] 64%
            LOGIN ITEM           [!!] approval required      [ OPEN SETTINGS ]
            REPAIR               [xx] 2 checks failed        [ RUN REPAIR ]
            """,
            font: BuddyMonBrand.Font.regular(11),
            highlights: ["[!!]": BuddyMonBrand.brand, "[xx]": BuddyMonBrand.brand],
            lineSpacing: 7
        )
        let stack = vertical(spacing: BuddyMonBrand.Spacing.medium)
        stack.alignment = .leading
        stack.addArrangedSubview(compactFlows)
        stack.addArrangedSubview(starters)
        stack.addArrangedSubview(setup)
        return specimenSection(
            "26",
            "STARTER + SOURCE + ART + REPAIR",
            "Starter selection, source connected/permission/missing, art fallback/install, login approval, and repair states.",
            stack
        )
    }

    private func tokenEdgeSection() -> NSView {
        let states = sampleRow([
            stateBlock("ZERO DATA", "No new activity yet.\nFirst scan sets a baseline.", color: BuddyMonBrand.textSecondary),
            stateBlock("OVERFLOW", "123,456,789 tokens\nvalue stays aligned", color: BuddyMonBrand.textPrimary),
            stateBlock("DETAIL OPEN", "07/15 / CODEX\ninput 98,765 / output 24,691", color: BuddyMonBrand.textPrimary),
            stateBlock("SOURCE ERROR", "Claude logs unavailable.\nOther sources remain visible.", color: BuddyMonBrand.brand),
        ])
        return specimenSection(
            "27",
            "TOKEN EDGE STATES",
            "No history/baseline, large-number overflow, expanded detail, partial-source failure, and preserved-report states.",
            states
        )
    }

    private func accessibilitySection() -> NSView {
        let keyboard = highlightedText(
            """
            KEYBOARD    ⌘1..⌘4 sections   ⌘K commands   ESC back   ↵ select
            FOCUS       > visible row     [[ focused control ]]   never color-only
            MOTION      cursor blinks     Reduce Motion => cursor remains solid
            CONTRAST    paper on black    muted copy remains readable
            VOICEOVER   action + state + Pokemon name + shortcut
            RESIZE      780px minimum     vertical scroll before content clipping
            """,
            font: BuddyMonBrand.Font.regular(11),
            highlights: ["[[ focused control ]]": BuddyMonBrand.brand],
            lineSpacing: 7
        )
        return specimenSection(
            "28",
            "KEYBOARD + ACCESSIBILITY",
            "The brand survives keyboard-only use, VoiceOver, reduced motion, narrow windows, and high-contrast needs.",
            keyboard
        )
    }

    private func specimenSection(
        _ number: String,
        _ title: String,
        _ detail: String,
        _ content: NSView
    ) -> NSView {
        let stack = vertical(spacing: BuddyMonBrand.Spacing.small)
        stack.alignment = .leading

        let heading = horizontal(spacing: BuddyMonBrand.Spacing.compact)
        heading.addArrangedSubview(text("\(number)::", color: BuddyMonBrand.brand, font: BuddyMonBrand.Font.strong(11)))
        heading.addArrangedSubview(text(title, color: BuddyMonBrand.textPrimary, font: BuddyMonBrand.Font.strong(13)))
        heading.addArrangedSubview(flexibleSpace())
        heading.addArrangedSubview(text("------------------------------------------------", color: BuddyMonBrand.rule, font: BuddyMonBrand.Font.regular(10)))
        stack.addArrangedSubview(heading)
        heading.widthAnchor.constraint(equalToConstant: BrandPreviewMetric.contentWidth).isActive = true
        let detailView = text(detail, color: BuddyMonBrand.textSecondary, font: BuddyMonBrand.Font.regular(10), lineSpacing: 2)
        stack.addArrangedSubview(detailView)
        detailView.widthAnchor.constraint(equalToConstant: BrandPreviewMetric.contentWidth).isActive = true
        stack.setCustomSpacing(BuddyMonBrand.Spacing.medium, after: stack.arrangedSubviews.last!)
        stack.addArrangedSubview(content)
        return stack
    }

    private func sampleRow(_ samples: [NSView]) -> NSView {
        let row = horizontal(spacing: BuddyMonBrand.Spacing.medium)
        row.alignment = .top
        row.distribution = .fill
        for sample in samples {
            row.addArrangedSubview(sample)
        }
        return row
    }

    private func controlSample(_ state: String, _ control: NSView) -> NSView {
        let stack = vertical(spacing: BuddyMonBrand.Spacing.compact)
        stack.addArrangedSubview(text(state, color: BuddyMonBrand.textSecondary, font: BuddyMonBrand.Font.strong(9)))
        stack.addArrangedSubview(control)
        return stack
    }

    private func fieldGuideControlSample(_ state: String, _ control: NSView) -> NSView {
        let surface = NSView()
        surface.wantsLayer = true
        surface.layer?.backgroundColor = BuddyMonBrand.Menu.surface.cgColor
        surface.layer?.cornerRadius = BuddyMonBrand.Geometry.cornerRadius
        surface.addSubview(control)
        control.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            control.leadingAnchor.constraint(
                equalTo: surface.leadingAnchor,
                constant: BuddyMonBrand.Menu.tightGap
            ),
            control.trailingAnchor.constraint(
                equalTo: surface.trailingAnchor,
                constant: -BuddyMonBrand.Menu.tightGap
            ),
            control.topAnchor.constraint(
                equalTo: surface.topAnchor,
                constant: BuddyMonBrand.Menu.microGap
            ),
            control.bottomAnchor.constraint(
                equalTo: surface.bottomAnchor,
                constant: -BuddyMonBrand.Menu.microGap
            ),
        ])
        return controlSample(state, surface)
    }

    private func surfaceSample(_ title: String, detail: String, level: Int) -> NSView {
        let surface = BuddyMonBrand.makeSurface(focused: level == 3)
        let colors = [BuddyMonBrand.canvas, BuddyMonBrand.surface, BuddyMonBrand.rule.withAlphaComponent(0.22), BuddyMonBrand.surface]
        surface.layer?.backgroundColor = colors[level].cgColor
        surface.heightAnchor.constraint(equalToConstant: 88).isActive = true

        let copy = vertical(spacing: BuddyMonBrand.Spacing.compact)
        copy.addArrangedSubview(text(title, color: BuddyMonBrand.textPrimary, font: BuddyMonBrand.Font.strong(11)))
        copy.addArrangedSubview(text(detail, color: BuddyMonBrand.textSecondary, font: BuddyMonBrand.Font.regular(9), lineSpacing: 2))
        surface.addSubview(copy)
        copy.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            copy.leadingAnchor.constraint(equalTo: surface.leadingAnchor, constant: BuddyMonBrand.Spacing.small),
            copy.trailingAnchor.constraint(lessThanOrEqualTo: surface.trailingAnchor, constant: -BuddyMonBrand.Spacing.small),
            copy.centerYAnchor.constraint(equalTo: surface.centerYAnchor),
        ])
        return surface
    }

    private func brandButton(
        _ title: String,
        role: BuddyMonBrand.ButtonRole = .secondary,
        state: BuddyMonBrand.ControlState = .normal
    ) -> NSButton {
        BuddyMonBrand.makeButton(title, role: role, state: state)
    }

    private func brandField(
        _ value: String,
        placeholder: String,
        state: BuddyMonBrand.FieldState = .normal
    ) -> NSTextField {
        BuddyMonBrand.makeField(
            value: value,
            placeholder: placeholder,
            state: state,
            interactive: false
        )
    }

    private func brandToggle(_ value: String, color: NSColor) -> NSTextField {
        BuddyMonBrand.makeControlLabel(value, color: color)
    }

    private func spriteFrame(_ state: String, name: String, color: NSColor, edge: String) -> NSView {
        let frame = vertical(spacing: BuddyMonBrand.Spacing.compact)
        frame.addArrangedSubview(text(state, color: BuddyMonBrand.textSecondary, font: BuddyMonBrand.Font.strong(9)))
        frame.addArrangedSubview(highlightedText(
            """
            \(edge)---------\(edge)
            |   /\\_/\\   |
            |  ( o.o )  |
            |   > ^ <   |
            \(edge)---------\(edge)
            \(name)
            """,
            font: BuddyMonBrand.Font.regular(10),
            highlights: [name: color],
            lineSpacing: 2
        ))
        return frame
    }

    private func stateBlock(_ title: String, _ body: String, color: NSColor) -> NSView {
        let stack = vertical(spacing: BuddyMonBrand.Spacing.compact)
        stack.addArrangedSubview(text("[ \(title) ]", color: color, font: BuddyMonBrand.Font.strong(10)))
        stack.addArrangedSubview(text(body, color: BuddyMonBrand.textPrimary, font: BuddyMonBrand.Font.regular(10), lineSpacing: 4))
        return stack
    }

    private func showcaseSlot(_ index: String, state: String, name: String, color: NSColor) -> NSView {
        highlightedText(
            """
            +----------+
            | SLOT \(index)  |
            | \(state.padding(toLength: 8, withPad: " ", startingAt: 0)) |
            +----------+
            \(name)
            """,
            font: BuddyMonBrand.Font.regular(9),
            highlights: [name: color],
            lineSpacing: 2
        )
    }

    private func brandDialog(
        _ title: String,
        body: String,
        actions: String,
        highlight: String,
        highlightColor: NSColor
    ) -> NSView {
        highlightedText(
            """
            +------------------------------------------------+
            | \(title)
            +------------------------------------------------+
            | \(body)
            |
            | \(actions)
            +------------------------------------------------+
            """,
            font: BuddyMonBrand.Font.regular(10),
            highlights: [highlight: highlightColor],
            lineSpacing: 4
        )
    }

    private func notificationLine(_ kind: String, _ message: String, action: String) -> NSView {
        let row = horizontal(spacing: BuddyMonBrand.Spacing.small)
        row.addArrangedSubview(text("[\(kind)]", color: kind == "ERROR" ? BuddyMonBrand.brand : BuddyMonBrand.textPrimary, font: BuddyMonBrand.Font.strong(10)))
        row.addArrangedSubview(text(message, color: BuddyMonBrand.textPrimary, font: BuddyMonBrand.Font.regular(10)))
        row.addArrangedSubview(flexibleSpace())
        row.addArrangedSubview(text("[ \(action) ]", color: BuddyMonBrand.textPrimary, font: BuddyMonBrand.Font.strong(10)))
        return row
    }

    private func buddyHero(
        state: String,
        name: String,
        detail: String,
        meter: String,
        color: NSColor
    ) -> NSView {
        highlightedText(
            """
            [ \(state) ]
              /\\_/\\
             ( o.o )    \(name)
              > ^ <     \(detail)
                        \(meter)
            """,
            font: BuddyMonBrand.Font.regular(10),
            highlights: [name: color],
            lineSpacing: 3
        )
    }

    private func battlePlate(
        title: String,
        buddy: String,
        buddyHP: String,
        wild: String,
        wildHP: String,
        status: String
    ) -> NSView {
        highlightedText(
            """
            [ \(title) ]
            BUDDY  \(buddy)
            HP     \(buddyHP)
            --------------------------------
            WILD   \(wild)
            HP     \(wildHP)
            \(status)
            """,
            font: BuddyMonBrand.Font.regular(10),
            highlights: [
                "PIKACHU": BuddyMonBrand.pikachu,
                "SQUIRTLE": BuddyMonBrand.starterWater,
                "BULBASAUR": BuddyMonBrand.starterGrass,
                "WARNING": BuddyMonBrand.brand,
            ],
            lineSpacing: 4
        )
    }

    private func profileSummary(
        state: String,
        name: String,
        identity: String,
        details: String,
        action: String,
        color: NSColor
    ) -> NSView {
        highlightedText(
            """
            [ \(state) ]
            \(name)
            \(identity)
            \(details)
            --------------------------------
            \(action)
            """,
            font: BuddyMonBrand.Font.regular(10),
            highlights: [name: color],
            lineSpacing: 4
        )
    }

    private func dexCell(_ number: String, name: String, state: String, color: NSColor) -> NSView {
        highlightedText(
            """
            +----------+
            | \(number)     |
            |   /\\_/\\  |
            |  ( o.o ) |
            +----------+
            \(name)
            \(state)
            """,
            font: BuddyMonBrand.Font.regular(9),
            highlights: [name: color],
            lineSpacing: 2
        )
    }

    private func starterChoice(_ name: String, state: String, color: NSColor) -> NSView {
        highlightedText(
            """
            +--------------+
            | \(state.padding(toLength: 12, withPad: " ", startingAt: 0)) |
            |    /\\_/\\    |
            |   ( o.o )   |
            +--------------+
            \(name)
            """,
            font: BuddyMonBrand.Font.regular(9),
            highlights: [name: color],
            lineSpacing: 2
        )
    }

    private func footnote() -> NSView {
        let row = horizontal(spacing: BuddyMonBrand.Spacing.small)
        row.addArrangedSubview(text("⌘⇧B / BUDDYMON / REDLINE MONO", color: BuddyMonBrand.brand, font: BuddyMonBrand.Font.strong(10)))
        row.addArrangedSubview(text("//", color: BuddyMonBrand.rule, font: BuddyMonBrand.Font.regular(10)))
        row.addArrangedSubview(text("spacing rhythm 04 / 08 / 12 / 20 / 32 / 48 / 72", color: BuddyMonBrand.textSecondary, font: BuddyMonBrand.Font.regular(10)))
        row.addArrangedSubview(flexibleSpace())
        row.addArrangedSubview(text("CANONICAL BRAND REFERENCE / NO STATE WRITES", color: BuddyMonBrand.textSecondary, font: BuddyMonBrand.Font.regular(10)))
        return row
    }

    private func vertical(spacing: CGFloat) -> NSStackView {
        let stack = NSStackView()
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = spacing
        return stack
    }

    private func horizontal(spacing: CGFloat) -> NSStackView {
        let stack = NSStackView()
        stack.orientation = .horizontal
        stack.spacing = spacing
        return stack
    }

    private func flexibleSpace() -> NSView {
        let space = NSView()
        space.setContentHuggingPriority(.defaultLow, for: .horizontal)
        return space
    }

    private func text(
        _ value: String,
        color: NSColor,
        font: NSFont,
        lineSpacing: CGFloat = 0
    ) -> NSTextField {
        let label = NSTextField(labelWithString: "")
        label.maximumNumberOfLines = 0
        label.lineBreakMode = .byWordWrapping
        label.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)

        let paragraph = NSMutableParagraphStyle()
        paragraph.lineSpacing = lineSpacing
        label.attributedStringValue = NSAttributedString(
            string: value,
            attributes: [
                .font: font,
                .foregroundColor: color,
                .paragraphStyle: paragraph,
            ]
        )
        return label
    }

    private func highlightedText(
        _ value: String,
        font: NSFont,
        highlights: [String: NSColor],
        lineSpacing: CGFloat
    ) -> NSTextField {
        let label = text(
            value,
            color: BuddyMonBrand.textPrimary,
            font: font,
            lineSpacing: lineSpacing
        )
        let attributed = NSMutableAttributedString(attributedString: label.attributedStringValue)
        for (needle, color) in highlights {
            let source = attributed.string as NSString
            var search = NSRange(location: 0, length: source.length)
            while search.length > 0 {
                let match = source.range(of: needle, options: [], range: search)
                if match.location == NSNotFound { break }
                attributed.addAttribute(.foregroundColor, value: color, range: match)
                let next = match.location + match.length
                search = NSRange(location: next, length: source.length - next)
            }
        }
        label.attributedStringValue = attributed
        return label
    }
}

private enum BrandSnapshotError: Error {
    case missingDocument
    case invalidSize
    case cannotCreateBitmap
    case cannotEncodePNG
}

private final class BrandPreviewFlippedDocumentView: NSView {
    override var isFlipped: Bool { true }
}

private final class BrandBlockCursor: NSTextField {
    init() {
        super.init(frame: .zero)
        isBezeled = false
        isEditable = false
        isSelectable = false
        drawsBackground = false
        stringValue = "█"
        font = BuddyMonBrand.Font.strong(13)
        textColor = BuddyMonBrand.brand
        wantsLayer = true
        setContentHuggingPriority(.required, for: .horizontal)

        if !NSWorkspace.shared.accessibilityDisplayShouldReduceMotion {
            let blink = CABasicAnimation(keyPath: "opacity")
            blink.fromValue = 1.0
            blink.toValue = 0.12
            blink.duration = 0.48
            blink.autoreverses = true
            blink.repeatCount = .infinity
            blink.timingFunction = CAMediaTimingFunction(name: .linear)
            layer?.add(blink, forKey: "brand-cursor-blink")
        }
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }
}
#endif
