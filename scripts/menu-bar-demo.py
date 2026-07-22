#!/usr/bin/env python3
"""Run one menu-bar state or a complete developer user story."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib import menu_bar_demo  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(menu_bar_demo.main())
