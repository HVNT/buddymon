import AppKit
import Foundation

struct MenuBarBuddyFrame: Decodable {
    let durationMilliseconds: Int
    let title: String
    let accessibilityLabel: String
    let imageBase64: String
    let pixelWidth: Int
    let pixelHeight: Int

    enum CodingKeys: String, CodingKey {
        case durationMilliseconds = "duration_ms"
        case title
        case accessibilityLabel = "accessibility_label"
        case imageBase64 = "image_base64"
        case pixelWidth = "pixel_width"
        case pixelHeight = "pixel_height"
    }
}

struct MenuBarBuddySequence: Decodable {
    let stateID: String
    let sequenceID: String
    let label: String
    let group: String
    let coverage: String
    let startedAt: TimeInterval
    let loops: Bool
    let reduceMotionFrame: Int
    let durationMilliseconds: Int
    let frames: [MenuBarBuddyFrame]

    enum CodingKeys: String, CodingKey {
        case stateID = "state_id"
        case sequenceID = "sequence_id"
        case label
        case group
        case coverage
        case startedAt = "started_at"
        case loops = "loop"
        case reduceMotionFrame = "reduce_motion_frame"
        case durationMilliseconds = "duration_ms"
        case frames
    }
}

struct MenuBarBuddyPayload: Decodable {
    let schemaVersion: Int
    let baseline: MenuBarBuddySequence
    let moments: [MenuBarBuddySequence]
    let persistent: MenuBarBuddySequence?

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case baseline
        case moments
        case persistent
    }

    static func decode(from status: [String: Any]) -> MenuBarBuddyPayload? {
        guard
            let object = status["menu_bar"],
            JSONSerialization.isValidJSONObject(object),
            let data = try? JSONSerialization.data(withJSONObject: object)
        else { return nil }
        return try? JSONDecoder().decode(MenuBarBuddyPayload.self, from: data)
    }
}

struct MenuBarBuddyPreviewEnvelope: Decodable {
    let schemaVersion: Int
    let cancel: Bool
    let holdMilliseconds: Int
    let sequence: MenuBarBuddySequence?

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case cancel
        case holdMilliseconds = "hold_ms"
        case sequence
    }
}

@MainActor
final class MenuBarBuddyPlayer {
    enum PlaybackMode {
        case once
        case loop
        case hold
    }

    private weak var button: NSButton?
    private var timer: Timer?
    private var generation = 0
    var reduceMotionOverride: Bool?

    init(button: NSButton) {
        self.button = button
        button.isBordered = false
        button.imageScaling = .scaleProportionallyDown
        button.imagePosition = .imageOnly
    }

    func stop() {
        generation += 1
        timer?.invalidate()
        timer = nil
    }

    func showText(_ title: String, accessibilityLabel: String) {
        stop()
        guard let button else { return }
        button.image = nil
        button.title = title
        button.imagePosition = .noImage
        button.toolTip = accessibilityLabel
        button.setAccessibilityLabel(accessibilityLabel)
    }

    func play(
        _ sequence: MenuBarBuddySequence,
        mode: PlaybackMode,
        completion: (() -> Void)? = nil
    ) {
        stop()
        guard !sequence.frames.isEmpty else {
            completion?()
            return
        }
        let activeGeneration = generation
        if reducesMotion {
            let index = min(
                max(0, sequence.reduceMotionFrame),
                sequence.frames.count - 1
            )
            show(sequence.frames[index])
            if mode == .once {
                schedule(
                    milliseconds: min(1_400, max(700, sequence.durationMilliseconds)),
                    generation: activeGeneration,
                    completion: completion
                )
            }
            return
        }
        playFrame(
            at: 0,
            in: sequence,
            mode: mode,
            generation: activeGeneration,
            completion: completion
        )
    }

    private var reducesMotion: Bool {
        reduceMotionOverride
            ?? NSWorkspace.shared.accessibilityDisplayShouldReduceMotion
    }

    private func playFrame(
        at index: Int,
        in sequence: MenuBarBuddySequence,
        mode: PlaybackMode,
        generation activeGeneration: Int,
        completion: (() -> Void)?
    ) {
        guard generation == activeGeneration else { return }
        let frame = sequence.frames[index]
        show(frame)
        let nextIndex = index + 1
        schedule(
            milliseconds: frame.durationMilliseconds,
            generation: activeGeneration
        ) { [weak self] in
            guard let self else { return }
            if nextIndex < sequence.frames.count {
                self.playFrame(
                    at: nextIndex,
                    in: sequence,
                    mode: mode,
                    generation: activeGeneration,
                    completion: completion
                )
                return
            }
            switch mode {
            case .loop:
                self.playFrame(
                    at: 0,
                    in: sequence,
                    mode: mode,
                    generation: activeGeneration,
                    completion: completion
                )
            case .once:
                completion?()
            case .hold:
                break
            }
        }
    }

    private func schedule(
        milliseconds: Int,
        generation activeGeneration: Int,
        completion: (() -> Void)?
    ) {
        timer?.invalidate()
        timer = Timer.scheduledTimer(
            withTimeInterval: TimeInterval(milliseconds) / 1_000,
            repeats: false
        ) { [weak self] _ in
            Task { @MainActor in
                guard let self, self.generation == activeGeneration else { return }
                completion?()
            }
        }
    }

    private func show(_ frame: MenuBarBuddyFrame) {
        guard let button else { return }
        let data = Data(base64Encoded: frame.imageBase64)
        let image = data.flatMap(NSImage.init(data:))
        let targetHeight = BuddyMonBrand.Geometry.menuBarIconHeight
        if let image {
            let width = max(1, frame.pixelWidth)
            let height = max(1, frame.pixelHeight)
            image.size = NSSize(
                width: targetHeight * CGFloat(width) / CGFloat(height),
                height: targetHeight
            )
            image.isTemplate = false
        }
        button.image = image
        button.title = frame.title.isEmpty ? "" : " \(frame.title)"
        button.imagePosition = frame.title.isEmpty ? .imageOnly : .imageLeft
        button.toolTip = frame.accessibilityLabel
        button.setAccessibilityLabel(frame.accessibilityLabel)
    }
}

@MainActor
final class MenuBarBuddyController {
    private enum DisplayKind {
        case baseline
        case persistent
        case moment
        case preview
        case fallback
    }

    private let player: MenuBarBuddyPlayer
    private var payload: MenuBarBuddyPayload?
    private var momentQueue: [MenuBarBuddySequence] = []
    private var seenSequenceIDs: [String] = []
    private var seenSequenceIDSet: Set<String> = []
    private var displayedSequenceID: String?
    private var displayKind: DisplayKind = .fallback
    private var currentMomentID: String?
    private var previewTimer: Timer?
    private var isPreviewing = false

    init(button: NSStatusBarButton) {
        player = MenuBarBuddyPlayer(button: button)
    }

    func showBooting() {
        clearPlayback()
        displayKind = .fallback
        player.showText("…", accessibilityLabel: "BuddyMon is starting")
    }

    func showUnavailable() {
        clearPlayback()
        displayKind = .fallback
        player.showText("?", accessibilityLabel: "BuddyMon status unavailable")
    }

    func apply(status: [String: Any]) {
        guard let decoded = MenuBarBuddyPayload.decode(from: status) else {
            showLegacy(status: status)
            return
        }
        payload = decoded
        for moment in decoded.moments where !seenSequenceIDSet.contains(moment.sequenceID) {
            remember(moment.sequenceID)
            momentQueue.append(moment)
        }
        momentQueue.sort { $0.startedAt < $1.startedAt }

        guard !isPreviewing else { return }
        if currentMomentID == nil, !momentQueue.isEmpty {
            playNextMoment()
            return
        }
        guard currentMomentID == nil else { return }
        showPersistentOrBaselineIfNeeded()
    }

    func preview(_ envelope: MenuBarBuddyPreviewEnvelope) {
        if envelope.cancel {
            finishPreview()
            return
        }
        guard let sequence = envelope.sequence else { return }

        previewTimer?.invalidate()
        currentMomentID = nil
        isPreviewing = true
        displayedSequenceID = sequence.sequenceID
        displayKind = .preview
        player.play(sequence, mode: sequence.loops ? .loop : .once)

        let holdMilliseconds = max(
            100,
            envelope.holdMilliseconds > 0
                ? envelope.holdMilliseconds
                : sequence.durationMilliseconds + 500
        )
        previewTimer = Timer.scheduledTimer(
            withTimeInterval: TimeInterval(holdMilliseconds) / 1_000,
            repeats: false
        ) { [weak self] _ in
            Task { @MainActor in
                self?.finishPreview()
            }
        }
    }

    private func finishPreview() {
        guard isPreviewing else { return }
        previewTimer?.invalidate()
        previewTimer = nil
        isPreviewing = false
        displayedSequenceID = nil
        if !momentQueue.isEmpty {
            playNextMoment()
        } else {
            showPersistentOrBaselineIfNeeded(force: true)
        }
    }

    private func playNextMoment() {
        guard !momentQueue.isEmpty else {
            currentMomentID = nil
            showPersistentOrBaselineIfNeeded(force: true)
            return
        }
        let moment = momentQueue.removeFirst()
        currentMomentID = moment.sequenceID
        displayedSequenceID = moment.sequenceID
        displayKind = .moment
        player.play(moment, mode: .once) { [weak self] in
            guard let self else { return }
            self.currentMomentID = nil
            self.playNextMoment()
        }
    }

    private func showPersistentOrBaselineIfNeeded(force: Bool = false) {
        guard let payload else { return }
        if let persistent = payload.persistent {
            guard
                force
                    || displayKind != .persistent
                    || displayedSequenceID != persistent.sequenceID
            else { return }
            displayedSequenceID = persistent.sequenceID
            displayKind = .persistent
            player.play(persistent, mode: .hold)
            return
        }
        let baseline = payload.baseline
        guard
            force
                || displayKind != .baseline
                || displayedSequenceID != baseline.sequenceID
        else { return }
        displayedSequenceID = baseline.sequenceID
        displayKind = .baseline
        player.play(baseline, mode: baseline.loops ? .loop : .hold)
    }

    private func remember(_ sequenceID: String) {
        seenSequenceIDSet.insert(sequenceID)
        seenSequenceIDs.append(sequenceID)
        while seenSequenceIDs.count > 128 {
            let forgotten = seenSequenceIDs.removeFirst()
            seenSequenceIDSet.remove(forgotten)
        }
    }

    private func clearPlayback() {
        previewTimer?.invalidate()
        previewTimer = nil
        isPreviewing = false
        player.stop()
        payload = nil
        momentQueue.removeAll()
        currentMomentID = nil
        displayedSequenceID = nil
    }

    private func showLegacy(status: [String: Any]) {
        clearPlayback()
        guard
            let button = status["menu_bar_icon_base64"] as? String,
            let data = Data(base64Encoded: button),
            let image = NSImage(data: data)
        else {
            player.showText("BM", accessibilityLabel: "BuddyMon")
            return
        }
        image.size = NSSize(
            width: BuddyMonBrand.Geometry.menuBarIconHeight,
            height: BuddyMonBrand.Geometry.menuBarIconHeight
        )
        image.isTemplate = false
        let frame = MenuBarBuddyFrame(
            durationMilliseconds: 1_000,
            title: (status["alert"] as? Bool) == true ? "!" : "",
            accessibilityLabel: "BuddyMon",
            imageBase64: button,
            pixelWidth: Int(image.size.width),
            pixelHeight: Int(image.size.height)
        )
        let sequence = MenuBarBuddySequence(
            stateID: "legacy",
            sequenceID: "legacy",
            label: "BuddyMon",
            group: "foundation",
            coverage: "legacy",
            startedAt: 0,
            loops: false,
            reduceMotionFrame: 0,
            durationMilliseconds: 1_000,
            frames: [frame]
        )
        displayKind = .fallback
        player.play(sequence, mode: .hold)
    }
}
