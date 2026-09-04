import json
from io import BytesIO
from pathlib import Path
import struct
import subprocess
import sys

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "docs" / "assets" / "brand"
ICONS = BRAND / "icons"
SCREENSHOTS = ROOT / "docs" / "screenshots"

PALETTE = {
    (247, 241, 223, 255),
    (255, 249, 232, 255),
    (231, 223, 201, 255),
    (38, 34, 54, 255),
    (109, 102, 120, 255),
    (185, 174, 189, 255),
    (217, 84, 98, 255),
    (79, 143, 199, 255),
    (57, 137, 120, 255),
    (211, 154, 44, 255),
    (114, 199, 169, 255),
    (59, 130, 111, 255),
    (182, 228, 207, 255),
}
ICON_NAMES = {
    "brand",
    "setup",
    "activity",
    "encounter",
    "collection",
    "native-app",
    "privacy",
    "development",
}


def test_brand_rasters_have_expected_dimensions():
    assert Image.open(BRAND / "buddymon-lockup.png").size == (1080, 272)
    assert Image.open(BRAND / "buddymon-mark.png").size == (256, 256)
    assert Image.open(
        ROOT / "macos" / "BuddyMonApp" / "Resources" / "AppIcon.png"
    ).size == (1024, 1024)


def test_app_icon_is_a_palette_limited_step_tile():
    image = Image.open(
        ROOT / "macos" / "BuddyMonApp" / "Resources" / "AppIcon.png"
    ).convert("RGBA")
    colors = set(image.get_flattened_data())
    assert colors - {(0, 0, 0, 0)} <= PALETTE
    assert image.getpixel((0, 0))[3] == 0
    assert image.getpixel((512, 512))[3] == 255

    generator = (ROOT / "scripts" / "render-brand-assets.swift").read_text(
        encoding="utf-8"
    )
    assert "let appIcon = drawAppIcon()" in generator


def test_semantic_icons_are_hard_alpha_and_palette_limited():
    assert {path.stem for path in ICONS.glob("*.png")} == ICON_NAMES
    for path in ICONS.glob("*.png"):
        image = Image.open(path).convert("RGBA")
        assert image.size == (32, 32)
        colors = set(image.get_flattened_data())
        assert colors - {(0, 0, 0, 0)} <= PALETTE
        assert {alpha for *_rgb, alpha in colors} <= {0, 255}


def test_app_icon_icns_contains_modern_pixel_sizes():
    path = ROOT / "macos" / "BuddyMonApp" / "Resources" / "AppIcon.icns"
    blob = path.read_bytes()
    assert blob[:4] == b"icns"
    assert struct.unpack(">I", blob[4:8])[0] == len(blob)
    for chunk in (b"icp4", b"icp5", b"icp6", b"ic07", b"ic08", b"ic09", b"ic10"):
        assert chunk in blob

    small_offset = blob.index(b"icp4")
    small_length = struct.unpack(">I", blob[small_offset + 4:small_offset + 8])[0]
    small = Image.open(BytesIO(blob[small_offset + 8:small_offset + small_length])).convert(
        "RGBA"
    )
    assert small.size == (16, 16)
    colors = set(small.get_flattened_data())
    assert (114, 199, 169, 255) in colors
    assert (217, 84, 98, 255) in colors
    assert small.getpixel((0, 0))[3] == 0


def test_readme_uses_current_shipping_screenshots():
    expected = {
        "buddymon-main.png": (608, 432),
        "encounter.png": (608, 448),
        "trainer-card.png": (608, 416),
        "token-usage.png": (608, 420),
        "showcase-export.png": (864, 600),
        "terminal-box-ghostty.png": (1648, 1474),
    }
    assert {path.name for path in SCREENSHOTS.glob("*.png")} == set(expected)
    for name, size in expected.items():
        assert Image.open(SCREENSHOTS / name).size == size

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for name in (
        "buddymon-main.png",
        "encounter.png",
        "terminal-box-ghostty.png",
        "showcase-export.png",
    ):
        assert f"docs/screenshots/{name}" in readme
    assert "docs/screenshots/trainer-card.png" not in readme
    assert "docs/screenshots/token-usage.png" not in readme


def test_readme_presents_a_readable_game_first_screenshot_story():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Start Playing" in readme
    assert "The Loop" in readme
    assert "A Collection Worth Opening" in readme
    assert readme.index("buddymon-main.png") < readme.index("Start Playing")
    assert readme.index("encounter.png") < readme.index("terminal-box-ghostty.png")
    assert readme.index("terminal-box-ghostty.png") < readme.index("showcase-export.png")
    assert 'width="49%"' not in readme
    assert "releases/latest" not in readme
    assert "there is no downloadable GitHub Release\nyet" in readme


def test_readme_capture_tool_instantiates_shipping_views():
    source = (ROOT / "tools" / "ReadmeScreenshotSnapshot.swift").read_text(
        encoding="utf-8"
    )
    for view in (
        "BuddyMonCompactMenuView",
        "BuddyMonCompactEncounterView",
        "BuddyMonCompactTrainerView",
        "BuddyMonCompactTokensView",
    ):
        assert view in source

    generator = (ROOT / "scripts" / "generate-readme-screenshots.py").read_text(
        encoding="utf-8"
    )
    assert '"Mewtwo"' in generator
    assert "shiny=True" in generator
    assert "showcase_export.render_showcase_png" in generator
    assert '"--terminal-state-only"' in generator

    ghostty_capture = (ROOT / "scripts" / "capture-readme-ghostty.sh").read_text(
        encoding="utf-8"
    )
    assert "--window-frame=80,80,1040,680" in ghostty_capture
    assert "XDG_STATE_HOME" in ghostty_capture
    assert "ReadmeGhosttyWindow.swift" in ghostty_capture


def test_readme_terminal_fixture_uses_isolated_deterministic_state():
    destination = (
        ROOT / ".build" / "readme-ghostty" / "state" / "buddymon" / "state.json"
    )
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "generate-readme-screenshots.py"),
            "--terminal-state-only",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["active"] == "readme-mewtwo"
    dragonite = next(p for p in payload["pokemon"] if p["name"] == "Dragonite")
    assert dragonite["id"] == "readme-dragonite-673"
