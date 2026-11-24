"""GUI regression: clean screen, optional Konami bezel and MAME-style keys.

Uses the existing fake SDL event/window layer, so this test works on build
machines without pygame. It exercises the actual game main(), not a copy.
"""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import scramble_game as game
from check_attract_gui_startup import Surface, Bank, make_pygame, key_event
from scramble_display import ScreenPresenter, preferred_window_size


def run_case(args, sequence, expected_sizes, minimum_screenshots=0):
    pg=make_pygame([])
    pg.FULLSCREEN=8
    for i, name in enumerate(('F3','F5','F8','F9','F11','F12')):
        setattr(pg,'K_'+name,1000+i)
    sizes=[]
    screenshots=[]
    loaded=[]
    def set_mode(dims,flags):
        sizes.append((dims,flags))
        return Surface((1920,1080) if dims==(0,0) else dims)
    pg.display=SimpleNamespace(set_mode=set_mode,set_caption=lambda name:None,flip=lambda:None)
    def load(path):
        loaded.append(Path(path))
        return Surface((1920,1080))
    pg.image=SimpleNamespace(load=load,save=lambda surface,path:screenshots.append((surface,path)))
    seq=[[key_event(pg,getattr(pg,'K_'+k))] for k in sequence]
    seq += [[SimpleNamespace(type=pg.QUIT)]]
    pg.event=SimpleNamespace(get=lambda:seq.pop(0) if seq else [SimpleNamespace(type=pg.QUIT)])
    with patch.dict(sys.modules,{'pygame':pg}),patch.object(game,'SpriteCharacterBank',Bank),patch.object(sys,'argv',['scramble.py']+args):
        game.main()
    got=[size for size,flags in sizes]
    assert got==expected_sizes, (args,got,expected_sizes)
    assert len(screenshots)>=minimum_screenshots, (args,len(screenshots))
    for surface,path in screenshots:
        assert path.endswith('.png') and '/screenshots/' in path.replace('\\','/')
    if '--artwork' in args or 'F8' in sequence:
        assert loaded and all(f.is_file() and 'Konami' in f.name for f in loaded)
    return screenshots,loaded


def main():
    assert preferred_window_size(224,256)==(672,768)
    assert preferred_window_size(224,256,bezel=True)==(1280,720)
    assert preferred_window_size(224,256,debug=True)==(1150,875)
    s,_=run_case([],['F12','F5','F5','F3','F12'],[(672,768)],2)
    assert s[0][0].get_size()==(672,768)
    run_case([],['F8','F12','F8'],[(672,768),(1280,720),(672,768)],1)
    run_case(['--artwork','bezel'],['F12'],[(1280,720)],1)
    run_case(['--artwork','bezel'],['F11','F12','F11'],
             [(1280,720),(0,0),(1280,720)],1)
    run_case(['--skip-attract'],['F5','F12','F5','F3'],[(672,768)],1)
    run_case(['--debug'],['F12'],[(1150,875)],1)
    # The correct scene baseline must not paint the red diagnostic clearance
    # marker, even on the direct-game bypass.
    assert game.PlayScene(None,None,game.read_stages()).show_clearance is False
    print('Finished-display GUI controls PASS (clean, bezel, F3/F5/F8/F11/F12, debug)')

if __name__=='__main__':
    main()
