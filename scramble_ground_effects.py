"""Original 16x16 character-based ground-target death animations.

Source: Scott Tunstall $1964-$19C3; ROM animation records $19E4,
$19F3, $1A02, $1A0C, $1A12. Four 8x8 characters per frame, not sprites.
"""
from __future__ import annotations
from dataclasses import dataclass
from scramble_objects import AnimationCollection, Animation


@dataclass
class GroundEffect:
    stage_index: int
    record_index: int
    world_x: int
    y: int
    kind: str
    duration: int
    animation: Animation

    @property
    def code(self) -> int:
        return self.animation.current.code

    def step(self) -> bool:
        """$19A7: animate and decrement lifetime; True while still alive."""
        self.animation.step()
        self.duration -= 1
        return self.duration > 0


class GroundEffects:
    def __init__(self, animations: AnimationCollection | None = None):
        self.animations = animations or AnimationCollection()
        self.active: dict[tuple[int, int], GroundEffect] = {}

    def reset(self) -> None:
        self.active.clear()

    def spawn(self, stage_index, target, world_x, points: int):
        """Change a hit target into its original explosion/points display.

        Non-mystery ground objects use $3F (63) update lifetime; mystery
        score images use $4F (79). A single new effect per target is allowed.
        """
        key = (stage_index, target.record_index)
        if key in self.active:
            return self.active[key]
        if target.kind == 'MYSTERY':
            if points not in (100, 200, 300):
                raise ValueError('Mystery points must be 100, 200 or 300')
            name = f'ground_mystery_{points}'
            duration = 0x4F
        elif target.kind == 'FUEL':
            name = 'ground_fuel_explosion'
            duration = 0x3F
        else:
            name = 'ground_explosion'
            duration = 0x3F
        effect = GroundEffect(stage_index, target.record_index, int(world_x),
                              target.y, target.kind, duration, self.animations.play(name))
        self.active[key] = effect
        return effect

    def step(self):
        for key, effect in tuple(self.active.items()):
            if not effect.step():
                del self.active[key]

    def render(self, bank, surface, scroll_px: int, landscape_colour: int):
        """Original character group remains world-anchored while scrolling."""
        for effect in self.active.values():
            x = effect.world_x - scroll_px
            if -16 < x < 224:
                bank.ground_object(surface, x, effect.y, effect.code, landscape_colour)
