"""Scramble (1981) native player bombs -- translated from the annotated Z80.

$26B1-$26F9  : button-2 rising edge; two bomb slots.
$1A30-$1AA7  : bomb init and per-update animation / movement.
$1578-$15A4  : follow the ROM's signed (X,Y) delta pairs.
$1AD8         : sprite animation, colour 6, codes $21-$25.
$2434-$2491  : ground target collision (native-screen conversion).
$251E-$2562  : terrain extent collision; circular buffer phase still
               approximated using the original unwrapped ROM records.

$1AAC-$1AD5 : a hit initiates the original 35-update, four-frame bomb
               explosion, which occupies its bomb slot until completion.
No Z80, sprite hardware or ROM is required at runtime.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path
from scramble_objects import AnimationCollection, Animation

MAX_PLAYER_BOMBS = 2


def load_original_path(path: Path | None = None) -> tuple[tuple[int, int], ...]:
    """Read extracted source ROM path deltas, one pair per game update."""
    if path is None:
        path = Path(__file__).resolve().parent / 'data' / 'bomb_path.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    deltas = tuple((int(dx), int(dy)) for dx, dy in data['deltas'])
    if len(deltas) != 203 or deltas[:3] != ((0,0),(1,0),(0,-1)):
        raise ValueError('Unexpected Scramble original bomb flight path')
    if any(dx not in (0,1) or dy not in (-1,0) for dx,dy in deltas):
        raise ValueError('Unexpected flight-path delta')
    return deltas


ORIGINAL_BOMB_PATH = load_original_path()


@dataclass
class Bomb:
    active: bool = False
    stage: int = 0   # 0 = initialisation, 1 = flight
    x: int = 0     # original PLAYER_BOMB.X = visual vertical coordinate
    y: int = 0     # original PLAYER_BOMB.Y = visual horizontal coordinate
    path_index: int = 0
    animation: Animation | None = None
    visible: bool = False
    exploding: bool = False
    explosion_counter: int = 0

    @property
    def screen_xy(self) -> tuple[int, int]:
        """Screen top-left via original $1FA6 / MAME ROT90 sprite projection."""
        return 230 - self.y, self.x - 7

    @property
    def screen_center(self) -> tuple[int, int]:
        sx,sy = self.screen_xy
        return sx+8,sy+8

    def deactivate(self) -> None:
        self.active = False
        self.exploding = False
        self.visible = False
        self.stage = 0
        self.animation = None
        self.explosion_counter = 0

    def explode(self) -> None:
        """$241D/$2482/$2510/$2553: change flight into explosion init.

        The next animation/movement update executes $1AAC; it doesn't make
        the slot available yet. The explosion is not another projectile.
        """
        if not self.active or self.exploding:
            return
        self.active = False
        self.exploding = True
        self.stage = 6
        self.animation = None
        self.visible = False
        self.explosion_counter = 0


class PlayerBombs:
    def __init__(self, path: tuple[tuple[int, int], ...] = ORIGINAL_BOMB_PATH):
        self.path = tuple(path)
        self.animations = AnimationCollection()
        self.slots = [Bomb() for _ in range(MAX_PLAYER_BOMBS)]
        self.bomb_held = False
        self.bombs_dropped = 0
        self.hits = 0
        self.terrain_impacts = 0

    def reset(self):
        for bomb in self.slots:
            bomb.deactivate()
            bomb.x = bomb.y = bomb.path_index = 0
        self.bomb_held = False
        self.bombs_dropped = 0
        self.hits = self.terrain_impacts = 0

    @property
    def active_count(self) -> int:
        return sum(bomb.active for bomb in self.slots)

    @property
    def occupied_count(self) -> int:
        """$26E3 checks both IsActive and IsExploding when finding a slot."""
        return sum(bomb.active or bomb.exploding for bomb in self.slots)

    def spawn_on_press(self, pressed: bool) -> bool:
        """$26B1: first free slot, only on rising edge; init is next update."""
        pressed = bool(pressed)
        rising = pressed and not self.bomb_held
        self.bomb_held = pressed
        if not rising:
            return False
        for bomb in self.slots:
            if not (bomb.active or bomb.exploding):
                bomb.active = True
                bomb.exploding = False
                bomb.explosion_counter = 0
                bomb.stage = 0
                bomb.visible = False
                bomb.path_index = 0
                bomb.animation = None
                self.bombs_dropped += 1
                return True
        return False

    def move(self, jet, *, scrolling: bool = False) -> None:
        """$1A30: flight and the independent $1AAC/$1AC0 explosion stages.

        `scrolling` follows the landscape scroll event: the explosion drifts
        one display pixel left when the world scrolls, unless scrolling stops.
        """
        for bomb in self.slots:
            if not (bomb.active or bomb.exploding):
                continue
            if bomb.stage == 6:
                bomb.animation = self.animations.play('bomb_explosion')
                bomb.explosion_counter = 0x23  # original $1AB9 = 35 updates
                bomb.visible = False
                bomb.stage = 7
                continue
            if bomb.stage == 7:
                if bomb.animation is not None:
                    if bomb.visible:
                        bomb.animation.step()
                    bomb.visible = True
                bomb.explosion_counter -= 1
                if bomb.explosion_counter <= 0:
                    bomb.deactivate()
                elif scrolling:
                    bomb.y = (bomb.y + 1) & 0xff  # $1AD2
                continue
            if bomb.stage == 0:
                bomb.x = (jet.x + 4) & 0xff
                bomb.y = (jet.y + 8) & 0xff
                bomb.path_index = 0
                # $1A84 initialises AnimationCounter to zero; the sprite
                # becomes visible when ANIMATE is called in the next update.
                bomb.animation = self.animations.play('player_bomb')
                bomb.visible = False
                bomb.stage = 1
                continue
            if bomb.animation is not None:
                if bomb.visible:
                    bomb.animation.step()
                bomb.visible = True
            dx,dy = self.path[bomb.path_index]
            bomb.x = (bomb.x + dx) & 0xff
            bomb.y = (bomb.y + dy) & 0xff
            bomb.path_index = (bomb.path_index + 1) % len(self.path)
            if bomb.x >= 0xf0:
                bomb.deactivate()  # $1A9A: bottom screen termination

    @staticmethod
    def ground_hit(bomb: Bomb, world_scroll: int,
                   target_world_x: int, target_top: int) -> bool:
        """$245B: 14x14 raw-byte collision window projected to upright screen.

        Target centres currently come from the unwrapped terrain target atlas,
        whose precise original circular-buffer offset remains to verify.
        """
        tx = target_world_x-world_scroll
        if not (-16 < tx < 224):
            return False
        sx,sy = bomb.screen_center
        tx += 8
        ty = target_top+8
        return -7 <= sx-tx < 7 and -7 <= sy-ty < 7

    def ground_hits(self, course, world_scroll: int, destroyed: set) -> list:
        """$2434: ground objects before terrain, points handled by the game."""
        hits=[]
        for bomb in self.slots:
            if not bomb.active or bomb.stage != 1:
                continue
            sx,_ = bomb.screen_center
            for i,target,tx,key in course.nearby_targets(world_scroll):
                if key in destroyed:
                    continue
                if abs((tx-world_scroll+8)-sx) > 7:
                    continue
                if self.ground_hit(bomb,world_scroll,tx,target.y):
                    bomb.explode()
                    self.hits+=1
                    destroyed.add(key)
                    hits.append((i,target,tx))
                    break
        return hits

    def terrain_hits(self, course, world_scroll: int) -> int:
        """$2531 terrain extents. Record lookup approximate until MAME parity."""
        n=0
        for bomb in self.slots:
            if not bomb.active or bomb.stage != 1:
                continue
            sx,_=bomb.screen_xy
            wx = world_scroll + sx + 8
            if wx < course.prefill_width:
                floor, ceiling = 0xc9,0x28
            elif wx >= course.total_width:
                continue
            else:
                idx = course.find_stage(wx)
                stage = course.stages[idx]
                local = wx-course.starts[idx]
                rec = stage.records[min(len(stage.records)-1, local//16)]
                side = (local//8)&1
                floor = int(rec['floor'][side]['x'])
                ceiling = int(rec['ceiling'][side]['x']) if rec['ceiling'] else 0x28
            if bomb.x > floor or bomb.x <= ceiling:
                bomb.explode()
                n+=1
        self.terrain_impacts += n
        return n
