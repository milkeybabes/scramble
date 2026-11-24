"""ROM $073E/$075F game-over character-address regression (no pygame required)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scramble_game import PlayScene
from scramble_scroll import read_stages
from scramble_hud import character_xy

class FakeSurface:
    def fill(self, *args): pass
class SpyBank:
    def __init__(self):self.words=[]
    def text(self, _surface, x, y, msg, colour):
        self.words.append((x,y,msg,colour))

assert character_xy(0x4A94) == (72,160)
assert character_xy(0x4A96) == (72,176)
assert len('PLAYER ONE') == len('GAME  OVER') == 10
bank=SpyBank()
scene=PlayScene(None, bank, read_stages())
scene.run_state = 'game_over'
scene.render(FakeSurface())
assert (72,160,'PLAYER ONE',6) in bank.words, bank.words
assert (72,176,'GAME  OVER',4) in bank.words, bank.words
assert all((x != 56 or y != 116) for x,y,_,_ in bank.words), bank.words
print('PASS: original $4A94/$4A96 positions, both 10 characters, centred at X=112')
