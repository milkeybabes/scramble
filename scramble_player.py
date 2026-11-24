"""Konami Scramble (1981) jet movement translated directly into native Python.

Primary reference: Scott Tunstall's annotated Z80 disassembly, PLAYER_INIT
$16FE, PLAYER_MOVE_VERTICAL $1749, PLAYER_MOVE_HORIZONTAL $179E and player
animation $1860. The game deliberately stores display-horizontal movement in
Z80 variable Y, and display-vertical movement in variable X (ROT90 hardware).

The code here maintains the ORIGINAL player register coordinates and 8-bit
semantics. The graphics coordinate conversion is separate; no Z80 is emulated.
Collision diagnostics use source terrain extents, but the complete hardware
scroll-buffer alignment is not proven yet, so these are advisory only.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Joystick:
    up: bool = False
    down: bool = False
    left: bool = False
    right: bool = False
    fire: bool = False  # BUTTON1; $257F tests the rising edge
    bomb: bool = False  # BUTTON2; $26B1 tests the rising edge


@dataclass
class PlayerJet:
    # Raw Scramble Z80 player structure ($4380), not display positions.
    x: int = 0x58  # Vertical axis on ROT90 screen, PLAYER.X at $4383
    y: int = 0xD0  # Horizontal axis on ROT90 screen, PLAYER.Y at $4384
    other_x: int = 0x58  # PLAYER TWO mirror: $43A3
    other_y: int = 0xE0  # PLAYER TWO mirror: $43A4
    updates: int = 0

    def reset(self):
        self.x, self.y = 0x58, 0xD0
        self.other_x, self.other_y = 0x58, 0xE0
        self.updates = 0

    def update(self, stick: Joystick):
        """Apply precisely one original frame's controller movement.

        $1766: UP has priority over DOWN if both pressed.
        $17AC: LEFT has priority over RIGHT if both pressed.
        Vertical AND horizontal are each checked once, so diagonal moves 1+1.
        Raw byte bounds from $176D/$177D and $17B5/$17C5.
        """
        self.updates += 1
        if stick.up:
            candidate = (self.x - 1) & 0xFF
            if candidate >= 0x38:
                self.x = candidate
                self.other_x = (self.other_x - 1) & 0xFF
        elif stick.down:
            candidate = (self.x + 1) & 0xFF
            if candidate < 0xD8:
                self.x = candidate
                self.other_x = (self.other_x + 1) & 0xFF

        if stick.left:
            candidate = (self.y + 1) & 0xFF
            if candidate < 0xD0:
                self.y = candidate
                self.other_y = (self.other_y + 1) & 0xFF
        elif stick.right:
            candidate = (self.y - 1) & 0xFF
            if candidate >= 0x80:
                self.y = candidate
                self.other_y = (self.other_y - 1) & 0xFF

    @property
    def screen_x(self) -> int:
        """Upright left edge from $1FBF-$1FC4 + MAME galaxold sprite draw.

        $1FBC: sprite raw X = player.X-8; MAME adds +1 to raw X.
        $1FC2: sprite raw Y = ~player.Y-8; MAME converts to 240-Y
        (+1 for sprite slots 0-2). ROT90 rotates a 16x16 sprite.
        Converted desktop top-left X is 230 - PLAYER.Y.
        """
        return 230 - self.y

    @property
    def screen_y(self) -> int:
        return self.x - 7

    @property
    def screen_xy(self) -> tuple[int, int]:
        return self.screen_x, self.screen_y

    @property
    def rear_screen_xy(self) -> tuple[int, int]:
        """Rear jet / exhaust sprite, original $43A3/$43A4.

        The original $1F8A function outputs FOUR sprites from the 0x4380
        PLAYER records: fuselage, rear exhaust, and two bombs. Although Scott
        labels the second struct PLAYER_TWO, it remains 16 pixels left of the
        fuselage and is part of the SAME on-screen ship.
        """
        return 230 - self.other_y, self.other_x - 7


def terrain_clearance(stage, scroll_pixels: int, jet: PlayerJet):
    """Advisory collision check derived from original $2113-$2148.

    Original compares player X +/-3 against ceiling/floor extent for three
    adjoining character columns, proceeding from ship nose to tail. This uses
    our Phase-3 *unwrapped* level record stream, not the original 32-slot
    circular LANDSCAPE_EXTENTS buffer; therefore not yet frame-exact.

    Returns (clear, (most restrictive ceil, lowest floor), sampled columns).
    """
    nose = scroll_pixels + jet.screen_x + 15
    indices = tuple((nose - 8 * i) // 8 for i in range(3))
    minimum_floor = 255
    maximum_ceiling = 0
    for col in indices:
        # No terrain beyond right-hand stage end (original prefill is separate).
        if col < 0 or col >= len(stage.cols):
            continue
        record = stage.records[col // 2]
        side = col & 1
        floor = int(record['floor'][side]['x'])
        ceiling = int(record['ceiling'][side]['x']) if record['ceiling'] else 0x28
        minimum_floor = min(minimum_floor, floor)
        maximum_ceiling = max(maximum_ceiling, ceiling)
    clear = (jet.x + 3 <= minimum_floor) and (jet.x - 3 > maximum_ceiling)
    return clear, (maximum_ceiling, minimum_floor), indices


def terrain_clearance_continuous(course, world_scroll: int, jet: PlayerJet):
    """Read three terrain extents across stage seams using global ROM-column IDs.

    Still a diagnostic, NOT frame-exact hardware collision; exact VRAM ring
    alignment and player/game script integration are deferred.
    """
    nose = world_scroll + jet.screen_x + 15
    indices = tuple((nose - 8 * i) // 8 for i in range(3))
    minimum_floor, maximum_ceiling = 255, 0
    for ci in indices:
        wx = ci * 8
        if wx < 0:
            continue
        if wx < course.prefill_width:
            minimum_floor = min(minimum_floor,0xC9)
            maximum_ceiling = max(maximum_ceiling,0x28)
            continue
        idx = course.find_stage(wx)
        stage = course.stages[idx]
        local = wx - course.starts[idx]
        if idx == len(course.stages)-1:
            local %= stage.width
        rec = stage.records[local//16]
        side = (local // 8) & 1
        floor = int(rec['floor'][side]['x'])
        ceiling = int(rec['ceiling'][side]['x']) if rec['ceiling'] else 0x28
        minimum_floor = min(minimum_floor, floor)
        maximum_ceiling = max(maximum_ceiling, ceiling)
    clear = (jet.x+3 <= minimum_floor) and (jet.x-3 > maximum_ceiling)
    return clear, (maximum_ceiling, minimum_floor), indices
