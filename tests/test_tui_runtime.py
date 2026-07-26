from lib import tui_runtime as runtime
from tests.tui_test_support import _feed_keys


def test_read_key_decodes_enter_arrows_and_lone_esc(monkeypatch):
    _feed_keys(monkeypatch, b"\r")
    assert runtime.read_key() == "enter"
    _feed_keys(monkeypatch, b"\x1b[A")
    assert runtime.read_key() == "up"
    _feed_keys(monkeypatch, b"\x1bOB")  # SS3 arrow
    assert runtime.read_key() == "down"
    _feed_keys(monkeypatch, b"\x1b")    # lone Escape (nothing queued behind)
    assert runtime.read_key() == "esc"


def test_read_key_skips_kitty_ack_then_returns_enter(monkeypatch):
    # The regression: a kitty graphics ack queued just before the user's Enter
    # must be skipped, not misread as 'esc' or allowed to swallow the Enter.
    _feed_keys(monkeypatch, b"\x1b_Gi=1;OK\x1b\\\r")
    assert runtime.read_key() == "enter"


def test_read_key_skips_query_response_then_returns_enter(monkeypatch):
    # A late cell-size / cursor-position style CSI reply must not register.
    _feed_keys(monkeypatch, b"\x1b[6;34;16t\r")
    assert runtime.read_key() == "enter"
    _feed_keys(monkeypatch, b"\x1b[24;80R\r")
    assert runtime.read_key() == "enter"


def test_read_key_ignores_mouse_move_but_keeps_wheel(monkeypatch):
    _feed_keys(monkeypatch, b"\x1b[<35;10;20M\r")  # plain move -> skipped
    assert runtime.read_key() == "enter"
    _feed_keys(monkeypatch, b"\x1b[<64;10;20M")    # wheel up
    assert runtime.read_key() == "wheel_up"
