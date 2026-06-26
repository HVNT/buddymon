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


def test_money_markers_use_billions_then_remaining_hundred_millions():
    assert token_usage._money_markers(99_999_999) == ""
    assert token_usage._money_markers(100_000_000) == "💰"
    assert token_usage._money_markers(999_999_999) == "💰" * 9
    assert token_usage._money_markers(1_000_000_000) == "🤑"
    assert token_usage._money_markers(1_200_000_000) == "🤑💰💰"
    assert token_usage._money_markers(2_900_000_000) == "🤑🤑" + ("💰" * 9)


def test_summary_row_marks_only_daily_and_weekly_ranges():
    assert token_usage._summary_row("This month", 999_999_999).endswith("999M")
    assert token_usage._summary_row("Today", 100_000_000).split()[-1] == "💰"
    assert token_usage._summary_row("Yesterday", 1_200_000_000).split()[-1] == "🤑💰💰"
    assert token_usage._summary_row("This week", 2_000_000_000).split()[-1] == "🤑🤑"
    assert token_usage._summary_row("This month", 1_000_000_000).split()[-1] == "1.00B"
    assert token_usage._summary_row("Last month", 4_300_000_000).split()[-1] == "4.30B"


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
    assert line_starting(lines, "2026-06-22").split() == [
        "2026-06-22", "2,300", "575", "1,725", "0", "0", "0",
    ]
    assert line_starting(lines, "WEEK Jun22-now").split() == [
        "WEEK", "Jun22-now", "2,300", "575", "1,725", "0", "0", "0", "✨",
    ]
    week_i = lines.index(line_starting(lines, "WEEK Jun22-now"))
    assert set(lines[week_i + 1]) == {"-"}
    assert line_starting(lines, "WEEK Jun15-21").split() == [
        "WEEK", "Jun15-21", "575", "575", "0", "0", "0", "0", "✨",
    ]
    assert line_starting(lines, "2026-06-01").split() == [
        "2026-06-01", "575", "0", "0", "575", "0", "0",
    ]
    assert line_starting(lines, "2026-05-31").split() == [
        "2026-05-31", "1.00B", "0", "0", "0", "1.00B", "0", "🤑",
    ]
    assert line_starting(lines, "WEEK May25-31").split() == [
        "WEEK", "May25-31", "1.00B", "0", "0", "0", "1.00B", "0",
        "🤑✨",
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
