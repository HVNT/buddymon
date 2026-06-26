"""Journal + notification gating tests."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import journal


def _isolate(tmp_path, monkeypatch):
    from lib import paths
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path)
    monkeypatch.setattr(paths, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(paths, "JOURNAL_FILE", tmp_path / "journal.jsonl")


def test_append_tail_roundtrip_and_corrupt_tolerance(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    journal.append("caught", "🎉 caught Pidgey", {"name": "Pidgey"})
    with open(tmp_path / "journal.jsonl", "a") as f:
        f.write("not json\n")
    journal.append("level", "⬆️ Lv.5")
    entries = journal.tail(10)
    assert [e["kind"] for e in entries] == ["caught", "level"]
    assert entries[0]["name"] == "Pidgey"


def test_log_outcomes_kinds(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    result = {"xp": 50, "old_level": 15, "new_level": 16, "leveled": True,
              "evolved": "Charmeleon", "buddy": "Charmeleon"}
    encounter = {"name": "Mewtwo", "emoji": "🧬", "rarity": "legendary",
                 "shiny": False, "outcome": "fled"}
    written = journal.log_outcomes(result, encounter, "claude")
    assert [e["kind"] for e in written] == ["evolved", "fled"]
    assert "Lv.16" in written[0]["text"]
    assert written[1]["rarity"] == "legendary"

    written = journal.log_outcomes(
        {"xp": 5, "old_level": 3, "new_level": 3, "leveled": False,
         "evolved": None, "buddy": "Pikachu"},
        {"name": "Pidgey", "emoji": "🐦", "rarity": "common", "shiny": True,
         "level": 12, "outcome": "caught", "new_species": True}, "cross")
    assert [e["kind"] for e in written] == ["caught"]
    assert written[0]["shiny"] is True
    assert written[0]["level"] == 12
    assert "Lv.12" in written[0]["text"]


def test_is_rare_truth_table():
    assert journal.is_rare({"kind": "evolved"})
    assert journal.is_rare({"kind": "caught", "shiny": True, "rarity": "common"})
    assert journal.is_rare({"kind": "fled", "shiny": False, "rarity": "legendary"})
    assert journal.is_rare({"kind": "no_balls", "rarity": "legendary"})
    assert not journal.is_rare({"kind": "caught", "shiny": False, "rarity": "common"})
    assert not journal.is_rare({"kind": "level", "level": 30})
    assert not journal.is_rare({"kind": "fled", "rarity": "rare"})


def test_notify_fires_only_for_rare(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    from lib import notify
    calls = []
    monkeypatch.setattr(notify, "notify", lambda title, text: calls.append(text))

    entries = journal.log_outcomes(
        {"xp": 9, "old_level": 2, "new_level": 2, "leveled": False,
         "evolved": None, "buddy": "Eevee"},
        {"name": "Articuno", "emoji": "🧊", "rarity": "legendary", "shiny": False,
         "outcome": "caught", "new_species": True}, "claude")
    for e in entries:
        if journal.is_rare(e):
            notify.notify("buddymon", e["text"])
    assert len(calls) == 1 and "Articuno" in calls[0]


def test_open_menu_cmd_runs_stateful_launcher():
    from lib import notify

    cmd = notify.open_menu_cmd("tokens")

    assert cmd.startswith("/usr/bin/python3 ")
    assert "buddymon.py open-menu tokens" in cmd


def test_open_menu_prefers_ghostty_and_replaces_owned_menu(monkeypatch):
    from lib import menu_launcher

    killed = []
    spawned = []
    ps = "\n".join([
        "  101 /Applications/Ghostty.app/Contents/MacOS/ghostty",
        "  202 /Applications/Ghostty.app/Contents/MacOS/ghostty --command=/bin/zsh --input=raw:exec /usr/bin/python3 /Users/hunt/buddymon/buddymon.py menu\\n",
        "  303 /Applications/Ghostty.app/Contents/MacOS/ghostty --command=/bin/zsh --input=raw:exec /usr/bin/python3 /tmp/other/buddymon.py menu\\n",
        "  404 /Applications/Ghostty.app/Contents/MacOS/ghostty --command=/bin/zsh",
    ])
    monkeypatch.setattr(menu_launcher, "_ghostty_available", lambda: True)
    monkeypatch.setattr(menu_launcher, "_iterm_available", lambda: True)

    def fake_run(args, **_kwargs):
        if args[:3] == ["ps", "-ax", "-o"]:
            return type("Result", (), {"returncode": 0, "stdout": ps})()
        if args[0] == "kill":
            killed.append(int(args[1]))
            return type("Result", (), {"returncode": 0, "stdout": ""})()
        raise AssertionError(args)

    monkeypatch.setattr(menu_launcher.subprocess, "run", fake_run)
    monkeypatch.setattr(menu_launcher.subprocess, "Popen", lambda args: spawned.append(args))

    menu_launcher.open_menu("tokens")

    assert killed == [202]
    assert spawned and spawned[0][:4] == ["open", "-na", "Ghostty", "--args"]
    assert "--window-width=88" in spawned[0]
    assert "--window-height=30" in spawned[0]
    assert any("buddymon.py menu tokens" in part for part in spawned[0])


def test_open_menu_uses_iterm_when_ghostty_missing(monkeypatch):
    from lib import menu_launcher

    spawned = []
    monkeypatch.setattr(menu_launcher, "_ghostty_available", lambda: False)
    monkeypatch.setattr(menu_launcher, "_iterm_available", lambda: True)
    monkeypatch.setattr(menu_launcher.subprocess, "Popen", lambda args: spawned.append(args))

    menu_launcher.open_menu("tokens")

    assert spawned and spawned[0][0] == "osascript"
    assert "iTerm" in spawned[0][2]
    assert "buddymon.py menu tokens" in spawned[0][2]


def test_open_menu_uses_terminal_when_ghostty_and_iterm_missing(monkeypatch):
    from lib import menu_launcher

    spawned = []
    monkeypatch.setattr(menu_launcher, "_ghostty_available", lambda: False)
    monkeypatch.setattr(menu_launcher, "_iterm_available", lambda: False)
    monkeypatch.setattr(menu_launcher.subprocess, "Popen", lambda args: spawned.append(args))

    menu_launcher.open_menu("tokens")

    assert spawned and spawned[0][0] == "osascript"
    assert any("Terminal" in part for part in spawned[0])
    assert any("buddymon.py menu tokens" in part for part in spawned[0])
