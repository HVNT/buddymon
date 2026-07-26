"""Token usage report parsing and date bucketing."""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import paths, token_usage


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def ms(year, month, day, hour=0):
    dt = datetime(year, month, day, hour, tzinfo=token_usage.LOCAL_TZ)
    return int(dt.timestamp() * 1000)


def line_starting(lines, prefix):
    return next(line for line in lines if line.startswith(prefix))


def test_compact_token_format_uses_four_digit_suffix_windows():
    cases = {
        0: "0",
        999: "999",
        1_000: "1,000",
        9_999: "9,999",
        10_000: "10K",
        9_999_999: "9999K",
        10_000_000: "10M",
        999_999_999: "999M",
        1_000_000_000: "1.00B",
        1_694_444_444: "1.69B",
        15_384_420_554: "15.38B",
    }
    for value, expected in cases.items():
        assert token_usage._fmt_compact(value) == expected


def test_money_markers_use_hundred_millions_wrapped_by_billions():
    assert token_usage._money_markers(99_999_999) == ""
    assert token_usage._money_markers(100_000_000) == "💰"
    assert token_usage._money_markers(999_999_999) == "💰" * 9
    assert token_usage._money_markers(1_000_000_000) == "💰" * 10
    assert token_usage._money_markers(1_200_000_000) == ("💰" * 10) + "\n💰💰"
    assert token_usage._money_markers(2_900_000_000) == (
        ("💰" * 10) + "\n" + ("💰" * 10) + "\n" + ("💰" * 9)
    )


def test_summary_row_marks_only_daily_and_weekly_ranges():
    assert token_usage._summary_row("This month", 999_999_999).endswith("999M")
    assert token_usage._summary_row("Today", 100_000_000).split()[-1] == "💰"
    yesterday_prefix = "Yesterday        1.20B "
    assert token_usage._summary_row("Yesterday", 1_200_000_000).splitlines()[-2:] == [
        yesterday_prefix + ("💰" * 10),
        (" " * len(yesterday_prefix)) + "💰💰",
    ]
    this_week_prefix = "This week        2.00B "
    assert token_usage._summary_row("This week", 2_000_000_000).splitlines()[-2:] == [
        this_week_prefix + ("💰" * 10),
        (" " * len(this_week_prefix)) + ("💰" * 10),
    ]
    assert token_usage._summary_row("This month", 1_000_000_000).split()[-1] == "1.00B"
    assert token_usage._summary_row("Last month", 4_300_000_000).split()[-1] == "4.30B"


def test_timeline_marker_wrap_keeps_marker_column_indent():
    vals = {client: 0 for client in token_usage.CLIENTS}
    vals["Claude"] = 1_200_000_000

    first, second = token_usage._timeline_row("2026-06-22", vals).splitlines()
    marker_col = first.index("💰")

    assert first.endswith(" " + ("💰" * 10))
    assert second == (" " * marker_col) + "💰💰"


def test_client_mix_lines_show_nonzero_sources_by_share():
    vals = {client: 0 for client in token_usage.CLIENTS}
    vals["Claude"] = 75
    vals["Codex"] = 25

    assert token_usage._client_mix_lines("This month by client", vals) == [
        "This month by client",
        "Tool          Tokens  Share           Pct",
        "Claude Code       75  ###########...  75%",
        "Codex CLI         25  ####..........  25%",
    ]


def test_current_day_totals_returns_today_and_yesterday(tmp_path, monkeypatch):
    codex = tmp_path / "codex"
    claude = tmp_path / "claude"
    augment = tmp_path / "augment"
    gemini = tmp_path / "gemini"
    monkeypatch.setattr(token_usage, "CODEX_ROOT", codex)
    monkeypatch.setattr(token_usage, "CLAUDE_ROOT", claude)
    monkeypatch.setattr(token_usage, "AUGMENT_ROOT", augment)
    monkeypatch.setattr(token_usage, "GEMINI_ROOT", gemini)
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path / "state")

    write_jsonl(claude / "proj" / "session.jsonl", [
        {
            "timestamp": "2026-06-22T10:00:00-07:00",
            "message": {"usage": {"input_tokens": 100, "output_tokens": 25}},
        },
        {
            "timestamp": "2026-06-21T10:00:00-07:00",
            "message": {"usage": {"input_tokens": 50, "output_tokens": 5}},
        },
    ])
    write_jsonl(codex / "2026" / "06" / "22" / "rollout-test.jsonl", [
        {
            "timestamp": "2026-06-22T11:00:00-07:00",
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "total_token_usage": {
                        "input_tokens": 200,
                        "output_tokens": 50,
                    },
                },
            },
        },
    ])

    now = datetime(2026, 6, 22, 12, tzinfo=token_usage.LOCAL_TZ)

    assert token_usage.current_day_totals(now) == {
        "today": 375,
        "yesterday": 55,
    }


def test_comparison_trend_handles_zero_baselines_without_fake_percentages():
    assert token_usage._comparison_trend(500, 0, "vs yesterday") == {
        "direction": "up",
        "change_percent": None,
        "value": "New",
        "detail": "vs yesterday",
    }
    assert token_usage._comparison_trend(0, 0, "vs last week") == {
        "direction": "flat",
        "change_percent": 0,
        "value": "0%",
        "detail": "vs last week",
    }


def test_dashboard_builds_daily_mix_trend_and_insights(monkeypatch):
    rows = {
        "2026-06-10": {"Claude": 200},
        "2026-06-12": {"Codex": 300},
        "2026-06-15": {"Codex": 250},
        "2026-06-16": {"Claude": 100},
        "2026-06-17": {"Codex": 200},
        "2026-06-19": {"Claude": 300},
        "2026-06-21": {"Codex": 400},
        "2026-06-22": {"Codex": 500},
    }
    monkeypatch.setattr(
        token_usage,
        "cached_daily_counts",
        lambda _start, _end: rows,
    )

    now = datetime(2026, 6, 22, 12, tzinfo=token_usage.LOCAL_TZ)
    dashboard = token_usage.dashboard(now)

    assert dashboard["range"] == {
        "days": 7,
        "label": "Last 7 days",
        "start": "2026-06-16",
        "end": "2026-06-22",
    }
    assert [day["date"] for day in dashboard["daily"]] == [
        "2026-06-16",
        "2026-06-17",
        "2026-06-18",
        "2026-06-19",
        "2026-06-20",
        "2026-06-21",
        "2026-06-22",
    ]
    assert dashboard["today"]["tokens"] == 500
    assert dashboard["headline"] == [
        {
            "id": "day",
            "label": "Today",
            "tokens": 500,
            "compact": "500",
            "comparison_label": "Yesterday",
            "comparison_tokens": 400,
            "comparison_compact": "400",
            "change": "+25%",
            "tone": "up",
        },
        {
            "id": "week",
            "label": "This week",
            "tokens": 500,
            "compact": "500",
            "comparison_label": "Last week thru Mon",
            "comparison_tokens": 250,
            "comparison_compact": "250",
            "change": "+100%",
            "tone": "up",
        },
    ]
    assert dashboard["total"] == {"tokens": 1500, "compact": "1,500"}
    assert dashboard["comparison"][1]["tokens"] == 750
    assert dashboard["trend"] == {
        "direction": "up",
        "change_percent": 100,
        "value": "+100%",
        "detail": "vs prior 7 days",
    }
    assert dashboard["clients"][:2] == [
        {
            "id": "codex",
            "label": "Codex CLI",
            "tokens": 1100,
            "compact": "1,100",
            "percent": 73,
        },
        {
            "id": "claude-code",
            "label": "Claude Code",
            "tokens": 400,
            "compact": "400",
            "percent": 27,
        },
    ]
    assert dashboard["insights"] == [
        {
            "id": "peak",
            "label": "Busiest day",
            "value": "Today",
            "detail": "500 tokens",
        },
        {
            "id": "average",
            "label": "Daily average",
            "value": "214",
            "detail": "across 7 days",
        },
        {
            "id": "active_days",
            "label": "Active days",
            "value": "5/7",
            "detail": "days with local usage",
        },
        {
            "id": "top_client",
            "label": "Top tool",
            "value": "Codex CLI",
            "detail": "73% of usage",
        },
        {
            "id": "active_streak",
            "label": "Active streak",
            "value": "2 days",
            "detail": "consecutive days with local AI use",
        },
        {
            "id": "tool_range",
            "label": "Tool range",
            "value": "2/4",
            "detail": "supported tools used this week",
        },
    ]
    assert dashboard["supported_tools"] == [
        {"id": "claude-code", "label": "Claude Code"},
        {"id": "codex", "label": "Codex CLI"},
        {"id": "auggie", "label": "Auggie"},
        {"id": "gemini-cli", "label": "Gemini CLI"},
    ]
    assert dashboard["tool_rhythm"]["tools"] == [
        {"id": "claude-code", "label": "Claude Code", "values": [100, 0, 0, 300, 0, 0, 0]},
        {"id": "codex", "label": "Codex CLI", "values": [0, 200, 0, 0, 0, 400, 500]},
    ]
    assert len(dashboard["history"]) == 28
    assert len(dashboard["weekly"]) == 4


def test_dashboard_fetches_previous_week_for_short_history(monkeypatch):
    requested = {}

    def daily_counts(start, end):
        requested["start"] = start
        requested["end"] = end
        return {
            "2026-06-15": {"Codex": 100},
            "2026-06-22": {"Codex": 200},
        }

    monkeypatch.setattr(token_usage, "cached_daily_counts", daily_counts)

    now = datetime(2026, 6, 22, 12, tzinfo=token_usage.LOCAL_TZ)
    dashboard = token_usage.dashboard(now, days=2, history_days=2)

    assert requested["start"] == datetime(
        2026,
        6,
        15,
        tzinfo=token_usage.LOCAL_TZ,
    )
    assert requested["end"] == now
    assert dashboard["headline"][1]["tokens"] == 200
    assert dashboard["headline"][1]["comparison_tokens"] == 100
    assert dashboard["headline"][1]["comparison_label"] == "Last week thru Mon"


def test_dashboard_week_comparison_uses_the_same_elapsed_weekdays(monkeypatch):
    rows = {
        "2026-06-29": {"Codex": 50},
        "2026-06-30": {"Codex": 100},
        "2026-07-01": {"Codex": 150},
        "2026-07-02": {"Codex": 10_000},
        "2026-07-03": {"Codex": 20_000},
        "2026-07-06": {"Codex": 100},
        "2026-07-07": {"Codex": 200},
        "2026-07-08": {"Codex": 300},
    }
    monkeypatch.setattr(
        token_usage,
        "cached_daily_counts",
        lambda _start, _end: rows,
    )

    dashboard = token_usage.dashboard(
        datetime(2026, 7, 8, 12, tzinfo=token_usage.LOCAL_TZ)
    )
    week = dashboard["headline"][1]

    assert week["tokens"] == 600
    assert week["comparison_tokens"] == 300
    assert week["comparison_label"] == "Last week thru Wed"
    assert week["change"] == "+100%"


def test_dashboard_sunday_compares_the_two_complete_weeks(monkeypatch):
    rows = {
        **{
            f"2026-06-{day:02d}": {"Codex": 100}
            for day in range(22, 29)
        },
        **{
            f"2026-06-{day:02d}": {"Codex": 200}
            for day in range(29, 31)
        },
        **{
            f"2026-07-{day:02d}": {"Codex": 200}
            for day in range(1, 6)
        },
    }
    monkeypatch.setattr(
        token_usage,
        "cached_daily_counts",
        lambda _start, _end: rows,
    )

    dashboard = token_usage.dashboard(
        datetime(2026, 7, 5, 20, tzinfo=token_usage.LOCAL_TZ)
    )
    week = dashboard["headline"][1]

    assert week["tokens"] == 1400
    assert week["comparison_tokens"] == 700
    assert week["comparison_label"] == "Last week"
    assert week["change"] == "+100%"


def test_token_report_groups_by_local_calendar_ranges(tmp_path, monkeypatch):
    codex = tmp_path / "codex"
    claude = tmp_path / "claude"
    augment = tmp_path / "augment"
    gemini = tmp_path / "gemini"
    monkeypatch.setattr(token_usage, "CODEX_ROOT", codex)
    monkeypatch.setattr(token_usage, "CLAUDE_ROOT", claude)
    monkeypatch.setattr(token_usage, "AUGMENT_ROOT", augment)
    monkeypatch.setattr(token_usage, "GEMINI_ROOT", gemini)
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path / "state")

    write_jsonl(claude / "proj" / "today.jsonl", [
        {
            "timestamp": "2026-06-22T10:00:00-07:00",
            "message": {"usage": {"input_tokens": 500, "output_tokens": 75}},
        },
        {
            "timestamp": "2026-06-21T10:00:00-07:00",
            "message": {"usage": {"input_tokens": 500, "output_tokens": 75}},
        },
    ])
    write_jsonl(codex / "2026" / "06" / "22" / "rollout-test.jsonl", [
        {
            "timestamp": "2026-06-22T09:00:00-07:00",
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {"total_token_usage": {"input_tokens": 1000, "output_tokens": 150}},
            },
        },
        {
            "timestamp": "2026-06-22T11:00:00-07:00",
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {"total_token_usage": {"input_tokens": 1500, "output_tokens": 225}},
            },
        },
    ])
    write_json(augment / "session.json", {
        "items": [
            {
                "timestamp_ms": ms(2026, 6, 1, 9),
                "token_usage": {"input_tokens": 500, "output_tokens": 75},
            }
        ]
    })
    write_json(gemini / "tmp-a" / "chats" / "chat.json", {
        "timestamp": "2026-05-31T18:00:00-07:00",
        "usageMetadata": {
            "promptTokenCount": 500_000_000,
            "candidatesTokenCount": 500_000_000,
            "totalTokenCount": 1_000_000_000,
        },
    })

    now = datetime(2026, 6, 22, 12, tzinfo=token_usage.LOCAL_TZ)
    lines = token_usage.report_lines(now)

    assert lines[:4] == [
        "Token Usage · 2026-06-22 12:00 PDT",
        "💰 = 100M tokens · ✨ = weekly total",
        "",
        "Summary",
    ]
    assert line_starting(lines, "Range").split() == ["Range", "Tokens"]
    assert line_starting(lines, "Today").split() == [
        "Today", "2,300",
    ]
    assert line_starting(lines, "Yesterday").split() == [
        "Yesterday", "575",
    ]
    assert line_starting(lines, "This week").split() == [
        "This", "week", "2,300",
    ]
    assert line_starting(lines, "This month").split() == [
        "This", "month", "3,450",
    ]
    assert line_starting(lines, "Last month").split() == [
        "Last", "month", "1.00B",
    ]
    assert "This month by supported tool" in lines
    assert line_starting(lines, "Claude Code").split()[:3] == ["Claude", "Code", "1,150"]
    assert line_starting(lines, "Codex CLI").split()[:3] == ["Codex", "CLI", "1,725"]
    assert "Timeline" in lines
    assert line_starting(lines, "2026-06-22").split() == [
        "2026-06-22", "2,300", "575", "1,725", "0", "0",
    ]
    assert line_starting(lines, "WEEK Jun22-now").split() == [
        "WEEK", "Jun22-now", "2,300", "575", "1,725", "0", "0", "✨",
    ]
    week_i = lines.index(line_starting(lines, "WEEK Jun22-now"))
    assert set(lines[week_i + 1]) == {"-"}
    assert line_starting(lines, "WEEK Jun15-21").split() == [
        "WEEK", "Jun15-21", "575", "575", "0", "0", "0", "✨",
    ]
    assert line_starting(lines, "2026-06-01").split() == [
        "2026-06-01", "575", "0", "0", "575", "0",
    ]
    assert not any(line.startswith("2026-06-20") for line in lines)
    assert line_starting(lines, "2026-05-31").split() == [
        "2026-05-31", "1.00B", "0", "0", "0", "1.00B", "💰" * 10,
    ]
    assert line_starting(lines, "WEEK May25-31").split() == [
        "WEEK", "May25-31", "1.00B", "0", "0", "0", "1.00B",
        ("💰" * 10) + "✨",
    ]


def test_token_report_empty_roots_is_graceful(tmp_path, monkeypatch):
    monkeypatch.setattr(token_usage, "CODEX_ROOT", tmp_path / "codex")
    monkeypatch.setattr(token_usage, "CLAUDE_ROOT", tmp_path / "claude")
    monkeypatch.setattr(token_usage, "AUGMENT_ROOT", tmp_path / "augment")
    monkeypatch.setattr(token_usage, "GEMINI_ROOT", tmp_path / "gemini")
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path / "state")

    now = datetime(2026, 6, 22, 12, tzinfo=token_usage.LOCAL_TZ)
    report = "\n".join(token_usage.report_lines(now))

    assert "Token Usage" in report
    assert "2026-06-22 12:00 PDT" in report
    assert "No local token usage records found." in report


def test_token_report_reuses_unchanged_file_cache(tmp_path, monkeypatch):
    codex = tmp_path / "codex"
    claude = tmp_path / "claude"
    augment = tmp_path / "augment"
    gemini = tmp_path / "gemini"
    monkeypatch.setattr(token_usage, "CODEX_ROOT", codex)
    monkeypatch.setattr(token_usage, "CLAUDE_ROOT", claude)
    monkeypatch.setattr(token_usage, "AUGMENT_ROOT", augment)
    monkeypatch.setattr(token_usage, "GEMINI_ROOT", gemini)
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path / "state")

    write_jsonl(claude / "proj" / "session.jsonl", [
        {
            "timestamp": "2026-06-21T10:00:00-07:00",
            "message": {"usage": {"input_tokens": 80, "output_tokens": 20}},
        },
    ])

    now = datetime(2026, 6, 22, 12, tzinfo=token_usage.LOCAL_TZ)
    token_usage.report_lines(now)

    assert (paths.STATE_DIR / "token-usage-cache.json").exists()

    def fail_if_reparsed(_path):
        raise AssertionError("unchanged file should have used cached daily totals")

    monkeypatch.setattr(token_usage, "_claude_file_events", fail_if_reparsed)
    report = "\n".join(token_usage.report_lines(now))

    assert line_starting(report.splitlines(), "Yesterday").split()[1] == "100"
