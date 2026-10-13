"""First-launch downloads use fake local artwork; never access the network."""

import fcntl
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from lib import art_setup, assets, packs, paths, species, state
from tools import fetch_gen5


@pytest.fixture
def setup(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path)
    monkeypatch.setattr(state, "load", state.default_state)
    monkeypatch.setattr(packs, "_cache", {})
    names = ("Pikachu", "Eevee")
    monkeypatch.setattr(species, "ALL_SPECIES", names)
    monkeypatch.setattr(art_setup, "_priority_names", lambda: ["Pikachu"])
    monkeypatch.setitem(assets.PACK_SPECIES, "gen5", names)
    ready = assets.pack_ready
    monkeypatch.setattr(assets, "pack_ready", lambda kind, root=None:
                        ready(kind, root) if kind == "gen5" else True)
    return tmp_path


def entry():
    return {
        "frames": [[["x"], {"x": "#123456"}]],
        "shiny_frames": [[["x"], {"x": "#abcdef"}]],
    }


def test_status_never_downloads_or_changes_game_state(setup, monkeypatch):
    monkeypatch.setattr(fetch_gen5, "species_entry", lambda *_, **__: pytest.fail("network"))
    original = b'{"personal": "unchanged"}'
    (setup / "state.json").write_bytes(original)
    assert art_setup.status()["state"] == "needed"
    (setup / art_setup.STATUS_FILE).write_text("invalid json")
    assert art_setup.status()["state"] == "needed"
    assert (setup / "state.json").read_bytes() == original


def test_progress_is_visible_before_download_finishes(setup, monkeypatch):
    release = threading.Event()
    entered = threading.Event()

    def fetch(_, name, **kwargs):
        if name == "Eevee":
            entered.set()
            assert release.wait(5)
        return entry()

    monkeypatch.setattr(fetch_gen5, "species_entry", fetch)
    original_write = art_setup._write_json
    visible = threading.Event()

    def write(path, value):
        original_write(path, value)
        if path.name == "pikachu.json":
            visible.set()

    monkeypatch.setattr(art_setup, "_write_json", write)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(art_setup.install)
        try:
            assert entered.wait(5) and visible.wait(5)
            assert art_setup.status()["state"] == "downloading"
            assert not assets.pack_ready("gen5")
            assert json.loads((setup / "packs/gen5/pikachu.json").read_text()) == entry()
            assert packs.gen5_frames("Pikachu")[0] == (["x"], {"x": "#123456"})
            assert art_setup.install() == {"ok": True, "already_running": True}
        finally:
            release.set()
        assert future.result(timeout=5)["ok"]
    assert art_setup.status()["state"] == "complete"
    assert not (setup / "packs/gen5/.downloading").exists()


def test_failure_preserves_progress_and_retry_fetches_only_missing(setup, monkeypatch):
    pack = setup / "packs/gen5"
    pack.mkdir(parents=True)
    previous = json.dumps(entry())
    (pack / "pikachu.json").write_text(previous)
    (pack / ".downloading").touch()
    calls = []

    def offline(_, name, **kwargs):
        calls.append(name)
        raise OSError("offline")

    monkeypatch.setattr(fetch_gen5, "species_entry", offline)
    assert not art_setup.install()["ok"]
    assert art_setup.status()["can_retry"]
    assert (pack / "pikachu.json").read_text() == previous
    assert calls == ["Eevee"]
    monkeypatch.setattr(fetch_gen5, "species_entry", lambda _, name, **kwargs: entry())
    assert art_setup.install()["ok"]
    assert art_setup.status()["state"] == "complete"
    assert (pack / "pikachu.json").read_text() == previous


def test_interrupted_process_exposes_retry(setup):
    (setup / art_setup.STATUS_FILE).write_text(json.dumps({"state": "downloading"}))
    with (setup / art_setup.LOCK_FILE).open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        assert art_setup.status()["state"] == "downloading"
    assert art_setup.status()["state"] == "incomplete"
    assert art_setup.status()["can_retry"]


def test_existing_complete_pack_is_untouched(setup, monkeypatch):
    pack = setup / "packs/gen5"
    pack.mkdir(parents=True)
    original = json.dumps(entry())
    for name in ("pikachu", "eevee"):
        (pack / f"{name}.json").write_text(original)
    monkeypatch.setattr(fetch_gen5, "species_entry", lambda *_, **__: pytest.fail("network"))
    assert art_setup.install() == {"ok": True}
    assert art_setup.status()["state"] == "complete"
    for name in ("pikachu", "eevee"):
        assert (pack / f"{name}.json").read_text() == original
    # Later status reads rely on the completion receipt, not a full pack scan.
    monkeypatch.setattr(art_setup, "_read_entry", lambda *_: pytest.fail("pack scan"))
    assert art_setup.install() == {"ok": True, "already_complete": True}
    assert art_setup.status()["state"] == "complete"


def test_shiny_failure_preserves_regular_and_retry_downloads_only_shiny(setup, monkeypatch):
    pack = setup / "packs/gen5"
    pack.mkdir(parents=True)
    (pack / "eevee.json").write_text(json.dumps(entry()))
    requests = []
    online = False

    def fetch(url):
        requests.append(url)
        if "/shiny/" in url:
            if not online:
                raise TimeoutError("connection interrupted")
            return b"shiny"
        return b"regular"

    monkeypatch.setattr(fetch_gen5, "fetch", fetch)
    monkeypatch.setattr(fetch_gen5, "frames_pack", lambda image:
                        entry()["shiny_frames" if image == b"shiny" else "frames"])
    assert art_setup.install()["ok"] is False
    assert art_setup.status()["can_retry"] is True
    assert (pack / ".downloading").exists()
    saved = json.loads((pack / "pikachu.json").read_text())
    assert saved == {"frames": entry()["frames"]}
    assert len(requests) == 2

    online = True
    requests.clear()
    assert art_setup.install()["ok"] is True
    assert requests == [f"{fetch_gen5.SPRITES}/shiny/25.gif"]
    assert json.loads((pack / "pikachu.json").read_text()) == entry()
    assert art_setup.status()["state"] == "complete"
    assert packs.gen5_frames("Pikachu", shiny=True) != packs.gen5_frames("Pikachu")


@pytest.mark.parametrize("layout", ["split", "legacy"])
def test_older_complete_receipt_repairs_regular_only_art(setup, monkeypatch, layout):
    pack = setup / "packs"
    pack.mkdir()
    saved = {"Pikachu": {"frames": entry()["frames"]}, "Eevee": entry()}
    if layout == "split":
        (pack / "gen5").mkdir()
        for name, sprite in saved.items():
            (pack / "gen5" / f"{name.lower()}.json").write_text(json.dumps(sprite))
    else:
        (pack / "gen5.json").write_text(json.dumps(saved))
    (setup / art_setup.STATUS_FILE).write_text('{"state":"complete"}')
    assert art_setup.status()["state"] == "needed"
    requests = []

    def fetch(url):
        requests.append(url)
        return b"shiny"

    monkeypatch.setattr(fetch_gen5, "fetch", fetch)
    monkeypatch.setattr(fetch_gen5, "frames_pack", lambda _: entry()["shiny_frames"])
    assert art_setup.install()["ok"] is True
    assert requests == [f"{fetch_gen5.SPRITES}/shiny/25.gif"]
    assert json.loads((pack / "gen5/pikachu.json").read_text()) == entry()
    assert json.loads((pack / "gen5/eevee.json").read_text()) == entry()
    assert art_setup.status()["state"] == "complete"
