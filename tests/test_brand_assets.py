from pathlib import Path
import struct

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


def test_readme_uses_current_shipping_screenshots():
    expected = {
        "buddymon-main.png": (608, 432),
        "encounter.png": (608, 448),
        "trainer-card.png": (608, 416),
        "token-usage.png": (608, 420),
        "showcase-export.png": (864, 600),
    }
    assert {path.name for path in SCREENSHOTS.glob("*.png")} == set(expected)
    for name, size in expected.items():
        assert Image.open(SCREENSHOTS / name).size == size

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for name in expected:
        assert f"docs/screenshots/{name}" in readme


def test_readme_distinguishes_native_views_from_showcase_export():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "### Curate your favorites" in readme
    assert "Open Showcase in the\nterminal game" in readme
    assert "Actual BuddyMon Showcase export rendered locally" in readme
    assert "docs/screenshots/showcase.png" not in readme
    showcase_section = readme.index("### Curate your favorites")
    for native_image in ("encounter.png", "trainer-card.png", "token-usage.png"):
        assert readme.index(native_image) < showcase_section
    assert readme.index("showcase-export.png") > showcase_section


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
