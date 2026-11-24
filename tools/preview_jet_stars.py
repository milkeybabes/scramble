"""Pillow-only QA preview. Original ROM atlases + MAME blink-state filter."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image,ImageDraw
from scramble_stars import blink_state, star_visible
from scroll_viewer import scramble_stars

DATA=Path(__file__).resolve().parents[1]/'data'
rear_atlas=Image.open(DATA/'sprites_color_0.png').convert('RGBA')
body_atlas=Image.open(DATA/'sprites_color_6.png').convert('RGBA')
stars=scramble_stars()
res=Image.new('RGB',(4*448+3*10,580),'#111827')
pen=ImageDraw.Draw(res)
for i,frame in enumerate((0,51,101,152)):
    stage=blink_state(frame)
    pane=Image.new('RGB',(224,256),'black')
    plot=ImageDraw.Draw(pane)
    for x,y,rgb,flags in stars:
        if star_visible(flags,stage):plot.point((x,y),fill=rgb)
    a,b=(0x27,0x29,0x2B,0x2D)[i],(0x28,0x2A,0x2C,0x2E)[i]
    def paste(code,atlas,x,y):
        patch=atlas.crop(((code%8)*16,(code//8)*16,(code%8+1)*16,(code//8+1)*16))
        pane.paste(patch,(x,y),patch)
    paste(a,rear_atlas,58,111)
    paste(b,body_atlas,74,111)
    scaled=pane.resize((448,512),Image.Resampling.NEAREST)
    x=i*(448+10)
    res.paste(scaled,(x,44))
    pen.text((x+8,15),f'STAR PHASE {stage}  FRAME {frame}  BODY ${b:02X}  REAR ${a:02X}',fill='#ffffff')
res.save(DATA/'jet_stars_preview.png')
print(DATA/'jet_stars_preview.png')
