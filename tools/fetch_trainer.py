#!/usr/bin/env python3
"""Fetch Trainer Red's FireRed/LeafGreen portrait into a local BuddyMon pack.

Run manually (network):
    python3 tools/fetch_trainer.py

The source is pinned to a pret/pokefirered commit and verified by SHA-256.
Output stays under the local BuddyMon state directory and is never bundled.
"""

import base64
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import assets  # noqa: E402


TRAINER_SOURCE_COMMIT = "df4449a27cd78dd747ce269e47d3ab4a0149d8f4"
TRAINER_SOURCE = (
    "https://raw.githubusercontent.com/pret/pokefirered/"
    f"{TRAINER_SOURCE_COMMIT}/graphics/trainers/front_pics/red_front_pic.png"
)
TRAINER_SHA256 = "4442795842373b5045041f7207619799160edcc9e0124e19996e46401ed149f0"


def fetch(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "buddymon-trainer"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def main(pack_root=None):
    portrait = fetch(TRAINER_SOURCE)
    digest = hashlib.sha256(portrait).hexdigest()
    if digest != TRAINER_SHA256:
        raise RuntimeError(
            "Trainer Red portrait checksum mismatch: "
            f"expected {TRAINER_SHA256}, got {digest}"
        )
    assets.validate_trainer_portrait(portrait)

    pack = {
        "red": {
            "portrait_base64": base64.b64encode(portrait).decode("ascii"),
            "source_url": TRAINER_SOURCE,
            "source_commit": TRAINER_SOURCE_COMMIT,
            "sha256": digest,
        }
    }
    output_root = (
        Path(pack_root) if pack_root is not None else assets.pack_root()
    )
    output_root.mkdir(parents=True, exist_ok=True)
    output = output_root / "trainer.json"
    output.write_text(json.dumps(pack), encoding="utf-8")
    print(f"wrote {output} — Trainer Red portrait")


if __name__ == "__main__":
    sys.exit(assets.installer_cli("trainer"))
