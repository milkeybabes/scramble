"""Regression: six continuous stages, repeating BASE, mission script."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scramble_scroll import read_stages, VIEW_WIDTH
from scramble_course import ContinuousCourse
from scramble_game import PlayScene

stages=read_stages(); course=ContinuousCourse(stages)
assert len(stages)==6
assert course.prefill_width==VIEW_WIDTH
assert course.total_width == 224 + sum(s.width for s in stages)
assert course.last_scroll==sum(s.width for s in stages)
assert course.find_stage(0)==0
assert course.producer_stage(0)==0
assert list(course.visible_slices(0))[0].stage_index == -1
assert sum(v.width for v in course.visible_slices(0))==VIEW_WIDTH
assert course.visible_slices(1).__next__().width == VIEW_WIDTH-1
for idx in range(1,6):
    marker=course.starts[idx]
    # The producer switches when the new stream starts at the RIGHT edge.
    assert course.producer_stage(marker - VIEW_WIDTH - 1) == idx-1
    assert course.producer_stage(marker - VIEW_WIDTH) == idx
    for pixel in (marker-VIEW_WIDTH-3,marker-VIEW_WIDTH-1,marker-VIEW_WIDTH,
                  marker-VIEW_WIDTH+1,marker-1,marker,marker+1):
        segs=list(course.visible_slices(pixel))
        assert sum(v.width for v in segs)==VIEW_WIDTH, (idx,pixel,segs)
        assert segs[0].screen_x==0
        assert all(a.screen_x+a.width==b.screen_x for a,b in zip(segs,segs[1:]))
    parts=list(course.visible_slices(marker - VIEW_WIDTH//2))
    assert len(parts)==2 and {x.stage_index for x in parts}=={idx-1,idx}

scene=PlayScene(None,None,stages,collisions=False,fuel_enabled=False)
assert scene.speed.pixels==0
assert scene.stage_idx==0
assert scene.course.total_width==11424
# Track six stages, monotonic world position, identical joystick at boundaries.
seen=[scene.stage_idx]; previous=0
for _ in range(course.last_scroll+100):
    scene.tick()
    assert scene.speed.pixels>=previous
    assert scene.speed.pixels-previous <=1
    assert scene.jet.screen_xy == (22,81)
    previous=scene.speed.pixels
    if seen[-1]!=scene.stage_idx:seen.append(scene.stage_idx)
assert seen==list(range(6)),seen
assert scene.at_base_end and scene.speed.pixels==course.last_scroll+100
assert scene.run_state=='playing' and scene.base_visible
for _ in range(80): scene.tick()
assert scene.at_base_end and scene.run_state=='playing'
assert scene.speed.pixels==course.last_scroll+180
assert not scene.base_visible  # missing the first base must NOT complete mission
# Original $27E1-$27FC reloads the BASE pointer; next copy enters from right.
for _ in range(course.base_width):
    if scene.base_visible:break
    scene.tick()
assert scene.base_visible and scene.run_state=='playing'
assert scene.simulate_base_destroyed()
assert scene.run_state=='cool_off' and scene.base_destroyed
for _ in range(150):scene.tick()
assert scene.run_state=='blank'
for _ in range(5):scene.tick()
assert scene.run_state=='message'
for _ in range(256):scene.tick()
assert scene.run_state=='playing' and scene.stage_idx==0
assert scene.speed.pixels==0 and scene.hud.missions_completed==1
assert scene.loop_number==2 and not scene.at_base_end
assert scene.hud.fuel==255
# A manual seek is a DEBUG control and resets only the requested scene.
scene.goto(4)
assert scene.speed.pixels == course.starts[4] and scene.stage_idx==4
assert scene.run_state == 'playing'
print('PASS: all six seamless stages, 224px flat prefill, 5 joins, contiguous 224px viewport,')
print('      monotonic 1px/frame scroll, repeating BASE after a miss, manual base-hit, 150+5+256-frame')
print('      mission sequence, automatic restart with preserved player animation and flags.')
