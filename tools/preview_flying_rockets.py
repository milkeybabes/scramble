"""Pillow-only still frame of the same indexed assets and rocket positions.

This is a development illustration, not a MAME-exact frame capture.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw, ImageFont
from scramble_game import PlayScene
from scramble_scroll import read_stages
from scramble_objects import ROTATED_GROUP_ORDER
from scramble_palette import screen_y_colour, character_colour
from scramble_hud import draw_hud
from scramble_stars import blink_state,star_visible

DATA=Path(__file__).resolve().parents[1]/'data'

class PG:
    class draw:
        @staticmethod
        def rect(surface, color, rect):
            x,y,w,h=rect
            ImageDraw.Draw(surface).rectangle((x,y,x+w-1,y+h-1),fill=tuple(color))

class Bank:
    pg=PG
    def __init__(self):
        self.chars=[Image.open(DATA/f'characters_color_{i}.png').convert('RGBA') for i in range(8)]
        self.sprites=[Image.open(DATA/f'sprites_color_{i}.png').convert('RGBA') for i in range(8)]
    def character(self, surf,x,y,code,colour):
        src=self.chars[colour].crop(((code%16)*8,(code//16)*8,(code%16+1)*8,(code//16+1)*8))
        surf.paste(src,(int(x),int(y)),src)
    def sprite(self,surf,x,y,code,colour):
        num=code&63
        src=self.sprites[colour].crop((num%8*16,num//8*16,num%8*16+16,num//8*16+16))
        if code&0x80:src=src.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if code&0x40:src=src.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        surf.paste(src,(int(x),int(y)),src)
    def ground_object(self,surf,x,y,group,colour):
        for xx,yy,order in ((0,0,2),(8,0,0),(0,8,3),(8,8,1)):
            self.character(surf,x+xx,y+yy,group*4+order,colour)
    def text(self,surf,x,y,val,colour):
        for i,ch in enumerate(val.upper()):
            if ch==' ':code=0x10
            elif '0'<=ch<='9':code=ord(ch)-48
            elif 'A'<=ch<='Z':code=ord(ch)-65+0x11
            else:code=0x10
            self.character(surf,x+8*i,y,code,colour)

bank=Bank()

def frame(scene):
    bg=(0,0,0x56) if scene.colour in (4,5) else (0,0,0)
    cv=Image.new('RGBA',(224,256),bg+(255,))
    if scene.stage.flags & 0x1c == 0:
        phase=blink_state(scene.frames)
        for x,y,rgb,flags in scene.stars:
            if star_visible(flags,phase) and 0<=x<224 and 0<=y<256:
                cv.putpixel((x,y),(*rgb,255))
    offset=scene.speed.pixels
    for item in scene.course.visible_slices(offset):
        if item.stage_index == -1:
            for x in range(0,224,8):
                xx=x-offset
                if xx < -8 or xx >= 224:continue
                bank.character(cv,xx,200,0x36,scene.colour)
                for y in (208,216,224):bank.character(cv,xx,y,0x39,scene.colour)
        else:
            stage=scene.stages[item.stage_index]
            for ci,col in enumerate(stage.cols):
                sx=scene.course.starts[item.stage_index]+ci*8-offset
                if sx < -8 or sx>=224:continue
                for j in range(5,29):
                    code=col[j]
                    if code!=0x10:bank.character(cv,sx,j*8,code,screen_y_colour(j*8,scene.colour))
    for i,stage in enumerate(scene.stages):
        for t in stage.targets:
            if (i,t.record_index) in scene.hit_targets:continue
            x=scene.course.target_world_x(i,t)-offset
            if -16<x<224:
                code=scene.base_anim.current.code if t.kind=='BASE' else t.group
                bank.ground_object(cv,x,t.y,code,scene.colour)
    scene.ground_effects.render(bank,cv,offset,scene.colour)
    for r in scene.rockets.slots:
        if (r.active or r.exploding) and r.animation and r.visible:
            x,y=r.screen_xy
            if -16<x<224 and 30<y<240:
                code=r.animation.current.code
                bank.sprite(cv,x,y,code,scene.colour if r.active else r.animation.current.colour)
    for b in scene.bullets.slots:
        if b.active:
            x,y=b.screen_xy
            if 0<=x<224 and 40<=y<240:cv.putpixel((x,y),(255,255,0,255))
    if scene.run_state=='playing':
        bank.sprite(cv,*scene.jet.rear_screen_xy,scene.jet_rear_anim.current.code,scene.jet_rear_anim.current.colour)
        bank.sprite(cv,*scene.jet.screen_xy,scene.jet_anim.current.code,scene.jet_anim.current.colour)
    draw_hud(cv,bank,scene.stage_idx,scene.frames,scene.hud)
    return cv.convert('RGB')

imgs=[]
for at in (330,640,710):
    s=PlayScene(None,None,read_stages(),collisions=False,fuel_enabled=False)
    for _ in range(at):s.tick()
    imgs.append((at,s,frame(s)))
zoom=2
out=Image.new('RGB',(len(imgs)*224*zoom+64,256*zoom+74),'#151721')
draw=ImageDraw.Draw(out)
try:
    font=ImageFont.truetype('DejaVuSans.ttf',15)
except OSError:font=ImageFont.load_default()
for i,(at,s,im) in enumerate(imgs):
    x=16+i*224*zoom;y=42
    im=im.resize((224*zoom,256*zoom),Image.Resampling.NEAREST)
    out.paste(im,(x,y))
    draw.text((x,10),f'FRAME {at}  /  ROCKETS {s.rockets.active_count}',fill='white',font=font)
    draw.text((x,y+256*zoom+8),f'Launches: {s.rockets.launches} | Palette: {s.colour}',fill='#adbacc',font=font)
path=Path('/mnt/data/Scramble_Flying_Rockets_Preview.png')
out.save(path)
print(path,out.size)
