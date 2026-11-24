"""Bomb regression tests: original ROM path, input edges, collision, render, loop."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scramble_bombs import PlayerBombs, Bomb, ORIGINAL_BOMB_PATH
from scramble_player import PlayerJet, Joystick
from scramble_scroll import read_stages
from scramble_game import PlayScene, parse_input_script, row, TRACE_FIELDS
from scramble_course import ContinuousCourse
import zlib, json

assert len(ORIGINAL_BOMB_PATH)==203
raw = bytes((a&0xff for pair in ORIGINAL_BOMB_PATH for a in pair))
assert zlib.crc32(raw)==0x522aa357
assert ORIGINAL_BOMB_PATH[0:3]==((0,0),(1,0),(0,-1))
assert len(TRACE_FIELDS)==len(row(PlayScene(None,None,read_stages(),collisions=False)))
assert parse_input_script('U+B+F:1,N:2')[:1]==[Joystick(up=True,fire=True,bomb=True)]

# Fresh press, two slots and initialisation stage, as in $26B1 and $1A6B.
jet=PlayerJet(); bombs=PlayerBombs()
assert bombs.spawn_on_press(True)
assert bombs.slots[0].active and bombs.slots[0].stage==0
assert not bombs.spawn_on_press(True)  # no automatic repeats
bombs.move(jet)
a=bombs.slots[0]
assert (a.x,a.y,a.stage,a.path_index)==(0x5c,0xd8,1,0)
assert a.screen_xy==(14,85)
assert not a.visible
bombs.move(jet)  # $1AFF first 00,00 pair
assert (a.x,a.y,a.path_index)==(0x5c,0xd8,1)
assert a.visible and a.animation.current.code==0x21
bombs.move(jet)  # 01,00
assert (a.x,a.y,a.path_index)==(0x5d,0xd8,2)
bombs.move(jet)  # 00,FF = forward one pixel in desktop
assert (a.x,a.y,a.path_index)==(0x5d,0xd7,3)
assert a.screen_xy==(15,86)
assert bombs.spawn_on_press(False)==False
assert bombs.spawn_on_press(True)
assert bombs.active_count==2 and bombs.bombs_dropped==2
assert bombs.spawn_on_press(False)==False
assert not bombs.spawn_on_press(True)
assert bombs.bombs_dropped==2
bombs.slots[0].deactivate()
assert not bombs.spawn_on_press(True)
bombs.spawn_on_press(False)
assert bombs.spawn_on_press(True)
assert bombs.active_count==2 and bombs.bombs_dropped==3
bombs.reset()
assert bombs.active_count==0 and bombs.bombs_dropped==0

# Follow the ROM byte path one pair at a time, compare raw coordinate and anim.
jet=PlayerJet()
bombs.spawn_on_press(True);bombs.move(jet)
x=0x5c;y=0xd8
for i,(dx,dy) in enumerate(ORIGINAL_BOMB_PATH):
    if x>=0xf0: break
    bombs.move(jet)
    x=(x+dx)&255;y=(y+dy)&255
    assert (bombs.slots[0].x,bombs.slots[0].y)==(x,y) or not bombs.slots[0].active
    if not bombs.slots[0].active: break

# Predicted hit box matches $245B comparisons: +/-7 with byte projection.
stages=read_stages();course=ContinuousCourse(stages)
tgt=stages[0].targets[0]
world=course.target_world_x(0,tgt)
scroll=world-64
b=Bomb(True,1,tgt.y+7,238-(64+8),0)
assert b.screen_center==(72,tgt.y+8)
assert PlayerBombs.ground_hit(b,scroll,world,tgt.y)
b.y += 15
assert not PlayerBombs.ground_hit(b,scroll,world,tgt.y)

# Game still updates jet, fires and bombs on SAME input tick, without stage reset.
scene=PlayScene(None,None,stages,collisions=False)
old=scene.jet.screen_xy
scene.tick(Joystick(up=True,right=True,fire=True,bomb=True))
assert scene.jet.screen_xy==(old[0]+1,old[1]-1)
assert scene.bullets.active_count==1 and scene.bombs.active_count==1
assert scene.speed.pixels==1
for _ in range(4):scene.tick(Joystick(bomb=True,fire=True))
assert scene.bombs.bombs_dropped==1 and scene.bullets.shots_fired==1

# Trigger a bomb-to-ground hit in the ACTUAL PlayScene, not only in a helper.
scene=PlayScene(None,None,stages,collisions=False)
scene.hud.high_score=0
scene.speed.pixels=scroll
scene.bombs.slots[0]=Bomb(True,1,tgt.y+7,238-(64+8),0)
# Move applies the next ROM pair, then the scroll moves by 1. Allow tolerance.
scene.tick(Joystick())
assert scene.last_hit and scene.last_hit[0]=='ROCKET',scene.last_hit
assert scene.hud.score==50 and scene.hud.high_score==50
assert scene.bombs.hits==1 and scene.bombs.active_count==0
assert (0,tgt.record_index) in scene.hit_targets

# Base hit by a bomb launches original mission sequence and restarts loop.
scene=PlayScene(None,None,stages,collisions=False)
scene.hud.high_score=0
base=stages[-1].targets[0]
scene.speed.pixels=scene.course.last_scroll
scene.at_base_end=True;scene.stage_idx=5
base_view=course.target_world_x(5,base)-scene.speed.pixels
scene.bombs.slots[0]=Bomb(True,1,base.y+7,238-(base_view+8),0)
scene.tick(Joystick())
assert scene.last_hit and scene.last_hit[0]=='BASE',scene.last_hit
assert scene.run_state=='cool_off' and scene.base_destroyed
assert scene.hud.score==800
for _ in range(150+5+256):scene.tick()
assert scene.run_state=='playing' and scene.loop_number==2
assert scene.bombs.active_count==0 and not scene.hit_targets

# Developer spy verifies bomb sprite draw in game, alongside both jet halves.
class FakeSurface:
    def __init__(self,*args):pass
    def fill(self,*args):pass
    def blit(self,*args):pass
    def set_at(self,*args):pass
    def convert_alpha(self):return self
class FakePG:
    SRCALPHA=1
    Surface=FakeSurface
    @staticmethod
    def Rect(*args):return args
    class draw:
        @staticmethod
        def rect(*args):pass
class FakeBank:
    pg=FakePG
    def __init__(self):self.sprites=[]
    def character(self,*a):pass
    def ground_object(self,*a):pass
    def sprite(self,surface,x,y,code,colour):self.sprites.append((x,y,code,colour))
    def text(self,*a):pass
bank=FakeBank()
scene=PlayScene(FakePG,bank,stages)
scene.show_clearance=False
scene.tick(Joystick(bomb=True))
scene.tick(Joystick())
scene.tick(Joystick())
scene.render(FakeSurface())
assert len(bank.sprites)==3,bank.sprites
assert bank.sprites[0][2:]==(0x21,6),bank.sprites

print('PASS: 203 ROM-derived bomb steps / edge-trigger / two slots / init+trajectory')
print('      ground hits +50, base +800 and restart; jet+bullet controls preserved; sprite render.')
