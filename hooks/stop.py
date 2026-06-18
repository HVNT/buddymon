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

from lib import engine, journal, notify, state, transcript  # noqa: E402


def main():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return
    session_id = payload.get("session_id") or "default"
    transcript_path = payload.get("transcript_path")

    detail = ""
    if transcript_path and Path(transcript_path).exists():
        with state.lock():
            s = state.load()
            if s["pokemon"]:
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
                    detail = engine.summarize_events(result, encounter)
                    for entry in journal.log_outcomes(result, encounter, "claude"):
                        if journal.is_rare(entry):
                            notify.notify("buddymon", entry["text"])
                state.save(s)

    state.record_event(session_id, "stop", detail)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
