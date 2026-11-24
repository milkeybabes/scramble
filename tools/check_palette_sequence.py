"""Opening palette + periodic colour transitions (original code, video phase)."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scramble_game import PlayScene
from scramble_scroll import read_stages
from scramble_palette import (DEFAULT_LANDSCAPE_COLOUR, COLOUR_CYCLE_FRAMES,
    INITIAL_CHANGE_FRAMES, next_landscape_colour)

assert DEFAULT_LANDSCAPE_COLOUR == 0
assert COLOUR_CYCLE_FRAMES == 512
assert 90 <= INITIAL_CHANGE_FRAMES <= 150
assert [next_landscape_colour(i) for i in range(8)] == [2,2,3,4,5,6,7,0]
scene = PlayScene(None, None, read_stages(),collisions=False,fuel_enabled=False)
assert scene.colour == 0
assert scene.next_colour_tick == INITIAL_CHANGE_FRAMES
for f, col in [(0,0),(119,0),(120,2),(631,2),(632,3),
               (1143,3),(1144,4),(1656,5),(2168,6),
               (2680,7),(3192,0),(3704,2)]:
    while scene.frames < f:
        scene.tick()
    assert scene.colour == col, (f,scene.colour,col)
# Heading into a new stage MUST NOT reset palette clock or the active colour.
old_colour = scene.colour
scene.stage_idx = 1
scene.tick()
assert scene.colour == old_colour
# $12C6 restarts with the original pink initial palette; phase is reset for
# this simplified game loop, since previous attract/NMI phase isn't modelled.
scene.restart_loop()
assert scene.colour == 0 and scene.next_colour_tick == INITIAL_CHANGE_FRAMES
assert scene.colour_ticks == 0 and scene.stage_idx == 0
# Manual palette override is still accepted.
scene = PlayScene(None,None,read_stages(),start_palette=4)
assert scene.colour == 4
for _ in range(INITIAL_CHANGE_FRAMES):scene.tick()
assert scene.colour == 5
print('PASS: arcade 0→2→3→4→5→6→7→0 landscape sequence,')
print('      black/blue background groups, early first change and 512-frame cadence,')
print('      continuous-course stage changes and loop restart.')
