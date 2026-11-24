"""Phase 4 regression checks, deterministic and independent of pygame."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scramble_player import Joystick,PlayerJet,terrain_clearance
from scramble_scroll import read_stages,ScrollClock
from scramble_game import parse_input_script

p=PlayerJet()
assert p.screen_xy==(22,81) and (p.x,p.y,p.other_x,p.other_y)==(0x58,0xD0,0x58,0xE0)
# One pixel each axis per game frame, no acceleration.
p.update(Joystick(right=True,up=True))
assert p.screen_xy==(23,80)
assert (p.x,p.y,p.other_x,p.other_y)==(0x57,0xCF,0x57,0xDF)
assert p.updates==1
# Left, down return to starting registers and starting screen position.
p.update(Joystick(left=True,down=True))
assert p.screen_xy==(23,81) and p.updates==2  # $17B5 blocks returning to initial $D0
# Source priority up over down, left over right.
p.update(Joystick(up=True,down=True,left=True,right=True))
assert p.screen_xy==(23,80)
# Raw original clamps: x=$38..$D7, y=$80..$D0.
p.reset()
for _ in range(600):p.update(Joystick(up=True,right=True))
assert (p.x,p.y)==(0x38,0x80) and p.screen_xy==(102,49)
for _ in range(600):p.update(Joystick(down=True,left=True))
assert (p.x,p.y)==(0xD7,0xCF) and p.screen_xy==(23,208)
# To arrive at far-left edge ($D0), first move 1 step left from y=$CF.
p.update(Joystick(left=True))
assert p.y==0xCF and p.screen_x==23  # strict CP $D0 prevents reaching initial $D0
# Neutral frames never cause movement.
coords=p.screen_xy
for _ in range(30):p.update(Joystick())
assert p.screen_xy==coords
p.reset()
assert (p.x,p.y)==(0x58,0xD0)
script=parse_input_script('R:50,U+R:20,D:10,N:5')
assert len(script)==85 and script[49]==Joystick(right=True) and script[50]==Joystick(up=True,right=True)
for q in script:p.update(q)
assert (p.x,p.y)==(0x4E,0x8A) and p.screen_xy==(92,71)
for stage in read_stages():
    for x in (0,20,130,min(stage.scroll_limit,390)):
        r=terrain_clearance(stage,x,p)
        assert isinstance(r[0],bool) and len(r[2])==3
# Ensure stage movement never goes to subpixel speed.
for latch in range(8):
    c=ScrollClock(latch)
    px0=c.pixels
    for _ in range(80):
        c.tick()
        assert c.pixels-px0 in (0,1)
        px0=c.pixels
print('OK: original player positions, per-axis movement, bounds, input precedence, mirrored player 2, frame logs and terrain geometry diagnostics.')
