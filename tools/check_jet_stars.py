"""Regression checks for full two-sprite jet and Scramble 555 star blinking."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scramble_stars import BLINK_PERIOD_MS, blink_state, star_visible
from scramble_player import PlayerJet, Joystick
from scramble_objects import AnimationCollection
from scroll_viewer import scramble_stars

assert BLINK_PERIOD_MS == 831, BLINK_PERIOD_MS
assert blink_state(0) == 0
assert blink_state(50) == 0
assert blink_state(51) == 1
assert blink_state(100) == 1
assert blink_state(101) == 2
assert blink_state(151) == 2
assert blink_state(152) == 3
assert blink_state(202) == 0
assert [star_visible(0, phase) for phase in range(4)] == [False,False,False,True]
assert [star_visible(1, phase) for phase in range(4)] == [True,False,False,True]
assert [star_visible(2, phase) for phase in range(4)] == [False,True,False,True]
assert [star_visible(4, phase) for phase in range(4)] == [False,False,True,True]

bank = AnimationCollection()
body = bank.play('player_one')
rear = bank.play('player_two')
assert [f.code for f in body.frames] == [0x28,0x2A,0x2C,0x2E]
assert [f.code for f in rear.frames] == [0x27,0x29,0x2B,0x2D]
assert all(f.colour == 6 and f.delay == 5 for f in body.frames)
assert all(f.colour == 0 and f.delay == 5 for f in rear.frames)
for i in range(300):
    assert body.index == rear.index, (i,body.index,rear.index)
    assert body.remaining == rear.remaining, (i,body.remaining,rear.remaining)
    body.step();rear.step()
jet=PlayerJet()
assert jet.screen_xy == (22,81)
assert jet.rear_screen_xy == (6,81)
for stick in [Joystick(right=True)]*60 + [Joystick(up=True, left=True)]*50 + [Joystick(down=True, right=True)]*90:
    jet.update(stick)
    assert jet.rear_screen_xy[0] == jet.screen_xy[0] - 16
    assert jet.rear_screen_xy[1] == jet.screen_xy[1]
jet.reset()
assert jet.rear_screen_xy == (6,81)

stars=scramble_stars()
assert len(stars) > 20
visible=[sum(star_visible(flags, phase) for _,_,_,flags in stars) for phase in range(4)]
assert len(set(visible)) >= 2 and visible[3] == len(stars),visible
print('OK: 2-sprite jet (body + exhaust), ROM frames/delays, 16px separation,')
print(f'    MAME {BLINK_PERIOD_MS}ms star phase, exact 4-phase visibility. Visible counts: {visible}')
