"""Canonical menu-bar buddy presentations.

The Python core decides *what* the buddy is doing and renders the tiny pixel
frames. Native shells only schedule those frames on a status-bar button. This
keeps gameplay/event policy independent from AppKit while giving previews and
tests the exact same payload consumed by the shipping app.
"""

import base64
import json
import time

from . import data, journal, packs, paths, png, scene, sprites


SCHEMA_VERSION = 1
MOMENT_RETENTION_SECS = 120
WORKING_SECS = 3 * 60
RESTING_SECS = 30 * 60


STATE_CATALOG = (
    {"id": "booting", "group": "foundation", "label": "Booting", "coverage": "automated"},
    {"id": "needs_buddy", "group": "foundation", "label": "Needs buddy", "coverage": "automated"},
    {"id": "idle", "group": "foundation", "label": "Idle", "coverage": "automated"},
    {"id": "working", "group": "foundation", "label": "Working", "coverage": "automated"},
    {"id": "resting", "group": "foundation", "label": "Resting", "coverage": "automated"},
    {"id": "shiny_idle", "group": "foundation", "label": "Shiny idle", "coverage": "automated"},
    {"id": "unavailable", "group": "foundation", "label": "Unavailable", "coverage": "automated"},
    {"id": "xp_gain", "group": "progress", "label": "XP gained", "coverage": "automated"},
    {"id": "level_up", "group": "progress", "label": "Level up", "coverage": "automated"},
    {"id": "evolving", "group": "progress", "label": "Evolving", "coverage": "automated"},
    {"id": "encounter_alert", "group": "encounters", "label": "Encounter alert", "coverage": "automated"},
    {"id": "waiting_for_player", "group": "encounters", "label": "Waiting for player", "coverage": "automated"},
    {"id": "auto_battle", "group": "encounters", "label": "Auto battle", "coverage": "automated"},
    {"id": "catching", "group": "encounters", "label": "Catching", "coverage": "automated"},
    {"id": "result.caught", "group": "results", "label": "Caught", "coverage": "automated"},
    {"id": "result.shiny_caught", "group": "results", "label": "Shiny caught", "coverage": "automated"},
    {"id": "result.new_species", "group": "results", "label": "New species", "coverage": "automated"},
    {"id": "result.broke_free", "group": "results", "label": "Broke free", "coverage": "automated"},
    {"id": "result.fled", "group": "results", "label": "Fled", "coverage": "automated"},
    {"id": "result.no_balls", "group": "results", "label": "No balls", "coverage": "automated"},
    {"id": "result.wild_ko", "group": "results", "label": "Wild fainted", "coverage": "automated"},
    {"id": "result.buddy_fainted", "group": "results", "label": "Buddy fainted", "coverage": "automated"},
    {"id": "result.ran", "group": "results", "label": "Ran safely", "coverage": "automated"},
)

ENVIRONMENT_VARIANTS = (
    {"id": "light", "label": "Light menu bar"},
    {"id": "dark", "label": "Dark menu bar"},
    {"id": "selected", "label": "Dropdown open"},
    {"id": "reduce_motion", "label": "Reduce Motion"},
    {"id": "fallback_art", "label": "Built-in fallback art"},
)


_EGG = (
    [
        "................",
        "................",
        ".......WW.......",
        ".....WWWWWW.....",
        "....WWWWWWWW....",
        "...WWWWYYWWWW...",
        "...WWWYYYYWWW...",
        "..WWWWYYYYWWWW..",
        "..WWWWWWWWWWWW..",
        "...WWWWWWWWWW...",
        "...WWWWWWWWWW...",
        "....WWWWWWWW....",
        ".....WWWWWW.....",
        ".......WW.......",
        "................",
        "................",
    ],
    {"W": "#f4f1e8", "Y": "#78b8d8"},
)


def catalog_ids():
    return tuple(entry["id"] for entry in STATE_CATALOG)


def _pokemon(name, ptype, *, shiny=False, rarity="common", **extra):
    return {
        "name": name,
        "type": ptype,
        "shiny": shiny,
        "rarity": rarity,
        **extra,
    }


def _shiny_fixture(frame):
    grid, palette = frame
    shiny = dict(palette)
    if "B" in shiny:
        shiny["B"] = "#d8b94e"
    if "L" in shiny:
        shiny["L"] = "#fff0a8"
    if "D" in shiny:
        shiny["D"] = "#b46ee8"
    return grid, shiny


def _fixture_frames(pokemon):
    frame = sprites.sprite_for(pokemon["name"], pokemon.get("type", "Normal"))
    if pokemon.get("shiny"):
        frame = _shiny_fixture(frame)
    return [frame]


def _runtime_frames(pokemon):
    return packs.menu_bar_frames(
        pokemon["name"],
        pokemon.get("type", "Normal"),
        bool(pokemon.get("shiny")),
    )


def _canvas_frame(
    sprite_frame,
    *,
    width=20,
    y_offset=0,
    sparkles=False,
    alert=False,
    dust=False,
):
    grid, palette = sprite_frame
    canvas = scene.Canvas(width, 16)
    x = max(0, (width - len(grid[0])) // 2)
    y = 16 - len(grid) + y_offset
    canvas.sprite(grid, palette, x, y)
    if sparkles:
        canvas.sparkles(width // 2, 7)
    if alert:
        canvas.alert_mark(max(0, width - 4), 2)
    if dust:
        canvas.dust(max(0, width // 2 - 2), 12)
    return canvas.result()


def _duo_frame(buddy_frame, wild_frame, *, buddy_dx=0, wild_dx=0, impact=False):
    buddy_grid, buddy_palette = buddy_frame
    wild_grid, wild_palette = wild_frame
    canvas = scene.Canvas(44, 16)
    canvas.sprite(
        scene.mirror(buddy_grid),
        buddy_palette,
        max(0, buddy_dx),
        16 - len(buddy_grid),
    )
    wild_x = max(22, 44 - len(wild_grid) + wild_dx)
    canvas.sprite(wild_grid, wild_palette, wild_x, 16 - len(wild_grid))
    if impact:
        canvas.dust(max(24, wild_x - 3), 9)
    return canvas.result()


def _encoded_frame(
    frame,
    *,
    duration_ms=500,
    title="",
    accessibility_label,
):
    grid, palette = frame
    blob = png.grid_to_png(grid, palette, 4, dpi=180)
    return {
        "duration_ms": duration_ms,
        "title": title,
        "accessibility_label": accessibility_label,
        "image_base64": base64.b64encode(blob).decode(),
        "pixel_width": len(grid[0]) * 4,
        "pixel_height": len(grid) * 4,
    }


def _sequence(
    state_id,
    frames,
    *,
    sequence_id=None,
    started_at=0,
    loop=False,
    reduce_motion_frame=0,
):
    catalog = next(entry for entry in STATE_CATALOG if entry["id"] == state_id)
    return {
        "state_id": state_id,
        "sequence_id": sequence_id or state_id,
        "label": catalog["label"],
        "group": catalog["group"],
        "coverage": catalog["coverage"],
        "started_at": started_at,
        "loop": loop,
        "reduce_motion_frame": min(max(0, reduce_motion_frame), len(frames) - 1),
        "duration_ms": sum(frame["duration_ms"] for frame in frames),
        "frames": frames,
    }


def _single_sequence(
    state_id,
    pokemon,
    provider,
    *,
    sequence_id=None,
    started_at=0,
    loop=False,
    title="",
    effect=None,
):
    source = provider(pokemon)
    frames = []
    count = max(2, len(source)) if loop else 1
    for index in range(count):
        sprite_frame = source[index % len(source)]
        kwargs = {}
        y_offset = 0
        if effect == "bob":
            y_offset = -1 if index % 2 else 0
        elif effect == "sparkle":
            kwargs["sparkles"] = True
        elif effect == "alert":
            kwargs["alert"] = True
        elif effect == "rest":
            y_offset = 1
        frames.append(_encoded_frame(
            _canvas_frame(sprite_frame, y_offset=y_offset, **kwargs),
            duration_ms=650 if loop else 900,
            title=title,
            accessibility_label=f"{pokemon['name']} — {state_id.replace('_', ' ')}",
        ))
    return _sequence(
        state_id,
        frames,
        sequence_id=sequence_id,
        started_at=started_at,
        loop=loop,
    )


def _evolution_sequence(old, new, provider, *, sequence_id=None, started_at=0):
    old_frames = provider(old)
    new_frames = provider(new)
    frames = []
    for phase in range(scene.EVOLUTION_SECS):
        title = (
            "?!" if phase in scene.EVO_SHOCK else
            "EVOLVE" if phase in scene.EVO_FLASH else
            "…" if phase in scene.EVO_MORPH else
            f"{new['name']}!" if phase in scene.EVO_REVEAL else
            "✨"
        )
        frames.append(_encoded_frame(
            scene.evolution_bar(
                old_frames[phase % len(old_frames)],
                new_frames[phase % len(new_frames)],
                phase,
            ),
            duration_ms=260,
            title=title,
            accessibility_label=f"{old['name']} is evolving into {new['name']}",
        ))
    return _sequence(
        "evolving",
        frames,
        sequence_id=sequence_id,
        started_at=started_at,
        reduce_motion_frame=scene.EVO_REVEAL.start,
    )


def _auto_battle_sequence(buddy, wild, provider, *, sequence_id=None, started_at=0):
    buddy_frame = provider(buddy)[0]
    wild_frame = provider(wild)[0]
    raw = [
        (_duo_frame(buddy_frame, wild_frame), "VS", "facing a wild Pokemon"),
        (_duo_frame(buddy_frame, wild_frame, buddy_dx=4, impact=True), "!", "buddy attacks"),
        (_duo_frame(buddy_frame, wild_frame, wild_dx=2), "…", "wild Pokemon recoils"),
        (_duo_frame(buddy_frame, wild_frame), "", "battle settles"),
    ]
    frames = [
        _encoded_frame(
            frame,
            duration_ms=420,
            title=title,
            accessibility_label=f"{buddy['name']} {label} {wild['name']}",
        )
        for frame, title, label in raw
    ]
    return _sequence(
        "auto_battle",
        frames,
        sequence_id=sequence_id,
        started_at=started_at,
        reduce_motion_frame=0,
    )


def _catching_sequence(
    buddy,
    wild,
    provider,
    *,
    caught=True,
    sequence_id=None,
    started_at=0,
):
    buddy_frame = provider(buddy)[0]
    wild_frame = provider(wild)[0]
    last_throw = {"caught": caught, "jiggles": 3, "ts": started_at}
    frames = []
    for phase in range(scene.THROW_SECS):
        frames.append(_encoded_frame(
            scene.throw_jiggle_bar(buddy_frame, wild_frame, phase, last_throw),
            duration_ms=520,
            title="",
            accessibility_label=f"Trying to catch {wild['name']}",
        ))
    return _sequence(
        "catching",
        frames,
        sequence_id=sequence_id,
        started_at=started_at,
        reduce_motion_frame=scene.THROW_SECS - 1,
    )


def _result_sequence(
    state_id,
    buddy,
    wild,
    provider,
    *,
    sequence_id=None,
    started_at=0,
):
    buddy_frame = provider(buddy)[0]
    wild_frame = provider(wild)[0]
    title = {
        "result.caught": "Caught!",
        "result.shiny_caught": "Shiny!",
        "result.new_species": "New!",
        "result.broke_free": "Broke free",
        "result.fled": "Fled",
        "result.no_balls": "No Balls",
        "result.wild_ko": "KO",
        "result.buddy_fainted": "Fainted",
        "result.ran": "Safe",
    }[state_id]

    caught_states = {"result.caught", "result.shiny_caught", "result.new_species"}
    if state_id in caught_states:
        raw = _canvas_frame(buddy_frame, width=20, sparkles=True)
    elif state_id == "result.broke_free":
        raw = scene.throw_jiggle_bar(
            buddy_frame,
            wild_frame,
            scene.THROW_SECS - 1,
            {"caught": False, "jiggles": 2, "ts": started_at},
        )
    elif state_id in {"result.fled", "result.no_balls"}:
        outcome = "fled" if state_id == "result.fled" else "no_balls"
        raw = scene.battle_bar(
            buddy_frame,
            wild_frame,
            scene.PHASE_RESULT.start,
            outcome,
        )
    elif state_id == "result.wild_ko":
        raw = _duo_frame(buddy_frame, wild_frame, wild_dx=3, impact=True)
    elif state_id == "result.buddy_fainted":
        raw = _canvas_frame(buddy_frame, y_offset=2, dust=True)
    else:
        raw = _canvas_frame(buddy_frame)

    if state_id == "result.shiny_caught":
        accessibility_label = f"{buddy['name']} caught shiny {wild['name']}"
    elif state_id == "result.new_species":
        accessibility_label = f"{buddy['name']} caught new species {wild['name']}"
    elif state_id == "result.caught":
        accessibility_label = f"{buddy['name']} caught {wild['name']}"
    else:
        accessibility_label = f"{title}: {wild['name']}"

    frames = [_encoded_frame(
        raw,
        duration_ms=1_400,
        title=title,
        accessibility_label=accessibility_label,
    )]
    return _sequence(
        state_id,
        frames,
        sequence_id=sequence_id,
        started_at=started_at,
    )


def _catalog_sequence(
    state_id,
    provider=_fixture_frames,
    *,
    buddy=None,
    evolved=None,
    wild=None,
):
    buddy = buddy or _pokemon("Charmander", "Fire", rarity="starter")
    evolved = evolved or _pokemon("Charmeleon", "Fire", rarity="starter")
    wild = wild or _pokemon("Eevee", "Normal")
    shiny_wild = {**wild, "shiny": True}

    if state_id == "booting":
        return _sequence(state_id, [_encoded_frame(
            _EGG,
            duration_ms=700,
            title="…",
            accessibility_label="BuddyMon is starting",
        )], loop=True)
    if state_id == "needs_buddy":
        return _sequence(state_id, [_encoded_frame(
            _EGG,
            duration_ms=1_200,
            accessibility_label="Choose a BuddyMon starter",
        )])
    if state_id == "unavailable":
        unavailable = (_EGG[0], {"W": "#8c8c92", "Y": "#55555c"})
        return _sequence(state_id, [_encoded_frame(
            unavailable,
            duration_ms=1_200,
            title="?",
            accessibility_label="BuddyMon status unavailable",
        )])
    if state_id == "idle":
        return _single_sequence(state_id, buddy, provider, loop=True)
    if state_id == "working":
        return _single_sequence(state_id, buddy, provider, loop=True, effect="bob")
    if state_id == "resting":
        return _single_sequence(state_id, buddy, provider, loop=True, title="z", effect="rest")
    if state_id == "shiny_idle":
        shiny_buddy = {**buddy, "shiny": True}
        return _single_sequence(state_id, shiny_buddy, provider, loop=True, title="✨", effect="sparkle")
    if state_id == "xp_gain":
        return _single_sequence(state_id, buddy, provider, title="+XP", effect="sparkle")
    if state_id == "level_up":
        sequence = _single_sequence(state_id, buddy, provider, loop=True, title="Lvl!", effect="bob")
        sequence["loop"] = False
        return sequence
    if state_id == "evolving":
        return _evolution_sequence(buddy, evolved, provider)
    if state_id == "encounter_alert":
        return _single_sequence(state_id, buddy, provider, effect="alert")
    if state_id == "waiting_for_player":
        return _single_sequence(state_id, buddy, provider, effect="alert")
    if state_id == "auto_battle":
        return _auto_battle_sequence(buddy, wild, provider)
    if state_id == "catching":
        return _catching_sequence(buddy, wild, provider)
    if state_id == "result.shiny_caught":
        wild = shiny_wild
    return _result_sequence(state_id, buddy, wild, provider)


def preview_sequence(
    state_id,
    *,
    buddy_name="Charmander",
    evolved_name=None,
    wild_name="Eevee",
    buddy_shiny=False,
    wild_shiny=False,
):
    """Render one catalog state through the production local-art path.

    This is the shared boundary for developer demos. It is deliberately pure:
    previewing a state never mutates a trainer's real BuddyMon state.
    """
    if state_id not in catalog_ids():
        expected = ", ".join(catalog_ids())
        raise ValueError(f"Unknown menu-bar state {state_id!r}. Expected: {expected}")

    buddy_type, _ = data.species_info(buddy_name)
    if evolved_name is None:
        targets = data.EVOLUTIONS.get(buddy_name, [])
        evolved_name = targets[0][0] if targets else buddy_name
    evolved_type, _ = data.species_info(evolved_name)
    wild_type, _ = data.species_info(wild_name)
    wild_info = data.WILDS.get(wild_name)
    wild_rarity = wild_info[2] if wild_info else "common"

    sequence = _catalog_sequence(
        state_id,
        provider=_runtime_frames,
        buddy=_pokemon(
            buddy_name,
            buddy_type,
            shiny=buddy_shiny,
            rarity="starter",
        ),
        evolved=_pokemon(
            evolved_name,
            evolved_type,
            shiny=buddy_shiny,
            rarity="starter",
        ),
        wild=_pokemon(
            wild_name,
            wild_type,
            shiny=wild_shiny,
            rarity=wild_rarity,
        ),
    )
    sequence["sequence_id"] = f"preview:{state_id}:{buddy_name}:{wild_name}"
    return sequence


def harness_payload():
    """State inventory using the same local-first art path as production.

    With no optional pack installed this is deterministic built-in fallback art;
    when a local pack exists the harness deliberately previews the art that the
    shipping menu-bar buddy will use on that Mac.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "menu_bar_harness",
        "catalog": [dict(entry) for entry in STATE_CATALOG],
        "environment_variants": [dict(entry) for entry in ENVIRONMENT_VARIANTS],
        "sequences": [
            _catalog_sequence(state_id, provider=_runtime_frames)
            for state_id in catalog_ids()
        ],
    }


def harness_json(indent=None):
    return json.dumps(harness_payload(), indent=indent, sort_keys=True)


def _active_pokemon(s):
    active_id = s.get("active")
    return next((pokemon for pokemon in s.get("pokemon", []) if pokemon.get("id") == active_id), None)


def _latest_activity(now):
    newest = None
    try:
        files = paths.SESSIONS_DIR.glob("*.json")
    except OSError:
        return None
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            timestamp = float(payload.get("ts") or path.stat().st_mtime)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
        if timestamp <= now and (newest is None or timestamp > newest["ts"]):
            newest = {"ts": timestamp, "detail": payload.get("detail", "")}
    return newest


def _pokemon_type(name, fallback="Normal"):
    if name in data.WILDS:
        return data.WILDS[name][0]
    root = name
    while root in data.PRE_EVOLUTION:
        root = data.PRE_EVOLUTION[root]
    return data.STARTERS.get(root, {}).get("type", fallback)


def _baseline_sequence(active, activity, now):
    if active.get("shiny"):
        state_id = "shiny_idle"
        return _single_sequence(
            state_id,
            active,
            _runtime_frames,
            sequence_id=f"baseline:{state_id}:{active.get('id') or active['name']}",
            loop=True,
            title="✨",
            effect="sparkle",
        )
    age = now - activity["ts"] if activity else float("inf")
    if age <= WORKING_SECS:
        state_id, title, effect = "working", "", "bob"
    elif age >= RESTING_SECS:
        state_id, title, effect = "resting", "z", "rest"
    else:
        state_id, title, effect = "idle", "", None
    return _single_sequence(
        state_id,
        active,
        _runtime_frames,
        sequence_id=f"baseline:{state_id}:{active.get('id') or active['name']}",
        loop=True,
        title=title,
        effect=effect,
    )


def _journal_moment(entry, active):
    state_id = entry.get("kind")
    timestamp = float(entry.get("ts") or 0)
    sequence_id = f"journal:{state_id}:{timestamp:.6f}:{entry.get('name', '')}"

    if state_id == "level":
        pokemon = {
            **active,
            "name": entry.get("name") or active["name"],
        }
        return _single_sequence(
            "level_up",
            pokemon,
            _runtime_frames,
            sequence_id=sequence_id,
            started_at=timestamp,
            loop=True,
            title="Lvl!",
            effect="bob",
        ) | {"loop": False}

    if state_id == "evolved":
        new_name = entry.get("name") or active["name"]
        old_name = data.PRE_EVOLUTION.get(new_name, active["name"])
        ptype = _pokemon_type(new_name, active.get("type", "Normal"))
        old = _pokemon(old_name, ptype, shiny=bool(entry.get("shiny")))
        new = _pokemon(new_name, ptype, shiny=bool(entry.get("shiny")))
        return _evolution_sequence(
            old,
            new,
            _runtime_frames,
            sequence_id=sequence_id,
            started_at=timestamp,
        )

    wild = _pokemon(
        entry.get("name", "Pokemon"),
        _pokemon_type(entry.get("name", "")),
        shiny=bool(entry.get("shiny")),
        rarity=entry.get("rarity", "common"),
    )
    if state_id == "caught":
        is_new_species = bool(entry.get("new_species")) or (
            "new species" in str(entry.get("text") or "").lower()
        )
        result_id = (
            "result.shiny_caught" if wild["shiny"] else
            "result.new_species" if is_new_species else
            "result.caught"
        )
    elif state_id == "no_balls":
        result_id = "result.no_balls"
    else:
        text = str(entry.get("text") or "").lower()
        if "your buddy fainted" in text:
            result_id = "result.buddy_fainted"
        elif "fainted" in text:
            result_id = "result.wild_ko"
        else:
            result_id = "result.fled"

    battle = _auto_battle_sequence(
        active,
        wild,
        _runtime_frames,
        sequence_id=sequence_id + ":battle",
        started_at=timestamp,
    )
    result = _result_sequence(
        result_id,
        active,
        wild,
        _runtime_frames,
        sequence_id=sequence_id,
        started_at=timestamp,
    )
    if result_id in {"result.caught", "result.shiny_caught", "result.new_species"}:
        catching = _catching_sequence(active, wild, _runtime_frames, started_at=timestamp)
        result["frames"] = battle["frames"] + catching["frames"] + result["frames"]
    else:
        result["frames"] = battle["frames"] + result["frames"]
    result["duration_ms"] = sum(frame["duration_ms"] for frame in result["frames"])
    result["reduce_motion_frame"] = len(result["frames"]) - 1
    return result


def runtime_payload(s, now=None):
    """Return baseline, queued moments, and persistent attention for native UI."""
    now = time.time() if now is None else now
    active = _active_pokemon(s)
    if active is None:
        baseline = _catalog_sequence("needs_buddy")
        baseline["sequence_id"] = "baseline:needs_buddy"
        return {
            "schema_version": SCHEMA_VERSION,
            "baseline": baseline,
            "moments": [],
            "persistent": None,
        }

    activity = _latest_activity(now)
    recent_entries = [
        entry
        for entry in journal.tail(30)
        if entry.get("kind") in {"level", "evolved", "caught", "fled", "no_balls"}
        and 0 <= now - float(entry.get("ts") or 0) <= MOMENT_RETENTION_SECS
    ][-5:]
    moments = [_journal_moment(entry, active) for entry in recent_entries]

    pending_battle = s.get("pending_battle")
    if pending_battle and pending_battle.get("last_throw"):
        last_throw = pending_battle["last_throw"]
        throw_timestamp = float(last_throw.get("ts") or 0)
        if 0 <= now - throw_timestamp <= MOMENT_RETENTION_SECS:
            wild = _pokemon(
                pending_battle.get("name", "Pokemon"),
                pending_battle.get("type", "Normal"),
                shiny=bool(pending_battle.get("shiny")),
                rarity=pending_battle.get("rarity", "common"),
            )
            throw_id = (
                f"throw:{throw_timestamp:.6f}:{pending_battle.get('name', 'wild')}"
            )
            catching = _catching_sequence(
                active,
                wild,
                _runtime_frames,
                caught=bool(last_throw.get("caught")),
                sequence_id=throw_id,
                started_at=throw_timestamp,
            )
            if not last_throw.get("caught"):
                broke_free = _result_sequence(
                    "result.broke_free",
                    active,
                    wild,
                    _runtime_frames,
                    started_at=throw_timestamp,
                )
                catching["frames"] += broke_free["frames"]
                catching["duration_ms"] = sum(
                    frame["duration_ms"] for frame in catching["frames"]
                )
                catching["reduce_motion_frame"] = len(catching["frames"]) - 1
            moments.append(catching)

    if activity and 0 <= now - activity["ts"] <= MOMENT_RETENTION_SECS:
        overlaps_journal = any(
            abs(float(entry.get("ts") or 0) - activity["ts"]) <= 2
            for entry in recent_entries
        )
        if not overlaps_journal:
            moments.append(_single_sequence(
                "xp_gain",
                active,
                _runtime_frames,
                sequence_id=f"activity:{activity['ts']:.6f}",
                started_at=activity["ts"],
                title="+XP",
                effect="sparkle",
            ))

    moments.sort(key=lambda item: item["started_at"])

    pending = pending_battle or s.get("pending_encounter")
    persistent = None
    if pending:
        created = float(pending.get("created_ts") or 0)
        persistent = _single_sequence(
            "waiting_for_player",
            active,
            _runtime_frames,
            sequence_id=f"pending:{created:.6f}:{pending.get('name', 'wild')}",
            started_at=created,
            effect="alert",
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "baseline": _baseline_sequence(active, activity, now),
        "moments": moments,
        "persistent": persistent,
    }
