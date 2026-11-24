"""Source $139C auto score and $1AAC-$1AD5 35-update bomb explosion.

Runs without pygame or a sound device; exercises the full PlayScene tick
and the original two-slot bomb lifecycle including collision and rendering.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scramble_scroll import read_stages
from scramble_game import PlayScene
from scramble_player import PlayerJet, Joystick
from scramble_bombs import PlayerBombs, Bomb
from scramble_aliens import FlyingAliens
from scramble_rockets import FlyingRockets

stages=read_stages()
# 10 per 64 actual PLAY_GAME updates, not per object hit, regardless of scrolling.
s=PlayScene(None,None,stages,collisions=False,fuel_enabled=False,
            rockets_enabled=False,aliens_enabled=False,lives=255)
s.hud.high_score=0
for _ in range(63): s.tick()
assert s.hud.score==0 and s.frames==63
s.tick()
assert s.hud.score==10 and s.hud.high_score==10 and s.frames==64
for _ in range(64): s.tick()
assert s.hud.score==20 and s.frames==128
# The original GAIN_POINTS_JUST_FOR_STAYING_ALIVE call belongs to PLAY_GAME:
# once base is destroyed, COOL_OFF does not keep accumulating time points.
s.run_state='cool_off';s.state_timer=150
for _ in range(90): s.tick()
assert s.hud.score==20 and s.run_state=='cool_off'
s.kill_player('terrain')
for _ in range(65): s.tick()
assert s.hud.score==20

# Bomb explosions start at stage 6 (next tick initializes their $1AF0 table)
# and occupy the slot until 35 animation updates have completed.
bombs=PlayerBombs()
b=Bomb(active=True,stage=1,x=0x80,y=0xa0)
bombs.slots[0]=b
b.explode()
assert not b.active and b.exploding and b.stage==6
assert bombs.active_count==0 and bombs.occupied_count==1
bombs.move(PlayerJet())
assert b.stage==7 and b.explosion_counter==0x23
assert not b.visible and b.animation.current.code==0x38
start_y=b.y
for i in range(34):
    bombs.move(PlayerJet(),scrolling=True)
    assert b.exploding and b.explosion_counter==34-i
assert b.y==(start_y+34)&0xff and b.visible
assert b.animation.current.code in (0x38,0x39,0x3a,0x3b)
bombs.move(PlayerJet(),scrolling=True)
assert not b.exploding and not b.active and bombs.occupied_count==0

# A second bomb can fire while the first explodes, but only two slots may
# be in use, matching $26E3's (IsActive OR IsExploding) capacity test.
bombs.reset(); first=bombs.slots[0];first.active=True;first.stage=1
first.explode()
assert bombs.spawn_on_press(True) and bombs.occupied_count==2
bombs.spawn_on_press(False)
assert not bombs.spawn_on_press(True) and bombs.occupied_count==2

# Ground collision changes the projectile into the explosion, and still
# awards precisely the same object score and fuel as before.
s=PlayScene(None,None,stages,collisions=False,fuel_enabled=False,
            rockets_enabled=False,aliens_enabled=False)
obj=stages[0].targets[0]
wx=s.course.target_world_x(0,obj)
s.speed.pixels=wx-64
s.bombs.slots[0]=Bomb(True,1,obj.y+7,238-(64+8),0)
s.tick(Joystick())
assert s.bombs.hits==1 and s.last_hit[0]=='ROCKET' and s.hud.score==50
b=s.bombs.slots[0]
assert b.exploding and not b.active and b.stage==6
s.tick()
assert b.stage==7 and b.animation.current.code==0x38
# Floating sprites also must trigger a projectile explosion, but fireballs
# are deliberately immune to player bombs in the original source.
bombs=PlayerBombs();a=FlyingAliens(seed=0)
u=a.slots[0];u.kind='ufo';u.active=True;u.stage=1;u.x=0x60;u.y=0x80
b=bombs.slots[0];b.active=True;b.stage=1;b.x=u.x;b.y=u.y
assert a.hit_bombs(bombs)==1 and b.exploding and u.exploding
bombs.reset();r=FlyingRockets();rocket=r.slots[0]
rocket.active=True;rocket.stage=1;rocket.x=0x60;rocket.y=0x80
b=bombs.slots[0];b.active=True;b.stage=1;b.x=rocket.x;b.y=rocket.y
assert r.hit_bombs(bombs)==1 and b.exploding and rocket.exploding

# Non-hardware graphics spy: confirm the explosion is presented from the
# sprite atlas in the same render path as the other actors.
class FakeSurface:
    def fill(self,*a):pass
    def blit(self,*a):pass
    def set_at(self,*a):pass
    def convert_alpha(self):return self
class FakePG:
    SRCALPHA=1
    @staticmethod
    def Surface(*a):return FakeSurface()
    @staticmethod
    def Rect(*a):return a
    class draw:
        @staticmethod
        def rect(*a):pass
class FakeBank:
    pg=FakePG
    def __init__(self):self.drawn=[]
    def character(self,*a):pass
    def ground_object(self,*a):pass
    def sprite(self,surface,x,y,code,colour):self.drawn.append((x,y,code,colour))
    def text(self,*a):pass
bank=FakeBank()
scene=PlayScene(FakePG,bank,stages,collisions=False,fuel_enabled=False,
                rockets_enabled=False,aliens_enabled=False)
scene.bombs.slots[0]=Bomb(active=True,stage=1,x=100,y=150)
scene.bombs.slots[0].explode()
scene.bombs.move(scene.jet)
scene.bombs.move(scene.jet)
scene.render(FakeSurface())
assert any(code==0x38 and colour==6 for _,_,code,colour in bank.drawn),bank.drawn
print('PASS: +10 per 64 gameplay ticks; no scoring during COOL_OFF/death;')
print('      35-tick bomb explosions, 2 occupied slots, UFO/rocket/ground hits and draw.')
