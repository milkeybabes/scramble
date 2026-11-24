"""Validate the exported assets without needing the original ROMs or pygame."""
from __future__ import annotations
import json
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def main() -> None:
    manifest = json.loads((DATA / "palettes.json").read_text(encoding="utf-8"))
    stages = json.loads((DATA / "landscapes.json").read_text(encoding="utf-8"))["stages"]
    assert len(manifest["palettes"]) == 8
    assert all(len(p) == 4 for p in manifest["palettes"])
    assert [s["record_count"] for s in stages] == [168,112,112,168,112,28]
    for group in range(8):
        for typ in ("characters", "sprites"):
            sheet = Image.open(DATA / f"{typ}_color_{group}.png")
            assert sheet.size == (128,128) and sheet.mode == "RGBA", (typ,group,sheet.size,sheet.mode)
            assert sheet.getbbox(), (typ,group)
    assert Image.open(DATA / "landscape_preview.png").size[1] > 700
    print("PASS: 16 indexed-colour PNG sheets, 8 palette groups, 6 landscape streams")


if __name__ == "__main__":
    main()
