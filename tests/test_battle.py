"""Battle Mode: combat state machine, mode gating, scene HP + throw render."""
import base64
import random
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import battle, data, engine, packs, png, scene, state


class SeqRandom:
    def __init__(self, randoms=(), uniforms=()):
        self._r, self._u = list(randoms), list(uniforms)

    def random(self):
        return self._r.pop(0) if self._r else 0.5

    def uniform(self, a, b):
        return self._u.pop(0) if self._u else (a + b) / 2

    def randint(self, a, b):
        return a


def spawn(rarity="common", name="Pidgey", ptype="Flying"):
    return {"name": name, "type": ptype, "emoji": "🐦", "rarity": rarity, "shiny": False}


def fresh(level=20, starter="Charmander"):
    s = state.default_state()
    engine.create_starter(s, starter)
    state.active_pokemon(s)["level"] = level
    return s


def test_start_sets_hp_from_levels():
    buddy = {"level": 20}
    p = battle.start(spawn(), buddy)
    assert p["buddy_hp"] == p["buddy_hp_max"] > 0
    assert p["wild_hp"] == p["wild_hp_max"] > 0
    assert p["wild_level"] >= 1


def test_start_uses_spawn_level_and_clamps_to_species_stage():
    buddy = {"level": 5}
    p = battle.start({**spawn(name="Charizard", ptype="Fire"), "level": 20}, buddy)
    assert p["wild_level"] == 36
    assert p["level"] == 36


def test_attack_lowers_wild_and_can_ko():
    buddy = {"level": 20}
    p = battle.start(spawn(), buddy)
    p["wild_hp"] = 3  # nearly dead
    out = battle.attack(p, buddy, {}, SeqRandom(uniforms=[1.5, 0.5]))
    assert out["done"] and out["outcome"] == "ko" and not out["caught"]


def test_buddy_faint_flees_and_full_revives():
    buddy = {"level": 20}
    p = battle.start(spawn(), buddy)
    p["buddy_hp"] = 1
    # attack doesn't KO wild (wild has full HP), then wild turn faints buddy
    out = battle.attack(p, buddy, {}, SeqRandom(uniforms=[0.8, 1.1]))
    assert out["done"] and out["outcome"] == "buddy_faint"
    assert p["buddy_hp"] == p["buddy_hp_max"]  # full revive


def test_catch_probability_rises_as_hp_drops():
    buddy = {"level": 20}
    p = battle.start(spawn("common"), buddy)
    full = battle.catch_probability(p)
    p["wild_hp"] = 1
    low = battle.catch_probability(p)
    assert low > full
    assert low <= data.BATTLE["catch_cap"]


def test_throw_catches_and_balls_are_infinite():
    buddy = {"level": 20}
    p = battle.start(spawn(), buddy)
    trainer = {"balls": 0}  # no balls — battle mode ignores supply
    out = battle.throw_ball(p, buddy, trainer, SeqRandom(randoms=[0.0]))  # 0.0 < prob -> catch
    assert out["caught"] and out["done"]
    assert trainer["balls"] == 0  # never decremented
    assert p["last_throw"]["caught"] is True


def test_throw_break_free_continues():
    buddy = {"level": 20}
    p = battle.start(spawn(), buddy)
    out = battle.throw_ball(p, buddy, {}, SeqRandom(randoms=[0.99, 0.5], uniforms=[0.5]))
    assert not out["caught"] and not out["done"]  # broke free, wild took its turn
    assert p["last_throw"]["caught"] is False


def test_run_ends():
    out = battle.run(battle.start(spawn(), {"level": 10}), {"level": 10}, {}, SeqRandom())
    assert out["done"] and out["outcome"] == "ran"


def test_roll_encounter_battle_mode_makes_any_wild_a_battle():
    import random as _r
    for seed in range(200):
        s = fresh()
        s["mode"] = "battle"
        res = engine.roll_encounter(s, _r.Random(seed))
        if res and res["outcome"] == "appeared":
            assert s.get("pending_battle") and not s.get("pending_encounter")
            # second spawn suppressed while one is pending
            assert engine.roll_encounter(s, _r.Random(seed)) is None
            return
    raise AssertionError("no battle spawn in 200 seeds")


def test_auto_mode_unchanged_by_battle_code():
    import random as _r
    for seed in range(200):
        s = fresh()  # default mode auto
        res = engine.roll_encounter(s, _r.Random(seed))
        if res and res["rarity"] in ("common", "uncommon"):
            assert res["outcome"] in ("caught", "fled", "no_balls")
            assert "pending_battle" not in s
            return
    raise AssertionError("no common encounter found")


def test_battle_screen_hp_bars_scale():
    buddy = (["BB" * 12] * 24, {"B": "#f08030"})
    wild = (["WW" * 12] * 24, {"W": "#58a8e8"})
    full = scene.battle_screen(buddy, wild, "active", wild_hp_frac=1.0, buddy_hp_frac=1.0)
    low = scene.battle_screen(buddy, wild, "active", wild_hp_frac=0.1, buddy_hp_frac=0.5)
    for g, pal in (full, low):
        assert png.grid_to_png(g, pal)[:1] == b"\x89"

    hp_colors = {scene._HP_GREEN, scene._HP_YELLOW, scene._HP_RED}

    def hp_cells(grid, palette):
        hp_chars = {ch for ch, hx in palette.items() if hx in hp_colors}
        return sum(row.count(ch) for row in grid for ch in hp_chars)

    assert hp_cells(*low) < hp_cells(*full)  # wild HP low → shorter fill


def test_throw_jiggle_bar_renders_all_phases():
    buddy = (["BB" * 8] * 14, {"B": "#f08030"})
    wild = (["WW" * 8] * 14, {"W": "#58a8e8"})
    for caught in (True, False):
        lt = {"jiggles": 3, "caught": caught, "ts": 0}
        for phase in range(scene.THROW_SECS):
            g, pal = scene.throw_jiggle_bar(buddy, wild, phase, lt)
            assert all(len(r) == 44 for r in g)
            assert png.grid_to_png(g, pal)[:1] == b"\x89"
    assert scene.throw_phase_for(scene.THROW_SECS) is None


def test_take_turn_resolves_safely(tmp_path, monkeypatch):
    # take_turn is the shared path for the dropdown commands AND the TUI; it must
    # apply the catch and clear pending without real journal writes / notifications.
    from lib import notify, paths, safari
    monkeypatch.setattr(paths, "JOURNAL_FILE", tmp_path / "j.jsonl")
    monkeypatch.setattr(notify, "notify", lambda *a, **k: None)

    # battle: a successful throw adds the wild and clears pending_battle
    s = fresh(level=20)
    s["pending_battle"] = battle.start(spawn("rare", "Beldum", "Steel"),
                                       state.active_pokemon(s))
    n = len(s["pokemon"])
    outcome, _ = battle.take_turn(s, "ball", SeqRandom(randoms=[0.0]))  # 0.0 < prob → catch
    assert outcome["caught"] and "pending_battle" not in s
    assert len(s["pokemon"]) == n + 1

    # safari: running clears pending_encounter without catching
    s2 = fresh()
    s2["pending_encounter"] = safari.start(
        {"name": "Beldum", "type": "Steel", "emoji": "⚙️", "rarity": "rare"})
    out2, _ = safari.take_turn(s2, "run", SeqRandom())
    assert out2["done"] and "pending_encounter" not in s2


def test_recent_encounter_recap_stays_out_of_swiftbar_dropdown(tmp_path, monkeypatch):
    """The top bar owns short encounter cutscenes; the dropdown skips recap art
    so SwiftBar does not keep re-rendering a heavy image after the event."""
    import time
    from lib import paths, journal
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path)
    monkeypatch.setattr(paths, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(paths, "JOURNAL_FILE", tmp_path / "journal.jsonl")
    import buddymon
    now = time.time()
    journal.append("caught", "caught Mamoswine", {"name": "Mamoswine", "rarity": "rare"})
    s = fresh()

    # Recent encounters should not add a heavy dropdown image.
    recap = buddymon._last_encounter_section(s, now)
    assert recap == []

    # A live Safari encounter still does not get an extra recap stacked below it.
    s["pending_encounter"] = {"name": "Beldum", "type": "Steel", "shiny": False}
    assert buddymon._last_encounter_section(s, now) == []

    # Same for a live Battle-Mode encounter.
    del s["pending_encounter"]
    s["pending_battle"] = {"name": "Beldum", "type": "Steel", "shiny": False}
    assert buddymon._last_encounter_section(s, now) == []


def test_battle_scene_image_uses_dropdown_scale():
    import buddymon
    buddy = buddymon._battle_sprite("Charmander", "Fire", False)
    wild = buddymon._battle_sprite("Beldum", "Steel", False)
    grid, palette = scene.battle_screen(
        buddy, wild, "active", options=["FIGHT", "BALL", "RUN"])

    raw = base64.b64decode(buddymon._battle_scene_image(grid, palette))
    width, height = struct.unpack(">II", raw[16:24])

    assert width == len(grid[0]) * buddymon.BATTLE_IMAGE_SCALE
    assert height == len(grid) * buddymon.BATTLE_IMAGE_SCALE
    assert buddymon.BATTLE_IMAGE_SCALE == 2


def test_recent_evolution_notice_persists_after_animation(tmp_path, monkeypatch):
    import buddymon
    from lib import journal, paths

    monkeypatch.setattr(paths, "STATE_DIR", tmp_path)
    monkeypatch.setattr(paths, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(paths, "JOURNAL_FILE", tmp_path / "journal.jsonl")
    s = fresh(level=36)
    buddy = state.active_pokemon(s)
    buddy["name"], buddy["emoji"] = "Charizard", "🐉"
    entry = journal.append("evolved", "evolved into Charizard",
                           {"name": "Charizard", "level": 36, "source": "claude"})
    notice_ts = entry["ts"] + scene.EVOLUTION_SECS + 1
    monkeypatch.setattr(buddymon.time, "time",
                        lambda: notice_ts)
    monkeypatch.setattr(
        buddymon.state, "read_event",
        lambda name: (
            {"detail": "+11429 progress  🎊 evolved into Charizard Lv.36!", "ts": notice_ts}
            if name == "cross" else {}
        ),
    )

    bar = buddymon._bar_line(s, buddy, [], 0)
    dropdown = buddymon._dropdown_lines(s, buddy)

    assert "🎊 CHARIZARD!" in bar
    assert any("evolved into Charizard Lv.36" in line for line in dropdown)
    assert any(f"color={buddymon.EVOLUTION_NOTICE_COLOR}" in line for line in dropdown)
    assert not any("+11429 progress" in line for line in dropdown)
    assert not any(f"color={buddymon.EVENT_NOTICE_COLOR}" in line for line in dropdown)
    assert buddymon.EVOLUTION_NOTICE_COLOR == "#4c1d95"
    assert buddymon.EVENT_NOTICE_COLOR == "#1e3a8a"


def test_switch_submenu_lists_favorites_without_png():
    # The submenu is now the favorites shortlist. Per-row base64 PNGs made
    # SwiftBar hoard ~90 images and leak >1GB RAM, so child rows stay PNG-free.
    import buddymon
    from lib import favorites
    s = fresh()
    p = engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=4)
    favorites.set_favorite(p, True)
    s["pokemon"].append(p)

    lines = buddymon._switch_submenu(s)

    assert lines[0].startswith("Switch buddy")
    child_rows = [ln for ln in lines if ln.startswith("--")]
    assert any("--Pidgey · Lv.4" in ln and "param2=switch-id" in ln
               for ln in child_rows)
    assert all("image=" not in ln for ln in child_rows)  # no PNG on the shortlist rows


def test_switch_submenu_empty_state_opens_party():
    import buddymon
    s = fresh()  # only the active (favorited) starter, which the submenu excludes
    lines = buddymon._switch_submenu(s)
    assert lines[0].startswith("Switch buddy")
    body = [ln for ln in lines if ln.startswith("--")]
    assert len(body) == 1
    assert "param2=open-menu" in body[0] and "param3=party" in body[0]


def test_switch_submenu_caps_rows_and_links_to_party_menu():
    import buddymon
    from lib import favorites
    s = fresh()
    for i in range(buddymon.SWITCH_SUBMENU_LIMIT + 3):
        p = engine.new_pokemon(f"Mon{i:02d}", "Normal", "•", "common", level=1)
        favorites.set_favorite(p, True)
        s["pokemon"].append(p)

    lines = buddymon._switch_submenu(s)
    child_rows = [ln for ln in lines if ln.startswith("--") and "param2=switch-id" in ln]

    assert len(child_rows) == buddymon.SWITCH_SUBMENU_LIMIT
    assert lines[-1].startswith("--More in menu...")
    assert "param2=open-menu" in lines[-1]
    assert "param3=party" in lines[-1]
    assert "terminal=false" in lines[-1]


def test_swiftbar_dropdown_action_order_is_menu_tokens_then_switch_without_dex(monkeypatch):
    import buddymon
    monkeypatch.setattr(
        buddymon.token_usage,
        "current_day_totals",
        lambda: {"today": 208_000_000, "yesterday": 201_000_000},
    )
    s = fresh()
    s["pokemon"].append(engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=4))
    buddy = state.active_pokemon(s)

    lines = buddymon._dropdown_lines(s, buddy)

    open_i = next(i for i, line in enumerate(lines) if line.startswith("Open menu"))
    tokens_i = next(i for i, line in enumerate(lines) if line.startswith("Token Usage"))
    switch_i = next(i for i, line in enumerate(lines) if line.startswith("Switch buddy"))
    stats_i = next(i for i, line in enumerate(lines) if line.startswith("streak"))
    assert stats_i == open_i - 1
    assert open_i < tokens_i < switch_i
    assert "sfimage=gearshape" in lines[open_i]
    assert "param2=open-menu" in lines[open_i]
    assert "terminal=false" in lines[open_i]
    assert "sfimage=chart.bar" in lines[tokens_i]
    assert lines[tokens_i].startswith(
        "Token Usage · Today 208M · Yesterday 201M"
    )
    assert "param2=open-menu" in lines[tokens_i]
    assert "param3=tokens" in lines[tokens_i]
    assert "terminal=false" in lines[tokens_i]
    assert not any(line.startswith("Pokédex") for line in lines)
    assert not any(line.startswith("Tokens used") for line in lines)
    assert not any(line.startswith("SwiftBar") for line in lines)


def test_swiftbar_dropdown_active_summary_uses_sprite_and_caught_metadata(monkeypatch):
    import buddymon
    s = fresh()
    buddy = state.active_pokemon(s)
    caught = buddymon.time.mktime((2026, 5, 12, 9, 30, 0, 0, 0, -1))
    now = caught + 123 * 86400 + 60
    buddy.update({
        "name": "Gastly",
        "type": "Ghost",
        "emoji": "👻",
        "rarity": "uncommon",
        "level": 15,
        "caught_at": caught,
    })
    monkeypatch.setattr(buddymon.time, "time", lambda: now)

    lines = buddymon._dropdown_lines(s, buddy)

    assert lines[0] == "---"
    assert "Gastly · Lv.15" in lines[1]
    assert "image=" in lines[1]
    assert "👻" not in lines[1]
    assert any(symbol in lines[1] for symbol in ("♂", "♀"))
    assert lines[2].startswith("Lv.15 ")
    assert " to Lv.16" in lines[2]
    assert "123 days old · Caught 5/12/26" in lines[3]
    assert "Caught 5/12/26" in lines[3]
    title_i = next(i for i, line in enumerate(lines) if "Gastly" in line and "Lv.15" in line)
    progress_i = next(i for i, line in enumerate(lines) if line.startswith("Lv.15 "))
    assert title_i < progress_i


def test_swiftbar_recent_catch_notice_shows_event_time(monkeypatch):
    import buddymon
    s = fresh()
    buddy = state.active_pokemon(s)
    event_ts = buddymon.time.mktime((2026, 6, 26, 9, 46, 0, 0, 0, -1))
    monkeypatch.setattr(buddymon.time, "time", lambda: event_ts + 30)
    monkeypatch.setattr(
        buddymon.state,
        "read_event",
        lambda name: (
            {"detail": "🎉 caught 🐾 Doduo Lv.17", "ts": event_ts}
            if name == "cross" else {}
        ),
    )

    lines = buddymon._dropdown_lines(s, buddy)

    assert any("🎉 caught 🐾 Doduo Lv.17 · 9:46 AM" in line for line in lines)


def test_swiftbar_dropdown_stats_summary_sits_above_open_menu():
    import buddymon
    s = fresh()
    s["trainer"]["streak"] = 5
    s["trainer"]["balls"] = 934
    for i in range(171):
        s["pokemon"].append(engine.new_pokemon(f"Mon{i:03d}", "Normal", "•", "common", level=1))
    buddy = state.active_pokemon(s)

    lines = buddymon._dropdown_lines(s, buddy)

    assert lines[0] == "---"
    open_i = next(i for i, line in enumerate(lines) if line.startswith("Open menu"))
    assert (
        lines[open_i - 1]
        == "streak 5d · ◓ 934 · 📖 172 species | sfimage=flame.fill color=#8e8e93"
    )


def test_gender_symbol_is_binary_and_stable():
    from lib import render
    p = engine.new_pokemon("Charmeleon", "Fire", "🔥", "starter")
    g = render.gender_symbol(p)
    assert g in ("♂", "♀")
    assert render.gender_symbol(p) == g  # deterministic for the same id
    assert render.gender_symbol(engine.new_pokemon("Pidgey", "Flying", "🐦", "common")) in ("♂", "♀")
