"""Regress the real ROM per-column palette pattern, HUD and mission message."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scramble_palette import (
    GAMEPLAY_BASE_ATTRIBUTES, MISSION_COMPLETE_ATTRIBUTES,
    character_colour, column_colour, gameplay_attributes, screen_y_colour)
from scramble_hud import draw_hud, HUDValues, character_xy
from scramble_scroll import colour_after_next_change
from scramble_game import PlayScene
from scramble_scroll import read_stages

assert len(GAMEPLAY_BASE_ATTRIBUTES) == len(MISSION_COMPLETE_ATTRIBUTES) == 32
assert GAMEPLAY_BASE_ATTRIBUTES[:5] == (0, 5, 0, 7, 7)
assert GAMEPLAY_BASE_ATTRIBUTES[30:] == (1, 6)
assert MISSION_COMPLETE_ATTRIBUTES[12:18] == (4, 4, 5, 5, 6, 6)
assert character_colour(0x4B5E) == 1  # FUEL $4B5E raw column 30
assert character_colour(0x4ABE) == 1  # fuel gauge same row
assert character_colour(0x4BBF) == 6  # remaining-life sprites raw col 31
assert character_colour(0x4B63) == 7  # progress bar top row
assert character_colour(0x4B64) == 7  # progress bar second row
assert (character_colour(0x4ACC, mission_complete=True),
        character_colour(0x4B6E, mission_complete=True),
        character_colour(0x4B70, mission_complete=True)) == (4, 5, 6)

class FakeSurface:
    def fill(self,*a): pass
    def blit(self,*a): pass
    def set_at(self,*a): pass

class FakePG:
    SRCALPHA=1
    @staticmethod
    def Surface(*a): return FakeSurface()
    @staticmethod
    def Rect(*a):return a
    class draw:
        @staticmethod
        def rect(*a):pass

class WatchBank:
    pg=FakePG
    def __init__(self):self.calls=[]
    def character(self, surf, x,y,code,col): self.calls.append((x,y,code,col))
    def text(self, surf,x,y,value,col): self.calls.append((x,y,value,col))
    def sprite(self,*a):pass
    def ground_object(self,*a):pass

for pal in range(8):
    attrs=gameplay_attributes(pal)
    assert attrs[:5] == (0,5,0,7,7),attrs
    assert attrs[5:30] == (pal,) * 25,attrs
    assert attrs[30:] == (1,6),attrs
    assert screen_y_colour(240,pal) == 1
    assert screen_y_colour(248,pal) == 6
    assert screen_y_colour(200,pal) == pal
    assert column_colour(29,pal) == pal
    b=WatchBank()
    draw_hud(None,b,stage_index=2,frame=0,hud=HUDValues())
    fuel=[c for c in b.calls if c[:3] == (*character_xy(0x4B5E),'FUEL')]
    assert len(fuel)==1 and fuel[0][3]==1,(pal,fuel)
    assert any(c[-1]==1 for c in b.calls if c[1]==240)

b=WatchBank()
scene=PlayScene(FakePG,b,read_stages())
scene.run_state='message'
scene.render(FakeSurface())
for addr,txt,col in [(0x4ACC,'CONGRATULATIONS',4),
                      (0x4B6E,'YOU COMPLETED YOUR DUTIES',5),
                      (0x4B70,'GOOD LUCK NEXT TIME AGAIN',6)]:
    assert (*character_xy(addr),txt,col) in b.calls, (txt,b.calls)

# Start from 4; ROM cycle skips index 1 in landscape, but index 1 remains
# valid and MUST remain enabled for the HUD's static FUEL label.
pal=4
sequence=[]
for _ in range(8):
    sequence.append(pal)
    pal=colour_after_next_change(pal)
assert sequence == [4,5,6,7,0,2,3,4],sequence
print('PASS: 32 ROM attributes, 8 landscape colours, fixed yellow FUEL,')
print('      red/yellow/cyan mission texts and isolated playfield cycling.')
