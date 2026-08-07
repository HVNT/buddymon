import AppKit
import Foundation

@MainActor
final class MenuPanelStateHarnessView: NSView {
    private enum Layout {
        static let width: CGFloat = 944
        static let cardWidth: CGFloat = 424
    }

    private let document = FlippedMenuPanelHarnessDocument()
    private let stack = NSStackView()

    let preferredSize = NSSize(width: Layout.width, height: 760)

    init(payload: [String: Any]) {
        super.init(frame: .zero)
        wantsLayer = true
        layer?.backgroundColor = BuddyMonBrand.Menu.canvas.cgColor
        build(payload: payload)
    }

    required init?(coder: NSCoder) {
        nil
    }

    var snapshotView: NSView {
        document.layoutSubtreeIfNeeded()
        let fitting = document.fittingSize
        document.frame = NSRect(
            origin: .zero,
            size: NSSize(width: Layout.width, height: max(1, fitting.height))
        )
        document.layoutSubtreeIfNeeded()
        return document
    }

    private func build(payload: [String: Any]) {
        let scroll = NSScrollView()
        scroll.translatesAutoresizingMaskIntoConstraints = false
        scroll.hasVerticalScroller = true
        scroll.drawsBackground = true
        scroll.backgroundColor = BuddyMonBrand.Menu.canvas
        addSubview(scroll)

        document.translatesAutoresizingMaskIntoConstraints = false
        document.wantsLayer = true
        document.layer?.backgroundColor = BuddyMonBrand.Menu.canvas.cgColor
        scroll.documentView = document

        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = BuddyMonBrand.Spacing.large
        stack.translatesAutoresizingMaskIntoConstraints = false
        document.addSubview(stack)

        NSLayoutConstraint.activate([
            scroll.leadingAnchor.constraint(equalTo: leadingAnchor),
            scroll.trailingAnchor.constraint(equalTo: trailingAnchor),
            scroll.topAnchor.constraint(equalTo: topAnchor),
            scroll.bottomAnchor.constraint(equalTo: bottomAnchor),
            document.widthAnchor.constraint(equalToConstant: Layout.width),
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

        stack.addArrangedSubview(label(
            "COMPACT DROPDOWN / STATE HARNESS",
            font: BuddyMonBrand.Font.strong(22),
            color: BuddyMonBrand.Menu.ink
        ))
        stack.addArrangedSubview(label(
            "Shipping component · compact-only policy · deterministic local fixtures",
            font: BuddyMonBrand.Font.regular(11),
            color: BuddyMonBrand.Menu.mutedInk
        ))
        stack.addArrangedSubview(rarityLegend())

        let fixtures = payload["fixtures"] as? [[String: Any]] ?? []
        for start in stride(from: 0, to: fixtures.count, by: 2) {
            let row = NSStackView()
            row.orientation = .horizontal
            row.alignment = .top
            row.spacing = BuddyMonBrand.Spacing.large
            row.addArrangedSubview(card(fixtures[start]))
            if start + 1 < fixtures.count {
                row.addArrangedSubview(card(fixtures[start + 1]))
            } else {
                let spacer = NSView()
                spacer.widthAnchor.constraint(equalToConstant: Layout.cardWidth).isActive = true
                row.addArrangedSubview(spacer)
            }
            stack.addArrangedSubview(row)
        }

        let setupRow = NSStackView()
        setupRow.orientation = .horizontal
        setupRow.alignment = .top
        setupRow.spacing = BuddyMonBrand.Spacing.large
        setupRow.addArrangedSubview(setupCard())
        setupRow.addArrangedSubview(noticeCard(kind: .loading))
        stack.addArrangedSubview(setupRow)

        let errorRow = NSStackView()
        errorRow.orientation = .horizontal
        errorRow.alignment = .top
        errorRow.spacing = BuddyMonBrand.Spacing.large
        errorRow.addArrangedSubview(noticeCard(kind: .error))
        let errorSpacer = NSView()
        errorSpacer.widthAnchor.constraint(
            equalToConstant: Layout.cardWidth
        ).isActive = true
        errorRow.addArrangedSubview(errorSpacer)
        stack.addArrangedSubview(errorRow)

        let tokenRow = NSStackView()
        tokenRow.orientation = .horizontal
        tokenRow.alignment = .top
        tokenRow.spacing = BuddyMonBrand.Spacing.large
        tokenRow.addArrangedSubview(tokensCard())
        tokenRow.addArrangedSubview(tokensCard(loading: true))
        stack.addArrangedSubview(tokenRow)

        let settingsRow = NSStackView()
        settingsRow.orientation = .horizontal
        settingsRow.alignment = .top
        settingsRow.spacing = BuddyMonBrand.Spacing.large
        settingsRow.addArrangedSubview(settingsCard())
        settingsRow.addArrangedSubview(settingsCard(loading: true))
        stack.addArrangedSubview(settingsRow)

        let encounterRow = NSStackView()
        encounterRow.orientation = .horizontal
        encounterRow.alignment = .top
        encounterRow.spacing = BuddyMonBrand.Spacing.large
        encounterRow.addArrangedSubview(encounterCard(fixtures: fixtures))
        let encounterSpacer = NSView()
        encounterSpacer.widthAnchor.constraint(
            equalToConstant: Layout.cardWidth
        ).isActive = true
        encounterRow.addArrangedSubview(encounterSpacer)
        stack.addArrangedSubview(encounterRow)

        let trainerRow = NSStackView()
        trainerRow.orientation = .horizontal
        trainerRow.alignment = .top
        trainerRow.spacing = BuddyMonBrand.Spacing.large
        trainerRow.addArrangedSubview(trainerCard(nationalComplete: false))
        trainerRow.addArrangedSubview(trainerCard(nationalComplete: true))
        stack.addArrangedSubview(trainerRow)

        let resultRow = NSStackView()
        resultRow.orientation = .horizontal
        resultRow.alignment = .top
        resultRow.spacing = BuddyMonBrand.Spacing.large
        resultRow.addArrangedSubview(encounterResultCard(
            fixtures: fixtures,
            title: "Caught Eevee!",
            message: "Eevee joined your collection.",
            stateID: "encounter_result_caught"
        ))
        resultRow.addArrangedSubview(encounterResultCard(
            fixtures: fixtures,
            title: "Got away safely",
            message: "You ran from Eevee.",
            stateID: "encounter_result_ran"
        ))
        stack.addArrangedSubview(resultRow)
    }

    private func rarityLegend() -> NSView {
        let row = NSStackView()
        row.orientation = .horizontal
        row.alignment = .centerY
        row.spacing = BuddyMonBrand.Spacing.medium
        for rarity in [
            "common",
            "uncommon",
            "rare",
            "legendary",
            "mythic",
            "starter",
        ] {
            let item = NSStackView()
            item.orientation = .horizontal
            item.alignment = .centerY
            item.spacing = BuddyMonBrand.Menu.tightGap
            item.addArrangedSubview(BuddyMonBrand.Menu.makeRarityLabel(rarity))
            item.addArrangedSubview(label(
                rarity.uppercased(),
                font: BuddyMonBrand.Font.regular(9),
                color: BuddyMonBrand.Menu.ink
            ))
            row.addArrangedSubview(item)
        }

        let content = NSStackView(views: [
            label(
                "LAST CATCH / RARITY MARKERS",
                font: BuddyMonBrand.Font.strong(11),
                color: BuddyMonBrand.Menu.chrome
            ),
            row,
        ])
        content.orientation = .vertical
        content.alignment = .leading
        content.spacing = BuddyMonBrand.Spacing.compact
        content.edgeInsets = NSEdgeInsets(
            top: BuddyMonBrand.Spacing.medium,
            left: BuddyMonBrand.Spacing.medium,
            bottom: BuddyMonBrand.Spacing.medium,
            right: BuddyMonBrand.Spacing.medium
        )
        content.widthAnchor.constraint(
            equalToConstant: (Layout.cardWidth * 2) + BuddyMonBrand.Spacing.large
        ).isActive = true
        BuddyMonBrand.Menu.applySurface(to: content)
        return content
    }

    private func card(_ fixture: [String: Any]) -> NSView {
        let title = label(
            fixture["label"] as? String ?? "STATE",
            font: BuddyMonBrand.Font.strong(11),
            color: BuddyMonBrand.Menu.chrome
        )
        let stateID = label(
            fixture["id"] as? String ?? "unknown",
            font: BuddyMonBrand.Font.regular(9),
            color: BuddyMonBrand.Menu.mutedInk
        )
        let panel = BuddyMonCompactMenuView(
            status: fixture["status"] as? [String: Any] ?? [:],
            target: self,
            action: #selector(noop(_:))
        )
        panel.widthAnchor.constraint(
            equalToConstant: BuddyMonBrand.Menu.panelWidth
        ).isActive = true
        panel.heightAnchor.constraint(equalToConstant: panel.preferredSize.height).isActive = true

        let content = NSStackView(views: [title, stateID, panel])
        content.orientation = .vertical
        content.alignment = .leading
        content.spacing = BuddyMonBrand.Spacing.compact
        content.edgeInsets = NSEdgeInsets(
            top: BuddyMonBrand.Spacing.medium,
            left: BuddyMonBrand.Spacing.medium,
            bottom: BuddyMonBrand.Spacing.medium,
            right: BuddyMonBrand.Spacing.medium
        )
        content.widthAnchor.constraint(equalToConstant: Layout.cardWidth).isActive = true
        BuddyMonBrand.Menu.applySurface(to: content)
        return content
    }

    private func tokensCard(loading: Bool = false) -> NSView {
        let payload: [String: Any]
        if loading {
            payload = ["loading": true]
        } else {
            payload = [
                "summary": [
                    [
                        "id": "day",
                        "label": "Today",
                        "compact": "148.2K",
                        "comparison_label": "Yesterday",
                        "comparison_compact": "102.4K",
                        "change": "+45%",
                    ],
                    [
                        "id": "week",
                        "label": "This week",
                        "compact": "714K",
                        "comparison_label": "Last week",
                        "comparison_compact": "1.2M",
                        "change": "-40%",
                    ],
                ],
                "dashboard": [
                    "daily": [
                        ["label": "Mon", "date_label": "Jul 14", "tokens": 82_000, "compact": "82K"],
                        ["label": "Tue", "date_label": "Jul 15", "tokens": 126_000, "compact": "126K"],
                        ["label": "Wed", "date_label": "Jul 16", "tokens": 64_000, "compact": "64K"],
                        ["label": "Thu", "date_label": "Jul 17", "tokens": 238_000, "compact": "238K"],
                        ["label": "Fri", "date_label": "Jul 18", "tokens": 176_000, "compact": "176K"],
                        ["label": "Sat", "date_label": "Jul 19", "tokens": 566_000, "compact": "566K"],
                        ["label": "Sun", "date_label": "Jul 20", "tokens": 148_200, "compact": "148K", "is_today": true],
                    ],
                    "clients": [
                        ["label": "Codex", "percent": 58],
                        ["label": "Claude", "percent": 32],
                        ["label": "Gemini", "percent": 10],
                    ],
                    "insights": [
                        ["id": "average", "value": "200K"],
                        ["id": "peak", "value": "Jul 19"],
                        ["id": "active_streak", "value": "7 days"],
                    ],
                ],
            ]
        }
        let title = label(
            loading
                ? "TOKEN USAGE / LOADING"
                : "TOKEN USAGE / COMPACT DRILL-IN",
            font: BuddyMonBrand.Font.strong(11),
            color: BuddyMonBrand.Menu.chrome
        )
        let stateID = label(
            loading ? "tokens_loading" : "tokens",
            font: BuddyMonBrand.Font.regular(9),
            color: BuddyMonBrand.Menu.mutedInk
        )
        let panel = BuddyMonCompactTokensView(
            view: payload,
            target: self,
            backAction: #selector(noop(_:))
        )
        panel.widthAnchor.constraint(
            equalToConstant: BuddyMonBrand.Menu.panelWidth
        ).isActive = true
        panel.heightAnchor.constraint(equalToConstant: panel.preferredSize.height).isActive = true

        let content = NSStackView(views: [title, stateID, panel])
        content.orientation = .vertical
        content.alignment = .leading
        content.spacing = BuddyMonBrand.Spacing.compact
        content.edgeInsets = NSEdgeInsets(
            top: BuddyMonBrand.Spacing.medium,
            left: BuddyMonBrand.Spacing.medium,
            bottom: BuddyMonBrand.Spacing.medium,
            right: BuddyMonBrand.Spacing.medium
        )
        content.widthAnchor.constraint(equalToConstant: Layout.cardWidth).isActive = true
        BuddyMonBrand.Menu.applySurface(to: content)
        return content
    }

    private func setupCard() -> NSView {
        let panel = BuddyMonCompactStarterSetupView(
            target: self,
            chooseAction: #selector(noop(_:))
        )
        return drillInCard(
            title: "FIRST SIGNAL / COMPACT SETUP",
            stateID: "starter_setup",
            panel: panel,
            height: panel.preferredSize.height
        )
    }

    private func noticeCard(kind: BuddyMonCompactNoticeView.Kind) -> NSView {
        let loading = kind == .loading
        let panel = BuddyMonCompactNoticeView(
            message: loading
                ? "Choosing your starter…"
                : "BuddyMon could not finish setup.\nYour local state was not changed.",
            kind: kind
        )
        return drillInCard(
            title: loading
                ? "FLOW NOTICE / LOADING"
                : "FLOW NOTICE / ERROR",
            stateID: loading ? "flow_loading" : "flow_error",
            panel: panel,
            height: panel.preferredSize.height
        )
    }

    private func settingsCard(loading: Bool = false) -> NSView {
        let rows: [[String: Any]] = [
            [
                "group": "Gameplay",
                "key": "mode",
                "label": "Encounter mode",
                "value": "auto",
                "display_value": "Quick",
                "allowed_values": ["auto", "safari", "battle"],
                "allowed_display_values": ["Quick", "Safari", "Battle"],
                "help": "Choose Quick, Safari, or Battle encounters.",
            ],
            [
                "group": "Notifications",
                "key": "notifications",
                "label": "Notifications",
                "value": "on",
                "display_value": "On",
                "allowed_values": ["on", "silent", "off"],
                "allowed_display_values": ["On", "Silent", "Off"],
                "help": "Rare-event banner behavior.",
            ],
            [
                "group": "Display",
                "key": "menu_launcher",
                "label": "Menu launcher",
                "value": "auto",
                "display_value": "Auto",
                "allowed_values": ["auto", "ghostty", "iterm", "terminal"],
                "allowed_display_values": ["Auto", "Ghostty", "iTerm2", "Terminal.app"],
                "help": "Preferred terminal app for deep screens.",
            ],
            [
                "group": "Display",
                "key": "menu_replace",
                "label": "Replace menus",
                "value": "on",
                "display_value": "On",
                "allowed_values": ["on", "off"],
                "allowed_display_values": ["On", "Off"],
                "help": "Close the prior Ghostty menu before opening another.",
            ],
            [
                "group": "Display",
                "key": "terminal_graphics",
                "label": "Terminal graphics",
                "value": "auto",
                "display_value": "Auto",
                "allowed_values": ["auto", "off"],
                "allowed_display_values": ["Auto", "Off"],
                "help": "Inline image behavior in terminal screens.",
            ],
            [
                "group": "Sharing",
                "key": "share_reveal",
                "label": "Reveal shares",
                "value": "on",
                "display_value": "On",
                "allowed_values": ["on", "off"],
                "allowed_display_values": ["On", "Off"],
                "help": "Reveal exported Showcase images in Finder.",
            ],
            [
                "group": "Sharing",
                "key": "share_banner",
                "label": "Share banners",
                "value": "on",
                "display_value": "On",
                "allowed_values": ["on", "off"],
                "allowed_display_values": ["On", "Off"],
                "help": "Show a banner after sharing Showcase.",
            ],
        ]
        let panel = BuddyMonCompactSettingsView(
            view: loading ? ["loading": true] : ["rows": rows],
            target: self,
            backAction: #selector(noop(_:)),
            selectionAction: #selector(noop(_:))
        )
        return drillInCard(
            title: loading ? "SETTINGS / LOADING" : "SETTINGS / ALL PREFERENCES",
            stateID: loading ? "settings_loading" : "settings",
            panel: panel,
            height: panel.preferredSize.height
        )
    }

    private func encounterCard(fixtures: [[String: Any]]) -> NSView {
        let fixture = fixtures.first { $0["id"] as? String == "pending" } ?? [:]
        let status = fixture["status"] as? [String: Any] ?? [:]
        let buddy = status["active"] as? [String: Any] ?? [:]
        var wild = status["pending"] as? [String: Any] ?? [:]
        wild["wild_level"] = 8
        wild["rarity"] = wild["rarity"] as? String ?? "rare"
        let payload: [String: Any] = [
            "encounter": [
                "mode": "battle",
                "state": "waiting",
                "buddy": buddy,
                "wild": wild,
                "message": "A wild Eevee blocks the path.",
                "hp": ["buddy_percent": 82, "wild_percent": 64],
                "actions": [
                    ["id": "attack", "compact_label": "Fight", "shortcut": "f"],
                    ["id": "ball", "compact_label": "Catch", "shortcut": "c"],
                    ["id": "run", "compact_label": "Run", "shortcut": "r"],
                ],
            ],
        ]
        let panel = BuddyMonCompactEncounterView(
            view: payload,
            message: nil,
            target: self,
            action: #selector(noop(_:)),
            backAction: #selector(noop(_:))
        )
        return drillInCard(
            title: "BATTLE / COMPACT DRILL-IN",
            stateID: "encounter_battle",
            panel: panel,
            height: panel.preferredSize.height
        )
    }

    private func encounterResultCard(
        fixtures: [[String: Any]],
        title: String,
        message: String,
        stateID: String
    ) -> NSView {
        let fixture = fixtures.first { $0["id"] as? String == "pending" } ?? [:]
        let status = fixture["status"] as? [String: Any] ?? [:]
        var wild = status["pending"] as? [String: Any] ?? [:]
        wild["rarity"] = wild["rarity"] as? String ?? "rare"
        let panel = BuddyMonCompactEncounterResultView(
            result: [
                "title": title,
                "message": message,
                "wild": wild,
            ],
            target: self,
            doneAction: #selector(noop(_:))
        )
        return drillInCard(
            title: "BATTLE RESULT / COMPACT",
            stateID: stateID,
            panel: panel,
            height: panel.preferredSize.height
        )
    }

    private func trainerCard(nationalComplete: Bool) -> NSView {
        // Deterministic repository fixture for the optional portrait payload path.
        // This is an existing built-in sprite, not the optional third-party pack.
        let localPortraitFixture =
            "iVBORw0KGgoAAAANSUhEUgAAAGAAAABICAYAAAAJZ/BjAAAA60lEQVR42u3auw2AMAwFwMzCBNSsxHJswyL0sAAfBWFi0Fl6bRT5mshOKQ9V1w1rTda5T5Xa+5dsBQAAAAAAAABoVNkaGh0AAAAAAAAAAAAAAAAAAAAAAAAAFTmox4Z3wecDAAAAAAAAAADcA4heYUafDwAAAAAAAAAAcAEwjvvJNmCrvCcAAAAAAAAAAMA7q8pW39/L1wsAAAAAAAAA4CNX00anAwYAAAAAAAAAZANYptgEN+L701MAAAAAAAAAAIBfNBoAAAAAAAAAAOCVZygAAAAAAAAAAMBFo4NXhj5mAQAAAAAAAABOawPSDZCM4/jv4AAAAABJRU5ErkJggg=="
        let definitions: [(String, String, String, Bool)] = [
            ("bond", "Bond Badge", "♥", true),
            ("safari", "Safari Badge", "◎", true),
            ("battle", "Battle Badge", "×", false),
            ("curator", "Curator Badge", "▣", true),
            ("types", "Type Badge", "◇", false),
            ("shiny", "Shiny Badge", "✦", true),
            ("legend", "Legend Badge", "★", true),
            ("national", "National Badge", "N", nationalComplete),
            ("shiny_legend", "Shiny Legend Badge", "✶", true),
        ]
        var badges = definitions.map { id, label, symbol, earned in
            [
                "id": id,
                "label": label,
                "symbol": symbol,
                "description": "Deterministic Trainer Card fixture.",
                "earned": earned,
            ] as [String: Any]
        }
        if nationalComplete {
            badges.append([
                "id": "shiny_national",
                "label": "Shiny National Badge",
                "symbol": "N✦",
                "description": "Own a shiny copy of every National Pokédex species.",
                "earned": false,
            ])
        }
        let payload: [String: Any] = [
            "id_no": nationalComplete ? "00649" : "45256",
            "star_count": nationalComplete ? 3 : 2,
            "facts": [
                ["id": "name", "label": "NAME", "value": "HUNT"],
                ["id": "tokens", "label": "TOKENS", "value": "12.4B"],
                [
                    "id": "pokedex",
                    "label": "POKÉDEX",
                    "value": nationalComplete ? "649 / 649" : "328 / 649",
                ],
                ["id": "caught", "label": "CAUGHT", "value": "768"],
            ],
            "trainer_stats": [
                [
                    "id": "mode",
                    "label": "MODE",
                    "value": nationalComplete ? "BATTLE" : "QUICK",
                ],
                [
                    "id": "streak",
                    "label": "STREAK",
                    "value": nationalComplete ? "365D" : "7D",
                ],
                [
                    "id": "balls",
                    "label": "BALLS",
                    "value": nationalComplete ? "∞" : "84",
                ],
                [
                    "id": "shiny",
                    "label": "SHINY",
                    "value": nationalComplete ? "42" : "3",
                ],
            ],
            "badges": badges,
            "selected_badge_id": nationalComplete ? "shiny_national" : "shiny_legend",
        ]
        var harnessPayload = payload
        if !nationalComplete {
            harnessPayload["portrait_base64"] = localPortraitFixture
        }
        let panel = BuddyMonCompactTrainerView(
            view: harnessPayload,
            target: self,
            backAction: #selector(noop(_:))
        )
        return drillInCard(
            title: nationalComplete
                ? "TRAINER CARD / NATIONAL COMPLETE"
                : "TRAINER CARD / LOCAL PORTRAIT FIXTURE",
            stateID: nationalComplete
                ? "trainer_national_complete"
                : "trainer_local_portrait_fixture",
            panel: panel,
            height: panel.preferredSize.height
        )
    }

    private func drillInCard(
        title: String,
        stateID: String,
        panel: NSView,
        height: CGFloat
    ) -> NSView {
        let titleLabel = label(
            title,
            font: BuddyMonBrand.Font.strong(11),
            color: BuddyMonBrand.Menu.chrome
        )
        let idLabel = label(
            stateID,
            font: BuddyMonBrand.Font.regular(9),
            color: BuddyMonBrand.Menu.mutedInk
        )
        panel.widthAnchor.constraint(
            equalToConstant: BuddyMonBrand.Menu.panelWidth
        ).isActive = true
        panel.heightAnchor.constraint(equalToConstant: height).isActive = true

        let content = NSStackView(views: [titleLabel, idLabel, panel])
        content.orientation = .vertical
        content.alignment = .leading
        content.spacing = BuddyMonBrand.Spacing.compact
        content.edgeInsets = NSEdgeInsets(
            top: BuddyMonBrand.Spacing.medium,
            left: BuddyMonBrand.Spacing.medium,
            bottom: BuddyMonBrand.Spacing.medium,
            right: BuddyMonBrand.Spacing.medium
        )
        content.widthAnchor.constraint(equalToConstant: Layout.cardWidth).isActive = true
        BuddyMonBrand.Menu.applySurface(to: content)
        return content
    }

    private func label(_ text: String, font: NSFont, color: NSColor) -> NSTextField {
        let field = NSTextField(labelWithString: text)
        field.font = font
        field.textColor = color
        field.alignment = .left
        field.lineBreakMode = .byTruncatingTail
        return field
    }

    @objc private func noop(_ sender: Any?) {}
}

private final class FlippedMenuPanelHarnessDocument: NSView {
    override var isFlipped: Bool { true }
}
