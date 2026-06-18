#!/usr/bin/env python3
"""Stop hook: convert the turn's token usage into XP, maybe roll an encounter.

Announcements (level ups, evolutions, catches) go into the session event file
so the statusline shows them — nothing is printed into the conversation.
"""
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import engine, state, transcript  # noqa: E402


def announce(result, encounter):
    parts = []
    if result:
        if result["evolved"]:
            parts.append(f"🎊 evolved into {result['evolved']}!")
        elif result["leveled"]:
            parts.append(f"⬆️ Lv.{result['new_level']}!")
        else:
            parts.append(f"+{result['xp']} XP")
    if encounter:
        shiny = "✨" if encounter["shiny"] else ""
        wild = f"{shiny}{encounter['emoji']} {encounter['name']}"
        if encounter["outcome"] == "caught":
            tag = " (new!)" if encounter.get("new_species") else ""
            parts.append(f"🎉 caught {wild}{tag}")
        elif encounter["outcome"] == "fled":
            parts.append(f"💨 {wild} fled")
        else:
            parts.append(f"😱 {wild} appeared — no balls left!")
    return "  ".join(parts)


def main():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return
    session_id = payload.get("session_id") or "default"
    transcript_path = payload.get("transcript_path")

    s = state.load()
    if not s["pokemon"]:
        return

    detail = ""
    if transcript_path and Path(transcript_path).exists():
        sessions = s.setdefault("xp_sessions", {})
        sess = sessions.setdefault(session_id, {})
        totals, anchor = transcript.collect_since(transcript_path, sess.get("last_uuid"))
        if anchor:
            sess["last_uuid"] = anchor
        sess["updated"] = time.time()
        state.prune_sessions(s)

        if totals:
            rng = random.Random()
            result = engine.award_xp(s, engine.xp_from_tokens(totals), rng)
            encounter = engine.roll_encounter(s, rng) if result else None
            detail = announce(result, encounter)
        state.save(s)

    state.record_event(session_id, "stop", detail)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
