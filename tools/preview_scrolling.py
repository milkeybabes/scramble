"""Headless diagnostic gallery using the same tile columns as scroll_viewer.py.

Use: py tools/preview_scrolling.py
Uses Pillow only, not pygame. All preview pictures are still screenshots of
our native tile-strip construction, NOT MAME captures.
"""
from __future__ import annotations
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scramble_scroll import read_stages, visible_columns,VIEW_WIDTH,VIEW_HEIGHT,reference_jet_y
from scramble_objects import ROTATED_GROUP_ORDER
from PIL import Image,ImageDraw,ImageFont
from scroll_viewer import scramble_stars

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT / 'data' / 'scrolling_preview.png'


def make_sheet(idx:int,palette:int=4,position:int=0,draw_reference_jet:bool=True):
    stage=read_stages()[idx]
    position=min(position,stage.scroll_limit)
    atlas=Image.open(ROOT/'data'/f'characters_color_{palette}.png').convert('RGBA')
    # Transparency from saved tiles is retained.
    bg=(0,0,0x56,255) if palette in (4,5) else (0,0,0,255)
    out=Image.new('RGBA',(VIEW_WIDTH,VIEW_HEIGHT),bg)
    # Original Galaxian LFSR star positions (sample blink phase).
    current = stage.records[min(len(stage.records)-1,(position+VIEW_WIDTH)//16)]
    if not current['ceiling']:
        for sx,sy,rgb,flags in scramble_stars():
            if flags & 1: out.putpixel((sx,sy),(*rgb,255))
    def tile(x,y,code):
        # Atlas is 16 columns x 16 rows, with 8x8 cells.
        ox=(code%16)*8; oy=(code//16)*8
        part=atlas.crop((ox,oy,ox+8,oy+8))
        out.alpha_composite(part,(int(x),int(y))) if x>=0 and x+8<=VIEW_WIDTH and y>=0 and y+8<=VIEW_HEIGHT else out.paste(part,(int(x),int(y)),part)
    for x, col, ci in visible_columns(stage,position):
        for row in range(5,29):
            code=col[row]
            if code != 0x10:
                tile(x,row*8,code)
    for target in stage.targets:
        sx=target.x-position
        if sx < -16 or sx >= VIEW_WIDTH:continue
        base=target.group*4
        for dx,dy,which in ((0,0,0),(8,0,1),(0,8,2),(8,8,3)):
            tile(sx+dx,target.y+dy,base+ROTATED_GROUP_ORDER[which])
    # Present the identical indexed HUD as the current pygame viewer.
    from preview_hud import apply_hud
    apply_hud(out, idx, 0)
    sprite=Image.open(ROOT/'data'/'sprites_color_6.png').convert('RGBA')
    code=0x28
    sx=(code%8)*16;sy=(code//8)*16
    ship=sprite.crop((sx,sy,sx+16,sy+16))
    yjet=reference_jet_y(stage,position)
    if draw_reference_jet and yjet is not None:out.paste(ship,(32,yjet),ship)
    return out


def main():
    stages=read_stages()
    panel_scale=2
    pad=16
    label_h=34
    cols=3;rows=2
    panel_w=VIEW_WIDTH*panel_scale;panel_h=VIEW_HEIGHT*panel_scale
    canvas=Image.new('RGB',(cols*(panel_w+pad)+pad,rows*(panel_h+label_h+pad)+pad),(15,18,28))
    draw=ImageDraw.Draw(canvas)
    font=ImageFont.load_default()
    # Each stage is shown from a different point in its terrain to demonstrate
    # cave/maze features; this is not a single gameplay timeline.
    offsets=(320,496,240,608,128,180)
    for i,stage in enumerate(stages):
        col=i%cols;row=i//cols
        x=pad+col*(panel_w+pad);y=pad+row*(panel_h+label_h+pad)
        offset=min(offsets[i],stage.scroll_limit)
        draw.text((x,y),f'{i+1}  {stage.name} | px={offset}',fill=(233,237,247),font=font)
        img=make_sheet(i,4,offset).resize((panel_w,panel_h),Image.Resampling.NEAREST)
        canvas.paste(img.convert('RGB'),(x,y+label_h))
    canvas.save(OUT,optimize=True)
    print(f'Wrote {OUT} ({canvas.width}x{canvas.height})')


if __name__=='__main__':main()
