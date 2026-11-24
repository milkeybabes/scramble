"""Continuous six-stage scenery stream from Scramble's original landscape data.

The game reaches an $FF end marker in $27C9 and selects the NEXT stage's
records; it does not clear or jump the displayed playfield at a stage boundary.
This module retains the complete terrain records as one logical pixel stream,
with the final BASE dataset repeating each time the original $FF terminator is
encountered ($27E1-$27FC). Each stage uses the native tile renderer.

The source hardware's 32-column ring/pre-fill phase is NOT claimed to be
cycle-perfect. No enemy/collision/CPU hardware is emulated here.
"""
from __future__ import annotations
from bisect import bisect_right
from dataclasses import dataclass
from typing import Sequence

from scramble_scroll import StageMap, VIEW_WIDTH


@dataclass(frozen=True)
class ViewSlice:
    stage_index: int
    source_x: int
    screen_x: int
    width: int


class ContinuousCourse:
    def __init__(self, stages: Sequence[StageMap]):
        if not stages:
            raise ValueError('The course requires at least one stage')
        self.stages = tuple(stages)
        # $10A1 draws a 30-character flat ground strip before level 1 starts.
        # The portrait-visible width is 28 characters. Treat the visible 224px
        # as prefilled scenery while ROM records enter from the right.
        self.prefill_width = VIEW_WIDTH
        starts = [self.prefill_width]
        for stage in stages:
            if stage.width <= 0:
                raise ValueError(f'Empty stage: {stage.name}')
            starts.append(starts[-1] + stage.width)
        self.starts = tuple(starts)
        self.total_width = starts[-1]
        # Position at which the original BASE strip has fully entered view.
        # A useful historical marker, NOT a hard limit: $27E1-$27FC
        # reloads the final BASE stream after its $FF end marker.
        self.last_scroll = max(0, self.total_width - VIEW_WIDTH)
        self.base_start = self.starts[-2]
        self.base_width = self.stages[-1].width

    def find_stage(self, world_x: int) -> int:
        """Find which of the six original ROM streams owns a world pixel."""
        x = max(0, min(self.total_width - 1, int(world_x)))
        if x < self.prefill_width:
            return 0
        return min(len(self.stages)-1, bisect_right(self.starts, x)-1)

    def producer_stage(self, scroll: int) -> int:
        """HUD stage follows the data being READ at the right edge.

        Original $27C9 advances stage upon consuming the $FF end marker,
        while old columns continue moving off the LEFT of the screen.
        """
        return self.find_stage(int(scroll) + VIEW_WIDTH)

    def visible_slices(self, scroll: int):
        """Return contiguous pixel slices, looping the BASE strip forever.

        $27C9/$27E1: $FF in the last landscape reloads the BASE pointer,
        rather than halting gameplay. Keep the previous strips visible at the
        seam. There is no physical cut or screen reset when this wraps.
        """
        pos = max(0, int(scroll))
        right = pos + VIEW_WIDTH
        if pos < self.prefill_width:
            lo, hi = pos, min(right, self.prefill_width)
            if lo < hi:
                yield ViewSlice(-1, lo, lo-pos, hi-lo)
        for idx in range(len(self.stages)-1):
            lo = max(pos, self.starts[idx]); hi = min(right,self.starts[idx+1])
            if lo < hi:
                yield ViewSlice(idx, lo-self.starts[idx],lo-pos,hi-lo)
        # Last stage is a periodic source: repeated as often as needed, even
        # after its original one-time source coordinates have been exhausted.
        x = max(pos, self.base_start)
        last = len(self.stages)-1
        while x < right:
            local = (x - self.base_start) % self.base_width
            width = min(right-x, self.base_width-local)
            yield ViewSlice(last, local, x-pos, width)
            x += width

    def nearby_targets(self, scroll: int, margin: int = 32):
        """Yield (stage_index, target, absolute_x, identity) in viewport area.

        Repeated BASE targets get a distinct identity per circuit, just like
        original hardware re-allocating new GROUND_OBJECT slots each time a
        new record is decoded. For the first circuit, retain old 2-tuple keys
        for backwards compatibility with rocket/ground-target tests.
        """
        left = int(scroll) - margin
        right = int(scroll) + VIEW_WIDTH + margin
        for i, stage in enumerate(self.stages):
            for target in stage.targets:
                original = self.target_world_x(i,target)
                if i != len(self.stages)-1:
                    if left <= original < right:
                        yield i,target,original,(i,target.record_index)
                    continue
                first = max(0, (left-original)//self.base_width)
                last = max(0, (right-1-original)//self.base_width)
                for repeat in range(first,last+1):
                    wx = original + repeat*self.base_width
                    if left <= wx < right:
                        key = (i,target.record_index) if repeat == 0 else (i,target.record_index,repeat)
                        yield i,target,wx,key

    def record_at(self, world_x: int):
        """Original record nearest the landscape producer head."""
        if int(world_x) < self.prefill_width:
            return {'ceiling': None}
        idx = self.find_stage(world_x)
        stage = self.stages[idx]
        x = int(world_x) - self.starts[idx]
        if idx == len(self.stages)-1:
            x %= stage.width  # $27E6 repeats BASE landscape indefinitely
        else:
            x = max(0,min(stage.width-1,x))
        return stage.records[x//16]

    def target_world_x(self, stage_index: int, target) -> int:
        return self.starts[stage_index] + target.x
