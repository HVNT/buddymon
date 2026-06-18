#!/usr/bin/env python3
"""Statusline entry point. Reads Claude Code's status JSON on stdin, prints art.

Never raises: a broken statusline must degrade to a quiet one-liner.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import render  # noqa: E402


def main():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        payload = {}
    try:
        print(render.statusline(payload))
    except Exception:
        print("🥚 buddymon hiccup")


if __name__ == "__main__":
    main()
