"""Create a ROM-atlas preview of the actual high-score ranking renderer (no SDL needed)."""
from pathlib import Path
import sys
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scramble_attract import AttractMode

class PillowSurface:
    def __init__(self): self.image=Image.new('RGB',(224,256),(0,0,0))
    def fill(self,rgb): self.image.paste(tuple(rgb),(0,0,224,256))
    def set_at(self,point,rgb):
        x,y=point
        if 0<=x<224 and 0<=y<256:self.image.putpixel(point,tuple(rgb))

class PillowBank:
    def __init__(self):
        self.tiles=[]
        for c in range(8):
            sheet=Image.open(ROOT/'data'/f'characters_color_{c}.png').convert('RGBA')
            self.tiles.append([sheet.crop(((n%16)*8,(n//16)*8,(n%16+1)*8,(n//16+1)*8))
                               for n in range(256)])
    def character(self,surface,x,y,code,color):
        tile=self.tiles[color&7][code&255]
        bg=surface.image.convert('RGBA')
        bg.alpha_composite(tile,(int(x),int(y)))
        surface.image=bg.convert('RGB')
    def sprite(self,*args):pass

a=AttractMode(boot_grid=False)
a.ranking=[22750,21100,18560,13200,10000,10000,10000,10000,10000,10000]
a.high_score=22750
a.player_scores=(22750,13100)
a.highlight_rank=0
a.go_to('ranking')
b=PillowBank(); surf=PillowSurface();a.render(surf,b)
out=ROOT/'data'/'highscore_ranking_preview.png'
surf.image.resize((672,768),Image.Resampling.NEAREST).save(out)
print(out)
