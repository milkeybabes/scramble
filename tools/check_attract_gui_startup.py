"""Exercise real graphical main() paths without requiring SDL on CI machines.

Covers GUI frame/tick/paint, the attract-to-gameplay handoff, and debug
bypasses. A minimal fake pygame provides surfaces/window events while real
Scramble logic, layout and scene updates remain in use. The test specifically
catches the missing `attract` closure initialization in Phase A's first ZIP.
"""
import sys
from pathlib import Path
from collections import defaultdict
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import scramble_game as game

class Surface:
    def __init__(self, size=(1,1), *args, **kwargs):
        self.size=size
    def copy(self): return Surface(self.size)
    def convert(self): return self
    def convert_alpha(self): return self
    def fill(self, *args): return None
    def blit(self, *args): return None
    def set_at(self, *args): return None
    def get_size(self): return self.size

class Font:
    def render(self, *args): return Surface()

class Bank:
    def __init__(self):
        self.pg=sys.modules['pygame']
    def sprite(self, *args): pass
    def character(self, *args): pass
    def text(self, *args): pass
    def ground_object(self, *args): pass

class Clock:
    def tick(self, fps): return 100  # bounded to 0.08 by the game

KEYS=('ESCAPE SPACE n F12 RETURN PAGEUP PAGEDOWN r m c p h t '
      'EQUALS PLUS KP_PLUS MINUS KP_MINUS UP DOWN LEFT RIGHT w s a d '
      'LCTRL RCTRL z LALT RALT x').split()

def make_pygame(batches):
    pg=ModuleType('pygame')
    pg.QUIT=100; pg.KEYUP=101; pg.KEYDOWN=102
    pg.RESIZABLE=2; pg.SRCALPHA=4
    pg.WINDOWFOCUSLOST=103
    for d in range(1,7):setattr(pg, f'K_{d}', 48+d)
    for i,tag in enumerate(KEYS):setattr(pg, 'K_'+tag, 300+i)
    pg.Surface=Surface
    pg.Rect=lambda *a: a
    pg.init=lambda:None
    pg.quit=lambda:None
    pg.display=SimpleNamespace(set_mode=lambda dims,flags:Surface(dims),
                               set_caption=lambda title:None,
                               flip=lambda:None)
    pg.time=SimpleNamespace(Clock=Clock)
    pg.font=SimpleNamespace(SysFont=lambda *a,**kw:Font())
    pg.draw=SimpleNamespace(rect=lambda *a:None)
    pg.transform=SimpleNamespace(scale=lambda surface,size:Surface(size))
    pg.image=SimpleNamespace(save=lambda *a:None)
    pg.key=SimpleNamespace(get_pressed=lambda:defaultdict(bool))
    seq=list(batches)
    pg.event=SimpleNamespace(get=lambda:(seq.pop(0) if seq else [SimpleNamespace(type=pg.QUIT)]))
    return pg

def key_event(pg,key):return SimpleNamespace(type=pg.KEYDOWN,key=key)

def check(args, mode):
    pg=make_pygame([])
    if mode=='two_player_start':
        batches=[[key_event(pg,pg.K_5)],[key_event(pg,pg.K_5)],
                 [key_event(pg,pg.K_2)],[SimpleNamespace(type=pg.QUIT)]]
    elif mode=='coin_start':
        batches=[[key_event(pg,pg.K_5)], [key_event(pg,pg.K_1)], [SimpleNamespace(type=pg.QUIT)]]
    else:
        batches=[[],[SimpleNamespace(type=pg.QUIT)]]
    pg.event=SimpleNamespace(get=lambda:(batches.pop(0) if batches else [SimpleNamespace(type=pg.QUIT)]))
    with patch.dict(sys.modules, {'pygame':pg}), \
         patch.object(game,'SpriteCharacterBank',Bank), \
         patch.object(sys,'argv',['scramble.py']+args):
        game.main()
    print('GUI startup PASS:',mode,args)

if __name__=='__main__':
    check([], 'default_grid')
    check(['--no-grid'], 'title_without_grid')
    check([], 'coin_start')
    check([], 'two_player_start')
    check(['--skip-attract'], 'direct_game')
    check(['--stage','5'], 'stage_seek')
