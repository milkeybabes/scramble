"""Scramble landscape geometry, using Konami's original ROM data and tile codes.

This is a native Python translation of the *data/character composition* used by
scramble.asm ($0793-$084A, $15A5-$16A5, $27C9-$2803).  Not a Z80 CPU or
Galaxian video-hardware emulator.

Each ROM record contains TWO 8-pixel scenery columns; each has one edge tile
and a 2-bitplane fill pattern. The source packs the memory in rotated 32x32
character RAM, so the screen-space columns here are in natural left->right
order. High-speed display can blit pre-rendered tile strips from these columns.

This module deliberately does not claim frame-exact game-start timing, initial
pre-fill, scroll latch, target spawn state, or MAME's video RAM wrap. Those
can be validated against MAME once a gameplay trace is available.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable

DATA = Path(__file__).resolve().parent / 'data'
EMPTY_CHAR = 0x10
ROCK_FILL = 0x39
BRICK_FILL_FIRST = 0x3D
BRICK_FILL_SECOND = 0xD0
PLAYFIELD_TOP = 5
PLAYFIELD_BOTTOM = 29  # char index; bottommost solid cell is index 28
CHAR_SIZE = 8
VIEW_WIDTH, VIEW_HEIGHT = 224, 256  # MAME 256x224 raw visible area, ROT90

# Scramble.asm $163F and $191F/$1915/$191A/$1910.
TARGET_GROUPS = {1: ('ROCKET', 0x1C), 2: ('FUEL', 0x10),
                 4: ('MYSTERY', 0x33), 8: ('BASE', 0x2F)}


@dataclass(frozen=True)
class GroundTarget:
    kind: str
    group: int
    x: int
    y: int
    record_index: int
    record_address: str


@dataclass
class StageMap:
    name: str
    flags: int
    cols: list[list[int]]
    targets: list[GroundTarget]
    records: list[dict]
    stage_index: int

    @property
    def width(self) -> int:
        return len(self.cols) * CHAR_SIZE

    @property
    def scroll_limit(self) -> int:
        return max(0, self.width - VIEW_WIDTH)


def build_stage(source: dict) -> StageMap:
    """Create one complete tile-strip from the packed six-/nine-byte records.

    In the original drawing code each pair is first written into two consecutive
    32-char VRAM rows, scrolled onto screen via column scroll attributes.
    Here the exact *tile indexes* and edge/fill algorithm are retained, but
    the circular offscreen buffer is replaced by natural screen-space columns.
    """
    columns: list[list[int]] = []
    targets: list[GroundTarget] = []
    flags = source['flags']
    is_brick = bool(flags & 0x1C)

    for ri, record in enumerate(source['records']):
        floor = record['floor']
        ceiling = record['ceiling']
        for side in range(2):
            col = [EMPTY_CHAR] * 32
            f = floor[side]
            y = (int(f['x']) & 0xF8) >> 3  # $15E4, $15FD
            if not PLAYFIELD_TOP <= y <= PLAYFIELD_BOTTOM:
                raise ValueError(f"invalid floor boundary at {record['address']} side={side}: {y}")
            col[y] = f['edge_char']
            fill = ROCK_FILL if not is_brick else (BRICK_FILL_FIRST if side == 0 else BRICK_FILL_SECOND)
            for row in range(y+1, PLAYFIELD_BOTTOM):
                col[row] = fill

            if ceiling:
                c = ceiling[side]
                cy = (int(c['x']) & 0xF8) >> 3
                if not PLAYFIELD_TOP <= cy <= PLAYFIELD_BOTTOM:
                    raise ValueError(f"invalid ceiling boundary {record['address']} side={side}: {cy}")
                col[cy] = c['edge_char']
                roof_fill = ROCK_FILL if not is_brick else (BRICK_FILL_SECOND if side == 0 else BRICK_FILL_FIRST)
                for row in range(PLAYFIELD_TOP, cy):
                    col[row] = roof_fill
            columns.append(col)

        obj_id = int(record['ground_object'])
        if obj_id:
            if obj_id not in TARGET_GROUPS:
                raise ValueError(f"Unknown ground target id {obj_id} at {record['address']}")
            kind, group = TARGET_GROUPS[obj_id]
            # Scramble.asm $1650: NEXT_GROUND_OBJECT_CHAR_PTR = SECOND_PTR-2.
            # $085E draws four characters in a 2x2 square. Our record's two
            # columns represent those two original char RAM rows.
            y_anchor = (((floor[1]['x'] & 0xF8) >> 3) - 2) * 8
            targets.append(GroundTarget(kind, group, ri * 16, y_anchor, ri, record['address']))

    if len(columns) != source['record_count'] * 2:
        raise AssertionError('missing stage tile columns')
    return StageMap(source['name'], flags, columns, targets,
                    source['records'], source['level_index'])


def read_stages(path: Path = DATA / 'landscapes.json') -> list[StageMap]:
    loaded = json.loads(path.read_text(encoding='utf-8'))['stages']
    return [build_stage(stage) for stage in loaded]


def visible_columns(stage: StageMap, offset: int, extra: int = 0) -> Iterable[tuple[int, list[int], int]]:
    """Yield (screen_x, tile column, source column index) for a viewport.

    Pixel positioning stays integer even when the offset is not tile-aligned.
    """
    offset = max(0, min(stage.scroll_limit, int(offset)))
    first = offset // CHAR_SIZE
    last = min(len(stage.cols), (offset + VIEW_WIDTH + 7) // CHAR_SIZE + extra)
    for ci in range(first, last):
        yield ci * CHAR_SIZE - offset, stage.cols[ci], ci


class ScrollClock:
    """One-pixel scroll events following $15A5's countdown mechanism.

    A reload latch of N produces one pixel increment every N+1 logical frames.
    The original latch value during gameplay still needs a MAME trace; default
    is zero for straightforward one-pixel-per-frame visual testing.
    """
    def __init__(self, speed_latch: int = 0):
        self.latch = speed_latch
        self.counter = 0
        self.pixels = 0
        self.logical_frames = 0

    def tick(self) -> bool:
        self.logical_frames += 1
        if self.counter:
            self.counter -= 1
            return False
        self.counter = self.latch
        self.pixels += 1
        return True

    def reset(self) -> None:
        self.counter = 0
        self.pixels = 0
        self.logical_frames = 0


def colour_after_next_change(current: int) -> int:
    """Compatibility entry for the $2810 increment-and-skip-palette-one behaviour."""
    from scramble_palette import next_landscape_colour
    return next_landscape_colour(current)


def reference_jet_y(stage: StageMap, offset: int, screen_x: int = 32) -> int | None:
    """Find a clear spot for the NON-PLAYABLE reference jet in this demo.

    This is deliberately not the original PLAYER movement/collision routine.
    It just prevents the static sprite reference being embedded in terrain.
    """
    ci = max(0,min(len(stage.cols)-1,(offset+screen_x)//8))
    rec=stage.records[min(len(stage.records)-1,ci//2)]
    side=ci%2
    floor=(int(rec['floor'][side]['x'])&0xF8)
    ceiling=(int(rec['ceiling'][side]['x'])&0xF8) if rec['ceiling'] else 40
    lo=max(42,ceiling+10)
    hi=min(224,floor-18)
    if hi<lo:return None
    return (hi+lo)//2
