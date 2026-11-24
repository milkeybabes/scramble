"""Pillow static comparison samples around seamless stage boundaries."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw, ImageFont
from scramble_scroll import read_stages, VIEW_WIDTH,VIEW_HEIGHT
from scramble_course import ContinuousCourse
from scramble_objects import ROTATED_GROUP_ORDER
from scramble_hud import character_xy

ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'
stages=read_stages();course=ContinuousCourse(stages)
colour=4
chars=Image.open(DATA/f'characters_color_{colour}.png').convert('RGBA')
sprites={c:Image.open(DATA/f'sprites_color_{c}.png').convert('RGBA') for c in (0,6)}

def blit_character(canvas,x,y,code):
    atlas_x=(code%16)*8; atlas_y=(code//16)*8
    canvas.alpha_composite(chars.crop((atlas_x,atlas_y,atlas_x+8,atlas_y+8)),(x,y)) if 0 <= x <= 216 else canvas.paste(chars.crop((atlas_x,atlas_y,atlas_x+8,atlas_y+8)),(x,y),chars.crop((atlas_x,atlas_y,atlas_x+8,atlas_y+8)))

def draw_object(cv,x,y,group):
    base=group*4
    for dx,dy,i in ((0,0,0),(8,0,1),(0,8,2),(8,8,3)):
        blit_character(cv,x+dx,y+dy,base+ROTATED_GROUP_ORDER[i])

def frame(scroll):
    bg=(0,0,0x56,255)
    cv=Image.new('RGBA',(VIEW_WIDTH,VIEW_HEIGHT),bg)
    for item in course.visible_slices(scroll):
        if item.stage_index == -1:
            for x in range(0,course.prefill_width,8):
                sx=x-scroll
                blit_character(cv,sx,25*8,0x36)
                for row in range(26,29):blit_character(cv,sx,row*8,0x39)
            continue
        stage=stages[item.stage_index]
        for ci in range(item.source_x//8, (item.source_x+item.width+7)//8):
            if ci >= len(stage.cols):break
            sx=course.starts[item.stage_index]+ci*8-scroll
            for yi in range(5,29):
                code=stage.cols[ci][yi]
                if code!=0x10:blit_character(cv,sx,yi*8,code)
        for t in stage.targets:
            tx=course.starts[item.stage_index]+t.x-scroll
            if -16<tx<VIEW_WIDTH:
                draw_object(cv,tx,t.y,t.group)
    # Original two-part jet at spawn position; don't pretend this is gameplay.
    for code,col,x in ((0x27,0,6),(0x28,6,22)):
        atlas=sprites[col];sx=code%8*16;sy=code//8*16
        img=atlas.crop((sx,sy,sx+16,sy+16))
        cv.alpha_composite(img,(x,81))
    return cv.convert('RGB')

cases=[
 ('FLAT START + FIRST ROCKS',96),
 ('STAGE 1 -> CAVES', course.starts[1]-VIEW_WIDTH//2),
 ('MAZE -> BASE',course.starts[5]-VIEW_WIDTH//2),
 ('END: BASE REMAINS VISIBLE',course.last_scroll),
]
S=2;pad=20;head=34
W=2*(VIEW_WIDTH*S+pad)+pad;H=2*(VIEW_HEIGHT*S+head+pad)+pad
out=Image.new('RGB',(W,H),(19,23,34));d=ImageDraw.Draw(out)
for k,(caption,pos) in enumerate(cases):
    x=pad+(k%2)*(VIEW_WIDTH*S+pad)
    y=pad+(k//2)*(VIEW_HEIGHT*S+head+pad)
    d.text((x,y+5),caption,fill=(235,239,245))
    im=frame(pos).resize((VIEW_WIDTH*S,VIEW_HEIGHT*S),Image.Resampling.NEAREST)
    out.paste(im,(x,y+head))
out.save(DATA/'continuous_course_preview.png')
print(DATA/'continuous_course_preview.png')
