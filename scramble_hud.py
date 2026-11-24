"""Original Scramble heads-up display, translated to indexed Python tile drawing.

Source: Scott Tunstall scramble.asm:
  $0223..$0262  1UP blink
  $03E8..$0433  packed-BCD scores and leading zero suppression
  $04EC           HIGH SCORE text at character address $4A80
  $0521           FUEL text at character address $4B5E
  $0880..$08B5  fuel cells at $4ABE
  $08FB..$091F  reserve jets at $4BBF
  $0920..$093D  mission flags at $485F
  $093E..$09A8  progress bar from $4B63, $4B64

This draws the real characters at the original addresses. Score and fuel now
receive player-bullet hit rewards; lives reflect actual reserve-life state.
"""
from __future__ import annotations

from dataclasses import dataclass
from scramble_palette import character_colour

# Original 24 character codes from $097F and $09A0.
PROGRESS_HEADERS = (
    0x50, 0x51, 0x52, 0x6D,
    0x53, 0x54, 0x55, 0x6D,
    0x56, 0x57, 0x55, 0x6D,
    0x58, 0x59, 0x5A, 0x6D,
    0x5B, 0x59, 0x5A, 0x6D,
    0x64, 0x65, 0x51, 0x66,
)
PURPLE_CELL = (0x6E, 0x6F, 0x6F, 0x80)
RED_CELL = (0x81, 0x82, 0x82, 0x83)


def character_xy(addr: int) -> tuple[int, int]:
    """Original $4800..$4BFF VRAM address -> upright 224x256 display.

    Galaxian uses 32*32 character RAM, with 90-degree clockwise ROT90.
    Only the original rows 2..29 (224px) are visible. A step of -$20
    therefore moves a glyph 8px to the right, as in original text routines.
    """
    if not 0x4800 <= addr <= 0x4BFF:
        raise ValueError(f'Invalid Scramble character RAM address ${addr:04X}')
    offset = addr - 0x4800
    row, column = divmod(offset, 32)
    return (29 - row) * 8, column * 8


def score_digits(value: int) -> str:
    """Original $0403: show up to 6 BCD digits, suppress first 4 zeros."""
    if not 0 <= value <= 999999:
        raise ValueError('Score must be in 0..999999')
    return f'{value:06d}'.lstrip('0').rjust(2,'0').rjust(6)


def fuel_codes(value: int) -> tuple[int, ...]:
    """Translate $0880-$08B5: fifteen full/partial/empty cells + final.

    The $0883 RRC A, $0885 AND $78, and three RRCA instructions produce
    fuel//16 full cells. The partial tile uses the lower 3 bits of fuel>>1.
    """
    if not 0 <= value <= 255:
        raise ValueError('Fuel must be in 0..255')
    full = value // 16
    partial = (0x3C, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9, 0xCA)[(value >> 1) & 7]
    return (0xCB,) * full + (partial,) + (0x3C,) * (15 - full)


@dataclass
class HUDValues:
    """Score, fuel and reserve lives are supplied by game state."""
    score: int = 0
    high_score: int = 10000
    fuel: int = 255
    lives: int = 3
    missions_completed: int = 0
    game_in_play: bool = False  # True enables the ROM's blinking 1UP label


def draw_hud(surface, bank, stage_index: int, frame: int,
             hud: HUDValues | None = None) -> None:
    if hud is None:
        hud = HUDValues()
    if not 0 <= stage_index <= 5:
        raise ValueError('Stage index must be in 0..5')
    pg = bank.pg

    # The original score + progress rows are 5 character columns tall.
    pg.draw.rect(surface, (0,0,0), (0,0,224,40))
    # FUEL at raw column 30, mission/lives at 31.
    pg.draw.rect(surface, (0,0,0), (0,240,224,16))

    def one(addr: int, code: int):
        bank.character(surface, *character_xy(addr), code, character_colour(addr))

    def text(addr: int, value: str):
        x, y = character_xy(addr)
        bank.text(surface, x, y, value, character_colour(addr))

    # Every HUD text/tile gets its colour from the ROM's 32-byte $0AE9
    # attribute table; the moving landscape is allowed to cycle separately.
    # Labels are sourced from the text pointer table, $04EC and $0223.
    # The original gameplay blinks 1UP when timing bit 4 is asserted;
    # phase currently approximate until game-start/NMI timing is matched.
    if not hud.game_in_play or ((frame // 16) & 1) == 0:
        text(0x4B40, '1UP')
    text(0x4A80, 'HIGH SCORE')

    # Packed-BCD score display $03E8: player and high score both end in 2 zeros
    # when zero, rather than printing the old mock-up's six leading zeroes.
    text(0x4B81, score_digits(hud.score))
    text(0x4A41, score_digits(hud.high_score))

    # Original 1ST..BASE headers and progress cells from $093E / $09A0.
    # 24 glyphs in a row; every set of 4 corresponds to one stage.
    # ROM rows 3 and 4 both use attribute group 7.
    for i, code in enumerate(PROGRESS_HEADERS):
        one(0x4B63 - i * 0x20, code)
    for i in range(24):
        tile_code = (RED_CELL if i//4 <= stage_index else PURPLE_CELL)[i%4]
        one(0x4B64 - i * 0x20, tile_code)

    text(0x4B5E, 'FUEL')
    for i, code in enumerate(fuel_codes(hud.fuel)):
        one(0x4ABE - i * 0x20, code)

    # $08FB: maximum six 2-character reserve jets.
    for i in range(min(max(int(hud.lives),0),6)):
        one(0x4BBF - i*0x40, 0x0A)
        one(0x4BBF - i*0x40 - 0x20, 0x0B)
    # $0920: original always shows one mission flag, plus completed loops.
    for i in range(min(max(hud.missions_completed,0)+1,16)):
        one(0x485F + i*0x20, 0x0E)
