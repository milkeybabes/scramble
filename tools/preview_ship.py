"""Still diagnostic scenes using Phase-3 Pillow raster, plus Phase-4 jet positions."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw, ImageFont
from scramble_player import PlayerJet, Joystick,terrain_clearance
from scramble_scroll import read_stages
from preview_scrolling import make_sheet

ROOT=Path(__file__).resolve().parents[1]
panel_scale=2
pad=16
label_h=44
scenes=[(0,320,[], 'STAGE 1 / ORIGINAL SPAWN'),
        (4,0,[], 'STAGE 5 / MAZE ENTRANCE'),
        (4,128,[Joystick(up=True,right=True)]*30, 'STAGE 5 / DIAGONAL MOVEMENT')]
width=224*panel_scale; height=256*panel_scale
canvas=Image.new('RGB',(3*(width+pad)+pad,height+label_h+pad*2),(14,19,30))
font=ImageFont.load_default();draw=ImageDraw.Draw(canvas)
for i,(stage_idx,offset,inputs,title) in enumerate(scenes):
    jet=PlayerJet()
    for step in inputs:jet.update(step)
    tile=make_sheet(stage_idx,4,offset,draw_reference_jet=False)
    # Both graphics used by the live player renderer: rear first, then body.
    for code, colour, xy in ((0x27,0,jet.rear_screen_xy),
                             (0x28,6,jet.screen_xy)):
        atlas=Image.open(ROOT/'data'/f'sprites_color_{colour}.png').convert('RGBA')
        frag=atlas.crop(((code%8)*16,(code//8)*16,(code%8+1)*16,(code//8+1)*16))
        tile.alpha_composite(frag,xy)
    clear,_,_=terrain_clearance(read_stages()[stage_idx],offset,jet)
    dx=pad+i*(width+pad);dy=pad+label_h
    draw.text((dx,pad),title,fill=(241,246,253),font=font)
    draw.text((dx,pad+16),f'Z80 X=${jet.x:02X} Y=${jet.y:02X}   SCREEN {jet.screen_xy}   Geometry={"clear" if clear else "contact"}',fill=(177,203,223),font=font)
    canvas.paste(tile.convert('RGB').resize((width,height),Image.Resampling.NEAREST),(dx,dy))
out=ROOT/'data'/'ship_preview.png'
canvas.save(out,optimize=True)
print(out)
