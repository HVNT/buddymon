"""Showcase PNG export stays local, labeled, and deterministic."""
from datetime import datetime
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import engine, showcase_export, state


def _png_size(blob):
    assert blob[:8] == b"\x89PNG\r\n\x1a\n"
    assert blob[12:16] == b"IHDR"
    return struct.unpack(">II", blob[16:24])


def fresh():
    s = state.default_state()
    engine.create_starter(s, "Charmander")
    return s


def test_showcase_filename_is_desktop_friendly():
    now = datetime(2026, 7, 6, 11, 7, 16)

    assert showcase_export.showcase_filename(now) == (
        "BuddyMon Showcase - 2026-07-06 11.07.16.png"
    )


def test_card_labels_include_dex_name_level_and_empty_states():
    pidgey = engine.new_pokemon("Pidgey", "Flying", "P", "common", level=5)
    shiny = engine.new_pokemon("Staryu", "Water", "S", "common", level=8, shiny=True)

    assert showcase_export.card_label_lines({"pokemon": pidgey}) == (
        "#016 PIDGEY",
        "LV.5 COMMON",
    )
    assert showcase_export.card_label_lines({"pokemon": shiny}) == (
        "#120 STARYU*",
        "LV.8 COMMON",
    )
    assert showcase_export.card_label_lines({"pokemon": None}, can_choose=True) == (
        "EMPTY PODIUM",
        "CHOOSE FROM BOX",
    )
    assert showcase_export.card_label_lines({"pokemon": None}, can_choose=False) == (
        "EMPTY PODIUM",
        "CATCH FIRST",
    )
    assert showcase_export.card_label_lines({"pokemon": None, "missing": True}) == (
        "MISSING SLOT",
        "REPLACE/CLEAR",
    )


def test_render_showcase_png_has_expected_dimensions_and_does_not_mutate_state():
    s = fresh()
    pidgey = engine.new_pokemon("Pidgey", "Flying", "P", "common", level=5)
    s["pokemon"].append(pidgey)
    s["showcase"] = {"slots": [pidgey["id"], None, "gone"]}
    before = dict(s["showcase"])

    blob = showcase_export.render_showcase_png(
        s,
        generated_at=datetime(2026, 7, 6, 11, 7, 16),
    )

    assert _png_size(blob) == (
        showcase_export.WIDTH * showcase_export.PNG_SCALE,
        showcase_export.HEIGHT * showcase_export.PNG_SCALE,
    )
    assert s["showcase"] == before


def test_save_showcase_image_writes_unique_png(tmp_path):
    s = fresh()
    now = datetime(2026, 7, 6, 11, 7, 16)
    first_name = showcase_export.showcase_filename(now)
    (tmp_path / first_name).write_bytes(b"already here")

    path = showcase_export.save_showcase_image(s, dest_dir=tmp_path, now=now)

    assert path.name == "BuddyMon Showcase - 2026-07-06 11.07.16 (2).png"
    assert path.parent == tmp_path
    assert _png_size(path.read_bytes()) == (
        showcase_export.WIDTH * showcase_export.PNG_SCALE,
        showcase_export.HEIGHT * showcase_export.PNG_SCALE,
    )


def test_share_showcase_reveals_and_notifies_saved_file(tmp_path, monkeypatch):
    import buddymon

    s = fresh()
    path = tmp_path / "BuddyMon Showcase.png"
    calls = []
    monkeypatch.setattr(buddymon.state, "load", lambda: s)
    monkeypatch.setattr(
        buddymon.showcase_share.showcase_export,
        "save_showcase_image",
        lambda loaded: path if loaded is s else None,
    )
    monkeypatch.setattr(buddymon.showcase_share, "reveal_file", lambda saved: calls.append(("reveal", saved)))
    monkeypatch.setattr(
        buddymon.showcase_share.notify,
        "banner",
        lambda title, text: calls.append(("banner", title, text)),
    )

    out = buddymon.share_showcase([])

    assert out == f"saved Showcase image to {path}"
    assert calls == [
        ("reveal", path),
        ("banner", "BuddyMon Showcase", "Saved BuddyMon Showcase.png"),
    ]


def test_share_showcase_notifies_save_failure(monkeypatch):
    import buddymon

    calls = []
    monkeypatch.setattr(buddymon.state, "load", state.default_state)

    def fail(_state):
        raise PermissionError("Desktop denied")

    monkeypatch.setattr(buddymon.showcase_share.showcase_export, "save_showcase_image", fail)
    monkeypatch.setattr(buddymon.showcase_share, "reveal_file", lambda _path: calls.append(("reveal",)))
    monkeypatch.setattr(
        buddymon.showcase_share.notify,
        "banner",
        lambda title, text: calls.append(("banner", title, text)),
    )

    out = buddymon.share_showcase([])

    assert out == "share failed: Desktop denied"
    assert calls == [("banner", "BuddyMon Showcase", "share failed: Desktop denied")]


def test_share_showcase_honors_quiet_feedback_preferences(tmp_path, monkeypatch):
    import buddymon

    s = fresh()
    s["preferences"]["share_reveal"] = "off"
    s["preferences"]["share_banner"] = "off"
    path = tmp_path / "BuddyMon Showcase.png"
    calls = []
    monkeypatch.setattr(buddymon.state, "load", lambda: s)
    monkeypatch.setattr(buddymon.showcase_share.showcase_export, "save_showcase_image", lambda _state: path)
    monkeypatch.setattr(buddymon.showcase_share, "reveal_file", lambda saved: calls.append(("reveal", saved)))
    monkeypatch.setattr(
        buddymon.showcase_share.notify,
        "banner",
        lambda title, text: calls.append(("banner", title, text)),
    )

    out = buddymon.share_showcase([])

    assert out == f"saved Showcase image to {path}"
    assert calls == []


def test_share_showcase_respects_failure_banner_preference(monkeypatch):
    import buddymon

    s = fresh()
    s["preferences"]["share_banner"] = "off"
    calls = []
    monkeypatch.setattr(buddymon.state, "load", lambda: s)

    def fail(_state):
        raise PermissionError("Desktop denied")

    monkeypatch.setattr(buddymon.showcase_share.showcase_export, "save_showcase_image", fail)
    monkeypatch.setattr(
        buddymon.showcase_share.notify,
        "banner",
        lambda title, text: calls.append(("banner", title, text)),
    )

    out = buddymon.share_showcase([])

    assert out == "share failed: Desktop denied"
    assert calls == []
