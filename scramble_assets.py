"""Scramble (Konami, 1981) graphics and level-data helpers.

Native data extraction, NOT Z80 or video-hardware emulation.
MAME references (BSD-3-Clause):
  src/mame/galaxian/scramble.cpp: scramble_charlayout, scramble_spritelayout
  src/mame/galaxian/galaxold_v.cpp: galaxold_palette
  src/mame/galaxian/galaxian.cpp: ROM_START(scramble)
"""
from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile
import zlib

from PIL import Image

GFX_ROM_FILES = ("c2.5f", "c1.5h")
COLOUR_PROM = "c01s.6e"
MAIN_ROM_FILES = ("s1.2d", "s2.2e", "s3.2f", "s4.2h", "s5.2j", "s6.2l", "s7.2m", "s8.2p")
# The original Konami parent-set CRCs from MAME.
CRC = {
    "c2.5f": 0x4708845B,
    "c1.5h": 0x11FD2887,
    "c01s.6e": 0x4E3CAEAB,
    "s1.2d": 0xEA35CCAA,
    "s2.2e": 0xE7BBA1B3,
    "s3.2f": 0x12D7FC3E,
    "s4.2h": 0xB59360EB,
    "s5.2j": 0x4919A91C,
    "s6.2l": 0x26A4547B,
    "s7.2m": 0x0BB49470,
    "s8.2p": 0x6A5740E5,
}

STAGES = (
    ("1ST / ROCKETS", 0x29E2, 0),
    ("2ND / UFO CAVES", 0x2DD3, 2),
    ("3RD / FIREBALLS", 0x31C4, 1),
    ("4TH / ROCKETS", 0x3465, 8),
    ("5TH / MAZE", 0x3856, 4),
    ("BASE", 0x3C47, 16),
)


def read_original_roms(zip_path: str | Path, *, with_main: bool = True) -> dict[str, bytes]:
    """Accept the parent-only ZIP or the merged ZIP; use ROOT entries only."""
    required = (*GFX_ROM_FILES, COLOUR_PROM)
    if with_main:
        required = (*required, *MAIN_ROM_FILES)
    with ZipFile(zip_path) as z:
        roots = {n.lower(): n for n in z.namelist() if "/" not in n and "\\" not in n}
        missing = [n for n in required if n not in roots]
        if missing:
            raise ValueError(f"Scramble original parent ROMs missing at ZIP root: {', '.join(missing)}")
        result = {}
        for name in required:
            data = z.read(roots[name])
            actual = zlib.crc32(data)
            if actual != CRC[name]:
                raise ValueError(f"ROM {name} differs from the original MAME parent set: "
                                 f"CRC {actual:08X}, expected {CRC[name]:08X}")
            result[name] = data
    return result


def palette_from_prom(prom: bytes) -> list[list[tuple[int, int, int]]]:
    """MAME Galaxian resistor-weight palette; PROM has 8 groups of 4 pens."""
    if len(prom) != 32:
        raise ValueError(f"Colour PROM should be 32 bytes, got {len(prom)}")
    rgb = []
    for b in prom:
        r = (0x21 if b & 0x01 else 0) + (0x47 if b & 0x02 else 0) + (0x97 if b & 0x04 else 0)
        g = (0x21 if b & 0x08 else 0) + (0x47 if b & 0x10 else 0) + (0x97 if b & 0x20 else 0)
        blue = (0x52 if b & 0x40 else 0) + (0xAD if b & 0x80 else 0)
        rgb.append((r, g, blue))
    return [rgb[p*4:p*4+4] for p in range(8)]


def decode_graphics(roms: dict[str, bytes]) -> tuple[list[Image.Image], list[Image.Image]]:
    """Decode 256 8x8 tiles and 64 16x16 sprites as PEN INDEX images.

    The two original graphics ROMs are separate bitplanes. MAME's first
    plane contributes the HIGH pixel bit (drawgfx.cpp: planebit=1<<(planes-1)),
    and its second plane the LOW bit. Sprites use 8x16 chunks.
    Each image has pixel indexes 0..3, not RGB values yet.

    IMPORTANT: The raw graphics are in the monitor's unrotated orientation.
    For a normal landscape monitor using Scramble's ROT90 presentation,
    rotate each element CLOCKWISE after decoding (done in render_atlas).
    """
    planes = [roms[n] for n in GFX_ROM_FILES]
    if any(len(x) != 2048 for x in planes):
        raise ValueError("Graphics ROMs should be 2048 bytes each")

    tiles = []
    for code in range(256):
        pixels = []
        for y in range(8):
            p0 = planes[0][code*8 + y]
            p1 = planes[1][code*8 + y]
            for x in range(8):
                bit = 7-x
                pixels.append((((p0 >> bit) & 1) << 1) | ((p1 >> bit) & 1))
        image = Image.new("L", (8, 8))
        image.putdata(pixels)
        tiles.append(image)

    sprites = []
    for code in range(64):
        pixels = []
        for y in range(16):
            row = y if y < 8 else y + 8  # MAME: yoffs 0..7, 16..23 bytes
            for x in range(16):
                byte_index = code*32 + row + (8 if x >= 8 else 0)
                bit = 7-(x % 8)
                pixels.append((((planes[0][byte_index] >> bit) & 1) << 1) |
                              ((planes[1][byte_index] >> bit) & 1))
        image = Image.new("L", (16, 16))
        image.putdata(pixels)
        sprites.append(image)
    return tiles, sprites


def render_atlas(elements: list[Image.Image], pens: list[tuple[int, int, int]],
                 columns: int, *, rotate_clockwise: bool = True) -> Image.Image:
    """Colourise and pack a grid. Pen 0 is transparent for game compositing."""
    if len(elements) % columns:
        raise ValueError("Grid does not contain a whole number of rows")
    size = elements[0].width
    atlas = Image.new("RGBA", (columns * size, len(elements) // columns * size), (0, 0, 0, 0))
    rgba = [(0, 0, 0, 0), *[(*p, 255) for p in pens[1:]]]
    for i, source in enumerate(elements):
        pixels = Image.new("RGBA", source.size)
        pixels.putdata([rgba[index] for index in source.getdata()])
        if rotate_clockwise:
            pixels = pixels.transpose(Image.Transpose.ROTATE_270)
        atlas.paste(pixels, ((i % columns)*size, (i//columns)*size))
    return atlas


def read_landscapes(main_rom: bytes) -> list[dict]:
    """Extract the six original stage streams without implementing scrolling.

    A record is 6 bytes without a cave ceiling, or 9 bytes with a ceiling.
    Data is indexed by ROM address and terminates on a single FF byte.
    Coordinates are ORIGINAL hardware X, so not yet converted to screen Y.
    """
    if len(main_rom) != 0x4000:
        raise ValueError("Expected the original 16 KiB main Z80 ROM image")
    result = []
    for number, (name, offset, expected_flags) in enumerate(STAGES):
        ptr_offset = 0x29D0 + number * 3
        ptr = main_rom[ptr_offset] + 256 * main_rom[ptr_offset + 1]
        flags = main_rom[ptr_offset + 2]
        if ptr != offset or flags != expected_flags:
            raise ValueError(f"Landscape table differs at {ptr_offset:04X}")
        start = ptr
        entries = []
        while ptr < len(main_rom) and main_rom[ptr] != 0xFF:
            has_ceiling = bool(main_rom[ptr+4])
            length = 9 if has_ceiling else 6
            block = main_rom[ptr:ptr+length]
            if len(block) != length:
                raise ValueError(f"Unexpected end of ROM at {ptr:04X}")
            entry = {
                "address": f"{ptr:04X}",
                "floor": [
                    {"x": block[0], "edge_char": block[1]},
                    {"x": block[2], "edge_char": block[3]},
                ],
                "ceiling": (
                    [{"x": block[4], "edge_char": block[5]},
                     {"x": block[6], "edge_char": block[7]}]
                    if has_ceiling else None
                ),
                "ground_object": block[8] if has_ceiling else block[5],
                "raw_hex": block.hex(" "),
            }
            entries.append(entry)
            ptr += length
            if len(entries) > 1000:
                raise ValueError("Unterminated landscape stream")
        if ptr >= len(main_rom) or main_rom[ptr] != 0xFF:
            raise ValueError("Missing end-of-level sentinel")
        result.append({"name": name, "level_index": number, "flags": flags,
                       "start_address": f"{start:04X}", "end_address": f"{ptr:04X}",
                       "record_count": len(entries), "records": entries})
    return result


def create_landscape_preview(stages: list[dict]) -> Image.Image:
    """Build a DIAGNOSTIC height-map, NOT a screenshot of Scramble.

    Uses original stream's hardware-X boundary values; the final renderer
    will convert those into character memory plus column-scroll positions.
    """
    from PIL import ImageDraw, ImageFont

    width, height_per = 1250, 154
    out = Image.new("RGB", (width, len(stages) * height_per + 20), (16, 18, 30))
    draw = ImageDraw.Draw(out)
    font = ImageFont.load_default()
    for si, stage in enumerate(stages):
        top = si * height_per + 12
        draw.text((20, top+3), f"{stage['name']} | {stage['record_count']} landscape records | flags {stage['flags']}",
                  fill=(232, 233, 243), font=font)
        x0, x1 = 20, width-20
        y0, y1 = top + 23, top + 135
        draw.rectangle((x0,y0,x1,y1), fill=(6, 8, 17), outline=(61, 65, 80))
        samples = [e for rec in stage["records"] for e in [rec]]
        floor = [p["x"] for rec in samples for p in rec["floor"]]
        ceil = [p["x"] if rec["ceiling"] else 0x28 for rec in samples for p in (rec["ceiling"] if rec["ceiling"] else [None,None])]
        # Screen coordinates run from $20 (near top) to $E8 (near bottom).
        # This is a geometry preview, not a direct screen-space trace.
        N = len(floor)
        def xx(i): return x0 + i * (x1-x0) / max(1, N-1)
        def yy(v): return y0 + max(0, min(1, (v-0x20)/(0xE8-0x20))) * (y1-y0)
        # Dense polygon stream, efficiently fills between boundary and frame edge.
        poly = [(xx(i),yy(v)) for i,v in enumerate(floor)] + [(x1,y1),(x0,y1)]
        draw.polygon(poly, fill=(124, 30, 130))
        if any(rec["ceiling"] for rec in samples):
            cpoly = [(x0,y0),(x1,y0)] + [(xx(i), yy(ceil[i])) for i in reversed(range(N))]
            draw.polygon(cpoly, fill=(43, 76, 132))
            draw.line([(xx(i), yy(v)) for i,v in enumerate(ceil)], fill=(92,180,224), width=2)
        draw.line([(xx(i),yy(v)) for i,v in enumerate(floor)], fill=(248, 168, 246), width=2)
    return out


def export_assets(rom_zip: str | Path, destination: str | Path) -> dict:
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    roms = read_original_roms(rom_zip)
    pens = palette_from_prom(roms[COLOUR_PROM])
    chars, sprites = decode_graphics(roms)

    for pal_idx, colors in enumerate(pens):
        render_atlas(chars, colors, 16).save(destination / f"characters_color_{pal_idx}.png")
        render_atlas(sprites, colors, 8).save(destination / f"sprites_color_{pal_idx}.png")

    manifest = {
        "game": "Scramble (Konami, 1981) - original parent set",
        "characters": {"count": 256, "dimensions": [8, 8], "atlas_columns": 16, "atlas_rows": 16},
        "sprites": {"count": 64, "dimensions": [16, 16], "atlas_columns": 8, "atlas_rows": 8},
        "orientation": "GFX assets rotated clockwise 90 degrees for standard horizontal-monitor viewing",
        "palette_source": "c01s.6e (MAME Galaxian resistor-weight conversion)",
        "graphics_bitplane_order": "MAME: first plane high bit, second plane low bit",
        "transparency": "pen 0 alpha=0 on exported RGBA character and sprite sheets",
        "palettes": [[list(rgb) for rgb in group] for group in pens],
        "background_blue_rgb": [0, 0, 86],
        "bullets_rgb": {"yellow": [239, 239, 0], "white": [239, 239, 239]},
        "tiles_sheet": "characters_color_{0..7}.png",
        "sprites_sheet": "sprites_color_{0..7}.png",
    }
    (destination / "palettes.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    rom = b"".join(roms[name] for name in MAIN_ROM_FILES)
    stages = read_landscapes(rom)
    (destination / "landscapes.json").write_text(json.dumps({
        "note": "Original ROM landscape records, hardware-axis coordinates; not a screen tilemap.",
        "stages": stages,
    }, indent=2) + "\n", encoding="utf-8")
    create_landscape_preview(stages).save(destination / "landscape_preview.png")
    return {
        "characters": len(chars), "sprites": len(sprites), "palette_groups": len(pens),
        "stage_records": [stage["record_count"] for stage in stages],
        "destination": str(destination),
    }
