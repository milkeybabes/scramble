"""Generate a ROM-asset-based comparison of Scramble's colour attribute rows.

This uses prepared character PNGs, not pygame or Z80 hardware emulation.
"""
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scramble_palette import column_colour, character_colour, MISSION_COMPLETE_ATTRIBUTES
from scramble_hud import character_xy, fuel_codes

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
ATLAS=[Image.open(DATA/f'characters_color_{i}.png').convert('RGBA') for i in range(8)]


def char(code, pal):
    x=(code%16)*8;y=(code//16)*8
    return ATLAS[pal].crop((x,y,x+8,y+8))


def draw_text(image, x,y,s,pal):
    for i,v in enumerate(s):
        c=0x10 if v==' ' else (ord(v)-48 if v.isdigit() else ord(v)-ord('A')+0x11)
        image.alpha_composite(char(c,pal),(x+i*8,y))


def ground(image,x,y,group,pal):
    # The asset sheet already contains the four *individual* character tiles.
    # Same order the current renderer uses after ROT90.
    from scramble_objects import ROTATED_GROUP_ORDER
    base=group*4
    for q,(xx,yy) in enumerate(((0,0),(8,0),(0,8),(8,8))):
        image.alpha_composite(char(base+ROTATED_GROUP_ORDER[q],pal),(x+xx,y+yy))


S=3
PANEL_W,PANEL_H=224,96
out=Image.new('RGB',(4*(PANEL_W*S+24)+24,2*(PANEL_H*S+47)+220),(17,19,25))
d=ImageDraw.Draw(out)
d.text((24,12),'Scramble - original column attributes / changing landscape colours',fill=(245,245,245))
d.text((24,32),'FUEL HUD always palette 1 (yellow); fuel tanks inherit moving playfield colour',fill=(172,187,201))
for pal in range(8):
    local=Image.new('RGBA',(PANEL_W,PANEL_H),(0,0,0,255))
    # A sample of the flat ground drawn in the changing playfield row 25-29.
    for xx in range(0,PANEL_W,8):
        local.alpha_composite(char(0x36,pal),(xx,48))
        for yy in range(56,80,8): local.alpha_composite(char(0x39,pal),(xx,yy))
    ground(local,120,32,0x10,pal)
    # Real $4B5E (row 30) and $4ABE fuel cell tiles, always palette 1.
    draw_text(local,0,80,'FUEL',character_colour(0x4B5E,pal))
    for i,code in enumerate(fuel_codes(176)):
        local.alpha_composite(char(code,character_colour(0x4ABE-i*0x20,pal)),(32+8*i,80))
    xx=24+(pal%4)*(PANEL_W*S+24)
    yy=65+(pal//4)*(PANEL_H*S+47)
    d.text((xx,yy),f'LANDSCAPE COLOUR {pal}  |  FUEL HUD COLOUR {character_colour(0x4B5E,pal)}',fill=(242,243,245))
    out.paste(local.resize((PANEL_W*S,PANEL_H*S),Image.Resampling.NEAREST).convert('RGB'),(xx,yy+18))

# A smaller on-source completion text demonstration.
footer_y=2*(PANEL_H*S+47)+66
msg=Image.new('RGBA',(224,32),(0,0,0,255))
for yy,(addr,line) in enumerate([(0x4ACC,'CONGRATULATIONS'),(0x4B6E,'YOU COMPLETED YOUR DUTIES'),(0x4B70,'GOOD LUCK NEXT TIME AGAIN')]):
    # Each string has its own column attribute from $0B89.
    draw_text(msg,0,yy*8,line[:28],character_colour(addr,mission_complete=True))
out.paste(msg.resize((896,128),Image.Resampling.NEAREST).convert('RGB'),(24,footer_y))
d.text((930,footer_y+10),'Mission-complete palette table $0B89:',fill=(240,240,240))
d.text((930,footer_y+40),'red/orange -> yellow -> cyan',fill=(178,197,207))
path=DATA/'palette_attribute_preview.png'
out.save(path)
print(f'Wrote {path}')
