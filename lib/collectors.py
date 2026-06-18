"""Cross-client XP collectors: read other agent CLIs' local token logs.

Parsing approach ported from Hunter's agent-platform token-usage workflow
(workflows/token-usage/scripts/report_token_usage.py), reduced to what XP
needs. Incremental anchors live in state["collectors"] so tokens are never
counted twice; the first-ever run bootstraps anchors without awarding, so
weeks of history don't dump into one level-up.

  codex   ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl  (append-only,
          cumulative totals in event_msg/token_count records)
  augment ~/.augment/sessions/*.json  (rewritten in place; per-node
          token_usage with timestamp_ms)
"""
import json
import time
from pathlib import Path

from . import engine

CODEX_ROOT = Path.home() / ".codex" / "sessions"
AUGMENT_ROOT = Path.home() / ".augment" / "sessions"
RECENT_WINDOW_DAYS = 14  # ignore files older than this


def _zero():
    return {"output": 0, "input": 0, "cache_write": 0, "cache_read": 0}


def _add(target, delta):
    for k in target:
        target[k] += max(0, delta.get(k, 0))


def _recent(path, anchors, key):
    """File worth scanning? Newer than its anchor and not ancient."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    if mtime < time.time() - RECENT_WINDOW_DAYS * 86400:
        return None
    anchor = anchors.get(key)
    if anchor and mtime <= anchor.get("mtime", 0):
        return None
    return mtime


def _codex_cum(record):
    """Cumulative usage from a codex token_count record, or None."""
    if record.get("type") != "event_msg":
        return None
    payload = record.get("payload") or {}
    if payload.get("type") != "token_count":
        return None
    usage = (payload.get("info") or {}).get("total_token_usage")
    return usage if isinstance(usage, dict) else None


def _codex_tiers(cum):
    cached = int(cum.get("cached_input_tokens") or 0)
    return {
        "output": int(cum.get("output_tokens") or 0),
        "input": max(0, int(cum.get("input_tokens") or 0) - cached),
        "cache_write": 0,
        "cache_read": cached,
    }


def _dir_unchanged(root, anchors, marker, glob):
    """True (skip scan) when nothing under root is newer than last time.
    One cheap pass over mtimes vs. opening every file. Updates the marker."""
    newest = 0.0
    for p in root.glob(glob):
        try:
            newest = max(newest, p.stat().st_mtime)
        except OSError:
            pass
    if newest <= anchors.get(marker, 0.0):
        return True
    anchors[marker] = newest
    return False


def collect_codex(anchors, award, totals):
    if _dir_unchanged(CODEX_ROOT, anchors, "_codex_seen", "*/*/*/rollout-*.jsonl"):
        return
    for path in sorted(CODEX_ROOT.glob("*/*/*/rollout-*.jsonl")):
        key = f"codex:{path}"
        mtime = _recent(path, anchors, key)
        if mtime is None:
            continue
        anchor = anchors.get(key, {})
        offset = anchor.get("offset", 0)
        last_cum = anchor.get("cum")
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(offset)
                for line in f:
                    line = line.strip()
                    if not line or "token_count" not in line:
                        continue
                    try:
                        cum = _codex_cum(json.loads(line))
                    except json.JSONDecodeError:
                        continue
                    if cum:
                        last_cum = _codex_tiers(cum)
                offset = f.tell()
        except OSError:
            continue
        prev = anchor.get("cum")
        if award and last_cum:
            _add(totals, {k: last_cum[k] - (prev or _zero())[k] for k in last_cum})
        anchors[key] = {"offset": offset, "cum": last_cum, "mtime": mtime}


def _augment_nodes(node):
    """Yield (timestamp_ms, tier_totals) for every token_usage node."""
    if isinstance(node, dict):
        usage, ts = node.get("token_usage"), node.get("timestamp_ms")
        if isinstance(usage, dict) and isinstance(ts, int):
            yield ts, {
                "output": int(usage.get("output_tokens") or 0),
                "input": int(usage.get("input_tokens") or 0),
                "cache_write": int(usage.get("cache_creation_input_tokens") or 0),
                "cache_read": int(usage.get("cache_read_input_tokens") or 0),
            }
        for value in node.values():
            yield from _augment_nodes(value)
    elif isinstance(node, list):
        for item in node:
            yield from _augment_nodes(item)


def collect_augment(anchors, award, totals):
    if _dir_unchanged(AUGMENT_ROOT, anchors, "_augment_seen", "*.json"):
        return
    for path in sorted(AUGMENT_ROOT.glob("*.json")):
        key = f"augment:{path}"
        mtime = _recent(path, anchors, key)
        if mtime is None:
            continue
        last_ts = anchors.get(key, {}).get("last_ts", 0)
        try:
            payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError):
            continue
        newest = last_ts
        for ts, tiers in _augment_nodes(payload):
            if ts > last_ts:
                if award:
                    _add(totals, tiers)
                newest = max(newest, ts)
        anchors[key] = {"last_ts": newest, "mtime": mtime}


def prune_anchors(anchors):
    """Drop anchors that can never be scanned again: deleted files, or files
    aged past the recency window. Keeps state.json from growing forever."""
    cutoff = time.time() - RECENT_WINDOW_DAYS * 86400
    for key in [k for k in anchors if ":" in k]:
        try:
            if Path(key.split(":", 1)[1]).stat().st_mtime >= cutoff:
                continue
        except OSError:
            pass
        del anchors[key]


def collect(state, rng):
    """Scan all clients; award XP + maybe an encounter. Returns summary dict."""
    anchors = state.setdefault("collectors", {})
    bootstrapped = anchors.get("_bootstrapped", False)
    totals = _zero()
    collect_codex(anchors, bootstrapped, totals)
    collect_augment(anchors, bootstrapped, totals)
    prune_anchors(anchors)
    anchors["_bootstrapped"] = True

    xp = engine.xp_from_tokens(totals)
    result = engine.award_xp(state, xp, rng) if xp > 0 else None
    encounter = engine.roll_encounter(state, rng) if result else None
    return {"bootstrapped_now": not bootstrapped, "tokens": totals,
            "result": result, "encounter": encounter}
