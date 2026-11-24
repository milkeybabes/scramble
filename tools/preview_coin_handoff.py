"""Static cabinet prompt and two-player handoff comparison, rendered from ROM tiles."""
import sys
from pathlib import Path
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scramble_attract import AttractMode
from scramble_cabinet import CabinetSession, render_turn_intro, draw_scoreboard
from scramble_game import PlayScene
from scramble_scroll import read_stages
from scramble_stars import blink_state,star_visible
from preview_attract import Bank, Canvas

class TextBank(Bank):
    def text(self,surface,x,y,msg,colour):
        for c in msg:
            if '0'<=c<='9':code=ord(c)-48
            elif 'A'<=c<='Z':code=ord(c)-ord('A')+0x11
            elif c==' ':code=0x10
            else:code=0x10
            self.character(surface,x,y,code,colour)
            x+=8

bank=TextBank()
shots=[]
for credits in (1,2):
    a=AttractMode(credits=credits,boot_grid=False)
    a.go_to('credit')
    cv=Canvas();a.render(cv,bank)
    shots.append(cv.im)

sessions=[]
for n in (1,2):
    s=PlayScene(None,bank,read_stages(),lives=3,collisions=False,fuel_enabled=False)
    s.player_number=n
    sessions.append(s)
cab=CabinetSession(sessions)
cab.scenes[0].hud.score=60
cab.scenes[1].hud.score=50
for player in (0,1):
    cab.active=player
    cab.phase='intro'
    cv=Canvas()
    render_turn_intro(cv,bank,cab,AttractMode(boot_grid=False).stars,blink_state(0),star_visible)
    shots.append(cv.im)

sheet=Image.new('RGB',(896,1024),(12,12,12))
for i,im in enumerate(shots):
    resized=im.resize((448,512),Image.Resampling.NEAREST)
    sheet.paste(resized,((i%2)*448,(i//2)*512))
path=Path(__file__).resolve().parents[1]/'data'/'cabinet_preview.png'
sheet.save(path)
print(path)
