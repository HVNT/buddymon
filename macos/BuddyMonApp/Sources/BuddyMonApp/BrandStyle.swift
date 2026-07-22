import AppKit
import Foundation
import QuartzCore

/// The only source of visual truth for shipping BuddyMon native UI.
///
/// New colors, type, spacing, geometry, or control treatments belong here
/// first, then in Brand Styles Preview and docs/brand.md in the same change.
enum BuddyMonBrand {
    static let systemName = "Redline Mono"

    // MARK: Color

    /// Interface planes stay monochrome. Color is reserved for brand focus,
    /// Pokemon identity, rarity, and a very small set of meaningful signals.
    static let canvas = NSColor(
        calibratedRed: 0.027,
        green: 0.025,
        blue: 0.031,
        alpha: 1
    )
    static let surface = NSColor(
        calibratedRed: 0.047,
        green: 0.043,
        blue: 0.052,
        alpha: 1
    )
    static let inset = NSColor(
        calibratedRed: 0.068,
        green: 0.063,
        blue: 0.074,
        alpha: 1
    )
    static let textPrimary = NSColor(
        calibratedRed: 0.92,
        green: 0.90,
        blue: 0.84,
        alpha: 1
    )
    static let textSecondary = NSColor(
        calibratedRed: 0.52,
        green: 0.50,
        blue: 0.48,
        alpha: 1
    )
    static let rule = NSColor(
        calibratedRed: 0.20,
        green: 0.19,
        blue: 0.22,
        alpha: 1
    )

    static let brand = NSColor(
        calibratedRed: 0.96,
        green: 0.10,
        blue: 0.13,
        alpha: 1
    )
    /// Secondary Pokemon-brand accent. Reserve it for Pokemon identity or
    /// official-brand references, never generic interface status.
    static let pokemonBlue = NSColor(
        calibratedRed: 0.28,
        green: 0.38,
        blue: 0.90,
        alpha: 1
    )
    static let rarity = NSColor(
        calibratedRed: 1.00,
        green: 0.25,
        blue: 0.72,
        alpha: 1
    )
    static let starterWater = NSColor(
        calibratedRed: 0.34,
        green: 0.62,
        blue: 1.00,
        alpha: 1
    )
    static let starterGrass = NSColor(
        calibratedRed: 0.38,
        green: 0.84,
        blue: 0.47,
        alpha: 1
    )
    static let pikachu = NSColor(
        calibratedRed: 1.00,
        green: 0.84,
        blue: 0.18,
        alpha: 1
    )

    // Semantic aliases prevent views from choosing colors by appearance.
    static let focus = brand
    static let alert = brand
    static let xpProgress = pikachu
    static let dataProgress = textPrimary

    // MARK: Spacing + geometry

    enum Spacing {
        static let micro: CGFloat = 4
        static let compact: CGFloat = 8
        static let small: CGFloat = 12
        static let medium: CGFloat = 20
        static let large: CGFloat = 32
        static let xlarge: CGFloat = 48
        static let section: CGFloat = 72

        // Semantic layout roles keep shipping screens on one rhythm.
        static let controlGap = compact
        static let panelPadding = small
        static let screenGap = large
        static let pageHorizontal = large
        static let pageVertical = xlarge
    }

    enum Geometry {
        static let borderWidth: CGFloat = 1
        static let focusBorderWidth: CGFloat = 2
        static let cornerRadius: CGFloat = 0
        static let controlHeight: CGFloat = 32
        static let menuBarIconHeight: CGFloat = 20
        static let contentWidth: CGFloat = 880
        static let homeMinimumWidth: CGFloat = 720
        static let homeMinimumHeight: CGFloat = 520
    }

    // MARK: Motion

    enum Motion {
        static let quickLinkHoverDuration: CFTimeInterval = 0.12
        static let quickLinkHoverAnimationKey = "buddymon-brand-quick-link-hover"

        static func animateQuickLinkHover(_ view: NSView, hovered: Bool) {
            view.wantsLayer = true
            guard let layer = view.layer else { return }
            guard !NSWorkspace.shared.accessibilityDisplayShouldReduceMotion else {
                layer.removeAnimation(forKey: quickLinkHoverAnimationKey)
                layer.setAffineTransform(.identity)
                return
            }

            let target = hovered ? Menu.quickLinkHoverLift : 0
            let current = (
                layer.presentation()?
                    .value(forKeyPath: "transform.translation.y") as? NSNumber
            )?.doubleValue ?? (hovered ? 0 : Double(Menu.quickLinkHoverLift))
            let lift = CABasicAnimation(keyPath: "transform.translation.y")
            lift.fromValue = current
            lift.toValue = Double(target)
            lift.duration = quickLinkHoverDuration
            lift.timingFunction = CAMediaTimingFunction(name: .easeOut)
            layer.setAffineTransform(CGAffineTransform(translationX: 0, y: target))
            layer.add(lift, forKey: quickLinkHoverAnimationKey)
        }
    }

    // MARK: Type

    enum Font {
        static func regular(_ size: CGFloat) -> NSFont {
            NSFont(name: "SFMono-Regular", size: size)
                ?? NSFont.monospacedSystemFont(ofSize: size, weight: .regular)
        }

        static func strong(_ size: CGFloat) -> NSFont {
            NSFont(name: "SFMono-Heavy", size: size)
                ?? NSFont.monospacedSystemFont(ofSize: size, weight: .bold)
        }

        static func mono(
            _ size: CGFloat,
            weight: NSFont.Weight = .regular
        ) -> NSFont {
            if weight.rawValue >= NSFont.Weight.bold.rawValue {
                return strong(size)
            }
            return NSFont(name: "SFMono-Regular", size: size)
                ?? NSFont.monospacedSystemFont(ofSize: size, weight: weight)
        }
    }

    /// A compact bitmap display face inspired by the FireRed/LeafGreen UI.
    /// It is drawn locally from a tiny glyph map so friend builds do not need
    /// an installed font or a downloaded asset.
    enum FireRedDisplay {
        static let glyphWidth = 5
        static let glyphHeight = 7
        static let glyphTracking: CGFloat = 1.5

        static let glyphs: [Character: [String]] = [
            " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
            "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
            "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
            "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
            "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
            "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
            "É": ["00100", "01000", "11111", "11110", "10000", "10000", "11111"],
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
            "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
            "5": ["11111", "10000", "10000", "11110", "00001", "00001", "11110"],
            "6": ["01110", "10000", "10000", "11110", "10001", "10001", "01110"],
            "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
            "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
            "9": ["01110", "10001", "10001", "01111", "00001", "00001", "01110"],
            "/": ["00001", "00010", "00010", "00100", "01000", "01000", "10000"],
            "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
            ".": ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
            ":": ["00000", "01100", "01100", "00000", "01100", "01100", "00000"],
            "!": ["00100", "00100", "00100", "00100", "00100", "00000", "00100"],
            "?": ["01110", "10001", "00001", "00010", "00100", "00000", "00100"],
            ">": ["10000", "11000", "11100", "11110", "11100", "11000", "10000"],
            "▶": ["10000", "11000", "11100", "11110", "11100", "11000", "10000"],
            "✦": ["00100", "10101", "01110", "11111", "01110", "10101", "00100"],
        ]

        private static func metrics(
            for character: Character
        ) -> (glyph: [String], leading: Int, width: Int) {
            let glyph = glyphs[character] ?? glyphs["?"]!
            if character == " " {
                return (glyph, 0, 3)
            }
            var first = glyphWidth
            var last = -1
            for row in glyph {
                for (column, bit) in row.enumerated() where bit == "1" {
                    first = min(first, column)
                    last = max(last, column)
                }
            }
            guard last >= first else { return (glyph, 0, 3) }
            return (glyph, first, last - first + 1)
        }

        static func size(of text: String, pixel: CGFloat) -> NSSize {
            let characters = Array(text.uppercased())
            let glyphUnits = characters.reduce(CGFloat.zero) { total, character in
                total + CGFloat(metrics(for: character).width)
            }
            let trackingUnits = CGFloat(max(0, characters.count - 1)) * glyphTracking
            let width = (glyphUnits + trackingUnits) * pixel
            return NSSize(
                width: width + pixel,
                height: CGFloat(glyphHeight + 1) * pixel
            )
        }

        static func draw(
            _ text: String,
            in rect: NSRect,
            color: NSColor,
            pixel: CGFloat,
            alignment: NSTextAlignment = .left,
            shadow: Bool = true,
            flipped: Bool = false
        ) {
            guard let context = NSGraphicsContext.current?.cgContext else { return }
            context.saveGState()
            defer { context.restoreGState() }
            context.setShouldAntialias(false)
            let textSize = size(of: text, pixel: pixel)
            let x: CGFloat
            switch alignment {
            case .center: x = rect.midX - textSize.width / 2
            case .right: x = rect.maxX - textSize.width
            default: x = rect.minX
            }
            let textHeight = CGFloat(glyphHeight) * pixel
            let firstRowY = flipped
                ? rect.midY - textHeight / 2
                : rect.midY + textHeight / 2 - pixel

            func paint(offsetX: CGFloat, offsetY: CGFloat, paint: NSColor) {
                paint.setFill()
                var cursor = x
                for character in text.uppercased() {
                    let glyphMetrics = metrics(for: character)
                    let glyph = glyphMetrics.glyph
                    for (rowIndex, row) in glyph.enumerated() {
                        for (columnIndex, bit) in row.enumerated() where bit == "1" {
                            NSBezierPath.fill(NSRect(
                                x: cursor
                                    + CGFloat(columnIndex - glyphMetrics.leading) * pixel
                                    + offsetX,
                                y: firstRowY
                                    + (flipped ? CGFloat(rowIndex) : -CGFloat(rowIndex)) * pixel
                                    + offsetY,
                                width: pixel,
                                height: pixel
                            ))
                        }
                    }
                    cursor += (CGFloat(glyphMetrics.width) + glyphTracking) * pixel
                }
            }

            if shadow {
                paint(
                    offsetX: pixel,
                    offsetY: flipped ? pixel : -pixel,
                    paint: Menu.mutedInk.withAlphaComponent(0.18)
                )
            }
            paint(offsetX: 0, offsetY: 0, paint: color)
        }
    }

    // MARK: Shared treatments

    enum ButtonRole {
        case primary
        case secondary
        case quiet
        case destructive
    }

    enum ControlState {
        case normal
        case hovered
        case focused
        case pressed
        case disabled
        case loading
    }

    enum FieldState {
        case normal
        case focused
        case error
        case disabled
    }

    /// Compact menu-bar dropdown styling. This is intentionally lighter than
    /// the archived console surfaces: it borrows the clarity of a field guide
    /// and the rhythm of a game dialogue box while keeping BuddyMon's mono type.
    enum Menu {
        enum AppStatusState {
            case active
            case idle
            case unavailable
        }

        enum ActionTreatment {
            case button
            case quickLink
        }

        struct SettingsOption {
            let value: String
            let label: String
            let isActive: Bool
        }

        static let systemName = "Field Guide"
        static let canvas = NSColor(
            calibratedRed: 0.95,
            green: 0.93,
            blue: 0.88,
            alpha: 1
        )
        static let surface = NSColor(
            calibratedRed: 0.99,
            green: 0.98,
            blue: 0.94,
            alpha: 1
        )
        static let raised = NSColor(
            calibratedRed: 0.91,
            green: 0.89,
            blue: 0.84,
            alpha: 1
        )
        static let spriteWell = NSColor(
            calibratedRed: 0.94,
            green: 0.92,
            blue: 0.87,
            alpha: 1
        )
        static let ink = NSColor(
            calibratedRed: 0.12,
            green: 0.12,
            blue: 0.10,
            alpha: 1
        )
        static let mutedInk = NSColor(
            calibratedRed: 0.39,
            green: 0.37,
            blue: 0.33,
            alpha: 1
        )
        static let rule = NSColor(
            calibratedRed: 0.70,
            green: 0.67,
            blue: 0.61,
            alpha: 1
        )
        static let subtleRule = rule.withAlphaComponent(0.28)
        static let settingsRowBackground = NSColor.clear
        static let settingsRowHover = raised.withAlphaComponent(0.55)
        static let appActive = pokemonGrass
        static let appIdle = mutedInk
        static let appUnavailable = alert
        static let chrome = NSColor(
            calibratedRed: 0.12,
            green: 0.12,
            blue: 0.10,
            alpha: 1
        )
        static let focus = NSColor(
            calibratedRed: 0.12,
            green: 0.12,
            blue: 0.10,
            alpha: 1
        )
        static let alert = NSColor(
            calibratedRed: 0.72,
            green: 0.16,
            blue: 0.13,
            alpha: 1
        )
        static let xpTrack = NSColor(
            calibratedRed: 0.78,
            green: 0.80,
            blue: 0.76,
            alpha: 1
        )
        static let xpFill = NSColor(
            calibratedRed: 0.12,
            green: 0.12,
            blue: 0.10,
            alpha: 1
        )
        static let dataTrack = raised
        static let dataFill = ink
        static let pokemonFire = NSColor(
            calibratedRed: 0.78,
            green: 0.18,
            blue: 0.15,
            alpha: 1
        )
        static let pokemonWater = NSColor(
            calibratedRed: 0.16,
            green: 0.40,
            blue: 0.68,
            alpha: 1
        )
        static let pokemonGrass = NSColor(
            calibratedRed: 0.16,
            green: 0.45,
            blue: 0.25,
            alpha: 1
        )
        static let pokemonElectric = NSColor(
            calibratedRed: 0.66,
            green: 0.43,
            blue: 0.02,
            alpha: 1
        )
        static let pokemonRare = NSColor(
            calibratedRed: 0.68,
            green: 0.12,
            blue: 0.48,
            alpha: 1
        )
        static let rarityLegendary = NSColor(
            calibratedRed: 0.48,
            green: 0.31,
            blue: 0.01,
            alpha: 1
        )
        static let rarityStarter = NSColor(
            calibratedRed: 0.05,
            green: 0.38,
            blue: 0.46,
            alpha: 1
        )

        static let panelWidth: CGFloat = 304
        static let popoverMinimumHeight: CGFloat = 160
        static let panelMinimumHeight: CGFloat = 210
        static let tokenPanelMinimumHeight = panelMinimumHeight
        static let settingsPanelMinimumHeight = panelMinimumHeight
        static let trainerPanelMinimumHeight: CGFloat = 208
        static let encounterPanelMinimumHeight: CGFloat = 224
        static let resultPanelMinimumHeight: CGFloat = 176
        static let flushInset: CGFloat = 0
        static let microGap: CGFloat = 2
        static let labelGap: CGFloat = 3
        static let tightGap: CGFloat = 4
        static let actionGap: CGFloat = 4
        static let headerGap: CGFloat = 5
        static let compactGap: CGFloat = 6
        static let panelPadding: CGFloat = 12
        static let sectionGap: CGFloat = 7
        static let cardPadding: CGFloat = 10
        static let buddySpriteSize: CGFloat = 54
        static let activeBuddyRowHeight: CGFloat = buddySpriteSize + (compactGap * 2)
        static let signalSpriteSize: CGFloat = 26
        static let statusIndicatorSize: CGFloat = 6
        static let settingsRowHeight: CGFloat = 18
        static let settingsOptionFontSize: CGFloat = 7.5
        static let encounterSpriteSize: CGFloat = 52
        static let compactProgressWidth: CGFloat = 78
        static let compactProgressHeight: CGFloat = 6
        static let tokenDailyPulseHeight: CGFloat = 38
        static let tokenHeaderWidth: CGFloat = 164
        static let terminalWindowWidth: CGFloat = 760
        static let terminalWindowHeight: CGFloat = 520
        static let fieldGuideFrameInset: CGFloat = 8
        static let trainerCardWidth: CGFloat = 288
        static let trainerCardHeight: CGFloat = 192
        static let trainerFactLabelWidth: CGFloat = 60
        static let trainerFactValueWidth: CGFloat = 64
        static let trainerPortraitPixel: CGFloat = 3
        static let trainerPortraitWidth: CGFloat = 64
        static let trainerPortraitHeight: CGFloat = 64
        static let trainerStatusRailHeight: CGFloat = 26
        static let trainerBadgeSize: CGFloat = 28
        static let trainerBadgeDenseSize: CGFloat = 25
        static let trainerBadgeSymbolSize: CGFloat = 12
        static let trainerBadgeDenseSymbolSize: CGFloat = 11
        static let trainerBadgeSymbolOpticalLift: CGFloat = 1
        static let trainerBadgeInnerInset: CGFloat = 3
        static let trainerBadgeRevealScale: CGFloat = 0.82
        static let trainerBadgeRevealOvershoot: CGFloat = 1.05
        static let trainerBadgeHoverScale: CGFloat = 1.08
        static let trainerBadgeRevealDuration: CFTimeInterval = 0.38
        static let trainerBadgeRevealStagger: CFTimeInterval = 0.045
        static let trainerBadgeHoverDuration: CFTimeInterval = 0.16
        static let trainerBadgeGlowDuration: CFTimeInterval = 2.6
        static let trainerBadgeShadowOpacity: Float = 0.08
        static let trainerBadgeRareShadowOpacity: Float = 0.14
        static let trainerBadgeGlowOpacity: Float = 0.30
        static let trainerBadgeShadowRadius: CGFloat = 2
        static let trainerBadgeRareShadowRadius: CGFloat = 4
        static let trainerStripeHeight: CGFloat = 2
        static let displayLabelPixel: CGFloat = 1.25
        static let displayButtonPixel: CGFloat = 1.1
        static let actionLabelPixel: CGFloat = 0.92
        static let controlHeight: CGFloat = 32
        static let quickLinkHeight: CGFloat = 22
        static let quickLinkColumns = 3
        static let quickLinkHoverLift: CGFloat = 1
        static let actionHorizontalInset: CGFloat = 5
        static let progressCornerRadius: CGFloat = 4
        static let noBorderWidth: CGFloat = 0
        static let cornerRadius: CGFloat = 10
        static let smallCornerRadius: CGFloat = 7

        static func applySurface(
            to view: NSView,
            raised isRaised: Bool = false,
            emphasized: Bool = false,
            bordered: Bool = true
        ) {
            view.wantsLayer = true
            view.layer?.backgroundColor = (isRaised ? raised : surface).cgColor
            view.layer?.borderColor = (emphasized ? chrome : rule).cgColor
            view.layer?.borderWidth = bordered
                ? (emphasized ? Geometry.focusBorderWidth : Geometry.borderWidth)
                : noBorderWidth
            view.layer?.cornerRadius = cornerRadius
        }

        static func applyFieldGuideCardSurface(to view: NSView) {
            view.wantsLayer = true
            view.layer?.backgroundColor = surface.cgColor
            view.layer?.borderColor = chrome.cgColor
            view.layer?.borderWidth = Geometry.focusBorderWidth
            view.layer?.cornerRadius = smallCornerRadius
            view.layer?.masksToBounds = true
        }

        static func applyPanelShell(to panel: NSPanel) {
            panel.appearance = NSAppearance(named: .aqua)
            panel.backgroundColor = canvas
            panel.isOpaque = true
            panel.hasShadow = true
            panel.animationBehavior = .none
        }

        static func makeActiveBuddyRow() -> NSStackView {
            let row = BuddyMonMenuActiveRowView(frame: .zero)
            row.heightAnchor.constraint(
                equalToConstant: activeBuddyRowHeight
            ).isActive = true
            return row
        }

        static func makeStatusIndicator(_ state: AppStatusState) -> NSView {
            BuddyMonMenuStatusIndicatorView(state: state)
        }

        static func makeTrainerStatusRail(
            _ stats: [(label: String, value: String)]
        ) -> NSStackView {
            let rail = BuddyMonMenuTrainerStatusRailView(frame: .zero)
            rail.orientation = .horizontal
            rail.alignment = .centerY
            rail.distribution = .fillEqually
            rail.spacing = flushInset
            rail.edgeInsets = NSEdgeInsets(
                top: microGap,
                left: flushInset,
                bottom: microGap,
                right: flushInset
            )
            rail.heightAnchor.constraint(
                equalToConstant: trainerStatusRailHeight
            ).isActive = true

            for stat in stats {
                let value = NSTextField(labelWithString: stat.value)
                value.textColor = ink
                value.font = Font.mono(9, weight: .bold)
                value.alignment = .center
                value.lineBreakMode = .byTruncatingTail
                value.maximumNumberOfLines = 1

                let label = NSTextField(labelWithString: stat.label)
                label.textColor = mutedInk
                label.font = Font.mono(7, weight: .medium)
                label.alignment = .center
                label.lineBreakMode = .byTruncatingTail
                label.maximumNumberOfLines = 1

                let cell = NSStackView(views: [value, label])
                cell.orientation = .vertical
                cell.alignment = .centerX
                cell.spacing = microGap
                cell.setAccessibilityElement(true)
                cell.setAccessibilityRole(.group)
                cell.setAccessibilityLabel("\(stat.label): \(stat.value)")
                value.setAccessibilityElement(false)
                label.setAccessibilityElement(false)
                rail.addArrangedSubview(cell)
            }
            return rail
        }

        static func makeSettingsRow(
            label: String,
            key: String,
            detail: String = "",
            options: [SettingsOption],
            target: AnyObject?,
            action: Selector?
        ) -> BuddyMonMenuSettingsRowView {
            BuddyMonMenuSettingsRowView(
                label: label,
                key: key,
                detail: detail,
                options: options,
                target: target,
                action: action
            )
        }

        static func applySettingsOption(
            to button: NSButton,
            state: ControlState = .normal
        ) {
            (button as? BuddyMonMenuSettingsOptionButton)?.apply(state: state)
        }

        static func statusIndicatorColor(_ state: AppStatusState) -> NSColor {
            switch state {
            case .active: return appActive
            case .idle: return appIdle
            case .unavailable: return appUnavailable
            }
        }

        static func statusIndicatorLabel(_ state: AppStatusState) -> String {
            switch state {
            case .active: return "BuddyMon active"
            case .idle: return "BuddyMon starting"
            case .unavailable: return "BuddyMon status unavailable"
            }
        }

        static func applyTrainerBadge(
            to view: NSView,
            size: CGFloat,
            earned: Bool,
            rare: Bool
        ) {
            view.wantsLayer = true
            view.layer?.backgroundColor = (earned ? raised : surface).cgColor
            view.layer?.borderColor = (
                earned && rare ? pokemonRare : (earned ? ink : rule)
            ).cgColor
            view.layer?.borderWidth = Geometry.borderWidth
            view.layer?.cornerRadius = size / 2
            view.layer?.masksToBounds = false
            view.layer?.shadowColor = (rare ? pokemonRare : ink).cgColor
            view.layer?.shadowOffset = .zero
            view.layer?.shadowRadius = rare
                ? trainerBadgeRareShadowRadius
                : trainerBadgeShadowRadius
            view.layer?.shadowOpacity = earned
                ? (rare ? trainerBadgeRareShadowOpacity : trainerBadgeShadowOpacity)
                : 0
        }

        static func trainerBadgeForeground(earned: Bool, rare: Bool) -> NSColor {
            earned && rare ? pokemonRare : (earned ? ink : rule)
        }

        static func trainerBadgeRingColor(earned: Bool, rare: Bool) -> NSColor {
            if earned && rare {
                return pokemonRare.withAlphaComponent(0.34)
            }
            return earned
                ? surface.withAlphaComponent(0.92)
                : rule.withAlphaComponent(0.28)
        }

        static func makeActionButton(
            _ title: String,
            target: AnyObject?,
            action: Selector?,
            role: ButtonRole,
            minimumHeight: CGFloat = controlHeight
        ) -> NSButton {
            let button = BuddyMonMenuActionButton(
                title: title,
                target: target,
                action: action
            )
            button.configure(
                role: role,
                treatment: .button,
                minimumHeight: minimumHeight
            )
            return button
        }

        static func makeQuickLink(
            _ title: String,
            target: AnyObject?,
            action: Selector?
        ) -> NSButton {
            let button = BuddyMonMenuActionButton(
                title: title,
                target: target,
                action: action
            )
            button.configure(
                role: .quiet,
                treatment: .quickLink,
                minimumHeight: quickLinkHeight
            )
            return button
        }

        static func makeDisplayLabel(
            _ text: String,
            color: NSColor,
            pixel: CGFloat = displayLabelPixel
        ) -> BuddyMonFireRedLabel {
            BuddyMonFireRedLabel(text: text, color: color, pixel: pixel)
        }

        static func rarityCode(_ rarity: String?) -> String {
            switch rarity?.lowercased() {
            case "common": return "C"
            case "uncommon": return "U"
            case "rare": return "R"
            case "legendary": return "L"
            case "mythic": return "M"
            case "starter": return "S"
            default: return "?"
            }
        }

        static func rarityColor(_ rarity: String?) -> NSColor {
            switch rarity?.lowercased() {
            case "common": return mutedInk
            case "uncommon": return pokemonGrass
            case "rare": return pokemonWater
            case "legendary": return rarityLegendary
            case "mythic": return pokemonRare
            case "starter": return rarityStarter
            default: return mutedInk
            }
        }

        static func makeRarityLabel(_ rarity: String?) -> BuddyMonFireRedLabel {
            let label = makeDisplayLabel(
                rarityCode(rarity),
                color: rarityColor(rarity),
                pixel: displayButtonPixel
            )
            label.setAccessibilityLabel(
                "\((rarity ?? "unknown").capitalized) rarity"
            )
            return label
        }

        static func refreshActionButton(
            _ button: NSButton,
            role: ButtonRole,
            state: ControlState
        ) {
            if
                let menuButton = button as? BuddyMonMenuActionButton,
                menuButton.actionTreatment == .quickLink
            {
                refreshQuickLink(menuButton, state: state)
                return
            }

            let isPrimary = role == .primary || role == .destructive
            let isFocused = state == .focused
            let isInactive = state == .disabled || state == .loading

            let background: NSColor
            let foreground: NSColor
            let border: NSColor
            switch state {
            case .focused:
                background = chrome
                foreground = .white
                border = chrome
            case .hovered:
                background = spriteWell
                foreground = ink
                border = chrome
            case .pressed:
                background = ink.withAlphaComponent(0.84)
                foreground = .white
                border = ink
            default:
                background = isPrimary ? ink : raised
                foreground = isPrimary ? .white : (role == .quiet ? mutedInk : ink)
                border = isPrimary ? ink : rule
            }
            let titleColor = isInactive ? mutedInk : foreground
            button.contentTintColor = titleColor
            if let menuButton = button as? BuddyMonMenuActionButton {
                menuButton.refreshTitle(color: titleColor)
            }
            button.layer?.backgroundColor = background.cgColor
            button.layer?.borderColor = border.cgColor
            button.layer?.borderWidth = isFocused ? Geometry.borderWidth : 0
            button.layer?.cornerRadius = smallCornerRadius
            button.isEnabled = !isInactive
        }

        private static func refreshQuickLink(
            _ button: BuddyMonMenuActionButton,
            state: ControlState
        ) {
            let isInactive = state == .disabled || state == .loading
            let background: NSColor
            let foreground: NSColor
            let border: NSColor
            switch state {
            case .focused:
                background = raised
                foreground = ink
                border = ink
            case .hovered:
                background = raised.withAlphaComponent(0.68)
                foreground = ink
                border = rule
            case .pressed:
                background = ink.withAlphaComponent(0.84)
                foreground = .white
                border = ink
            case .disabled, .loading:
                background = surface.withAlphaComponent(0.12)
                foreground = mutedInk
                border = subtleRule
            default:
                background = surface.withAlphaComponent(0.18)
                foreground = ink
                border = subtleRule
            }

            button.contentTintColor = foreground
            button.refreshTitle(color: foreground)
            button.layer?.backgroundColor = background.cgColor
            button.layer?.borderColor = border.cgColor
            button.layer?.borderWidth = Geometry.borderWidth
            button.layer?.cornerRadius = Geometry.cornerRadius
            button.isEnabled = !isInactive
        }

        static func pokemonColor(_ pokemon: [String: Any]?) -> NSColor {
            if
                pokemon?["shiny"] as? Bool == true
                    || (pokemon?["rarity"] as? String)?
                        .localizedCaseInsensitiveContains("rare") == true
            {
                return pokemonRare
            }
            switch (pokemon?["type"] as? String)?.lowercased() {
            case "fire": return pokemonFire
            case "water": return pokemonWater
            case "grass": return pokemonGrass
            case "electric": return pokemonElectric
            default: return ink
            }
        }
    }

    static func applySurface(
        to view: NSView,
        inset: Bool = false,
        focused: Bool = false
    ) {
        view.wantsLayer = true
        view.layer?.backgroundColor = (inset ? self.inset : surface).cgColor
        view.layer?.borderColor = (focused ? focus : rule).cgColor
        view.layer?.borderWidth = Geometry.borderWidth
        view.layer?.cornerRadius = Geometry.cornerRadius
    }

    static func makeSurface(
        inset: Bool = false,
        focused: Bool = false
    ) -> NSView {
        let view = NSView()
        applySurface(to: view, inset: inset, focused: focused)
        return view
    }

    static func makeButton(
        _ title: String,
        target: AnyObject? = nil,
        action: Selector? = nil,
        role: ButtonRole = .secondary,
        state: ControlState = .normal
    ) -> NSButton {
        let button = BuddyMonBrandButton(title: title, target: target, action: action)
        applyButton(button, role: role, state: state)
        return button
    }

    static func applyButton(
        _ button: NSButton,
        role: ButtonRole = .secondary,
        state: ControlState = .normal
    ) {
        button.isBordered = false
        button.controlSize = .large
        button.font = Font.strong(11)
        button.focusRingType = .none
        button.wantsLayer = true
        if let brandButton = button as? BuddyMonBrandButton {
            brandButton.configure(role: role, state: state)
        } else {
            refreshButtonAppearance(button, role: role, state: state)
        }
        button.heightAnchor.constraint(
            greaterThanOrEqualToConstant: Geometry.controlHeight
        ).isActive = true
    }

    static func refreshButtonAppearance(
        _ button: NSButton,
        role: ButtonRole,
        state: ControlState
    ) {
        let isEmphasized = role == .primary || role == .destructive
        let isFocused = state == .focused
        let isInactive = state == .disabled || state == .loading

        button.contentTintColor = isInactive
            ? textSecondary
            : (isEmphasized ? focus : textPrimary)
        switch state {
        case .hovered:
            button.layer?.backgroundColor = rule.withAlphaComponent(0.36).cgColor
        case .pressed:
            button.layer?.backgroundColor = textPrimary.withAlphaComponent(0.12).cgColor
        default:
            button.layer?.backgroundColor = surface.cgColor
        }
        button.layer?.borderColor = (
            !isInactive && (isEmphasized || isFocused) ? focus : rule
        ).cgColor
        if role == .quiet && !isFocused {
            button.layer?.borderWidth = 0
        } else {
            button.layer?.borderWidth = isFocused
                ? Geometry.focusBorderWidth
                : Geometry.borderWidth
        }
        button.layer?.cornerRadius = Geometry.cornerRadius
        button.isEnabled = !isInactive
    }

    static func makeField(
        value: String,
        placeholder: String = "",
        state: FieldState = .normal,
        interactive: Bool = true
    ) -> NSTextField {
        let field = NSTextField(string: value)
        field.placeholderString = placeholder
        applyField(field, state: state, interactive: interactive)
        return field
    }

    static func applyField(
        _ field: NSTextField,
        state: FieldState = .normal,
        interactive: Bool = true
    ) {
        let isDisabled = state == .disabled
        let isFocused = state == .focused
        let isError = state == .error

        field.font = Font.regular(10)
        field.textColor = isDisabled ? textSecondary : textPrimary
        field.isEditable = interactive && !isDisabled
        field.refusesFirstResponder = !interactive
        field.isBezeled = false
        field.drawsBackground = true
        field.backgroundColor = surface
        field.wantsLayer = true
        field.layer?.borderWidth = isFocused || isError
            ? Geometry.focusBorderWidth
            : Geometry.borderWidth
        field.layer?.borderColor = (isFocused || isError ? focus : rule).cgColor
        field.layer?.cornerRadius = Geometry.cornerRadius
        field.heightAnchor.constraint(
            greaterThanOrEqualToConstant: Geometry.controlHeight
        ).isActive = true
    }

    static func makeControlLabel(
        _ value: String,
        color: NSColor = textPrimary
    ) -> NSTextField {
        let field = NSTextField(labelWithString: value)
        field.font = Font.strong(10)
        field.textColor = color
        field.lineBreakMode = .byClipping
        return field
    }

    static func pokemonColor(
        name: String? = nil,
        type: String? = nil,
        shiny: Bool = false,
        rarityValue: String? = nil
    ) -> NSColor {
        if shiny || rarityValue?.localizedCaseInsensitiveContains("rare") == true {
            return rarity
        }

        switch name?.lowercased() {
        case "pikachu", "pichu", "raichu":
            return pikachu
        case "bulbasaur", "ivysaur", "venusaur":
            return starterGrass
        case "squirtle", "wartortle", "blastoise":
            return starterWater
        default:
            break
        }

        switch type?.lowercased() {
        case "fire":
            return brand
        case "electric":
            return pikachu
        case "grass":
            return starterGrass
        case "water":
            return starterWater
        default:
            return textPrimary
        }
    }

    static func pokemonColor(_ pokemon: [String: Any]?) -> NSColor {
        pokemonColor(
            name: pokemon?["name"] as? String,
            type: pokemon?["type"] as? String,
            shiny: pokemon?["shiny"] as? Bool ?? false,
            rarityValue: pokemon?["rarity"] as? String
        )
    }
}

private final class BuddyMonMenuActiveRowView: NSStackView {
    private let topRule = CALayer()
    private let bottomRule = CALayer()

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        wantsLayer = true
        layer?.backgroundColor = BuddyMonBrand.Menu.raised.cgColor
        layer?.cornerRadius = BuddyMonBrand.Geometry.cornerRadius
        layer?.masksToBounds = true
        topRule.backgroundColor = BuddyMonBrand.Menu.subtleRule.cgColor
        bottomRule.backgroundColor = BuddyMonBrand.Menu.subtleRule.cgColor
        layer?.addSublayer(topRule)
        layer?.addSublayer(bottomRule)
    }

    required init?(coder: NSCoder) {
        nil
    }

    override func layout() {
        super.layout()
        let ruleWidth = BuddyMonBrand.Geometry.borderWidth
        topRule.frame = NSRect(
            x: 0,
            y: bounds.height - ruleWidth,
            width: bounds.width,
            height: ruleWidth
        )
        bottomRule.frame = NSRect(
            x: 0,
            y: 0,
            width: bounds.width,
            height: ruleWidth
        )
    }
}

private final class BuddyMonMenuTrainerStatusRailView: NSStackView {
    private let topRule = CALayer()
    private let bottomRule = CALayer()

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        wantsLayer = true
        layer?.backgroundColor = BuddyMonBrand.Menu.raised.cgColor
        topRule.backgroundColor = BuddyMonBrand.Menu.subtleRule.cgColor
        bottomRule.backgroundColor = BuddyMonBrand.Menu.subtleRule.cgColor
        layer?.addSublayer(topRule)
        layer?.addSublayer(bottomRule)
    }

    required init?(coder: NSCoder) {
        nil
    }

    override func layout() {
        super.layout()
        let ruleWidth = BuddyMonBrand.Geometry.borderWidth
        topRule.frame = NSRect(
            x: 0,
            y: bounds.height - ruleWidth,
            width: bounds.width,
            height: ruleWidth
        )
        bottomRule.frame = NSRect(
            x: 0,
            y: 0,
            width: bounds.width,
            height: ruleWidth
        )
    }
}

private final class BuddyMonMenuStatusIndicatorView: NSView {
    init(state: BuddyMonBrand.Menu.AppStatusState) {
        super.init(frame: .zero)
        wantsLayer = true
        layer?.backgroundColor = BuddyMonBrand.Menu.statusIndicatorColor(state).cgColor
        layer?.cornerRadius = BuddyMonBrand.Menu.statusIndicatorSize / 2
        setAccessibilityElement(true)
        setAccessibilityRole(.image)
        setAccessibilityLabel(BuddyMonBrand.Menu.statusIndicatorLabel(state))
        widthAnchor.constraint(
            equalToConstant: BuddyMonBrand.Menu.statusIndicatorSize
        ).isActive = true
        heightAnchor.constraint(
            equalToConstant: BuddyMonBrand.Menu.statusIndicatorSize
        ).isActive = true
    }

    required init?(coder: NSCoder) {
        nil
    }
}

final class BuddyMonMenuSettingsRowView: NSView {
    private(set) var optionButtons: [NSButton] = []

    init(
        label: String,
        key: String,
        detail: String,
        options: [BuddyMonBrand.Menu.SettingsOption],
        target: AnyObject?,
        action: Selector?
    ) {
        super.init(frame: .zero)
        wantsLayer = true
        layer?.backgroundColor = BuddyMonBrand.Menu.settingsRowBackground.cgColor

        let content = NSStackView()
        content.orientation = .horizontal
        content.alignment = .centerY
        content.spacing = BuddyMonBrand.Menu.compactGap

        let labelView = BuddyMonBrand.Menu.makeDisplayLabel(
            label.uppercased(),
            color: BuddyMonBrand.Menu.ink,
            pixel: BuddyMonBrand.Menu.actionLabelPixel
        )
        labelView.setContentCompressionResistancePriority(.required, for: .horizontal)
        content.addArrangedSubview(labelView)

        let spacer = NSView()
        spacer.setContentHuggingPriority(.defaultLow, for: .horizontal)
        spacer.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        content.addArrangedSubview(spacer)

        let optionStack = NSStackView()
        optionStack.orientation = .horizontal
        optionStack.alignment = .centerY
        optionStack.spacing = BuddyMonBrand.Menu.tightGap
        optionStack.setContentCompressionResistancePriority(.required, for: .horizontal)
        for option in options {
            let button = BuddyMonMenuSettingsOptionButton(
                label: option.label,
                settingLabel: label,
                detail: detail,
                isActive: option.isActive
            )
            button.identifier = NSUserInterfaceItemIdentifier(
                "settings_preference:\(key):\(option.value)"
            )
            button.target = target
            button.action = action
            optionButtons.append(button)
            optionStack.addArrangedSubview(button)
        }
        content.addArrangedSubview(optionStack)

        addSubview(content)
        content.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            heightAnchor.constraint(equalToConstant: BuddyMonBrand.Menu.settingsRowHeight),
            content.leadingAnchor.constraint(
                equalTo: leadingAnchor,
                constant: BuddyMonBrand.Menu.microGap
            ),
            content.trailingAnchor.constraint(
                equalTo: trailingAnchor,
                constant: -BuddyMonBrand.Menu.microGap
            ),
            content.centerYAnchor.constraint(equalTo: centerYAnchor),
        ])
        setAccessibilityElement(true)
        setAccessibilityRole(.group)
        setAccessibilityLabel(label)
    }

    required init?(coder: NSCoder) {
        nil
    }
}

private final class BuddyMonMenuSettingsOptionButton: NSButton {
    private let optionLabel: String
    private let activeOption: Bool
    private var tracking: NSTrackingArea?

    init(label: String, settingLabel: String, detail: String, isActive: Bool) {
        optionLabel = label.uppercased()
        activeOption = isActive
        super.init(frame: .zero)
        title = ""
        isBordered = false
        focusRingType = .none
        setButtonType(.momentaryChange)
        setAccessibilityLabel("Set \(settingLabel) to \(label)")
        setAccessibilityValue(isActive ? "Active" : "Inactive")
        toolTip = detail.isEmpty ? nil : detail
        apply(state: .normal)
    }

    required init?(coder: NSCoder) {
        nil
    }

    override var acceptsFirstResponder: Bool { isEnabled }

    func apply(state: BuddyMonBrand.ControlState) {
        let emphasized = activeOption || state == .hovered || state == .focused
        let value = activeOption ? "› \(optionLabel)" : optionLabel
        var attributes: [NSAttributedString.Key: Any] = [
            .foregroundColor: emphasized
                ? BuddyMonBrand.Menu.ink
                : BuddyMonBrand.Menu.mutedInk,
            .font: emphasized
                ? BuddyMonBrand.Font.strong(BuddyMonBrand.Menu.settingsOptionFontSize)
                : BuddyMonBrand.Font.regular(BuddyMonBrand.Menu.settingsOptionFontSize),
        ]
        if activeOption {
            attributes[.underlineStyle] = NSUnderlineStyle.single.rawValue
        }
        attributedTitle = NSAttributedString(string: value, attributes: attributes)
        wantsLayer = true
        layer?.backgroundColor = (
            state == .hovered || state == .pressed
                ? BuddyMonBrand.Menu.settingsRowHover
                : BuddyMonBrand.Menu.settingsRowBackground
        ).cgColor
        layer?.borderColor = BuddyMonBrand.Menu.ink.cgColor
        layer?.borderWidth = state == .focused
            ? BuddyMonBrand.Geometry.borderWidth
            : BuddyMonBrand.Menu.noBorderWidth
        layer?.cornerRadius = BuddyMonBrand.Geometry.cornerRadius
    }

    override func resetCursorRects() {
        super.resetCursorRects()
        if isEnabled {
            addCursorRect(bounds, cursor: .pointingHand)
        }
    }

    override func cursorUpdate(with event: NSEvent) {
        NSCursor.pointingHand.set()
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
        guard isEnabled, window?.firstResponder !== self else { return }
        apply(state: .hovered)
    }

    override func mouseExited(with event: NSEvent) {
        guard window?.firstResponder !== self else { return }
        apply(state: .normal)
    }

    override func becomeFirstResponder() -> Bool {
        let accepted = super.becomeFirstResponder()
        if accepted {
            apply(state: .focused)
        }
        return accepted
    }

    override func resignFirstResponder() -> Bool {
        let resigned = super.resignFirstResponder()
        apply(state: .normal)
        return resigned
    }
}

final class BuddyMonFireRedLabel: NSView {
    private let value: String
    private let color: NSColor
    private let pixel: CGFloat

    init(text: String, color: NSColor, pixel: CGFloat) {
        value = text
        self.color = color
        self.pixel = pixel
        super.init(frame: .zero)
        setAccessibilityElement(true)
        setAccessibilityRole(.staticText)
        setAccessibilityLabel(text)
    }

    required init?(coder: NSCoder) {
        nil
    }

    override var intrinsicContentSize: NSSize {
        BuddyMonBrand.FireRedDisplay.size(of: value, pixel: pixel)
    }

    override func draw(_ dirtyRect: NSRect) {
        super.draw(dirtyRect)
        BuddyMonBrand.FireRedDisplay.draw(
            value,
            in: bounds,
            color: color,
            pixel: pixel,
            flipped: isFlipped
        )
    }
}

private final class BuddyMonBrandButton: NSButton {
    private var brandRole: BuddyMonBrand.ButtonRole = .secondary
    private var baseState: BuddyMonBrand.ControlState = .normal
    private var tracking: NSTrackingArea?

    override func resetCursorRects() {
        super.resetCursorRects()
        if isEnabled {
            addCursorRect(bounds, cursor: .pointingHand)
        }
    }

    override var acceptsFirstResponder: Bool {
        isEnabled
    }

    func configure(
        role: BuddyMonBrand.ButtonRole,
        state: BuddyMonBrand.ControlState
    ) {
        brandRole = role
        baseState = state
        BuddyMonBrand.refreshButtonAppearance(self, role: role, state: state)
    }

    override func becomeFirstResponder() -> Bool {
        let accepted = super.becomeFirstResponder()
        if accepted, isEnabled {
            BuddyMonBrand.refreshButtonAppearance(
                self,
                role: brandRole,
                state: .focused
            )
        }
        return accepted
    }

    override func resignFirstResponder() -> Bool {
        let resigned = super.resignFirstResponder()
        if resigned {
            BuddyMonBrand.refreshButtonAppearance(
                self,
                role: brandRole,
                state: baseState
            )
        }
        return resigned
    }

    override func mouseDown(with event: NSEvent) {
        guard isEnabled else {
            super.mouseDown(with: event)
            return
        }
        BuddyMonBrand.refreshButtonAppearance(
            self,
            role: brandRole,
            state: .pressed
        )
        super.mouseDown(with: event)
        let restingState: BuddyMonBrand.ControlState = window?.firstResponder === self
            ? .focused
            : baseState
        BuddyMonBrand.refreshButtonAppearance(
            self,
            role: brandRole,
            state: restingState
        )
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
        guard isEnabled, window?.firstResponder !== self else { return }
        BuddyMonBrand.refreshButtonAppearance(
            self,
            role: brandRole,
            state: .hovered
        )
    }

    override func mouseExited(with event: NSEvent) {
        guard isEnabled, window?.firstResponder !== self else { return }
        BuddyMonBrand.refreshButtonAppearance(
            self,
            role: brandRole,
            state: baseState
        )
    }
}

private final class BuddyMonMenuActionButton: NSButton {
    private var menuRole: BuddyMonBrand.ButtonRole = .secondary
    private var tracking: NSTrackingArea?
    private var menuTitle = ""
    private var menuTitleColor = BuddyMonBrand.Menu.ink
    fileprivate var actionTreatment: BuddyMonBrand.Menu.ActionTreatment = .button

    override var acceptsFirstResponder: Bool { isEnabled }

    override func resetCursorRects() {
        super.resetCursorRects()
        if isEnabled {
            addCursorRect(bounds, cursor: .pointingHand)
        }
    }

    func configure(
        role: BuddyMonBrand.ButtonRole,
        treatment: BuddyMonBrand.Menu.ActionTreatment,
        minimumHeight: CGFloat
    ) {
        menuRole = role
        actionTreatment = treatment
        menuTitle = title
        self.title = ""
        isBordered = false
        controlSize = .large
        font = BuddyMonBrand.Font.strong(11)
        focusRingType = .none
        wantsLayer = true
        alignment = .left
        setAccessibilityLabel(menuTitle)
        if treatment == .quickLink {
            heightAnchor.constraint(equalToConstant: minimumHeight).isActive = true
        } else {
            heightAnchor.constraint(
                greaterThanOrEqualToConstant: minimumHeight
            ).isActive = true
        }
        BuddyMonBrand.Menu.refreshActionButton(self, role: role, state: .normal)
    }

    func refreshTitle(color: NSColor) {
        menuTitleColor = color
        needsDisplay = true
    }

    override func draw(_ dirtyRect: NSRect) {
        super.draw(dirtyRect)
        BuddyMonBrand.FireRedDisplay.draw(
            menuTitle,
            in: bounds.insetBy(
                dx: BuddyMonBrand.Menu.actionHorizontalInset,
                dy: BuddyMonBrand.Menu.tightGap
            ),
            color: menuTitleColor,
            pixel: BuddyMonBrand.Menu.actionLabelPixel,
            shadow: false,
            flipped: isFlipped
        )
    }

    override func becomeFirstResponder() -> Bool {
        let accepted = super.becomeFirstResponder()
        if accepted, isEnabled {
            resetQuickLinkLift()
            BuddyMonBrand.Menu.refreshActionButton(self, role: menuRole, state: .focused)
        }
        return accepted
    }

    override func resignFirstResponder() -> Bool {
        let resigned = super.resignFirstResponder()
        if resigned {
            resetQuickLinkLift()
            BuddyMonBrand.Menu.refreshActionButton(self, role: menuRole, state: .normal)
        }
        return resigned
    }

    override func mouseDown(with event: NSEvent) {
        guard isEnabled else {
            super.mouseDown(with: event)
            return
        }
        resetQuickLinkLift()
        BuddyMonBrand.Menu.refreshActionButton(self, role: menuRole, state: .pressed)
        super.mouseDown(with: event)
        let next: BuddyMonBrand.ControlState = window?.firstResponder === self
            ? .focused
            : .normal
        BuddyMonBrand.Menu.refreshActionButton(self, role: menuRole, state: next)
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
        guard isEnabled, window?.firstResponder !== self else { return }
        if actionTreatment == .quickLink {
            BuddyMonBrand.Motion.animateQuickLinkHover(self, hovered: true)
        }
        BuddyMonBrand.Menu.refreshActionButton(self, role: menuRole, state: .hovered)
    }

    override func mouseExited(with event: NSEvent) {
        guard isEnabled, window?.firstResponder !== self else { return }
        resetQuickLinkLift()
        BuddyMonBrand.Menu.refreshActionButton(self, role: menuRole, state: .normal)
    }

    private func resetQuickLinkLift() {
        guard actionTreatment == .quickLink else { return }
        BuddyMonBrand.Motion.animateQuickLinkHover(self, hovered: false)
    }
}
