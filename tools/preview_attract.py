"""Render attract screenshots without pygame (Pillow required; developer preview only)."""
import sys
from pathlib import Path
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scramble_attract import AttractMode, SCORE_TOTAL
ROOT=Path(__file__).resolve().parents[1]
ATLAS=ROOT/'data'
class Canvas:
    def __init__(self):self.im=Image.new('RGB',(224,256),'black')
    def fill(self,rgb):self.im.paste(rgb,(0,0,224,256))
    def set_at(self,xy,rgb):
        if 0<=xy[0]<224 and 0<=xy[1]<256:self.im.putpixel(xy,rgb)
class Drawer:
    @staticmethod
    def rect(surface, colour, rect, width=0):
        x,y,w,h=rect;d=ImageDraw.Draw(surface.im)
        d.rectangle((x,y,x+w-1,y+h-1),outline=colour if width else None,fill=None if width else colour,width=width if width else 1)
class PG:
    draw=Drawer()
class Bank:
    def __init__(self):
        self.pg=PG()
        self.chars=[Image.open(ATLAS/f'characters_color_{i}.png').convert('RGBA') for i in range(8)]
        self.sprites=[Image.open(ATLAS/f'sprites_color_{i}.png').convert('RGBA') for i in range(8)]
    def character(self,surface,x,y,code,colour):
        atlas=self.chars[colour];box=(code%16*8,code//16*8,code%16*8+8,code//16*8+8)
        im=atlas.crop(box);surface.im.paste(im,(x,y),im)
    def sprite(self,surface,x,y,code,colour):
        base=code&0x3f;box=(base%8*16,base//8*16,base%8*16+16,base//8*16+16)
        im=self.sprites[colour].crop(box)
        if code&0x80:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if code&0x40:im=im.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        surface.im.paste(im,(x,y),im)

def run():
    bank=Bank();stage=AttractMode(boot_grid=True)
    images=[]
    for page in ('grid','title','ranking','score_table'):
        stage.go_to(page)
        if page=='score_table':stage.page_frame=SCORE_TOTAL-1
        cv=Canvas();stage.render(cv,bank)
        images.append(cv.im)
    sheet=Image.new('RGB',(448*2,512*2),(10,10,18))
    for i,im in enumerate(images):sheet.paste(im.resize((448,512),Image.Resampling.NEAREST),((i%2)*448,(i//2)*512))
    path=ROOT/'data'/'attract_preview.png';sheet.save(path)
    print(path)
if __name__=='__main__':run()
