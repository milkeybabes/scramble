"""Pillow inspection of Phase 5 HUD, using the SAME draw_hud as the game.

Run: python tools/preview_hud.py
Only Pillow needed. Does not claim frame-exact MAME capture.
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image,ImageDraw,ImageFont
from scramble_hud import draw_hud,HUDValues
from scramble_scroll import VIEW_WIDTH,VIEW_HEIGHT

ROOT=Path(__file__).resolve().parents[1]

class FakeDraw:
    @staticmethod
    def rect(surface, color, rect):
        x,y,w,h=rect
        ImageDraw.Draw(surface).rectangle((x,y,x+w-1,y+h-1), fill=(*color,255))

class FakePG:
    draw=FakeDraw()

class PillowBank:
    def __init__(self):
        self.pg=FakePG()
        self.ats=[Image.open(ROOT/'data'/f'characters_color_{pal}.png').convert('RGBA')
                  for pal in range(8)]
    def character(self,surface,x,y,code,colour):
        a=self.ats[colour]
        frag=a.crop((code%16*8,code//16*8,code%16*8+8,code//16*8+8))
        if 0<=x<=VIEW_WIDTH-8 and 0<=y<=VIEW_HEIGHT-8:
            surface.alpha_composite(frag,(int(x),int(y)))
        else:
            surface.paste(frag,(int(x),int(y)),frag)
    def text(self,surface,x,y,value,colour):
        for i,ch in enumerate(value.upper()):
            if ch==' ': c=0x10
            elif '0'<=ch<='9':c=ord(ch)-ord('0')
            elif 'A'<=ch<='Z':c=ord(ch)-ord('A')+0x11
            else:c=0x10
            self.character(surface,x+i*8,y,c,colour)

def apply_hud(surface, stage_index:int=0, frame:int=0,
              values:HUDValues|None=None):
    draw_hud(surface,PillowBank(),stage_index,frame,values)
    return surface

def main():
    f=ImageFont.load_default()
    background=(13,17,28)
    panels=[(0,HUDValues(),"START / 1ST STAGE / 00 PTS"),
            (3,HUDValues(score=15850,high_score=15850,fuel=208,lives=3),"4TH STAGE / 15850 PTS")]
    scale=3;size=(224*scale,256*scale)
    pad=20; label_h=24
    canvas=Image.new('RGB',(pad+len(panels)*(size[0]+pad),size[1]+2*pad+label_h),background)
    draw=ImageDraw.Draw(canvas)
    for i,(stage,hud,label) in enumerate(panels):
        s=Image.new('RGBA',(224,256),(0,0,0,255))
        apply_hud(s,stage,0,hud)
        x=pad+i*(size[0]+pad)
        draw.text((x,pad),label,fill=(237,240,248),font=f)
        canvas.paste(s.convert('RGB').resize(size,Image.Resampling.NEAREST),(x,pad+label_h))
    dest=ROOT/'data'/'hud_preview.png'
    canvas.save(dest)
    print('Saved',dest)

if __name__=='__main__':main()
