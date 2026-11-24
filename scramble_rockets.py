"""Konami Scramble 1981: original launched-ground-rocket handler (native Python).

Primary source: Scott Tunstall's scramble.asm:
  $260C-$2673  launch request, stage flag gate, 64-tick cadence, four slots
  $1C98-$1D70  rocket lifecycle, movement, sprite animation, disappearance
  $20F4-$2112  rocket versus ship
  $2346-$238E  bullet versus rocket (80 points)
  $2494-$251D  bomb versus rocket (80 points)

The 8-slot ground-object allocation and the original timing-variable startup
phase are approximated by the current unwrapped world representation. No Z80
or raster hardware is emulated. Original raw-byte hit inequalities, velocities,
slot limits, frame art and 63-update explosion lifetime are retained.
"""
from __future__ import annotations
from dataclasses import dataclass
from scramble_objects import AnimationCollection, Animation

MAX_FLYING_ROCKETS = 4
LAUNCH_INTERVAL = 64
ROCKET_STAGES_FLAGS = (0, 8)   # landscapes 1 and 4


@dataclass
class FlyingRocket:
    active: bool = False
    exploding: bool = False
    stage: int = 0                # original StageOfLife = 0 init, 1 moving, 6 explode init, 7 explode
    x: int = 0                   # Z80 INFLIGHT_ENEMY.X: upright vertical axis
    y: int = 0                   # Z80 INFLIGHT_ENEMY.Y: upright horizontal axis
    animation: Animation | None = None
    visible: bool = False
    explosion_counter: int = 0
    source: tuple[int, int] | None = None

    @property
    def screen_xy(self) -> tuple[int, int]:
        # Shared $1FA6 sprite projection, rotated to upright screen axes.
        # IMPORTANT: do not wrap the display coordinate modulo 256.  The raw
        # Z80 Y byte is unsigned, but a rocket exiting screen-left must be
        # rendered at x=-1, -2, ... so pygame clips its 16px sprite instead
        # of jumping to x=255 and disappearing.  Source $1D11-$1D1F retires
        # a flying rocket when raw Y >= $F0 (display x ~ -10).
        return 230 - self.y, self.x - 7

    def clear(self):
        self.active = self.exploding = self.visible = False
        self.stage = 0
        self.animation = None
        self.explosion_counter = 0
        self.source = None

    def hit(self, animations: AnimationCollection):
        self.active = False
        self.exploding = True
        self.stage = 6
        self.animation = None
        self.explosion_counter = 0
        self.visible = False


class FlyingRockets:
    def __init__(self, animations: AnimationCollection | None = None):
        self.animations = animations or AnimationCollection()
        self.slots = [FlyingRocket() for _ in range(MAX_FLYING_ROCKETS)]
        self.launches = 0
        self.bullet_hits = 0
        self.bomb_hits = 0
        self.ship_hits = 0

    def reset(self):
        for rocket in self.slots:
            rocket.clear()
        self.launches = self.bullet_hits = self.bomb_hits = self.ship_hits = 0

    @property
    def active_count(self):
        return sum(r.active for r in self.slots)

    @staticmethod
    def enabled(stage_flags: int) -> bool:
        return stage_flags in ROCKET_STAGES_FLAGS

    @staticmethod
    def raw_from_target(target, screen_x: int) -> tuple[int, int]:
        """Ground object $18EF: project current scenery target into Z80 bytes.

        16x16 target top-left as existing scene defines it. Hardware's ground
        object CharRAM pointer is not recreated, so this is a screen-projected
        estimate to be calibrated with MAME (usually within one pixel).
        """
        return ((target.y + 7) & 0xFF, (230 - screen_x) & 0xFF)

    def launch(self, *, stage_flags: int, timing: int, course, world_scroll: int,
               destroyed: set[tuple[int, int]], stage_idx: int | None = None):
        """$260C: test 64-update cadence, first eligible ground rocket, free slot.

        The arcade keeps up to eight active ground-object slots; our stage data
        is a continuous world map. Restrict to the first eight visible targets
        (oldest/leftmost first) to approximate its current allocation order.
        """
        if not self.enabled(stage_flags) or timing & (LAUNCH_INTERVAL-1):
            return None
        free = next((r for r in self.slots if not (r.active or r.exploding)), None)
        if free is None:
            return None
        # Ground-object ROM order is earliest world X first, matching entry
        # order in the normal scrolling direction.
        present = []
        for i, stage in enumerate(course.stages):
            for target in stage.targets:
                key = (i, target.record_index)
                if key in destroyed:
                    continue
                sx = course.target_world_x(i,target) - world_scroll
                if -16 < sx < 224:
                    present.append((sx,i,target))
        present.sort(key=lambda tup: tup[0])
        for sx,i,target in present[:8]:
            if target.kind != 'ROCKET':
                continue
            if stage_idx is not None and i != stage_idx:
                # Source checks LANDSCAPE_FLAGS, not target's stage; while
                # the producer changes at a seam the next stage has no rocket
                # launches unless it is itself a rocket stage.
                continue
            x,y = self.raw_from_target(target,sx)
            # Exact $2635: 0x60 <= GROUND_OBJECT.Y < 0xE8
            if not (0x60 <= y < 0xE8):
                continue
            free.clear()
            free.active = True
            free.stage = 0   # $266C: initialise animation on next update
            free.x, free.y = x,y
            free.source = (i,target.record_index)
            self.launches += 1
            destroyed.add(free.source)  # $2654: remove stationary rocket graphic
            return free
        return None

    def move(self, *, scrolling: bool = True):
        """$1CE3-$1D55: init, animate and move -1 raw X per update.

        When background scroll increments, original raw Y increments too,
        which projects to moving one display pixel left. Rocket explosions
        share the same scrolling offset and last 63 updates.
        """
        for r in self.slots:
            if not (r.active or r.exploding):
                continue
            if r.stage == 0:
                r.animation = self.animations.play('rocket')
                r.visible = False
                r.stage = 1
                continue
            if r.stage == 6:
                r.animation = self.animations.play('rocket_explosion')
                r.explosion_counter = 0x3F
                r.visible = False
                r.stage = 7
                continue
            if r.animation is not None:
                if r.visible:
                    r.animation.step()
                r.visible = True
            if r.stage == 1:
                r.x = (r.x - 1) & 0xff  # $1D70: FF 00 delta, straight up
                if scrolling:
                    r.y = (r.y + 1) & 0xff
                if r.y >= 0xf0 or r.x < 0x28:
                    r.clear()
            elif r.stage == 7:
                r.explosion_counter -= 1
                if r.explosion_counter <= 0:
                    r.clear()
                elif scrolling:
                    r.y = (r.y + 1) & 0xff

    @staticmethod
    def touches_ship(r: FlyingRocket, jet) -> bool:
        # Source $207F-$2096. Byte wrap is deliberate.
        return (r.active and
                ((jet.x - r.x + 6) & 0xff) < 13 and
                ((jet.y + 4 - r.y + 13) & 0xff) < 25)

    @staticmethod
    def touches_bullet(r: FlyingRocket, bullet) -> bool:
        # $2361-$2376, 11x7 raw-byte hit region.
        return (r.active and bullet.active and
                ((bullet.x - r.x + 5) & 0xff) < 11 and
                ((bullet.y - r.y + 3) & 0xff) < 7)

    @staticmethod
    def touches_bomb(r: FlyingRocket, bomb) -> bool:
        # $24EA-$24FF, 13x9 raw-byte hit region.
        return (r.active and bomb.active and bomb.stage == 1 and
                ((bomb.x - r.x + 6) & 0xff) < 13 and
                ((bomb.y - r.y + 4) & 0xff) < 9)

    def hit_ship(self, jet) -> bool:
        for r in self.slots:
            if self.touches_ship(r,jet):
                r.hit(self.animations)  # $2097: enemy also starts exploding
                self.ship_hits += 1
                return True
        return False

    def hit_bullets(self, bullets) -> int:
        count = 0
        for bullet in bullets.slots:
            for r in self.slots:
                if self.touches_bullet(r,bullet):
                    bullet.active = False
                    bullets.hits += 1
                    self.bullet_hits += 1
                    r.hit(self.animations)
                    count += 1
                    break
        return count

    def hit_bombs(self, bombs) -> int:
        count = 0
        for bomb in bombs.slots:
            for r in self.slots:
                if self.touches_bomb(r,bomb):
                    bomb.explode()
                    bombs.hits += 1
                    self.bomb_hits += 1
                    r.hit(self.animations)
                    count += 1
                    break
        return count

    def render(self, bank, surface, colour: int):
        for r in self.slots:
            if (r.active or r.exploding) and r.visible and r.animation:
                sx,sy=r.screen_xy
                if -16 < sx < 224 and 30 < sy < 240:
                    f=r.animation.current
                    bank.sprite(surface,sx,sy,f.code,(colour if r.active else f.colour))
