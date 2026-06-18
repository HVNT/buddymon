"""Append-only journey journal: the buddy's permanent story.

One JSON line per event in journal.jsonl. Writers already hold state.lock(),
so a single appended write per event is safe and atomic enough.
"""
import json
import time

from . import paths


def append(kind, text, data=None):
    paths.ensure_dirs()
    entry = {"ts": time.time(), "kind": kind, "text": text, **(data or {})}
    with open(paths.JOURNAL_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def tail(n=20):
    try:
        lines = paths.JOURNAL_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    entries = []
    for line in lines[-n:]:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def log_outcomes(result, encounter, source):
    """Translate award/encounter dicts (engine.summarize_events shapes) into
    journal entries. Returns the entries written."""
    written = []
    if result:
        if result.get("evolved"):
            written.append(append(
                "evolved", f"🎊 evolved into {result['evolved']}",
                {"name": result["evolved"], "level": result["new_level"], "source": source}))
        elif result.get("leveled"):
            written.append(append(
                "level", f"⬆️ {result['buddy']} reached Lv.{result['new_level']}",
                {"name": result["buddy"], "level": result["new_level"], "source": source}))
    if encounter:
        shiny = "✨" if encounter.get("shiny") else ""
        wild = f"{shiny}{encounter['emoji']} {encounter['name']}"
        data = {"name": encounter["name"], "rarity": encounter["rarity"],
                "shiny": bool(encounter.get("shiny")), "source": source}
        if encounter["outcome"] == "caught":
            tag = " (new species!)" if encounter.get("new_species") else ""
            written.append(append("caught", f"🎉 caught {wild}{tag}", data))
        elif encounter["outcome"] == "fled":
            written.append(append("fled", f"💨 {wild} fled", data))
        else:
            written.append(append("no_balls", f"😱 {wild} appeared — no balls left", data))
    return written


def latest(kinds, within_secs, now=None):
    """Newest entry of the given kinds younger than the window, else None."""
    now = now or time.time()
    for entry in reversed(tail(20)):
        if entry.get("kind") in kinds:
            return entry if now - entry.get("ts", 0) <= within_secs else None
    return None


def latest_encounter(within_secs, now=None):
    return latest(("caught", "fled", "no_balls"), within_secs, now)


def latest_evolution(within_secs, now=None):
    return latest(("evolved",), within_secs, now)


def is_rare(entry):
    """Worth interrupting the user for: evolutions, shinies, legendaries."""
    if entry["kind"] == "evolved":
        return True
    if entry.get("shiny"):
        return True
    return entry["kind"] in ("caught", "fled", "no_balls") and entry.get("rarity") == "legendary"
