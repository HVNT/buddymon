"""Read-only local token usage report for the terminal UI.

This intentionally parses only local client usage logs and returns display
lines. It does not update BuddyMon state or award progress.
"""
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from . import paths


LOCAL_TZ = ZoneInfo("America/Los_Angeles")
CODEX_ROOT = Path.home() / ".codex" / "sessions"
CLAUDE_ROOT = Path.home() / ".claude" / "projects"
AUGMENT_ROOT = Path.home() / ".augment" / "sessions"
GEMINI_ROOT = Path.home() / ".gemini" / "tmp"
CLIENTS = ("Claude", "Codex", "Auggie", "Gemini", "Other")
CACHE_VERSION = 3
TIMELINE_LABEL_W = 16
NUM_W = 8


@dataclass(frozen=True)
class TokenEvent:
    client: str
    when: datetime
    tokens: int


def _usage_total(usage):
    if not isinstance(usage, dict):
        return 0
    if "totalTokenCount" in usage:
        return max(0, int(usage.get("totalTokenCount") or 0))
    return sum(max(0, int(usage.get(key) or 0)) for key in (
        "input_tokens",
        "output_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
        "cached_input_tokens",
        "promptTokenCount",
        "candidatesTokenCount",
    ))


def _event_from_usage(client, when, usage):
    tokens = _usage_total(usage)
    if when is None or not tokens:
        return None
    return TokenEvent(client, when, tokens)


def _parse_time(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, LOCAL_TZ)
    if not isinstance(value, str):
        return None
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).astimezone(LOCAL_TZ)
    except ValueError:
        return None


def _codex_usage(record):
    if record.get("type") != "event_msg":
        return None
    payload = record.get("payload") or {}
    if payload.get("type") != "token_count":
        return None
    info = payload.get("info") or {}
    usage = info.get("total_token_usage")
    return usage if isinstance(usage, dict) else None


def _codex_file_events(path):
    previous = None
    try:
        rows = path.open("r", encoding="utf-8", errors="replace")
    except OSError:
        return
    with rows:
        for line in rows:
            if "token_count" not in line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            usage = _codex_usage(record)
            when = _parse_time(record.get("timestamp"))
            if not usage or when is None:
                continue
            total = _usage_total(usage)
            tokens = max(0, total - (previous or 0))
            previous = total
            if tokens:
                yield TokenEvent("Codex", when, tokens)


def _codex_events():
    for path in sorted(CODEX_ROOT.glob("*/*/*/rollout-*.jsonl")):
        yield from _codex_file_events(path)


def _claude_file_events(path):
    try:
        rows = path.open("r", encoding="utf-8", errors="replace")
    except OSError:
        return
    with rows:
        for line in rows:
            if "usage" not in line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            message = record.get("message") if isinstance(record.get("message"), dict) else {}
            usage = message.get("usage") or record.get("usage")
            when = _parse_time(record.get("timestamp"))
            event = _event_from_usage("Claude", when, usage)
            if event is not None:
                yield event


def _claude_events():
    for path in sorted(CLAUDE_ROOT.glob("*/*.jsonl")):
        yield from _claude_file_events(path)


def _augment_nodes(node):
    if isinstance(node, dict):
        usage, ts = node.get("token_usage"), node.get("timestamp_ms")
        if isinstance(usage, dict) and isinstance(ts, int):
            when = datetime.fromtimestamp(ts / 1000, LOCAL_TZ)
            event = _event_from_usage("Auggie", when, usage)
            if event is not None:
                yield event
        for value in node.values():
            yield from _augment_nodes(value)
    elif isinstance(node, list):
        for item in node:
            yield from _augment_nodes(item)


def _augment_file_events(path):
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return
    yield from _augment_nodes(payload)


def _augment_events():
    for path in sorted(AUGMENT_ROOT.glob("*.json")):
        yield from _augment_file_events(path)


def _gemini_nodes(node, fallback_when=None):
    if isinstance(node, dict):
        usage = node.get("usageMetadata") or node.get("usage") or node.get("tokenUsage")
        when = _parse_time(node.get("timestamp") or node.get("createdAt")) or fallback_when
        event = _event_from_usage("Gemini", when, usage)
        if event is not None:
            yield event
        for value in node.values():
            yield from _gemini_nodes(value, when)
    elif isinstance(node, list):
        for item in node:
            yield from _gemini_nodes(item, fallback_when)


def _gemini_file_events(path):
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return
    yield from _gemini_nodes(payload)


def _gemini_events():
    # Avoid account/auth files; Gemini's local chat snapshots, when present, are
    # under tmp/*/chats/.
    for path in sorted(GEMINI_ROOT.glob("*/chats/*.json")):
        yield from _gemini_file_events(path)


def collect_events():
    events = []
    for source in (_claude_events, _codex_events, _augment_events, _gemini_events):
        events.extend(source())
    return events


def _cache_file():
    return paths.STATE_DIR / "token-usage-cache.json"


def _load_cache():
    try:
        cache = json.loads(_cache_file().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": CACHE_VERSION, "files": {}}
    if not isinstance(cache, dict) or cache.get("version") != CACHE_VERSION:
        return {"version": CACHE_VERSION, "files": {}}
    if not isinstance(cache.get("files"), dict):
        cache["files"] = {}
    return cache


def _save_cache(cache):
    path = _cache_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _source_files():
    specs = (
        ("claude", CLAUDE_ROOT.glob("*/*.jsonl"), _claude_file_events),
        ("codex", CODEX_ROOT.glob("*/*/*/rollout-*.jsonl"), _codex_file_events),
        ("augment", AUGMENT_ROOT.glob("*.json"), _augment_file_events),
        ("gemini", GEMINI_ROOT.glob("*/chats/*.json"), _gemini_file_events),
    )
    for kind, files, parser in specs:
        for path in sorted(files):
            yield kind, path, parser


def _empty_day_counts():
    return {client: 0 for client in CLIENTS}


def _events_to_days(events):
    days = defaultdict(_empty_day_counts)
    for event in events:
        client = event.client if event.client in CLIENTS else "Other"
        days[event.when.date().isoformat()][client] += event.tokens
    return {day: dict(vals) for day, vals in days.items()}


def _merge_day_counts(dest, src, start, end):
    for day, vals in src.items():
        try:
            day_dt = datetime.fromisoformat(day).replace(tzinfo=LOCAL_TZ)
        except ValueError:
            continue
        if not (start <= day_dt < end):
            continue
        out = dest[day]
        for client in CLIENTS:
            out[client] += int(vals.get(client) or 0)


def cached_daily_counts(start, end):
    cache = _load_cache()
    cached_files = cache["files"]
    current = set()
    changed = False
    rows = defaultdict(_empty_day_counts)

    for kind, path, parser in _source_files():
        try:
            stat = path.stat()
        except OSError:
            continue
        key = f"{kind}:{path}"
        current.add(key)
        entry = cached_files.get(key)
        if (
            isinstance(entry, dict)
            and entry.get("mtime_ns") == stat.st_mtime_ns
            and entry.get("size") == stat.st_size
            and isinstance(entry.get("days"), dict)
        ):
            days = entry["days"]
        else:
            days = _events_to_days(parser(path))
            cached_files[key] = {
                "kind": kind,
                "path": str(path),
                "mtime_ns": stat.st_mtime_ns,
                "size": stat.st_size,
                "days": days,
            }
            changed = True
        _merge_day_counts(rows, days, start, end)

    stale = set(cached_files) - current
    if stale:
        for key in stale:
            del cached_files[key]
        changed = True
    if changed:
        _save_cache(cache)
    return rows


def _day_start(dt):
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def _month_start(dt):
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _previous_month_start(dt):
    start = _month_start(dt)
    if start.month == 1:
        return start.replace(year=start.year - 1, month=12)
    return start.replace(month=start.month - 1)


def _fmt_dt(dt):
    return dt.strftime("%b %-d %H:%M")


def _fmt_short_day(dt):
    return dt.strftime("%b%-d")


def _fmt_n(n):
    return f"{int(n):,}"


def _fmt_compact(n):
    n = max(0, int(n))
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    units = (
        (1_000_000, "M"),
        (1_000, "K"),
    )
    for factor, suffix in units:
        value = n // factor
        if value >= 10:
            return f"{value}{suffix}"
    return _fmt_n(n)


def _sum(events, start, end):
    return sum(e.tokens for e in events if start <= e.when < end)


def _sum_days(rows, start, end):
    total = 0
    for day, vals in rows.items():
        try:
            day_dt = datetime.fromisoformat(day).replace(tzinfo=LOCAL_TZ)
        except ValueError:
            continue
        if start <= day_dt < end:
            total += sum(int(vals.get(client) or 0) for client in CLIENTS)
    return total


def _counts_days(rows, start, end):
    counts = _empty_day_counts()
    for day, vals in rows.items():
        try:
            day_dt = datetime.fromisoformat(day).replace(tzinfo=LOCAL_TZ)
        except ValueError:
            continue
        if start <= day_dt < end:
            for client in CLIENTS:
                counts[client] += int(vals.get(client) or 0)
    return counts


def _total_tokens(vals):
    return sum(vals.get(client, 0) for client in CLIENTS)


def _money_markers(total):
    billions = int(total) // 1_000_000_000
    hundred_millions = (int(total) % 1_000_000_000) // 100_000_000
    return ("🤑" * billions) + ("💰" * hundred_millions)


def _markers(total, weekly=False):
    marks = []
    money = _money_markers(total)
    if money:
        marks.append(money)
    if weekly:
        marks.append("✨")
    return f" {''.join(marks)}" if marks else ""


def _summary_markers(label, total):
    if label not in {"Today", "Yesterday", "This week"}:
        return ""
    markers = _money_markers(total)
    return f" {markers}" if markers else ""


def _summary_row(label, tokens):
    return f"{label:<14}{_fmt_compact(tokens):>8}{_summary_markers(label, tokens)}"


def _timeline_row(label, vals, weekly=False):
    total = _total_tokens(vals)
    return (
        f"{label:<{TIMELINE_LABEL_W}}{_fmt_compact(total):>{NUM_W}}"
        f"{_fmt_compact(vals['Claude']):>{NUM_W}}"
        f"{_fmt_compact(vals['Codex']):>{NUM_W}}{_fmt_compact(vals['Auggie']):>{NUM_W}}"
        f"{_fmt_compact(vals['Gemini']):>{NUM_W}}{_fmt_compact(vals['Other']):>{NUM_W}}"
        f"{_markers(total, weekly)}"
    )


def _timeline_rule():
    return "-" * (TIMELINE_LABEL_W + NUM_W * 6)


def _week_label(start, last_day, today):
    if last_day.date() == today.date():
        end = "now"
    elif start.month == last_day.month and start.year == last_day.year:
        end = str(last_day.day)
    else:
        end = _fmt_short_day(last_day)
    return f"WEEK {_fmt_short_day(start)}-{end}"


def _daily(events, start, end):
    days = defaultdict(lambda: {client: 0 for client in CLIENTS})
    for event in events:
        if not (start <= event.when < end):
            continue
        key = event.when.date().isoformat()
        client = event.client if event.client in CLIENTS else "Other"
        days[key][client] += event.tokens
    return days


def _coerce_now(now=None):
    now = now or datetime.now(LOCAL_TZ)
    if now.tzinfo is None:
        return now.replace(tzinfo=LOCAL_TZ)
    return now.astimezone(LOCAL_TZ)


def compact_tokens(n):
    return _fmt_compact(n)


def current_day_totals(now=None):
    now = _coerce_now(now)
    today = _day_start(now)
    yesterday = today - timedelta(days=1)
    rows = cached_daily_counts(yesterday, now)
    return {
        "today": _sum_days(rows, today, now),
        "yesterday": _sum_days(rows, yesterday, today),
    }


def report_lines(now=None):
    now = _coerce_now(now)

    today = _day_start(now)
    yesterday = today - timedelta(days=1)
    week = today - timedelta(days=today.weekday())
    month = _month_start(now)
    last_month = _previous_month_start(now)

    timeline_start = _day_start(last_month)
    rows = cached_daily_counts(timeline_start, now)
    today_tokens = _sum_days(rows, today, now)
    yesterday_tokens = _sum_days(rows, yesterday, today)
    week_tokens = _sum_days(rows, week, now)
    month_tokens = _sum_days(rows, month, now)
    last_month_tokens = _sum_days(rows, last_month, month)

    lines = [
        f"{'Token Usage':<16}{now.strftime('%Y-%m-%d %H:%M %Z')}",
        "",
        f"{'Range':<14}{'Tokens':>8}",
        _summary_row("Today", today_tokens),
        _summary_row("Yesterday", yesterday_tokens),
        _summary_row("This week", week_tokens),
        _summary_row("This month", month_tokens),
        _summary_row("Last month", last_month_tokens),
        "",
        "Daily Timeline",
        f"{'Date':<{TIMELINE_LABEL_W}}{'Total':>{NUM_W}}"
        f"{'Claude':>{NUM_W}}{'Codex':>{NUM_W}}{'Auggie':>{NUM_W}}"
        f"{'Gemini':>{NUM_W}}{'Other':>{NUM_W}}",
    ]

    day = _day_start(now)
    while day >= timeline_start:
        key = day.date().isoformat()
        vals = rows.get(key, _empty_day_counts())
        total = _total_tokens(vals)
        if total or day >= last_month:
            lines.append(_timeline_row(key, vals))
        week_start = day - timedelta(days=day.weekday())
        visible_week_start = max(week_start, timeline_start)
        if day == visible_week_start:
            visible_last_day = min(week_start + timedelta(days=6), today)
            week_end = min(week_start + timedelta(days=7), now)
            weekly = _counts_days(rows, visible_week_start, week_end)
            lines.append(_timeline_row(
                _week_label(visible_week_start, visible_last_day, today),
                weekly,
                weekly=True,
            ))
            if day > timeline_start:
                lines.append(_timeline_rule())
        day -= timedelta(days=1)

    if not any(sum(vals.get(client, 0) for client in CLIENTS) for vals in rows.values()):
        lines += ["", "No local token usage records found."]
    return lines
