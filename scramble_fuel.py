"""Scramble's fuel countdown, translated from $1725-$1734 and $29B5-$29CC.

The countdown after the first five ticks depends on *completed missions*:
0 missions: 10 frames/unit; 1 mission: 8; 2+ missions: 6.
Fuel tanks add $30 (48) and saturate at $FF ($2283).
The game owns the numeric fuel value; the timer owns only the countdown.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class FuelTimer:
    counter: int = 5

    def reset(self) -> None:
        """$1113: each GAME_INIT starts with a five-tick first countdown."""
        self.counter = 5

    @staticmethod
    def drain_interval(completed_missions: int) -> int:
        return 10 if completed_missions == 0 else 8 if completed_missions == 1 else 6

    def step(self, fuel: int, completed_missions: int) -> tuple[int, bool]:
        """Return (fuel left, just ran out). Invoke on each active player update.

        Original $1725 decrements counter; at zero it reloads the correct
        interval and decrements fuel by one. $1731 branches to out-of-fuel
        movement only when the newly decremented value becomes zero.
        """
        if not 0 <= fuel <= 255:
            raise ValueError('Fuel byte must be 0..255')
        if self.counter <= 0:
            raise ValueError('Fuel countdown must be positive')
        self.counter -= 1
        if self.counter:
            return fuel, False
        self.counter = self.drain_interval(completed_missions)
        # A zero externally supplied debug-fuel value is already empty;
        # avoid making the HUD jump from empty to 255 through 8-bit wrap.
        if fuel <= 1:
            return 0, True
        return fuel-1, False

    @staticmethod
    def refuel(fuel: int) -> int:
        """$2283: FUEL hit: +$30, saturating to $FF. No timer reset."""
        return min(255, fuel + 0x30)
