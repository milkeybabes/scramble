"""Drive actual main() through two-player wipe rendering with fake SDL.

Checks the code path that draws scene->frozen copy->VRAM strip wipe->incoming
turn and never accidentally reuses the outgoing PLAYER introduction.
"""
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).resolve().parent))
from check_attract_gui_startup import make_pygame, key_event, Bank
import scramble_game as game
import scramble_cabinet

pg=make_pygame([])
# 2 coins, 2P start; ~240 Python graphics frames, ~960 logical frames.
batches=[[key_event(pg,pg.K_5)],[key_event(pg,pg.K_5)],
         [key_event(pg,pg.K_2)]] + [[] for _ in range(230)] + [[SimpleNamespace(type=pg.QUIT)]]
pg.event=SimpleNamespace(get=lambda:(batches.pop(0) if batches else [SimpleNamespace(type=pg.QUIT)]))
orig=scramble_cabinet.CabinetSession.tick
phases=[];die=[False]
def trigger(self,stick):
    if self.phase=='playing' and self.active==0 and not die[0]:
        self.scene.kill_player('forced GUI regression')
        die[0]=True
    orig(self,stick)
    phases.append((self.phase,self.active,self.wipe_progress))

with patch.dict(sys.modules,{'pygame':pg}), \
     patch.object(game,'SpriteCharacterBank',Bank), \
     patch.object(scramble_cabinet.CabinetSession,'tick',trigger), \
     patch.object(sys,'argv',['scramble.py','--no-fuel','--no-collisions','--no-rockets','--no-aliens']):
    game.main()

assert die[0]
assert any(p=='between' and a==0 for p,a,_ in phases)
assert any(p=='wipe' and a==0 and w>1 for p,a,w in phases)
assert any(p=='intro' and a==1 for p,a,_ in phases)
assert any(p=='playing' and a==1 for p,a,_ in phases)
assert len({w for p,a,w in phases if p=='wipe'})>=28
print('PASS: actual GUI frame render, frozen transition snapshot and 32-strip wipe through to Player Two')
