"""Scramble player firing, using the original byte coordinates and four slots.

Source: Scott Tunstall scramble.asm $16AA-$16CF (movement), $1FE3-$202C
(video coordinates), $257F-$25CB (edge-triggered launch), $2217-$2269
(ground hits), and $238F-$23C8 (terrain hit test).

This is native Python game logic, NOT a CPU or video-hardware emulator.
The original 32-entry circular terrain-extent *phase* has not been validated
against MAME; the record-derived extent test here is an approximation of that
lookup. The intended coordinates, comparisons, and timing are retained.
"""
from __future__ import annotations
from dataclasses import dataclass


MAX_PLAYER_BULLETS = 4


@dataclass
class Bullet:
    active: bool = False
    x: int = 0  # raw PLAYER_BULLET.X, vertical on ROT90 screen
    y: int = 0  # raw PLAYER_BULLET.Y, horizontal on ROT90 screen

    @property
    def screen_xy(self) -> tuple[int, int]:
        """$1FFB-$2023, MAME scrambold_draw_bullets, ROT90 conversion.

        Original hardware renders a single yellow pixel. No sprite/bitmap
        scaling is applied until the complete 224x256 game screen is scaled.
        """
        return 239 - self.y, self.x - 1


class PlayerBullets:
    def __init__(self):
        self.slots = [Bullet() for _ in range(MAX_PLAYER_BULLETS)]
        self.fire_held = False
        self.shots_fired = 0
        self.hits = 0

    def reset(self) -> None:
        for slot in self.slots:
            slot.active = False
            slot.x = slot.y = 0
        self.fire_held = False
        self.shots_fired = 0
        self.hits = 0

    @property
    def active_count(self) -> int:
        return sum(b.active for b in self.slots)

    def move(self) -> None:
        """$16AA: 3 raw-coordinate pixels per update, no acceleration."""
        for bullet in self.slots:
            if bullet.active:
                bullet.y = (bullet.y - 3) & 0xff
                if bullet.y < 0x1f:
                    bullet.active = False

    def spawn_on_press(self, pressed: bool, jet) -> bool:
        """$257F: fire only on a 0->1 button transition, first unused slot."""
        pressed = bool(pressed)
        rising_edge = pressed and not self.fire_held
        self.fire_held = pressed
        if not rising_edge:
            return False
        for bullet in self.slots:
            if not bullet.active:
                bullet.active = True
                bullet.x = (jet.x + 2) & 0xff
                bullet.y = (jet.y - 7) & 0xff
                self.shots_fired += 1
                return True
        return False

    def terrain_hits(self, course, world_scroll: int) -> int:
        """$23A2 terrain-extent inequality on ROM record nearest bullet.

        The source's VRAM circular-buffer phase is not yet proven, so the
        *record selection* is an approximation; no ship deaths use it.
        """
        n = 0
        for bullet in self.slots:
            if not bullet.active:
                continue
            sx, _ = bullet.screen_xy
            wx = world_scroll + sx
            if wx < course.prefill_width:
                floor, ceiling = 0xc9, 0x28
            else:
                idx = course.find_stage(wx)
                stage = course.stages[idx]
                local = wx - course.starts[idx]
                if idx == len(course.stages)-1:
                    local %= stage.width
                rec = stage.records[local // 16]
                side = (local // 8) & 1
                floor = int(rec['floor'][side]['x'])
                ceiling = int(rec['ceiling'][side]['x']) if rec['ceiling'] else 0x28
            if bullet.x > floor or bullet.x <= ceiling:
                bullet.active = False
                n += 1
        return n

    @staticmethod
    def ground_hit(bullet: Bullet, world_scroll: int, target_world_x: int,
                   target_top: int) -> bool:
        """$2242: hit a narrow 9x15 region within a 16x16 ground target.

        Native-screen projection of the original +/-4 horizontal and +/-7
        vertical byte comparisons. Revisit exact offset at MAME parity stage.
        """
        sx, sy = bullet.screen_xy
        center_x = target_world_x - world_scroll + 8
        center_y = target_top + 7
        return abs(sx - center_x) <= 4 and abs(sy - center_y) <= 7

    def ground_hits(self, course, world_scroll: int, destroyed: set) -> list:
        """Return (stage, target) hits; caller applies gameplay side effects.

        Do not mutate score or remove scenery inside drawing logic.
        Target collision occurs before the terrain test in original $2036.
        """
        hits = []
        for bullet in self.slots:
            if not bullet.active:
                continue
            sx, _ = bullet.screen_xy
            for i,target,tx,key in course.nearby_targets(world_scroll):
                if key in destroyed:
                    continue
                if abs((tx-world_scroll+8)-sx) > 4:
                    continue
                if self.ground_hit(bullet,world_scroll,tx,target.y):
                    bullet.active = False
                    self.hits += 1
                    destroyed.add(key)
                    hits.append((i,target,tx))
                    break
        return hits
