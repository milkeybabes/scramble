"""Konami Scramble 1981: stage 2 UFOs and stage 3 fireballs (native Python).

Scott Tunstall's annotated source:
  $25CC-$2608  UFO 64-tick spawn, raw X=$88, raw Y=(R&$0F)+9
  $2674-$26B0  Fireball 16-tick spawn, raw X=(R&$7F)+$30, raw Y=8
  $1D84-$1E19  UFO lifecycle, signed movement path, 43-tick explosion
  $1EC6-$1F34  Fireball lifecycle/path, shared UFO explosion handler
  $205E-$20DD  Enemy/ship collision (8-bit signed-window logic)
  $2166-$21C9  Bullet/UFO collision, 100 pts
  $23C9-$2433  Bomb/UFO collision, 100 pts

The UFO's 74 signed movement pairs and fireball's (0,4) delta have been
EXTRACTED from the parent game ROM and are exact. The spawn phase and Z80
R-register sample are not known instruction-for-instruction; the seeded
7-bit sequence below is a deterministic stand-in, NOT a MAME-identical R
register trace. This is intentionally native game logic, not CPU emulation.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json
from scramble_objects import AnimationCollection, Animation

PATH_DATA = Path(__file__).resolve().parent / 'data' / 'enemy_paths.json'
raw = json.loads(PATH_DATA.read_text(encoding='utf-8'))
UFO_PATH = tuple((int(x), int(y)) for x, y in raw['ufo']['deltas'])
FIREBALL_PATH = tuple((int(x), int(y)) for x, y in raw['fireball']['deltas'])
if len(UFO_PATH) != 74 or UFO_PATH[:3] != ((-1,0),(-2,0),(-2,0)) or FIREBALL_PATH != ((0,4),):
    raise ValueError('Enemy path data does not match the original Scramble ROM')

MAX_INFLIGHT = 4
UFO_FLAG = 2
FIREBALL_FLAG = 1


class RefreshSample:
    """Repeatable *approximation* of a sampled Z80 refresh register.

    The original refresh register advances with Z80 opcode fetches, not just
    game frames. Its exact value needs a synchronized MAME trace. A 7-bit
    full-period LCG gives varied, reproducible starts without inventing an
    independent movement AI. The supplied seed controls testing only.
    """
    def __init__(self, seed: int = 0):
        self.seed = int(seed) & 0x7f
        self.value = self.seed

    def read(self) -> int:
        self.value = (self.value * 73 + 41) & 0x7f
        return self.value

    def reset(self):
        self.value = self.seed


@dataclass
class Alien:
    kind: str = ''
    active: bool = False
    exploding: bool = False
    stage: int = 0  # arcade: 0 initialise, 1 flying, 6 explosion init, 7 explosion
    x: int = 0     # original Z80 X = visual vertical coordinate
    y: int = 0     # original Z80 Y = visual horizontal coordinate
    path_index: int = 0
    animation: Animation | None = None
    visible: bool = False
    explosion_counter: int = 0
    launch_frame: int = 0
    refresh_value: int = 0

    @property
    def screen_xy(self) -> tuple[int, int]:
        # Original $1FA6 sprite positioning mapped through ROT90.
        # Keep signed display coordinate for correct left-edge clipping.
        return 230 - self.y, self.x - 7

    def clear(self):
        self.kind = ''
        self.active = self.exploding = self.visible = False
        self.stage = self.x = self.y = self.path_index = 0
        self.animation = None
        self.explosion_counter = 0
        self.launch_frame = self.refresh_value = 0

    def hit(self):
        self.active = False
        self.exploding = True
        self.stage = 6
        self.animation = None
        self.visible = False
        self.explosion_counter = 0


class FlyingAliens:
    def __init__(self, animations: AnimationCollection | None = None, seed: int = 0):
        self.animations = animations or AnimationCollection()
        self.refresh = RefreshSample(seed)
        self.slots = [Alien() for _ in range(MAX_INFLIGHT)]
        self.spawns = 0
        self.ufo_spawns = 0
        self.fireball_spawns = 0
        self.bullet_hits = 0
        self.bomb_hits = 0
        self.ship_hits = 0
        self.spawn_log = []

    def reset(self, *, reset_seed: bool = False):
        for a in self.slots:
            a.clear()
        if reset_seed:
            self.refresh.reset()
        self.spawns = self.ufo_spawns = self.fireball_spawns = 0
        self.bullet_hits = self.bomb_hits = self.ship_hits = 0
        self.spawn_log.clear()

    @property
    def active_count(self):
        return sum(a.active for a in self.slots)

    @property
    def occupied_count(self):
        return sum(a.active or a.exploding for a in self.slots)

    @staticmethod
    def enabled(stage_flags: int):
        return stage_flags in (UFO_FLAG, FIREBALL_FLAG)

    def spawn(self, *, stage_flags: int, timing: int, reserved_slots: int = 0):
        """Original stage gates / $425F timer masks / four slot capacity.

        The exact R register byte at this call is not yet trace-matched.
        """
        if stage_flags == UFO_FLAG:
            kind, interval = 'ufo', 64
        elif stage_flags == FIREBALL_FLAG:
            kind, interval = 'fireball', 16
        else:
            return None
        if timing & (interval - 1):
            return None
        if self.occupied_count + reserved_slots >= MAX_INFLIGHT:
            return None
        a = next((a for a in self.slots if not (a.active or a.exploding)), None)
        if a is None:
            return None
        sample = self.refresh.read()
        a.clear()
        a.kind = kind
        a.active = True
        a.stage = 0
        a.launch_frame = timing
        a.refresh_value = sample
        if kind == 'ufo':
            a.x = 0x88
            a.y = (sample & 0x0f) + 9
            self.ufo_spawns += 1
        else:
            a.x = ((sample & 0x7f) + 0x30) & 0xff
            a.y = 8
            self.fireball_spawns += 1
        self.spawns += 1
        self.spawn_log.append((timing, kind, sample, a.x, a.y))
        return a

    def move(self, *, stage_flags: int, scrolling: bool = True):
        """Translated from $1D9D/$1EDF with path pointer increment per frame."""
        expected = {UFO_FLAG: 'ufo', FIREBALL_FLAG: 'fireball'}.get(stage_flags)
        for a in self.slots:
            if not (a.active or a.exploding):
                continue
            # Source only executes a stage's enemy handler while those flags
            # are enabled. Previous-stage entities are no longer rendered;
            # release their slot at a transition in the native implementation.
            if a.kind != expected:
                a.clear()
                continue
            if a.stage == 0:
                a.animation = self.animations.play(a.kind)
                a.visible = False
                a.stage = 1
                a.path_index = 0
                # FIREBALL_INIT $1F18 falls directly through to ANIMATE;
                # UFO_INIT $1DD3 waits until the following update.
                if a.kind == 'ufo':
                    continue
            if a.stage == 6:
                a.animation = self.animations.play('ufo_explosion')
                a.explosion_counter = 0x2B
                a.visible = False
                a.stage = 7
                continue
            if a.animation is not None:
                if a.visible:
                    a.animation.step()
                a.visible = True
            if a.stage == 1:
                path = UFO_PATH if a.kind == 'ufo' else FIREBALL_PATH
                dx, dy = path[a.path_index]
                a.x = (a.x + dx) & 0xff
                a.y = (a.y + dy) & 0xff
                a.path_index = (a.path_index + 1) % len(path)
                # UFO and fireball don't inherit ground scroll: unlike
                # launched rockets, $1DD6 follows only the ROM path.
                if a.y >= 0xF0:
                    a.clear()
            elif a.stage == 7:
                a.explosion_counter -= 1
                if a.explosion_counter <= 0:
                    a.clear()
                elif scrolling:
                    a.y = (a.y + 1) & 0xff  # $1E14 explosion drift

    @staticmethod
    def touches_ship(a: Alien, jet) -> bool:
        return (a.active and
                ((jet.x - a.x + 6) & 0xff) < 13 and
                ((jet.y + 4 - a.y + 13) & 0xff) < 25)

    @staticmethod
    def touches_bullet(a: Alien, bullet) -> bool:
        # Only UFOs are destroyed by player projectiles: source $2166.
        return (a.kind == 'ufo' and a.active and bullet.active and
                ((bullet.x - a.x + 3) & 0xff) < 7 and
                ((bullet.y - a.y + 4) & 0xff) < 9)

    @staticmethod
    def touches_bomb(a: Alien, bomb) -> bool:
        return (a.kind == 'ufo' and a.active and bomb.active and bomb.stage == 1 and
                ((bomb.x - a.x + 5) & 0xff) < 11 and
                ((bomb.y - a.y + 6) & 0xff) < 13)

    def hit_ship(self, jet) -> bool:
        for a in self.slots:
            if self.touches_ship(a, jet):
                a.hit()
                self.ship_hits += 1
                return True
        return False

    def hit_bullets(self, bullets) -> int:
        hits = 0
        for bullet in bullets.slots:
            for a in self.slots:
                if self.touches_bullet(a,bullet):
                    bullet.active = False
                    bullets.hits += 1
                    a.hit()
                    self.bullet_hits += 1
                    hits += 1
                    break
        return hits

    def hit_bombs(self, bombs) -> int:
        hits = 0
        for bomb in bombs.slots:
            for a in self.slots:
                if self.touches_bomb(a,bomb):
                    bomb.explode()
                    bombs.hits += 1
                    a.hit()
                    self.bomb_hits += 1
                    hits += 1
                    break
        return hits

    def render(self, bank, surface):
        for a in self.slots:
            if (a.active or a.exploding) and a.visible and a.animation is not None:
                sx, sy = a.screen_xy
                if -16 < sx < 224 and -16 < sy < 256:
                    f = a.animation.current
                    bank.sprite(surface,sx,sy,f.code,f.colour)
