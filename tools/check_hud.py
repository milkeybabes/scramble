"""Validate HUD coordinate conversion, ROM character groups, and render coverage."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scramble_hud import character_xy,score_digits,fuel_codes,HUDValues,draw_hud,PROGRESS_HEADERS

assert character_xy(0x4B40)==(24,0)   # 1UP
assert character_xy(0x4A80)==(72,0)   # HIGH SCORE
assert character_xy(0x4B81)==(8,8)    # P1 score begins 8px below header
assert character_xy(0x4A41)==(88,8)   # high score
assert character_xy(0x4B63)==(16,24)  # header cells
assert character_xy(0x4B64)==(16,32)  # progress cells
assert character_xy(0x4B5E)==(24,240) # FUEL label
assert character_xy(0x4ABE)==(64,240) # fuel gauge
assert character_xy(0x4BBF)==(0,248)  # reserve jets
assert character_xy(0x485F)==(216,248)# mission flags
assert len(PROGRESS_HEADERS)==24
assert score_digits(0)=='    00'
assert score_digits(50)=='    50'
assert score_digits(15850)==' 15850'
assert score_digits(123456)=='123456'
for f in range(256):
    cells=fuel_codes(f)
    assert len(cells)==16
    assert cells.count(0xCB)==f//16
    assert set(cells) <= {0x3C,0xC4,0xC5,0xC6,0xC7,0xC8,0xC9,0xCA,0xCB}
assert fuel_codes(255)==(0xCB,)*15+(0xCA,)
assert fuel_codes(0)==(0x3C,)*16

class SpyPG:
    class draw:
        @staticmethod
        def rect(*args): pass
class SpyBank:
    pg=SpyPG()
    def __init__(self):self.calls=[]
    def character(self,surface,x,y,code,palette):
        assert 0<=x<224 and 0<=y<256
        assert 0<=code<256 and 0<=palette<8
        self.calls.append((x,y,code,palette))
    def text(self,surface,x,y,value,palette):
        for i,ch in enumerate(value):
            if ch==' ':code=0x10
            elif ch.isdigit():code=ord(ch)-48
            else:code=ord(ch)-ord('A')+0x11
            self.character(surface,x+i*8,y,code,palette)

for stage in range(6):
    b=SpyBank();draw_hud(None,b,stage,0,HUDValues())
    headers=[x for x in b.calls if x[1]==24]
    cells=[x for x in b.calls if x[1]==32]
    assert len(headers)==24 and len(cells)==24
    assert [x[2] for x in headers]==list(PROGRESS_HEADERS)
    assert [x[2] for x in cells]==[
        (0x81,0x82,0x82,0x83)[i%4] if i//4<=stage
        else (0x6E,0x6F,0x6F,0x80)[i%4] for i in range(24)]
    assert len([x for x in b.calls if x[1]==240 and x[0]>=64])==16
    assert len([x for x in b.calls if x[1]==248 and x[0]<96])==6
print('OK: original HUD addresses, 24-char progress table, 256 fuel values, 6 stages, reserve lives/flags and leading zero suppression.')
