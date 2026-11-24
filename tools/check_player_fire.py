"""Deterministic native-Python tests: movement retained and shooting works."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scramble_scroll import read_stages
from scramble_game import PlayScene,parse_input_script,TRACE_FIELDS,row
from scramble_player import Joystick,PlayerJet
from scramble_bullets import PlayerBullets,Bullet

# Original source $257F edge-triggered fire and 4 free slots.
p=PlayerJet(); shots=PlayerBullets()
assert shots.spawn_on_press(True,p)
assert shots.slots[0].active and (shots.slots[0].x,shots.slots[0].y)==(0x5A,0xC9)
assert shots.slots[0].screen_xy==(38,89)
for _ in range(10):
    assert not shots.spawn_on_press(True,p), 'Holding must not autofire'
assert shots.shots_fired==1 and shots.active_count==1
shots.move()
assert shots.slots[0].y==0xC6 and shots.slots[0].screen_xy==(41,89)
for n in range(3):
    assert not shots.spawn_on_press(False,p)
    assert shots.spawn_on_press(True,p)
assert shots.active_count==4
assert not shots.spawn_on_press(False,p)
assert not shots.spawn_on_press(True,p), 'All 4 slots filled'
assert shots.shots_fired==4
shots.slots[1].active=False
shots.spawn_on_press(False,p)
assert shots.spawn_on_press(True,p), 'Reuse freed slot'
assert shots.active_count==4
shots.reset()
assert shots.active_count==0 and shots.shots_fired==0
shots.slots[0]=Bullet(True,0xF0,0xC0)
assert shots.terrain_hits(PlayScene(None,None,read_stages(),collisions=False).course,0)==1
assert shots.active_count==0

# Game entry point: jet still moves with fire, scrolling continues, stage transitions don't reset it.
scene=PlayScene(None,None,read_stages(),collisions=False)
old=scene.jet.screen_xy
scene.tick(Joystick(right=True,up=True,fire=True))
assert scene.jet.screen_xy==(old[0]+1,old[1]-1), 'Movement lost from PlayScene.tick!'
assert scene.speed.pixels==1 and scene.bullets.active_count==1
assert scene.bullets.shots_fired==1
for _ in range(10):scene.tick(Joystick(right=True,fire=True))
assert scene.jet.screen_x==old[0]+11
assert scene.bullets.shots_fired==1
assert len(TRACE_FIELDS)==len(row(scene)), 'Trace header/data out of sync'
assert parse_input_script('R+F:1,R:2,N:1,F:1')[-1].fire

# Actual hit on first-stage ground rocket near level plateau: bullet disappears,
# target is removed, +50 original points, high score tracks if appropriate.
scene=PlayScene(None,None,read_stages(),collisions=False,rockets_enabled=False);scene.hud.high_score=0
# Legacy ground-target shot is isolated from the new flying-rocket subsystem.
for _ in range(29):scene.tick(Joystick(down=True))
for _ in range(305-scene.speed.pixels):scene.tick(Joystick())
scene.tick(Joystick(fire=True))
assert scene.bullets.active_count==1
for _ in range(60):
    scene.tick(Joystick())
    if scene.last_hit:break
assert scene.last_hit and scene.last_hit[0]=='ROCKET', scene.last_hit
assert scene.bullets.active_count==0 and scene.bullets.hits==1
assert scene.hud.score==50 + 10*(scene.frames//64) and scene.hud.high_score==scene.hud.score
assert len(scene.hit_targets)==1 and scene.run_state=='playing'

# A projectile can hit the actual BASE. We do not need the M debug control:
# this exercises the base hit->mission state path without explosions.
scene=PlayScene(None,None,read_stages(),collisions=False)
base=scene.stages[-1].targets[0]
assert base.kind=='BASE'
scene.speed.pixels=scene.course.last_scroll
scene.at_base_end=True
scene.stage_idx=5
base_view_x=scene.course.target_world_x(5,base)-scene.speed.pixels
# Bullet is moved 3 pixels before collision: after step, it lands at x=base+8.
final_bullet_y=239-(base_view_x+8)
scene.bullets.slots[0]=Bullet(True,base.y+8, (final_bullet_y+3)&0xff)
scene.tick(Joystick())
assert scene.hud.score==800 and scene.last_hit[0]=='BASE',scene.last_hit
assert scene.run_state=='cool_off' and scene.base_destroyed
assert scene.bullets.active_count==0
for _ in range(150+5+256):scene.tick()
assert scene.run_state=='playing' and scene.loop_number==2 and scene.hud.score==800
assert scene.bullets.active_count==0 and not scene.hit_targets

# Headless rendering spy: ensure main view draws BOTH jet parts and the
# exact yellow 1px bullet while scenery remains composited in the same scene.
class FakeSurface:
    def __init__(self,*args): self.pixels=[]
    def convert_alpha(self):return self
    def fill(self,*args):pass
    def blit(self,*args):pass
    def set_at(self,pos,color):self.pixels.append((pos,color))
class FakePG:
    SRCALPHA=1
    Surface=FakeSurface
    @staticmethod
    def Rect(*parts):return parts
    class draw:
        @staticmethod
        def rect(*args):pass
class FakeBank:
    pg=FakePG
    def __init__(self):self.sprites=[];self.targets=[]
    def character(self,*args):pass
    def sprite(self,surf,x,y,code,colour):self.sprites.append((x,y,code,colour))
    def ground_object(self,surf,x,y,code,colour):self.targets.append((x,y,code,colour))
    def text(self,*args):pass

bank=FakeBank()
scene=PlayScene(FakePG,bank,read_stages())
scene.show_clearance=False
scene.tick(Joystick(up=True,right=True,fire=True))
cv=FakeSurface()
scene.render(cv)
assert len(bank.sprites)==2, bank.sprites  # rear flame and main ship
assert ((39,88),(239,239,0)) in cv.pixels, cv.pixels[:3]

print('PASS: main-game movement+fire, edge-trigger, max4, +3px/frame, terrain hit,')
print('      ground rocket +50, base +800 -> original mission sequence, input trace, restart.')
