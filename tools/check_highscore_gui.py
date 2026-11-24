"""The real pygame main() flow with a mocked SDL window: GAME OVER -> ranking -> attract.

Catches graphical-only state errors that a headless scoring test would miss.
"""
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tools'))
from check_attract_gui_startup import make_pygame,key_event,Bank
import scramble_game as game
import scramble_cabinet

pg=make_pygame([])
# each GUI tick advances as many as four logical steps
batches=[[key_event(pg,pg.K_5)],[key_event(pg,pg.K_1)]] + [[] for _ in range(180)] + [[SimpleNamespace(type=pg.QUIT)]]
pg.event=SimpleNamespace(get=lambda: (batches.pop(0) if batches else [SimpleNamespace(type=pg.QUIT)]))
orig_tick=scramble_cabinet.CabinetSession.tick
phases=[];killed=[False]
def tick_with_death(self,stick):
    if self.phase=='playing' and not killed[0]:
        self.scene.hud.score=25600
        self.scene.remaining_lives=0
        self.scene.kill_player('mock GUI final-life test')
        killed[0]=True
    orig_tick(self,stick)
    phases.append((self.phase,list(self.ranking),self.last_qualification))

original_attract=game.AttractMode
instances=[]
class AttractProbe(original_attract):
    def __init__(self,*a,**kw):
        super().__init__(*a,**kw)
        instances.append(self)

with patch.dict(sys.modules,{'pygame':pg}), \
     patch.object(game,'SpriteCharacterBank',Bank), \
     patch.object(game,'AttractMode',AttractProbe), \
     patch.object(scramble_cabinet.CabinetSession,'tick',tick_with_death), \
     patch.object(sys,'argv',['scramble.py','--no-fuel','--no-collisions','--no-rockets','--no-aliens']):
    game.main()
assert killed[0]
assert any(phase=='game_over_hold' for phase,_,_ in phases)
assert any(phase=='ranking' and ranking[0]==25600 and q==(0,0,True)
           for phase,ranking,q in phases)
assert any(phase=='ended' for phase,_,_ in phases)
assert len(instances)>=2 and instances[-1].ranking[0]==25600
assert instances[-1].page in ('title','ranking','score_table')
print('PASS: actual graphical main GAME OVER -> ROM ranking -> attract, high score retained')
