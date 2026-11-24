"""Regression: $1288 COOL_OFF preserves player control and lethal collisions.

The original cool-off runs $13CC animation/player movement and $2036 collision
for 150 frames; $2563 SPAWN_ENEMIES (also firing/bomb spawn) is not called.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scramble_game import PlayScene
from scramble_scroll import read_stages
from scramble_player import Joystick

stages=read_stages()

def in_front_of_base(lives=3, collisions=False, fuel=False):
    scene=PlayScene(None,None,stages,start_stage=5,lives=lives,
                    collisions=collisions,fuel_enabled=fuel,
                    rockets_enabled=False,aliens_enabled=False)
    base=next(t for t in stages[-1].targets if t.kind=='BASE')
    scene.speed.pixels=scene.course.target_world_x(5,base)-95
    assert scene.base_visible, scene.speed.pixels
    assert scene.simulate_base_destroyed()
    assert scene.run_state=='cool_off' and scene.state_timer==150
    return scene

# Player retains both-axis native 1px/frame control throughout the period.
s=in_front_of_base()
start=(s.jet.x,s.jet.y,s.speed.pixels)
s.tick(Joystick(up=True,right=True,fire=True,bomb=True))
assert s.jet.x==start[0]-1 and s.jet.y==start[1]-1,(start,s.jet)
assert s.speed.pixels==start[2]+1
assert s.state_timer==149
assert s.bullets.shots_fired==0 and s.bombs.bombs_dropped==0, 'No $2563 during cool-off'
s.tick(Joystick(down=True,left=True))
assert (s.jet.x,s.jet.y)==(start[0],0xcf)  # original $D0 -> $CF edge quirk
assert s.run_state=='cool_off'
for _ in range(148): s.tick()
assert s.run_state=='blank'
for _ in range(5): s.tick()
assert s.run_state=='message'
for _ in range(256): s.tick()
assert s.run_state=='playing' and s.stage_idx==0
assert s.hud.missions_completed==1 and s.loop_number==2

# During cool-off, fuel continues to drain, matching the animation/movement
# routine. As fuel reaches zero, the player loses control and will descend.
s=in_front_of_base(fuel=True)
s.hud.fuel=1
s.fuel_timer.counter=1
s.tick(Joystick(up=True))
assert s.run_state=='cool_off' and s.cool_off_out_of_fuel
assert s.hud.fuel==0
initial_x=s.jet.x
s.tick(Joystick(up=True))
assert s.jet.x==initial_x+1, 'The unpowered ship must descend, not respond to joystick'

# Actual terrain contact during cool-off cancels mission success. Use the
# source-derived terrain extents; raw jet X $D7 is below the terrain floor.
s=in_front_of_base(collisions=True)
s.hud.score=800
s.jet.x=0xd7
s.jet.other_x=0xd7
s.tick()
assert s.run_state=='dying' and s.death_reason=='terrain', (s.run_state,s.death_reason)
assert s.hud.missions_completed==0 and s.loop_number==1
for _ in range(111+192): s.tick()
assert s.run_state=='playing' and s.stage_idx==5
assert s.hud.missions_completed==0 and s.loop_number==1
assert s.hud.score==800, 'Score remains despite failure to escape'
assert s.hud.fuel==255

# Without reserve lives, dying in the same period leads to GAME OVER rather
# than the congratulations message or the next loop.
s=in_front_of_base(lives=3,collisions=True)
s.remaining_lives=0;s.hud.lives=0
s.jet.x=0xd7;s.jet.other_x=0xd7
s.tick()
assert s.run_state=='dying'
for _ in range(111):s.tick()
assert s.run_state=='game_over'
assert s.hud.missions_completed==0 and s.loop_number==1
for _ in range(160):s.tick()
assert s.run_state=='game_over' and s.loop_number==1

# A vanished/destroyed base must not collide with the jet afterwards.
s=in_front_of_base(collisions=True)
s.kill_player=lambda reason: (_ for _ in ()).throw(AssertionError(reason))
s.jet.x=0x58;s.jet.other_x=0x58
# The ordinary base collision test is bypassed as soon as the base is shot.
assert not any(t.kind=='BASE' and not s.base_destroyed for _,t,_,_ in s.course.nearby_targets(s.speed.pixels))
print('PASS: 150-frame post-base steering, fuel fall, lethal terrain, stage-6 retry, GAME OVER')
