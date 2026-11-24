"""UFO + fireball native logic regression checks, requiring no pygame or ROMs."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scramble_aliens import FlyingAliens,Alien,UFO_PATH,FIREBALL_PATH
from scramble_player import PlayerJet
from scramble_bullets import PlayerBullets,Bullet
from scramble_bombs import PlayerBombs,Bomb
from scramble_game import PlayScene,TRACE_FIELDS,row
from scramble_scroll import read_stages

stages=read_stages()
assert [s.flags for s in stages]==[0,2,1,8,4,16]
assert len(UFO_PATH)==74 and UFO_PATH[0]==(-1,0) and UFO_PATH[-1]==(-2,0)
assert FIREBALL_PATH==((0,4),)
assert sum(d[1] for d in UFO_PATH)==70

# UFO 64-frame cadence, original spawn coordinates, first-free-slot policy.
a=FlyingAliens(seed=12)
assert a.spawn(stage_flags=2,timing=63) is None
u=a.spawn(stage_flags=2,timing=64)
assert u and u.kind=='ufo' and u.stage==0 and u.x==0x88 and 9<=u.y<=24
assert u.screen_xy==(230-u.y,u.x-7)
assert a.spawn(stage_flags=1,timing=65) is None
assert a.spawn(stage_flags=4,timing=128) is None
x,y=u.x,u.y
a.move(stage_flags=2)
assert u.stage==1 and not u.visible and u.x==x and u.y==y
a.move(stage_flags=2)
assert u.visible and u.x==x-1 and u.y==y and u.path_index==1
for _ in range(73):a.move(stage_flags=2)
assert u.path_index==0  # $1EC3 marker points back to $1E2F

# Every 64 frames, occupancy max four including explosions.
a=FlyingAliens(seed=1)
for f in [64,128,192,256]: assert a.spawn(stage_flags=2,timing=f) is not None
assert a.occupied_count==4
assert a.spawn(stage_flags=2,timing=320) is None
assert a.spawn(stage_flags=2,timing=384,reserved_slots=4) is None

# Fireball checks 16-frame cadence; 7-bit R-derived original range.
a=FlyingAliens(seed=10)
assert a.spawn(stage_flags=1,timing=15) is None
fb=a.spawn(stage_flags=1,timing=16)
assert fb and fb.kind=='fireball' and 0x30<=fb.x<=0xaf and fb.y==8
# FIREBALL_INIT calls animation/movement immediately, unlike UFO_INIT.
a.move(stage_flags=1)
assert fb.stage==1 and fb.visible and fb.y==12
assert fb.animation.current.code==0x35
for _ in range(6):a.move(stage_flags=1)
assert fb.y==36
assert fb.animation.current.code in (0x35,0x36,0x37,0x30)

# Both spawns remain repeatable with same Python test seed, different seeds differ.
def run_spawn(seed,flag):
    a=FlyingAliens(seed=seed)
    return [(a.spawn(stage_flags=flag,timing=(i+1)*(64 if flag==2 else 16)).x,
             a.slots[i].y) for i in range(4)]
assert run_spawn(8,2)==run_spawn(8,2)
assert run_spawn(8,1)==run_spawn(8,1)
assert run_spawn(8,1)!=run_spawn(9,1)

# Only the UFO can be shot/bombed, both award 100 through game integration.
a=FlyingAliens()
u=a.slots[0]
u.active=True;u.kind='ufo';u.stage=1;u.x=0x65;u.y=0xa0
b=PlayerBullets();b.slots[0]=Bullet(True,u.x,u.y)
assert a.hit_bullets(b)==1 and not b.slots[0].active and u.exploding
assert a.bullet_hits==1
# Explosion initialization and 43 update lifetime from $1DFB.
a.move(stage_flags=2)
assert u.stage==7 and u.explosion_counter==43
for _ in range(42):a.move(stage_flags=2)
assert u.exploding and u.explosion_counter==1
a.move(stage_flags=2)
assert not u.active and not u.exploding

u=a.slots[0]
u.active=True;u.kind='ufo';u.stage=1;u.x=0x65;u.y=0xa0
bombs=PlayerBombs();bombs.slots[0]=Bomb(active=True,stage=1,x=u.x,y=u.y)
assert a.hit_bombs(bombs)==1 and u.exploding and bombs.active_count==0

fb=a.slots[1]
fb.kind='fireball';fb.active=True;fb.stage=1;fb.x=0x65;fb.y=0xa0
bullet=PlayerBullets();bullet.slots[0]=Bullet(True,fb.x,fb.y)
assert a.hit_bullets(bullet)==0 and bullet.active_count==1
bomb=PlayerBombs();bomb.slots[0]=Bomb(active=True,stage=1,x=fb.x,y=fb.y)
assert a.hit_bombs(bomb)==0 and bomb.active_count==1

# Jet collision uses the source's same raw byte-window for both types.
jet=PlayerJet()
assert a.touches_ship(Alien(kind='fireball',active=True,x=jet.x,y=jet.y),jet)
assert not a.touches_ship(Alien(kind='ufo',active=True,x=0,y=0),jet)

# The real game tick spawns UFOs only in stage 2 and fireballs only in stage 3.
for stage,kind in ((2,'ufo'),(3,'fireball')):
    scene=PlayScene(None,None,stages,start_stage=stage-1,collisions=False,
                    fuel_enabled=False,enemy_seed=11)
    for _ in range(130):scene.tick()
    assert scene.aliens.spawns>=2
    assert len(row(scene))==len(TRACE_FIELDS)
    assert all(k==kind for _,k,_,_,_ in scene.aliens.spawn_log)
    if stage==2:
        assert scene.aliens.fireball_spawns==0
    else:
        assert scene.aliens.ufo_spawns==0

# In stage 2 a bullet hitting the UFO awards 100 via the normal scene.
scene=PlayScene(None,None,stages,start_stage=1,collisions=False,
                fuel_enabled=False,aliens_enabled=False)
u=scene.aliens.slots[0];u.kind='ufo';u.active=True;u.stage=1;u.x=0x85;u.y=0x90
u.animation=scene.animations.play('ufo');u.visible=True
scene.bullets.slots[0]=Bullet(True,0x83,0x93)  # moving +3 horizontal to 0x90
scene.tick()
assert scene.aliens.bullet_hits==1 and scene.hud.score==100
assert u.exploding

# Enemy collision enters the same jet-death state as ground rockets.
for stage,kind in ((2,'ufo'),(3,'fireball')):
    scene=PlayScene(None,None,stages,start_stage=stage-1,collisions=True,
                    fuel_enabled=False,aliens_enabled=False)
    a=scene.aliens.slots[0];a.kind=kind;a.active=True;a.stage=1
    a.x=scene.jet.x+1 if kind=='ufo' else scene.jet.x
    a.y=scene.jet.y
    a.animation=scene.animations.play(kind)
    scene.tick()
    assert scene.run_state=='dying' and scene.death_reason==kind
    assert scene.aliens.ship_hits==1 and a.exploding

# The seed and previous state are cleared on a fresh play, but the stage
# retries retain the original 7-bit pseudo-refresh progression.
s=PlayScene(None,None,stages,start_stage=1,collisions=False,fuel_enabled=False,enemy_seed=13)
for _ in range(128):s.tick()
log=s.aliens.spawn_log.copy()
s.new_game(start_stage=1)
for _ in range(128):s.tick()
assert [item[1:] for item in s.aliens.spawn_log]==[item[1:] for item in log]
print('PASS: UFO and fireball source-paths, spawn phase, seed, collisions, explosions and game integration')
