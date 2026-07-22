import AppKit
import Foundation

struct MenuBarHarnessVariant: Decodable {
    let id: String
    let label: String
}

struct MenuBarHarnessPayload: Decodable {
    let schemaVersion: Int
    let kind: String
    let environmentVariants: [MenuBarHarnessVariant]
    let sequences: [MenuBarBuddySequence]

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case kind
        case environmentVariants = "environment_variants"
        case sequences
    }
}

@MainActor
final class MenuBarStateHarnessView: NSView {
    private struct Playback {
        let sequence: MenuBarBuddySequence
        let animatedPlayers: [MenuBarBuddyPlayer]
        let reducedMotionPlayer: MenuBarBuddyPlayer
    }

    private let scrollView = NSScrollView()
    private let document = FlippedMenuBarHarnessView()
    private let stack = NSStackView()
    private var playbacks: [Playback] = []
    private var animationButton: NSButton!
    private var animationsAreRunning = true

    let preferredSize = NSSize(width: 1_180, height: 780)

    init(payload: MenuBarHarnessPayload, animationsEnabled: Bool = true) {
        super.init(frame: .zero)
        BuddyMonBrand.applySurface(to: self)
        build(payload: payload)
        setAnimationsRunning(animationsEnabled)
    }

    required init?(coder: NSCoder) {
        nil
    }

    var snapshotView: NSView {
        document.layoutSubtreeIfNeeded()
        let fitting = document.fittingSize
        document.frame = NSRect(
            origin: .zero,
            size: NSSize(width: preferredSize.width, height: max(1, fitting.height))
        )
        document.layoutSubtreeIfNeeded()
        return document
    }

    func prepareForSnapshot() {
        animationsAreRunning = false
        animationButton.title = "PLAY"
        for playback in playbacks {
            playback.animatedPlayers.forEach { player in
                player.reduceMotionOverride = true
                player.play(playback.sequence, mode: .hold)
            }
            playback.reducedMotionPlayer.reduceMotionOverride = true
            playback.reducedMotionPlayer.play(playback.sequence, mode: .hold)
        }
    }

    private func build(payload: MenuBarHarnessPayload) {
        scrollView.translatesAutoresizingMaskIntoConstraints = false
        scrollView.hasVerticalScroller = true
        scrollView.hasHorizontalScroller = false
        scrollView.drawsBackground = true
        scrollView.backgroundColor = BuddyMonBrand.canvas
        addSubview(scrollView)

        document.translatesAutoresizingMaskIntoConstraints = false
        BuddyMonBrand.applySurface(to: document)
        scrollView.documentView = document

        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = BuddyMonBrand.Spacing.medium
        stack.translatesAutoresizingMaskIntoConstraints = false
        document.addSubview(stack)

        NSLayoutConstraint.activate([
            scrollView.leadingAnchor.constraint(equalTo: leadingAnchor),
            scrollView.trailingAnchor.constraint(equalTo: trailingAnchor),
            scrollView.topAnchor.constraint(equalTo: topAnchor),
            scrollView.bottomAnchor.constraint(equalTo: bottomAnchor),
            document.widthAnchor.constraint(equalToConstant: preferredSize.width),
            stack.leadingAnchor.constraint(
                equalTo: document.leadingAnchor,
                constant: BuddyMonBrand.Spacing.large
            ),
            stack.trailingAnchor.constraint(
                equalTo: document.trailingAnchor,
                constant: -BuddyMonBrand.Spacing.large
            ),
            stack.topAnchor.constraint(
                equalTo: document.topAnchor,
                constant: BuddyMonBrand.Spacing.large
            ),
            stack.bottomAnchor.constraint(
                equalTo: document.bottomAnchor,
                constant: -BuddyMonBrand.Spacing.large
            ),
        ])

        stack.addArrangedSubview(header(payload: payload))
        stack.addArrangedSubview(columnHeader())

        var lastGroup: String?
        for sequence in payload.sequences {
            if sequence.group != lastGroup {
                stack.addArrangedSubview(groupHeading(sequence.group))
                lastGroup = sequence.group
            }
            stack.addArrangedSubview(sequenceRow(sequence))
        }
    }

    private func header(payload: MenuBarHarnessPayload) -> NSView {
        let title = label(
            "MENU-BAR BUDDY / STATE HARNESS",
            font: BuddyMonBrand.Font.strong(22),
            color: BuddyMonBrand.textPrimary
        )
        let subtitle = label(
            "Shipping renderer · true 20-point art · \(payload.sequences.count) canonical states",
            font: BuddyMonBrand.Font.regular(12),
            color: BuddyMonBrand.textSecondary
        )
        let variants = label(
            payload.environmentVariants.map(\.label).joined(separator: "  ·  "),
            font: BuddyMonBrand.Font.regular(10),
            color: BuddyMonBrand.textSecondary
        )

        animationButton = BuddyMonBrand.makeButton(
            "PAUSE",
            target: self,
            action: #selector(toggleAnimations),
            role: .secondary
        )
        let restart = BuddyMonBrand.makeButton(
            "RESTART",
            target: self,
            action: #selector(restartAnimations),
            role: .primary
        )
        let controls = NSStackView(views: [animationButton, restart])
        controls.orientation = .horizontal
        controls.alignment = .centerY
        controls.spacing = BuddyMonBrand.Spacing.compact

        let copy = NSStackView(views: [title, subtitle, variants])
        copy.orientation = .vertical
        copy.alignment = .leading
        copy.spacing = BuddyMonBrand.Spacing.compact

        let header = NSStackView(views: [copy, NSView(), controls])
        header.orientation = .horizontal
        header.alignment = .top
        header.spacing = BuddyMonBrand.Spacing.medium
        header.widthAnchor.constraint(
            equalToConstant: preferredSize.width - BuddyMonBrand.Spacing.large * 2
        ).isActive = true
        return header
    }

    private func columnHeader() -> NSView {
        let row = NSStackView()
        row.orientation = .horizontal
        row.alignment = .centerY
        row.spacing = BuddyMonBrand.Spacing.small
        row.addArrangedSubview(fixedLabel("STATE", width: 220))
        row.addArrangedSubview(fixedLabel("LIGHT", width: 250))
        row.addArrangedSubview(fixedLabel("DARK", width: 250))
        row.addArrangedSubview(fixedLabel("SELECTED / REDUCE MOTION", width: 310))
        return row
    }

    private func groupHeading(_ group: String) -> NSView {
        let heading = label(
            group.uppercased(),
            font: BuddyMonBrand.Font.strong(13),
            color: BuddyMonBrand.pokemonBlue
        )
        heading.widthAnchor.constraint(
            equalToConstant: preferredSize.width - BuddyMonBrand.Spacing.large * 2
        ).isActive = true
        return heading
    }

    private func sequenceRow(_ sequence: MenuBarBuddySequence) -> NSView {
        let stateStack = NSStackView()
        stateStack.orientation = .vertical
        stateStack.alignment = .leading
        stateStack.spacing = BuddyMonBrand.Spacing.micro
        stateStack.addArrangedSubview(label(
            sequence.label.uppercased(),
            font: BuddyMonBrand.Font.strong(11),
            color: BuddyMonBrand.textPrimary
        ))
        stateStack.addArrangedSubview(label(
            sequence.stateID,
            font: BuddyMonBrand.Font.regular(10),
            color: BuddyMonBrand.textSecondary
        ))
        stateStack.addArrangedSubview(label(
            "\(sequence.frames.count) frame\(sequence.frames.count == 1 ? "" : "s") · \(sequence.coverage)",
            font: BuddyMonBrand.Font.regular(9),
            color: coverageColor(sequence.coverage)
        ))
        stateStack.widthAnchor.constraint(equalToConstant: 220).isActive = true

        let light = menuBarSample(sequence, appearance: .aqua, selected: false)
        let dark = menuBarSample(sequence, appearance: .darkAqua, selected: false)
        let selected = menuBarSample(
            sequence,
            appearance: .darkAqua,
            selected: true,
            reduceMotion: true,
            width: 310
        )

        let row = NSStackView(views: [stateStack, light.view, dark.view, selected.view])
        row.orientation = .horizontal
        row.alignment = .centerY
        row.spacing = BuddyMonBrand.Spacing.small
        row.edgeInsets = NSEdgeInsets(
            top: BuddyMonBrand.Spacing.small,
            left: BuddyMonBrand.Spacing.small,
            bottom: BuddyMonBrand.Spacing.small,
            right: BuddyMonBrand.Spacing.small
        )
        BuddyMonBrand.applySurface(to: row, inset: true)
        row.widthAnchor.constraint(
            equalToConstant: preferredSize.width - BuddyMonBrand.Spacing.large * 2
        ).isActive = true
        row.heightAnchor.constraint(greaterThanOrEqualToConstant: 72).isActive = true

        playbacks.append(Playback(
            sequence: sequence,
            animatedPlayers: [light.player, dark.player],
            reducedMotionPlayer: selected.player
        ))
        return row
    }

    private func menuBarSample(
        _ sequence: MenuBarBuddySequence,
        appearance: NSAppearance.Name,
        selected: Bool,
        reduceMotion: Bool = false,
        width: CGFloat = 250
    ) -> (view: NSView, player: MenuBarBuddyPlayer) {
        let strip = NSView()
        strip.translatesAutoresizingMaskIntoConstraints = false
        strip.wantsLayer = true
        strip.appearance = NSAppearance(named: appearance)
        strip.layer?.backgroundColor = (
            appearance == .darkAqua
                ? NSColor.black.withAlphaComponent(0.82)
                : NSColor.white.withAlphaComponent(0.94)
        ).cgColor
        strip.layer?.borderColor = BuddyMonBrand.rule.cgColor
        strip.layer?.borderWidth = BuddyMonBrand.Geometry.borderWidth

        let button = NSButton()
        button.translatesAutoresizingMaskIntoConstraints = false
        button.isBordered = false
        button.appearance = strip.appearance
        button.wantsLayer = true
        if selected {
            button.layer?.backgroundColor = NSColor.selectedContentBackgroundColor.cgColor
        }
        strip.addSubview(button)
        NSLayoutConstraint.activate([
            strip.widthAnchor.constraint(equalToConstant: width),
            strip.heightAnchor.constraint(equalToConstant: 32),
            button.centerXAnchor.constraint(equalTo: strip.centerXAnchor),
            button.centerYAnchor.constraint(equalTo: strip.centerYAnchor),
            button.heightAnchor.constraint(equalToConstant: 24),
        ])

        let player = MenuBarBuddyPlayer(button: button)
        player.reduceMotionOverride = reduceMotion
        return (strip, player)
    }

    private func fixedLabel(_ text: String, width: CGFloat) -> NSTextField {
        let field = label(
            text,
            font: BuddyMonBrand.Font.strong(10),
            color: BuddyMonBrand.textSecondary
        )
        field.widthAnchor.constraint(equalToConstant: width).isActive = true
        return field
    }

    private func label(_ text: String, font: NSFont, color: NSColor) -> NSTextField {
        let field = NSTextField(labelWithString: text)
        field.font = font
        field.textColor = color
        field.lineBreakMode = .byTruncatingTail
        return field
    }

    private func coverageColor(_ coverage: String) -> NSColor {
        switch coverage {
        case "automated": return BuddyMonBrand.starterGrass
        case "legacy_renderer": return BuddyMonBrand.starterGrass
        case "payload", "partial": return BuddyMonBrand.pikachu
        case "logic": return BuddyMonBrand.starterWater
        default: return BuddyMonBrand.textSecondary
        }
    }

    @objc private func toggleAnimations() {
        setAnimationsRunning(!animationsAreRunning)
    }

    @objc private func restartAnimations() {
        setAnimationsRunning(true)
    }

    private func setAnimationsRunning(_ running: Bool) {
        animationsAreRunning = running
        animationButton?.title = running ? "PAUSE" : "PLAY"
        for playback in playbacks {
            if running {
                playback.animatedPlayers.forEach { player in
                    player.reduceMotionOverride = false
                    player.play(playback.sequence, mode: .loop)
                }
                playback.reducedMotionPlayer.reduceMotionOverride = true
                playback.reducedMotionPlayer.play(playback.sequence, mode: .hold)
            } else {
                playback.animatedPlayers.forEach { $0.stop() }
                playback.reducedMotionPlayer.stop()
            }
        }
    }
}

private final class FlippedMenuBarHarnessView: NSView {
    override var isFlipped: Bool { true }
}
