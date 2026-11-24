"""Export Scott Tunstall's annotated original animation ROM tables as JSON.

No ROM bytes are copied into the resulting game; each frame contains only
palette index, tile/sprite code, and the delay used by the original algorithm.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scramble_assets import MAIN_ROM_FILES, read_original_roms  # noqa: E402

# Source: Scott Tunstall, scramble.asm, ANIMATE at $13E4, individual tables.
# 'character' codes refer to groups of four 8x8 chars, not to 16x16 sprites.
TABLES = {
    "player_one": (0x1860, "sprite", "Player 1 jet"),
    "player_two": (0x186F, "sprite", "Jet rear/exhaust sprite (original PLAYER_TWO record)"),
    "player_explosion": (0x187E, "sprite", "Player explosion"),
    "player_two_explosion": (0x1896, "sprite", "Player 2 explosion"),
    "player_bomb": (0x1AD8, "sprite", "Player bomb"),
    "bomb_explosion": (0x1AF0, "sprite", "Bomb explosion"),
    "rocket": (0x1D58, "sprite", "Launched rocket"),
    "rocket_explosion": (0x1D61, "sprite", "Rocket explosion"),
    "ufo": (0x1E1A, "sprite", "UFO"),
    "ufo_explosion": (0x1E20, "sprite", "UFO explosion"),
    "fireball": (0x1F1B, "sprite", "Fireball"),
    "ground_rocket": (0x19C6, "character", "Stationary rocket"),
    "ground_fuel": (0x19CC, "character", "Fuel tank"),
    "ground_mystery": (0x19D2, "character", "Mystery target"),
    "ground_base": (0x19D8, "character", "Enemy base"),
    "ground_explosion": (0x19E4, "character", "Ground object explosion"),
    "ground_fuel_explosion": (0x19F3, "character", "Fuel tank explosion"),
    "ground_mystery_100": (0x1A02, "character", "Mystery 100 points"),
    "ground_mystery_200": (0x1A0C, "character", "Mystery 200 points"),
    "ground_mystery_300": (0x1A12, "character", "Mystery 300 points"),
}


def decode_animation(rom: bytes, addr: int, kind: str, label: str) -> dict:
    start = addr
    frames = []
    for _ in range(80):
        palette = rom[addr]
        if palette == 0xFF:
            repeat = rom[addr + 1] | (rom[addr + 2] << 8)
            if repeat != start:
                raise ValueError(f"{label} ${start:04X}: jump is ${repeat:04X}, not self")
            return {"source_address": f"{start:04X}", "kind": kind,
                    "label": label, "loop_address": f"{repeat:04X}",
                    "frames": frames}
        code, delay = rom[addr + 1:addr + 3]
        if not (0 <= palette <= 7):
            raise ValueError(f"Unexpected palette {palette} in {label}")
        if kind == "character" and code > 63:
            raise ValueError(f"Invalid 2x2 character group ${code:02X} in {label}")
        if kind == "sprite" and (code & 0x3F) >= 64:
            raise ValueError(f"Invalid sprite code {code} in {label}")
        frames.append({"colour": palette, "code": code,
                       "delay": delay})
        addr += 3
    raise ValueError(f"Animation didn't terminate: {label}")


def export_animations(rom_zip: Path, out: Path) -> dict:
    roms = read_original_roms(rom_zip)
    main = b"".join(roms[name] for name in MAIN_ROM_FILES)
    animations = {key: decode_animation(main, *definition)
                  for key, definition in TABLES.items()}
    result = {
        "source": "Original Konami Scramble main Z80 ROM (parent set)",
        "reference": "ScottTunstall/Scramble/scramble.asm; ANIMATE $13E4",
        "note": "Sprite code bit 6/7 may carry flip flags; low 6 bits select graphics. "
                "Character code is a GROUP index: four consecutive 8x8 chars form one 16x16 target. "
                "Delay follows the original decrement-until-zero ANIMATE routine.",
        "animations": animations,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "animations.json")
    args = parser.parse_args()
    result = export_animations(args.rom, args.out)
    print(f"Extracted {len(result['animations'])} animation tables into {args.out}")


if __name__ == "__main__":
    main()
