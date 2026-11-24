"""Native Scramble drawing primitives: ROM-defined animations, tiles and sprites.

No Z80 execution. Uses 8 pre-rendered colour atlases from Phase 1.
Ground targets follow the *original* $085E renderer: one group code = four
consecutive 8x8 chars. Each individual atlas tile was rotated clockwise
for the normal desktop display, so the 2x2 group must also be rearranged.

Sources: Scott Tunstall, scramble.asm $085E, $13E4, $1F59, $1F8A;
         MAME scramble_charlayout, scramble_spritelayout and ROT90.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"

# Row-major order AFTER clockwise rotation of original four tile cells:
# hardware original [0 1]       desktop orientation [2 0]
#                   [2 3]                           [3 1]
ROTATED_GROUP_ORDER = (2, 0, 3, 1)


@dataclass(frozen=True)
class AnimationFrame:
    colour: int
    code: int
    delay: int


class Animation:
    """Direct translation of the frame selection/delay portion of ANIMATE $13E4.

    Movement, collisions and explosions are distinct game logic (future phase).
    `step()` is called once per *logical game update*, not once per drawing.
    """
    def __init__(self, frames: list[dict]):
        self.frames = tuple(AnimationFrame(int(d["colour"]), int(d["code"]), int(d["delay"]))
                            for d in frames)
        if not self.frames:
            raise ValueError("Animation must contain at least one frame")
        self.index = -1
        self.remaining = 0
        self.step()  # initialise as the real routine does when counter is zero

    def step(self) -> None:
        if self.remaining:
            self.remaining -= 1
        else:
            self.index = (self.index + 1) % len(self.frames)
            self.remaining = self.frames[self.index].delay

    @property
    def current(self) -> AnimationFrame:
        return self.frames[self.index]


class AnimationCollection:
    def __init__(self, path: Path = DATA / "animations.json"):
        self.raw = json.loads(path.read_text(encoding="utf-8"))["animations"]

    def play(self, name: str) -> Animation:
        return Animation(self.raw[name]["frames"])

    def kind(self, name: str) -> str:
        return str(self.raw[name]["kind"])


class SpriteCharacterBank:
    """Use after pygame.display.set_mode; pygame-ce loaded inside this method."""
    def __init__(self, data_dir: Path = DATA):
        import pygame
        self.pg = pygame
        self.chars = [pygame.image.load(str(data_dir / f"characters_color_{p}.png")).convert_alpha()
                      for p in range(8)]
        self.sprites = [pygame.image.load(str(data_dir / f"sprites_color_{p}.png")).convert_alpha()
                        for p in range(8)]

    def character(self, surface, x: int, y: int, code: int, colour: int):
        """Draw one already-rotated 8x8 character on logical screen."""
        if not 0 <= code < 256 or not 0 <= colour < 8:
            raise ValueError("Character code/palette outside range")
        self._blit(self.chars[colour], surface, x, y, code, 8, 16)

    def sprite(self, surface, x: int, y: int, code: int, colour: int):
        """Draw 16x16 sprite with high-bit hardware flips transformed for ROT90."""
        if not 0 <= code < 256 or not 0 <= colour < 8:
            raise ValueError("Sprite code/palette outside range")
        base_code = code & 0x3F
        rect = self.pg.Rect((base_code % 8) * 16, (base_code // 8) * 16, 16, 16)
        src = self.sprites[colour].subsurface(rect)
        if code & 0xC0:
            # Hardware flipx(bit6) -> desktop flipy; flipy(bit7) -> flipx.
            src = self.pg.transform.flip(src, bool(code & 0x80), bool(code & 0x40))
        surface.blit(src, (x, y))

    @staticmethod
    def _blit(atlas, surface, x, y, code, size, columns):
        rect = (code % columns * size, code // columns * size, size, size)
        surface.blit(atlas, (x, y), rect)

    def ground_object(self, surface, x: int, y: int, group_code: int, colour: int):
        """Exactly four chars per ground object; original source multiplies code by 4.

        Colour comes from the *character column attribute*, not each object's
        animation colour. Pass the active landscape/column colour explicitly.
        """
        if not 0 <= group_code < 64:
            raise ValueError(f"Not a valid ground group ${group_code:02X}")
        base = group_code * 4
        self.character(surface, x,     y,     base + ROTATED_GROUP_ORDER[0], colour)
        self.character(surface, x + 8, y,     base + ROTATED_GROUP_ORDER[1], colour)
        self.character(surface, x,     y + 8, base + ROTATED_GROUP_ORDER[2], colour)
        self.character(surface, x + 8, y + 8, base + ROTATED_GROUP_ORDER[3], colour)

    def text(self, surface, x: int, y: int, value: str, colour: int):
        """Simple native character ROM text (used for demonstration only)."""
        for i, ch in enumerate(value.upper()):
            if ch == " ":
                code = 0x10
            elif "0" <= ch <= "9":
                code = ord(ch) - ord("0")
            elif "A" <= ch <= "Z":
                code = ord(ch) - ord("A") + 0x11
            else:
                code = 0x10
            self.character(surface, x + i*8, y, code, colour)
