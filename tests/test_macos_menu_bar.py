import json
import os
import struct
import subprocess
import sys

from tests.native_test_support import ROOT, pytestmark as pytestmark


def test_menu_bar_state_harness_snapshot_is_complete_and_deterministic(
    menu_bar_state_snapshot_harness,
    tmp_path,
):
    env = os.environ.copy()
    env["XDG_STATE_HOME"] = str(tmp_path / "state")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    payload_result = subprocess.run(
        [sys.executable, str(ROOT / "buddymon.py"), "app-menu-bar-harness"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert payload_result.returncode == 0, payload_result.stderr
    payload = json.loads(payload_result.stdout)
    assert len(payload["sequences"]) == 23

    first = tmp_path / "menu-bar-states-first.png"
    second = tmp_path / "menu-bar-states-second.png"
    for output in [first, second]:
        result = subprocess.run(
            [str(menu_bar_state_snapshot_harness), str(output)],
            cwd=ROOT,
            input=payload_result.stdout,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    first_png = first.read_bytes()
    assert first_png == second.read_bytes()
    assert first_png.startswith(b"\x89PNG\r\n\x1a\n")
    width, height = struct.unpack(">II", first_png[16:24])
    assert width == 1_180
    assert 2_200 <= height <= 3_000
    assert len(first_png) >= 100_000
