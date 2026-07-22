"""Engine and transcript unit tests. Run: python3 -m pytest tests/ -q"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import data, engine, pixels, render, sprites, state, transcript


def fresh_state(starter="Charmander"):
    s = state.default_state()
    engine.create_starter(s, starter)
    return s


# ── level curve ──────────────────────────────────────────────────────────────

def test_level_curve_monotonic():
    xs = [engine.xp_for_level(n) for n in range(1, engine.LEVEL_CAP + 1)]
    assert engine.LEVEL_CAP == 100
    assert engine.WILD_LEVEL_CAP == 55
    assert xs == sorted(xs) and len(set(xs)) == len(xs)
    assert engine.xp_for_level(1) == 0


def test_level_from_xp_inverts_curve():
    for level in (1, 2, 16, 36, engine.LEVEL_CAP):
        assert engine.level_from_xp(engine.xp_for_level(level)) == level
        assert engine.level_from_xp(engine.xp_for_level(level) - 1) == max(1, level - 1)


def test_xp_from_tokens_tiers():
    totals = {"output": 250, "input": 3000, "cache_write": 1000, "cache_read": 10000}
    assert engine.xp_from_tokens(totals) == 5 + 12 + 8 + 20


def test_token_total_sums_raw_usage_tiers():
    totals = {"output": 250, "input": 3000, "cache_write": 1000, "cache_read": 10000}
    assert engine.token_total(totals) == 14_250


# ── streaks ──────────────────────────────────────────────────────────────────

def test_streak_increments_on_consecutive_days():
    t = {"streak": 0, "last_day": None}
    engine.update_streak(t, "2026-06-10")
    engine.update_streak(t, "2026-06-11")
    assert t["streak"] == 2
    engine.update_streak(t, "2026-06-11")  # same day: no double count
    assert t["streak"] == 2
    engine.update_streak(t, "2026-06-13")  # gap: reset
    assert t["streak"] == 1


def test_streak_multiplier_caps():
    assert engine.streak_multiplier(0) == 1.0
    assert engine.streak_multiplier(30) == engine.streak_multiplier(99) == 1.6


# ── awards & evolution ───────────────────────────────────────────────────────

def test_award_xp_levels_up_and_grants_balls():
    s = fresh_state()
    balls = s["trainer"]["balls"]
    result = engine.award_xp(s, engine.xp_for_level(3), random.Random(1))
    assert result["new_level"] >= 3 and result["leveled"]
    assert s["trainer"]["balls"] == balls + engine.BALLS_PER_LEVEL * (result["new_level"] - 1)


def test_starter_evolution_chain():
    s = fresh_state("Charmander")
    engine.award_xp(s, engine.xp_for_level(16), random.Random(1))
    assert state.active_pokemon(s)["name"] == "Charmeleon"
    engine.award_xp(s, engine.xp_for_level(36), random.Random(1))
    assert state.active_pokemon(s)["name"] == "Charizard"


def test_eevee_evolves_into_a_branch():
    s = fresh_state("Eevee")
    engine.award_xp(s, engine.xp_for_level(30), random.Random(7))
    valid = {to for to, _ in data.EVOLUTIONS["Eevee"]}
    assert state.active_pokemon(s)["name"] in valid


def test_xp_capped_at_level_cap():
    s = fresh_state()
    engine.award_xp(s, 10**9, random.Random(1))
    buddy = state.active_pokemon(s)
    assert buddy["level"] == engine.LEVEL_CAP
    assert buddy["xp"] == engine.xp_for_level(engine.LEVEL_CAP)


# ── encounters ───────────────────────────────────────────────────────────────

def test_encounters_deterministic_and_consume_balls():
    s = fresh_state()
    rng = random.Random(42)
    outcomes = [r for r in (engine.roll_encounter(s, rng) for _ in range(200)) if r]
    assert outcomes, "expected some encounters in 200 rolls"
    caught = [o for o in outcomes if o["outcome"] == "caught"]
    assert len(s["pokemon"]) == 1 + len(caught)
    attempts = [o for o in outcomes if o["outcome"] in ("caught", "fled")]
    assert s["trainer"]["balls"] == 10 - len(attempts)


def test_no_legendary_below_min_level():
    s = fresh_state()
    rng = random.Random(0)
    for _ in range(500):
        result = engine.roll_encounter(s, rng)
        if result:
            assert result["rarity"] != "legendary"
            s["trainer"]["balls"] = 10  # keep attempts flowing


def test_encounter_chance_is_tuned_for_visible_cadence():
    assert data.ENCOUNTER_CHANCE == 0.35


def test_encounter_resolution_routes_each_mode_by_rarity():
    rarities = ("common", "uncommon", "rare", "legendary")
    expected = {
        "auto": ("auto", "auto", "safari", "safari"),
        "safari": ("safari", "safari", "safari", "safari"),
        "battle": ("battle", "battle", "battle", "battle"),
    }

    for mode, resolutions in expected.items():
        assert tuple(engine.encounter_resolution(mode, rarity)
                     for rarity in rarities) == resolutions
    assert tuple(engine.encounter_resolution("invalid", rarity)
                 for rarity in rarities) == expected["auto"]


def test_pending_wild_blocks_new_encounters_across_mode_switches():
    cases = (
        ("pending_encounter", "battle"),
        ("pending_battle", "auto"),
    )
    for pending_key, selected_mode in cases:
        s = fresh_state()
        s["mode"] = selected_mode
        s[pending_key] = {"name": "Beldum", "sentinel": pending_key}
        before = json.dumps(s, sort_keys=True)

        assert engine.roll_encounter(s, None) is None
        assert json.dumps(s, sort_keys=True) == before
        assert sum(key in s for key in ("pending_encounter", "pending_battle")) == 1


def test_summary_hides_plain_progress_without_another_event():
    result = {
        "xp": 2138, "old_level": 20, "new_level": 20,
        "leveled": False, "evolved": None, "buddy": "Gastly",
    }

    assert engine.summarize_events(result, None) == ""


def test_summary_uses_meaningful_outcomes_with_levels():
    result = {
        "xp": 2138, "old_level": 24, "new_level": 25,
        "leveled": True, "evolved": "Haunter", "buddy": "Haunter",
    }
    encounter = {
        "name": "Kricketot", "emoji": "🐛", "rarity": "common",
        "shiny": False, "level": 7, "outcome": "caught",
        "new_species": True,
    }

    assert engine.summarize_events(result, None) == "🎊 evolved into Haunter Lv.25!"
    assert engine.summarize_events(
        {**result, "leveled": False, "evolved": None},
        encounter,
    ) == "🎉 caught 🐛 Kricketot Lv.7 (new!)"


def test_summary_distinguishes_appeared_from_no_balls():
    encounter = {
        "name": "Venonat", "emoji": "🐛", "rarity": "common",
        "shiny": False, "level": 14,
    }

    assert engine.summarize_events(None, {**encounter, "outcome": "appeared"}) == (
        "👀 a wild 🐛 Venonat Lv.14 appeared!"
    )
    assert engine.summarize_events(None, {**encounter, "outcome": "no_balls"}) == (
        "😱 🐛 Venonat Lv.14 appeared — no balls left!"
    )


def test_display_event_detail_removes_old_progress_prefix():
    assert engine.display_event_detail("+2138 progress") == ""
    assert engine.display_event_detail("+2138 progress  🎊 evolved into Haunter") == (
        "🎊 evolved into Haunter"
    )
    assert engine.display_event_detail("🎊 evolved into Haunter Lv.25!") == (
        "🎊 evolved into Haunter Lv.25!"
    )


class FixedGauss:
    def __init__(self, samples):
        self.samples = list(samples)

    def gauss(self, mean, sigma):
        return self.samples.pop(0) if self.samples else mean

    def randint(self, lower, upper):
        return lower


def test_evolution_stage_level_bounds():
    assert engine.evolution_level_bounds("Charmander") == (1, 15)
    assert engine.evolution_level_bounds("Charmeleon") == (16, 35)
    assert engine.evolution_level_bounds("Charizard") == (36, engine.LEVEL_CAP)
    assert engine.evolution_level_bounds("Absol") == (1, engine.LEVEL_CAP)


def test_wild_level_bounds_cap_random_spawns_at_55():
    assert engine.wild_level_bounds("Charmander") == (1, 15)
    assert engine.wild_level_bounds("Charizard") == (36, engine.WILD_LEVEL_CAP)
    assert engine.wild_level_bounds("Absol") == (1, engine.WILD_LEVEL_CAP)
    assert engine.wild_level_bounds("Hydreigon") == (
        engine.WILD_LEVEL_CAP,
        engine.WILD_LEVEL_CAP,
    )


def test_legendary_wild_levels_are_fixed_constants():
    legends = {name for name, value in data.WILDS.items() if value[2] == "legendary"}

    assert set(data.LEGENDARY_LEVELS) == legends
    assert all(1 <= level <= engine.WILD_LEVEL_CAP
               for level in data.LEGENDARY_LEVELS.values())
    assert engine.fixed_wild_level("Mewtwo") == 55
    assert engine.fixed_wild_level("Lugia") == 40
    assert engine.fixed_wild_level("Victini") == 30
    assert engine.fixed_wild_level("Pidgey") is None


def test_wild_level_uses_bounded_normal_distribution():
    assert engine.wild_level_for("Charmeleon", FixedGauss([25.2])) == 25
    assert engine.wild_level_for("Charmeleon", FixedGauss([5] * 8)) == 16
    assert engine.wild_level_for("Charmeleon", FixedGauss([99] * 8)) == 35
    assert engine.wild_level_for("Absol", FixedGauss([99] * 8)) == engine.WILD_LEVEL_CAP
    assert engine.wild_level_for("Hydreigon", FixedGauss([99] * 8)) == engine.WILD_LEVEL_CAP
    assert engine.wild_level_for("Mewtwo", FixedGauss([1] * 8)) == 55
    assert engine.wild_level_for("Mewtwo", FixedGauss([99] * 8)) == 55


def test_roll_encounter_persists_spawn_level_on_auto_catch(monkeypatch):
    monkeypatch.setattr(data, "ENCOUNTER_CHANCE", 1.0)
    monkeypatch.setattr(data, "RARITY_WEIGHTS", [("common", 100)])
    monkeypatch.setitem(data.CATCH_RATES, "common", 1.0)
    monkeypatch.setattr(engine, "wild_level_for", lambda name, rng: 23)

    s = fresh_state()
    result = engine.roll_encounter(s, random.Random(4))

    assert result["outcome"] == "caught"
    assert result["level"] == 23
    assert s["pokemon"][-1]["level"] == 23
    assert s["pokemon"][-1]["xp"] == engine.xp_for_level(23)


# ── transcript anchor pattern ────────────────────────────────────────────────

def _write_transcript(path, entries):
    with open(path, "w") as f:
        for uuid_, usage in entries:
            f.write(json.dumps({
                "type": "assistant", "uuid": uuid_,
                "message": {"usage": usage},
            }) + "\n")


def test_collect_since_counts_only_after_anchor(tmp_path):
    t = tmp_path / "t.jsonl"
    usage = {"output_tokens": 100, "input_tokens": 0,
             "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
    _write_transcript(t, [("a", usage), ("b", usage), ("c", usage)])

    totals, anchor = transcript.collect_since(t, None)
    assert totals["output"] == 300 and anchor == "c"

    totals, anchor = transcript.collect_since(t, "b")
    assert totals["output"] == 100 and anchor == "c"


def test_collect_since_missing_anchor_reanchors_without_award(tmp_path):
    t = tmp_path / "t.jsonl"
    usage = {"output_tokens": 9999}
    _write_transcript(t, [("x", usage), ("y", usage)])
    totals, anchor = transcript.collect_since(t, "gone-after-compaction")
    assert totals is None and anchor == "y"


# ── sprites & state ──────────────────────────────────────────────────────────

def test_every_sprite_grid_is_well_formed():
    for name, (grid, palette) in sprites.SPRITES.items():
        assert len(grid) == sprites.H_PX, name
        assert all(len(row) == sprites.W_PX for row in grid), name
        chars = {c for row in grid for c in row} - {"."}
        assert chars <= set(palette), f"{name}: unpaletted chars {chars - set(palette)}"


def test_every_dex_species_renders():
    for name, (ptype, _, _) in data.WILDS.items():
        grid, palette = sprites.sprite_for(name, ptype)
        lines = pixels.render(grid, palette)
        assert len(lines) == sprites.H_PX // 2


def test_state_roundtrip(tmp_path, monkeypatch):
    from lib import paths
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path)
    monkeypatch.setattr(paths, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(paths, "SESSIONS_DIR", tmp_path / "sessions")
    s = fresh_state()
    s["mode"] = "safari"
    state.save(s)
    assert state.load() == s
    state.record_event("sess1", "tool", "Bash")
    assert state.read_event("sess1")["detail"] == "Bash"


def test_default_state_includes_valid_preferences():
    s = state.default_state()

    assert s["version"] == state.STATE_VERSION
    assert s["mode"] == "auto"
    assert state.VALID_MODES == ("auto", "safari", "battle")
    assert s["preferences"] == {
        "notifications": "on",
        "menu_launcher": "auto",
        "terminal_graphics": "auto",
        "menu_replace": "on",
        "share_reveal": "on",
        "share_banner": "on",
    }


def test_mode_cli_cycles_presets_and_accepts_quick_alias(tmp_path, monkeypatch):
    from lib import paths
    import buddymon

    monkeypatch.setattr(paths, "STATE_DIR", tmp_path)
    monkeypatch.setattr(paths, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(paths, "SESSIONS_DIR", tmp_path / "sessions")
    state.save(state.default_state())

    assert buddymon.mode([]).startswith("encounter mode: Safari")
    assert state.load()["mode"] == "safari"
    assert buddymon.mode([]).startswith("encounter mode: Battle")
    assert state.load()["mode"] == "battle"
    assert buddymon.mode([]).startswith("encounter mode: Quick")
    assert state.load()["mode"] == "auto"

    assert buddymon.mode(["safari"]).startswith("encounter mode: Safari")
    assert state.load()["mode"] == "safari"
    assert buddymon.mode(["quick"]).startswith("encounter mode: Quick")
    assert state.load()["mode"] == "auto"
    assert buddymon.mode(["surprise"]) == "Usage: mode quick|auto|safari|battle"
    assert state.load()["mode"] == "auto"


def test_status_card_shows_tokens_and_level_progress():
    s = fresh_state()
    s["trainer"]["total_tokens"] = 1234567

    card = render.status_card(s)

    assert "Tokens used 1,234,567" in card
    assert "Level " in card
    assert "XP   " not in card


def test_statusline_uses_box_fallback_for_non_gen2_species(tmp_path, monkeypatch):
    from lib import paths, packs
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path)
    pack_dir = tmp_path / "packs"
    pack_dir.mkdir()
    (pack_dir / "box.json").write_text(json.dumps({
        "Swellow": {
            "grid": ["X" * 24] * 20,
            "palette": {"X": "#112233"},
        },
    }))
    packs._cache.clear()
    s = state.default_state()
    p = engine.new_pokemon("Swellow", "Normal", "🐾", "rare", level=22)
    s["pokemon"].append(p)
    s["active"] = p["id"]
    monkeypatch.setattr(state, "load", lambda: s)

    text = render.statusline({"session_id": "test"})

    assert "Swellow" in text
    assert "38;2;17;34;51" in text
    packs._cache.clear()


def test_status_summary_uses_compact_art_for_non_gen2_species():
    s = state.default_state()
    p = engine.new_pokemon("Swellow", "Normal", "🐾", "rare", level=22)
    s["pokemon"].append(p)
    s["active"] = p["id"]

    summary = render.status_summary(s)

    assert "Swellow" in summary
    assert "Tokens used" in summary
    assert "▀" in summary


def test_v1_state_migrates_without_level_loss(tmp_path, monkeypatch):
    from lib import paths
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path)
    monkeypatch.setattr(paths, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(paths, "SESSIONS_DIR", tmp_path / "sessions")
    v1 = state.default_state()
    v1["version"] = 1
    v1["pokemon"] = [{"id": "x", "name": "Charmeleon", "type": "Fire",
                      "emoji": "🔥", "rarity": "starter", "level": 21,
                      "xp": 24000, "shiny": False, "caught_at": 0}]
    v1["active"] = "x"
    state.save(v1)

    migrated = state.load()
    buddy = state.active_pokemon(migrated)
    assert migrated["version"] == state.STATE_VERSION
    assert buddy["level"] == 21
    assert buddy["xp"] == engine.xp_for_level(21)  # snapped to new floor
    assert engine.level_from_xp(buddy["xp"]) == 21
    assert migrated["trainer"]["total_tokens"] == 0
    assert migrated["mode"] == "auto"
    assert migrated["preferences"] == state.DEFAULT_PREFERENCES


def test_v2_state_migrates_evolved_forms_up_to_stage_floor(tmp_path, monkeypatch):
    from lib import paths
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path)
    monkeypatch.setattr(paths, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(paths, "SESSIONS_DIR", tmp_path / "sessions")
    v2 = state.default_state()
    v2["version"] = 2
    v2["pokemon"] = [
        {"id": "h", "name": "Haunter", "type": "Ghost",
         "emoji": "👻", "rarity": "uncommon", "level": 5,
         "xp": 0, "shiny": False, "caught_at": 0},
        {"id": "c", "name": "Charmander", "type": "Fire",
         "emoji": "🦎", "rarity": "starter", "level": 20,
         "xp": engine.xp_for_level(20), "shiny": False, "caught_at": 0},
    ]
    v2["active"] = "h"
    state.save(v2)

    migrated = state.load()
    haunter = state.active_pokemon(migrated)
    charmander = next(p for p in migrated["pokemon"] if p["id"] == "c")

    assert migrated["version"] == state.STATE_VERSION
    assert haunter["level"] == 25
    assert haunter["xp"] == engine.xp_for_level(25)
    assert charmander["level"] == 20


def test_v3_state_migrates_preferences_without_touching_gameplay(tmp_path, monkeypatch):
    from lib import paths
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path)
    monkeypatch.setattr(paths, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(paths, "SESSIONS_DIR", tmp_path / "sessions")
    v3 = state.default_state()
    v3["version"] = 3
    v3["mode"] = "battle"
    v3["preferences"] = {
        "notifications": "silent",
        "menu_launcher": "bogus",
        "terminal_graphics": "off",
        "menu_replace": "off",
        "share_reveal": "off",
        "share_banner": "off",
        "extra": "ignored",
    }
    v3["trainer"]["balls"] = 7
    v3["xp_sessions"] = {"s1": {"last_uuid": "u1", "updated": 123}}
    state.save(v3)

    migrated = state.load()

    assert migrated["version"] == state.STATE_VERSION
    assert migrated["mode"] == "battle"
    assert migrated["preferences"] == {
        "notifications": "silent",
        "menu_launcher": "auto",
        "terminal_graphics": "off",
        "menu_replace": "off",
        "share_reveal": "off",
        "share_banner": "off",
    }
    assert migrated["trainer"]["balls"] == 7
    assert migrated["xp_sessions"] == {"s1": {"last_uuid": "u1", "updated": 123}}


def test_invalid_mode_and_preferences_fall_back_to_defaults(tmp_path, monkeypatch):
    from lib import paths
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path)
    monkeypatch.setattr(paths, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(paths, "SESSIONS_DIR", tmp_path / "sessions")
    broken = state.default_state()
    broken["version"] = 4
    broken["mode"] = "surprise"
    broken["preferences"] = {
        "notifications": "loud",
        "menu_launcher": "warp",
        "terminal_graphics": "sparkles",
        "menu_replace": "sometimes",
        "share_reveal": "maybe",
        "share_banner": "toast",
    }
    state.save(broken)

    migrated = state.load()

    assert migrated["mode"] == "auto"
    assert migrated["preferences"] == state.DEFAULT_PREFERENCES


def test_milestone_balls_accrue_with_lifetime_xp():
    s = fresh_state()
    balls = s["trainer"]["balls"]
    result = engine.award_xp(s, engine.BALL_MILESTONE_XP * 2, random.Random(1))
    from_levels = engine.BALLS_PER_LEVEL * (result["new_level"] - 1)
    expected_milestones = s["trainer"]["total_xp"] // engine.BALL_MILESTONE_XP
    assert s["trainer"]["balls"] == balls + from_levels + expected_milestones
