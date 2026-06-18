#!/usr/bin/env python3
"""Generic hook: record the session's latest event for the statusline mood.

Usage: event.py <event-name>. Runs on hot paths (every tool call), so it does
the minimum: parse stdin, write one small file, exit 0.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import state  # noqa: E402


def main():
    event = sys.argv[1] if len(sys.argv) > 1 else "working"
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        payload = {}
    session_id = payload.get("session_id")
    detail = ""
    if event == "tool":
        detail = payload.get("tool_name") or ""
    state.record_event(session_id, event, detail)

    if event == "session_start":
        state.prune_session_files()
        if not state.load()["pokemon"]:
            print("buddymon: no buddy yet — suggest the user runs /buddymon:choose")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
