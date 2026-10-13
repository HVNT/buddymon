"""Token accounting from Claude Code transcripts.

Anchor pattern (idea credited to pokemon-buddy-claude): remember the uuid of
the last assistant entry we counted per session; on each Stop, sum usage only
from entries after that anchor. If the anchor vanishes (compaction, resume),
skip the award and re-anchor at the tail so stale tokens are never back-filled.
"""
import json
import time
from pathlib import Path


def claim_usage(state, transcript_path, session_id, *, bootstrap=False):
    """Claim usage once for the app and Stop hook, under the caller's state lock.

    Keep the durable cursor alongside the other file collectors. The smaller
    legacy session cache is still updated for plugin compatibility, but pruning
    that cache must not make an already-counted transcript eligible again.
    """
    path = Path(transcript_path).resolve()
    mtime = path.stat().st_mtime
    anchors = state.setdefault("collectors", {})
    key = f"claude:{path}"
    previous = anchors.get(key)
    legacy = state.get("xp_sessions", {}).get(session_id, {})
    last_uuid = (previous if previous is not None else legacy).get("last_uuid") or None
    if bootstrap and last_uuid is None:
        totals, newest = None, _tail_uuid(path)
    else:
        totals, newest = collect_since(path, last_uuid)
    cursor = newest or last_uuid or ""
    anchors[key] = {"last_uuid": cursor, "mtime": mtime}
    state.setdefault("xp_sessions", {})[session_id] = {
        "last_uuid": cursor,
        "updated": time.time(),
    }
    return totals


def _usage(entry):
    usage = (entry.get("message") or {}).get("usage") or {}
    if not usage:
        return None
    return {
        "output": int(usage.get("output_tokens") or 0),
        "input": int(usage.get("input_tokens") or 0),
        "cache_write": int(usage.get("cache_creation_input_tokens") or 0),
        "cache_read": int(usage.get("cache_read_input_tokens") or 0),
    }


def collect_since(transcript_path, last_uuid):
    """Sum assistant token usage after last_uuid.

    Returns (totals, new_anchor_uuid). totals is None when the anchor was not
    found (caller should re-anchor without awarding).
    """
    totals = {"output": 0, "input": 0, "cache_write": 0, "cache_read": 0}
    anchor_seen = last_uuid is None
    newest = last_uuid
    counted = 0

    with open(transcript_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") != "assistant":
                continue
            entry_uuid = entry.get("uuid")
            if not anchor_seen:
                if entry_uuid == last_uuid:
                    anchor_seen = True
                continue
            usage = _usage(entry)
            if usage is None:
                continue
            for k in totals:
                totals[k] += usage[k]
            counted += 1
            if entry_uuid:
                newest = entry_uuid

    if not anchor_seen:
        return None, _tail_uuid(transcript_path)
    if counted == 0:
        return None, newest
    return totals, newest


def _tail_uuid(transcript_path):
    newest = None
    with open(transcript_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") == "assistant" and entry.get("uuid"):
                newest = entry["uuid"]
    return newest
