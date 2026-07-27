import AppKit
import Darwin
import Foundation

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    private enum CommandTimeout {
        static let status: TimeInterval = 15
        static let view: TimeInterval = 20
        static let action: TimeInterval = 30
        static let terminalLaunch: TimeInterval = 30
        static let scheduledCollection: TimeInterval = 300
    }

    private let runner = BuddyMonRunner()
    private let menuPanelController = MenuPanelController()
    private let singleInstanceGuard = SingleInstanceGuard()
    private let localStateObserver = LocalStateObserver()
    private var statusItem: NSStatusItem!
    private var menuBarBuddyController: MenuBarBuddyController!
    private var latestStatus: [String: Any] = [:]
    private var collectionTask: Task<Void, Never>?
    private var passiveStatusRefreshTask: Task<Void, Never>?
    private var passiveStatusRefreshPending = false
    private var menuBarPreviewSignalSource: DispatchSourceSignal?
    private var statusRefreshGeneration = 0
    private var hasConfirmedStatus = false
    private var awaitsInitialStatus = true
    private static let openPanelNotification = Notification.Name(
        "com.hunt.buddymon.open-menu-panel"
    )

    func applicationDidFinishLaunching(_ notification: Notification) {
        guard claimSingleInstance() else {
            NSApp.terminate(nil)
            return
        }

        NSApp.setActivationPolicy(.accessory)
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        if let button = statusItem.button {
            menuBarBuddyController = MenuBarBuddyController(button: button)
            menuBarBuddyController.showBooting()
        }
        statusItem.button?.target = self
        statusItem.button?.action = #selector(handleStatusItemClick(_:))
        statusItem.button?.sendAction(on: [.leftMouseUp])
        menuPanelController.attach(to: statusItem.button)
        DistributedNotificationCenter.default().addObserver(
            self,
            selector: #selector(handleOpenPanelSignal(_:)),
            name: Self.openPanelNotification,
            object: nil,
            suspensionBehavior: .deliverImmediately
        )
        installMenuBarPreviewSignal()
        installLocalStateObserver()
        Task { [weak self] in
            guard let self else { return }
            await refreshStatus()
            collectLocalUsage()
        }
        Timer.scheduledTimer(withTimeInterval: 30, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.requestStatusRefresh()
            }
        }
        Timer.scheduledTimer(withTimeInterval: 300, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.collectLocalUsage()
            }
        }
    }

    private func claimSingleInstance() -> Bool {
        do {
            switch try singleInstanceGuard.acquire() {
            case .acquired:
                return true
            case .alreadyRunning:
                DistributedNotificationCenter.default().post(
                    name: Self.openPanelNotification,
                    object: nil
                )
                return false
            }
        } catch {
            let alert = NSAlert()
            alert.messageText = "BuddyMon could not start"
            alert.informativeText = [
                "The app could not secure its single-instance lock.",
                error.localizedDescription,
            ].joined(separator: " ")
            alert.runModal()
            return false
        }
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        presentRootPanel()
        return true
    }

    func applicationWillTerminate(_ notification: Notification) {
        localStateObserver.stop()
        passiveStatusRefreshTask?.cancel()
        passiveStatusRefreshTask = nil
        menuBarPreviewSignalSource?.cancel()
        menuBarPreviewSignalSource = nil
        try? FileManager.default.removeItem(at: menuBarPreviewURL)
        DistributedNotificationCenter.default().removeObserver(self)
    }

    private func refreshStatus() async {
        statusRefreshGeneration += 1
        let generation = statusRefreshGeneration
        do {
            let status = try await runner.status(timeout: CommandTimeout.status)
            guard generation == statusRefreshGeneration else { return }
            latestStatus = status
            hasConfirmedStatus = true
            menuBarBuddyController.apply(status: status)
            refreshRootPanelIfVisible()
            if awaitsInitialStatus {
                awaitsInitialStatus = false
                _ = presentStarterSetupIfNeeded()
            }
        } catch {
            guard generation == statusRefreshGeneration else { return }
            latestStatus = ["error": runner.diagnosticText(error: error)]
            hasConfirmedStatus = false
            menuBarBuddyController.showUnavailable()
            refreshRootPanelIfVisible()
        }
    }

    private func installLocalStateObserver() {
        localStateObserver.start { [weak self] in
            self?.requestStatusRefresh()
        }
    }

    private func requestStatusRefresh() {
        guard passiveStatusRefreshTask == nil else {
            passiveStatusRefreshPending = true
            return
        }

        passiveStatusRefreshTask = Task { @MainActor [weak self] in
            guard let self else { return }
            repeat {
                passiveStatusRefreshPending = false
                await refreshStatus()
            } while passiveStatusRefreshPending && !Task.isCancelled
            passiveStatusRefreshTask = nil
        }
    }

    @objc private func handleNativeMenuAction(_ sender: NSButton) {
        switch sender.identifier?.rawValue {
        case "encounter": openEncounter()
        case "tokens": openTokenUsage()
        case "trainer": openTrainerCard()
        case "terminal_party": openTerminalExperience(screen: "party")
        case "terminal_box": openTerminalExperience(screen: "box")
        case "terminal_dex": openTerminalExperience(screen: "dex")
        case "terminal_activity": openTerminalExperience(screen: "journal")
        case "settings": openSettings()
        case "refresh":
            Task { [weak self] in
                await self?.refreshStatus()
            }
        case "quit": quit()
        default: break
        }
    }

    @objc private func handleStatusItemClick(_ sender: NSStatusBarButton) {
        if menuPanelController.isVisible {
            menuPanelController.close()
        } else {
            presentRootPanel()
        }
    }

    @objc private func handleOpenPanelSignal(_ notification: Notification) {
        presentRootPanel()
    }

    private var menuBarPreviewURL: URL {
        FileManager.default.temporaryDirectory.appendingPathComponent(
            "buddymon-menu-bar-preview-\(getuid()).json"
        )
    }

    private func installMenuBarPreviewSignal() {
        Darwin.signal(SIGWINCH, SIG_IGN)
        let source = DispatchSource.makeSignalSource(signal: SIGWINCH, queue: .main)
        source.setEventHandler { [weak self] in
            self?.consumeMenuBarPreview()
        }
        source.resume()
        menuBarPreviewSignalSource = source
    }

    private func consumeMenuBarPreview() {
        let url = menuBarPreviewURL
        defer { try? FileManager.default.removeItem(at: url) }
        guard
            let data = try? Data(contentsOf: url),
            let envelope = try? JSONDecoder().decode(
                MenuBarBuddyPreviewEnvelope.self,
                from: data
            ),
            envelope.schemaVersion == 1
        else { return }
        menuBarBuddyController.preview(envelope)
    }

    private func presentRootPanel() {
        requestStatusRefresh()
        if presentStarterSetupIfNeeded() {
            return
        }
        menuPanelController.presentRoot(
            status: latestStatus,
            target: self,
            action: #selector(handleNativeMenuAction(_:))
        )
    }

    private func refreshRootPanelIfVisible() {
        guard
            menuPanelController.isVisible,
            menuPanelController.displayMode == .menu
        else { return }
        menuPanelController.presentRoot(
            status: latestStatus,
            target: self,
            action: #selector(handleNativeMenuAction(_:))
        )
    }

    private func presentStarterSetupIfNeeded() -> Bool {
        guard hasConfirmedStatus else { return false }
        guard latestStatus["error"] == nil else { return false }
        guard latestStatus["recovery_required"] as? Bool != true else { return false }
        guard (latestStatus["has_buddy"] as? Bool) == false else { return false }
        guard latestStatus["active"] as? [String: Any] == nil else { return false }
        guard
            let setup = latestStatus["setup"] as? [String: Any],
            setup["needs_starter"] as? Bool == true
        else { return false }
        menuPanelController.presentStarterSetup(
            target: self,
            chooseAction: #selector(chooseStarterFromWelcome(_:))
        )
        return true
    }

    private func chooseStarter(_ starter: String) async -> Bool {
        menuPanelController.presentLoading("Choosing your starter…")
        do {
            _ = try await runner.run(
                ["choose", starter],
                timeout: CommandTimeout.action
            )
            await refreshStatus()
            return true
        } catch {
            presentMessage(runner.diagnosticText(error: error))
            return false
        }
    }

    @objc private func chooseStarterFromWelcome(_ sender: NSButton) {
        guard let starter = sender.identifier?.rawValue else { return }
        Task { [weak self] in
            guard let self else { return }
            if await chooseStarter(starter) {
                presentRootPanel()
            }
        }
    }

    private func collectLocalUsage() {
        guard collectionTask == nil else { return }
        collectionTask = Task { [weak self] in
            guard let self else { return }
            defer { collectionTask = nil }
            _ = try? await runner.run(
                ["collect", "--scheduled"],
                timeout: CommandTimeout.scheduledCollection
            )
            await refreshStatus()
        }
    }

    private func presentMessage(_ text: String) {
        menuPanelController.presentMessage(text)
    }

    @objc private func openRootPanel() {
        menuPanelController.presentRoot(
            status: latestStatus,
            target: self,
            action: #selector(handleNativeMenuAction(_:))
        )
    }

    private func loadEncounter(message: String? = nil) async {
        do {
            let view = try await runner.appView(
                "encounter",
                timeout: CommandTimeout.view
            )
            menuPanelController.presentEncounter(
                view: view,
                message: message,
                target: self,
                action: #selector(handleEncounterAction(_:)),
                backAction: #selector(openRootPanel)
            )
        } catch {
            menuPanelController.presentEncounterResult(
                result: [
                    "title": "Encounter unavailable",
                    "message": error.localizedDescription,
                ],
                target: self,
                doneAction: #selector(openRootPanel)
            )
        }
    }

    @objc private func handleEncounterAction(_ sender: NSButton) {
        let action = sender.identifier?.rawValue ?? ""
        sender.isEnabled = false
        Task { [weak self, weak sender] in
            guard let self else { return }
            defer { sender?.isEnabled = true }
            do {
                let response = try await runner.appAction(
                    "encounter",
                    [action],
                    timeout: CommandTimeout.action
                )
                await refreshStatus()
                let message = response["message"] as? String
                if let result = response["encounter_result"] as? [String: Any] {
                    menuPanelController.presentEncounterResult(
                        result: result,
                        target: self,
                        doneAction: #selector(openRootPanel)
                    )
                } else if let view = response["view"] as? [String: Any] {
                    menuPanelController.presentEncounter(
                        view: view,
                        message: message,
                        target: self,
                        action: #selector(handleEncounterAction(_:)),
                        backAction: #selector(openRootPanel)
                    )
                } else {
                    await loadEncounter(message: message)
                }
            } catch {
                menuPanelController.presentEncounterResult(
                    result: [
                        "title": "Move failed",
                        "message": error.localizedDescription,
                    ],
                    target: self,
                    doneAction: #selector(openRootPanel)
                )
            }
        }
    }

    private func loadTokenUsage() async {
        do {
            let view = try await runner.appView(
                "tokens",
                timeout: CommandTimeout.view
            )
            presentTokenUsage(view)
        } catch {
            presentTokenUsage([
                "error": runner.diagnosticText(error: error),
            ])
        }
    }

    private func presentTokenUsage(_ view: [String: Any]) {
        menuPanelController.presentTokenUsage(
            view: view,
            target: self,
            backAction: #selector(openRootPanel)
        )
    }

    private func loadTrainerCard() async {
        do {
            let view = try await runner.appView(
                "trainer",
                timeout: CommandTimeout.view
            )
            menuPanelController.presentTrainerCard(
                view: view,
                target: self,
                backAction: #selector(openRootPanel)
            )
        } catch {
            presentMessage(runner.diagnosticText(error: error))
        }
    }

    private func presentSettings(_ view: [String: Any]) {
        menuPanelController.presentSettings(
            view: view,
            target: self,
            backAction: #selector(openRootPanel),
            selectionAction: #selector(handleCompactSettingsAction(_:))
        )
    }

    private func loadSettings() async {
        do {
            let view = try await runner.appView(
                "settings",
                timeout: CommandTimeout.view
            )
            presentSettings(view)
        } catch {
            presentSettings(["error": runner.diagnosticText(error: error)])
        }
    }

    @objc private func handleCompactSettingsAction(_ sender: NSButton) {
        guard let identifier = sender.identifier?.rawValue else { return }
        let preferencePrefix = "settings_preference:"
        guard identifier.hasPrefix(preferencePrefix) else { return }
        let selection = identifier.dropFirst(preferencePrefix.count).split(
            separator: ":",
            maxSplits: 1
        )
        guard selection.count == 2 else { return }
        let key = String(selection[0])
        let value = String(selection[1])
        sender.isEnabled = false
        Task { [weak self, weak sender] in
            guard let self else { return }
            defer { sender?.isEnabled = true }
            do {
                let response = try await runner.appAction(
                    "preference",
                    [key, value],
                    timeout: CommandTimeout.action
                )
                guard response["ok"] as? Bool == true else {
                    let message = response["message"] as? String
                        ?? "The setting could not be changed."
                    presentSettings(["error": message])
                    return
                }
                let view: [String: Any]
                if let responseView = response["view"] as? [String: Any] {
                    view = responseView
                } else {
                    view = try await runner.appView(
                        "settings",
                        timeout: CommandTimeout.view
                    )
                }
                presentSettings(view)
                await refreshStatus()
            } catch {
                presentSettings(["error": runner.diagnosticText(error: error)])
            }
        }
    }

    @objc private func openEncounter() {
        Task { [weak self] in
            await self?.loadEncounter()
        }
    }

    @objc private func openTokenUsage() {
        presentTokenUsage(["loading": true])
        Task { [weak self] in
            await self?.loadTokenUsage()
        }
    }

    @objc private func openTrainerCard() {
        Task { [weak self] in
            await self?.loadTrainerCard()
        }
    }

    @objc private func openSettings() {
        presentSettings(["loading": true])
        Task { [weak self] in
            await self?.loadSettings()
        }
    }

    private func openTerminalExperience(screen: String? = nil) {
        let windowFrame = menuPanelController.prepareForTerminalHandoff()
        Task { [weak self] in
            guard let self else { return }
            do {
                var arguments = ["open-menu"]
                if let screen {
                    arguments.append(screen)
                }
                if let windowFrame {
                    arguments.append("--window-frame=\(windowFrame)")
                }
                _ = try await runner.run(
                    arguments,
                    timeout: CommandTimeout.terminalLaunch
                )
            } catch {
                presentMessage(
                    "Terminal experience could not open.\n\n" +
                    runner.diagnosticText(error: error)
                )
            }
        }
    }

    @objc private func quit() {
        NSApp.terminate(nil)
    }
}
