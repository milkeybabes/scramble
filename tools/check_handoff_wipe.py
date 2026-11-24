"""Regression for MAME player-change wipe, timing and old-label bug."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scramble_game import PlayScene
from scramble_scroll import read_stages
from scramble_player import Joystick
from scramble_cabinet import (CabinetSession,INTRO_FRAMES,READY_FRAMES,
    TURN_DELAY,P2_TURN_DELAY,WIPE_FRAMES,wipe_clear_width,
    draw_turn_wipe,render_turn_intro)
from scramble_attract import AttractMode, BOOT_FRAMES, BOOT_WIPE_START

neutral=Joystick()
stages=read_stages()
def make_scene(n,lives=3):
    s=PlayScene(None,None,stages,lives=lives,collisions=False,fuel_enabled=False,
                rockets_enabled=False,aliens_enabled=False)
    s.player_number=n
    return s

def ticks(c,n):
    for _ in range(n): c.tick(neutral)

p1,p2=make_scene(1),make_scene(2)
c=CabinetSession([p1,p2]);assert c.phase=='intro'
ticks(c,INTRO_FRAMES);assert c.phase=='prepare'
ticks(c,READY_FRAMES);assert c.phase=='playing' and c.active==0
p1.goto(4);p1.hud.score=1440;p1.colour=4
assert p1.kill_player('test')
ticks(c,111);assert c.phase=='between' and c.active==0
assert c.pending_player==1
# It is NEVER a second 'intro' for the outgoing player.
ticks(c,TURN_DELAY-1);assert c.phase=='between' and c.active==0
ticks(c,1);assert c.phase=='wipe' and c.active==0
assert c.intro_background==(0,0,0x56) or c.intro_background==(0,0,0)
assert c.wipe_progress==0
ticks(c,WIPE_FRAMES);assert c.phase=='wipe' and c.wipe_progress==WIPE_FRAMES
assert c.active==0  # no incoming label before all memory strips clear
c.tick(neutral);assert c.phase=='intro' and c.active==1 and c.pending_player is None
assert p2.hud.score==0 and p1.hud.score==1440
ticks(c,INTRO_FRAMES);assert c.phase=='prepare' and c.active==1
ticks(c,READY_FRAMES);assert c.phase=='playing' and c.active==1
# P2 -> P1 has a longer $64 countdown. P1's stage and score survive.
p2.goto(2);p2.hud.score=620;p2.kill_player('test')
ticks(c,111+P2_TURN_DELAY);assert c.phase=='wipe' and c.active==1
ticks(c,WIPE_FRAMES+1);assert c.phase=='intro' and c.active==0
ticks(c,INTRO_FRAMES+READY_FRAMES)
assert c.phase=='playing' and p1.run_state=='playing' and p1.stage_idx==4
assert c.scores==(1440,620) and p1.hud.fuel==255
assert p1.remaining_lives==1 and p2.remaining_lives==2
# One player still has a proper wipe and intro after a death.
one=make_scene(1);solo=CabinetSession([one]);ticks(solo,INTRO_FRAMES+READY_FRAMES)
one.goto(4);one.kill_player('test');ticks(solo,111)
assert solo.phase=='between' and solo.pending_player==0
ticks(solo,TURN_DELAY+WIPE_FRAMES+1)
assert solo.phase=='intro' and solo.active==0
ticks(solo,INTRO_FRAMES+READY_FRAMES)
assert solo.phase=='playing' and one.stage_idx==4 and one.remaining_lives==1
# Render checks without pygame or a graphical window.
class MockSurface:
    def __init__(self): self.blocks=[];self.pixels=[];self.fills=[]
    def blit(self,*args): self.blocks.append(args)
    def set_at(self,*args):self.pixels.append(args)
    def fill(self,*args):self.fills.append(args)
class MockPG:
    class draw:
        rectangles=[]
        @staticmethod
        def rect(surface,colour,rect):
            MockPG.draw.rectangles.append((colour,rect))
class Bank:
    pg=MockPG
    def __init__(self):self.texts=[];self.chars=[]
    def text(self,s,x,y,t,col):self.texts.append(t)
    def character(self,*v):self.chars.append(v)
old=MockSurface();screen=MockSurface()
for k in (0,1,13,28,32):
    c.wipe_progress=k
    draw_turn_wipe(screen,old,c,[],0,lambda *a: True,MockPG)
    assert wipe_clear_width(k)==min(224,k*8)
assert any(rc[1]==(0,0,224,24) for rc in MockPG.draw.rectangles)
intro_bank=Bank()
c.active=1;c.phase='intro';c.intro_background=(0,0,0x56)
render_turn_intro(MockSurface(),intro_bank,c,[],0,lambda *a: True)
assert 'PLAYER TWO' in intro_bank.texts and 'PLAYER ONE' not in intro_bank.texts
assert BOOT_WIPE_START==160 and BOOT_FRAMES==192
# A 32-frame true memory strip effect, not a single-frame scene cut.
a=AttractMode()
for _ in range(BOOT_WIPE_START):a.tick()
assert a.page=='grid'
for _ in range(BOOT_FRAMES-BOOT_WIPE_START):a.tick()
assert a.page=='title'
print('PASS: 32-column VRAM wipe, outgoing/incoming label separation, startup grid, phase durations, 1P/2P resume')
