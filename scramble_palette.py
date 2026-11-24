"""Scramble (1981) original per-character-row colour attribute data.

Each pixel colour is chosen from one of 8 groups in the 32-byte PROM. The
hardware's 32 *columns* become 32 horizontal character *rows* after ROT90.

The original Z80 sets the 32 attributes in two ways:
  $0AD9/$0AE9   load the fixed initial/play HUD attributes
  $1F44-$1F58   overwrite attributes 5..29 with LANDSCAPE_COLOUR
  $12AB/$0B89   use a separate 32-byte table for completion messages

Thus HUD FUEL at $4B5E (raw column $1E/row 30) stays palette 1 regardless
of landscape changes. Character-based ground fuel tanks are in the moving
playfield and intentionally share the landscape's current colour selection.
No video memory or graphics hardware emulation is needed; this module only
indexes the original byte data.
"""
from __future__ import annotations

# Source: Scott Tunstall scramble.asm $0AE9, 32 literal bytes.
GAMEPLAY_BASE_ATTRIBUTES = (
    0x00, 0x05, 0x00, 0x07, 0x07, 0x01, 0x06, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x06,
)

# Source: scramble.asm $0B89, loaded by the mission-complete routine $12BD.
MISSION_COMPLETE_ATTRIBUTES = (
    0x00, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01,
    0x02, 0x02, 0x03, 0x03, 0x04, 0x04, 0x05, 0x05,
    0x06, 0x06, 0x07, 0x07, 0x01, 0x01, 0x02, 0x02,
    0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x06,
)

PLAYFIELD_FIRST_ROW = 5
PLAYFIELD_LAST_ROW = 29


def column_colour(raw_column: int, landscape_colour: int = 0, *,
                  mission_complete: bool = False) -> int:
    """One of eight colour groups for a raw 0..31 character column.

    In ROT90 display orientation this is the *vertical* 8-pixel row index.
    Gameplay changes only raw columns 5..29. HUD rows are fixed.
    """
    if not 0 <= raw_column < 32:
        raise ValueError('Scramble character column out of range')
    if not 0 <= landscape_colour < 8:
        raise ValueError('Scramble landscape palette out of range')
    if mission_complete:
        return MISSION_COMPLETE_ATTRIBUTES[raw_column]
    if PLAYFIELD_FIRST_ROW <= raw_column <= PLAYFIELD_LAST_ROW:
        return landscape_colour
    return GAMEPLAY_BASE_ATTRIBUTES[raw_column]


def character_colour(address: int, landscape_colour: int = 0, *,
                     mission_complete: bool = False) -> int:
    """Colour-group index for an original $4800-$4BFF VRAM character."""
    if not 0x4800 <= address < 0x4C00:
        raise ValueError(f'Invalid Scramble character address ${address:04X}')
    return column_colour((address - 0x4800) & 31, landscape_colour,
                         mission_complete=mission_complete)


def screen_y_colour(y: int, landscape_colour: int = 0) -> int:
    """Select attribute from logical 224x256 ROT90 screen Y in pixels."""
    if not 0 <= y < 256:
        raise ValueError('Screen Y must be 0..255')
    return column_colour(y // 8, landscape_colour)


def gameplay_attributes(landscape_colour: int) -> tuple[int, ...]:
    """Result of the source $1F44 loop applied to source $0AE9."""
    return tuple(column_colour(i, landscape_colour) for i in range(32))


# Main game's landscape colours.  $2804 tests the 8-bit TIMING_VARIABLE
# for zero; $280C increments its counter, and $280E changes colours on
# every OTHER zero crossing.  That yields a 256*2 = 512-frame cadence.
# $2817-$281F skips palette 1, but palette 1 remains in use by FUEL HUD.
# The initial phase depends on prior attract/startup timing; the first delay
# below is calibrated against the supplied reference playthrough, where the
# opening pink terrain changes to blue around 1.9-2.0 seconds into active play.
# It is an initial-phase visual match, not a claimed exact MAME reset trace.
DEFAULT_LANDSCAPE_COLOUR = 0
COLOUR_CYCLE_FRAMES = 512
INITIAL_CHANGE_FRAMES = 120


def next_landscape_colour(current: int) -> int:
    """Original $2810-$281F: 0 -> 2 -> 3 -> ... -> 7 -> 0."""
    if not 0 <= current <= 7:
        raise ValueError('Landscape colour must be 0..7')
    result = (current + 1) & 7
    return 2 if result == 1 else result
