"""Original Scramble ground-to-air rockets: source-driven deterministic checks."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scramble_scroll import read_stages
from scramble_course import ContinuousCourse
from scramble_rockets import FlyingRockets, FlyingRocket
from scramble_objects import AnimationCollection
from scramble_player import PlayerJet, Joystick
from scramble_bullets import PlayerBullets, Bullet
from scramble_bombs import PlayerBombs, Bomb
from scramble_game import PlayScene, TRACE_FIELDS, row

stages = read_stages()
course = ContinuousCourse(stages)
assert [s.flags for s in stages] == [0,2,1,8,4,16]
assert [FlyingRockets.enabled(s.flags) for s in stages] == [True,False,False,True,False,False]
assert len(TRACE_FIELDS)==len(row(PlayScene(None,None,stages)))

# First launch: gate 64 updates, first eligible ground rocket and one of 4 slots.
rs=FlyingRockets()
removed=set()
scroll=256
assert rs.launch(stage_flags=0,timing=63,course=course,world_scroll=scroll,
                 destroyed=removed,stage_idx=0) is None
launch = rs.launch(stage_flags=0,timing=64,course=course,world_scroll=scroll,
                   destroyed=removed,stage_idx=0)
assert launch is not None and launch.source in removed
assert launch.active and launch.stage==0 and not launch.exploding
assert launch.screen_xy[1] in range(40,240)
assert launch.y in range(0x60,0xe8)
assert rs.launches == 1
# Source stage flags are authoritative: cannot launch in cave/UFO, fireball, maze or base.
for fl in (2,1,4,16):
    assert rs.launch(stage_flags=fl,timing=64,course=course,
                     world_scroll=scroll,destroyed=removed,stage_idx=0) is None
x,y=launch.x,launch.y
rs.move(scrolling=True)   # $1CE3 init step, no displacement yet
assert launch.stage==1 and (launch.x,launch.y)==(x,y)
assert launch.animation is not None and not launch.visible
rs.move(scrolling=True)   # $1CFC: up -1, background left -1
assert launch.x==x-1 and launch.y==(y+1)&255
assert launch.visible and launch.animation.current.code==0x1d
for _ in range(17):rs.move(scrolling=True)
assert launch.animation.current.code==0x1e, 'two-frame ROM rocket animation'

# 4 flying slots, including exploding slots, never over-allocated.
rs=FlyingRockets()
for r in rs.slots:r.active=True
assert rs.launch(stage_flags=0,timing=64,course=course,world_scroll=scroll,
                 destroyed=set(),stage_idx=0) is None
assert len(rs.slots)==4
rs.reset()
assert rs.launches==0 and rs.active_count==0

# The exact raw Z80 tests preserve 8-bit arithmetic and hit windows.
r=FlyingRocket(active=True,stage=1,x=0x60,y=0xB0)
assert rs.touches_bullet(r,Bullet(True,0x60,0xB0))
assert rs.touches_bomb(r,Bomb(active=True,stage=1,x=0x60,y=0xB0))
assert not rs.touches_bullet(r,Bullet(True,0x70,0xB0))
assert not rs.touches_bomb(r,Bomb(active=True,stage=1,x=0x60,y=0xD0))
p=PlayerJet();r.x,r.y=p.x,p.y
assert rs.touches_ship(r,p)
assert not rs.touches_ship(FlyingRocket(True,False,1,0,0),p)

# A hit changes rocket into its original 63-tick, four-frame explosion.
r=rs.slots[0]
r.active=True;r.stage=1;r.x,r.y=0x75,0xB0
bullets=PlayerBullets();bullets.slots[0]=Bullet(True,r.x,r.y)
assert rs.hit_bullets(bullets)==1
assert bullets.active_count==0 and bullets.hits==1
assert rs.bullet_hits==1 and r.exploding and r.stage==6 and not r.active
rs.move(scrolling=True)  # stage6 explosion initialise
assert r.stage==7 and r.explosion_counter==63
assert r.animation.current.code==0x38
for _ in range(62):rs.move(scrolling=True)
assert r.exploding and r.explosion_counter==1
rs.move(scrolling=True)
assert not r.exploding and not r.active

r=rs.slots[0];r.active=True;r.stage=1;r.x,r.y=0x73,0xB0
bombs=PlayerBombs();bombs.slots[0]=Bomb(active=True,stage=1,x=r.x,y=r.y)
assert rs.hit_bombs(bombs)==1 and rs.bomb_hits==1
assert bombs.active_count==0 and r.exploding

# Gameplay integration: travelling target is 80 points, ground one 50;
# launch happens in the source spawn phase (AFTER collision and bullet checks).
scene=PlayScene(None,None,stages,collisions=False,fuel_enabled=False)
while scene.rockets.launches==0 and scene.frames<1000:
    scene.tick()
assert scene.rockets.launches==1 and scene.rockets.active_count==1
src=next(r.source for r in scene.rockets.slots if r.active)
assert src in scene.hit_targets, 'stationary rocket must disappear on launch'
while not any(r.active and r.stage==1 for r in scene.rockets.slots): scene.tick()
r=next(r for r in scene.rockets.slots if r.active and r.stage==1)
# On next tick rocket moves (-1,+1), bullet moves 3 towards right.
scene.bullets.slots[0]=Bullet(True,r.x,(r.y+4)&0xff)
scene.tick()
assert scene.rockets.bullet_hits==1 and scene.hud.score==80 + 10*(scene.frames//64)
assert any(r.exploding for r in scene.rockets.slots)
assert scene.run_state=='playing'

# Rocket colliding with the ship enters SAME ship explosion / life-loss flow.
scene=PlayScene(None,None,stages,collisions=True,fuel_enabled=False)
r=scene.rockets.slots[0]
r.active=True;r.stage=1;r.animation=scene.animations.play('rocket')
r.visible=True;r.x=scene.jet.x;r.y=scene.jet.y
scene.tick()
assert scene.run_state=='dying' and scene.death_reason=='flying_rocket'
assert scene.rockets.ship_hits==1 and r.exploding
for _ in range(111+192):scene.tick()
assert scene.run_state=='playing' and scene.remaining_lives==1
assert scene.rockets.active_count==0 and scene.rockets.launches==0

# Stage 4 is a second rocket-launch level, with stage 5 explicitly excluded.
rs=FlyingRockets()
t=next(t for t in stages[3].targets if t.kind=='ROCKET')
p=course.target_world_x(3,t)-100
assert rs.launch(stage_flags=8,timing=64,course=course,world_scroll=p,
                 destroyed=set(),stage_idx=3) is not None
assert rs.launch(stage_flags=4,timing=128,course=course,world_scroll=p,
                 destroyed=set(),stage_idx=4) is None

# Rocket drawing chooses active landscape colour, explosion uses ROM palette 6.
class Bank:
    def __init__(self): self.calls=[]
    def sprite(self,surf,x,y,code,palette):self.calls.append((x,y,code,palette))
b=Bank();rs=FlyingRockets();r=rs.slots[0]
r.active=True;r.stage=1;r.visible=True;r.x=0x65;r.y=0x90
r.animation=rs.animations.play('rocket')
rs.render(b,None,4)
assert len(b.calls)==1 and b.calls[0][2:]==(0x1d,4)
r.hit(rs.animations);rs.move(scrolling=True);r.visible=True
rs.render(b,None,4)
assert b.calls[-1][2:]==(0x38,6)
# Leaving the left edge: the Z80 rocket is NOT deactivated when the
# top-left of its 16px sprite reaches display x=0.  Preserve negative
# screen positions and rely on Pygame's native surface clipping.
rs=FlyingRockets()
r=rs.slots[0]
r.active=True; r.stage=1; r.visible=True; r.x=0x65
r.animation=rs.animations.play('rocket')
b=Bank()
for raw_y, expected_x in [(0xE5,1),(0xE6,0),(0xE7,-1),(0xEF,-9)]:
    r.y=raw_y
    assert r.screen_xy[0]==expected_x, (raw_y, r.screen_xy)
    assert r.active
    rs.render(b,None,4)
    assert b.calls[-1][0]==expected_x, (raw_y,b.calls[-1])
# $1D11-$1D1F: after advancing to raw Y=$F0, retire the slot.
r.y=0xEF
rs.move(scrolling=True)
assert not r.active and rs.active_count==0
# Even the last pre-retirement frame has partly visible sprite area.
assert -16 < (230-0xEF) < 0

print('PASS: original stage flags [1,4], 64-tick launches, 4 slots, source ground removal,')
print('      -1 vertical/+1 scenery displacement, sprite animations, ship contact,')
print('      projectile raw-byte hits, +80 points, 63-update explosions, respawn reset.')
