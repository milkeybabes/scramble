"""ROM-style score insertion, game-over ranking and turn transition."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scramble_highscores import initial_ranking, record_score, validate_ranking
from scramble_game import PlayScene
from scramble_scroll import read_stages
from scramble_player import Joystick
from scramble_cabinet import CabinetSession, INTRO_FRAMES, READY_FRAMES, GAME_OVER_HOLD, RANKING_HOLD, WIPE_FRAMES

zero=Joystick()

# $135D/$137F: unequal comparison inserts in descending BCD order.
r=initial_ranking()
rank,inserted=record_score(r,12340)
assert (rank,inserted)==(0,True) and r[:3]==[12340,10000,10000]
rank,inserted=record_score(r,11880)
assert (rank,inserted)==(1,True) and r[:4]==[12340,11880,10000,10000]
rank,inserted=record_score(r,12110)
assert (rank,inserted)==(1,True) and r[:5]==[12340,12110,11880,10000,10000]
old=r[:]
rank,inserted=record_score(r,12110)
assert (rank,inserted)==(1,False) and r==old  # equal: highlight, do NOT insert
rank,inserted=record_score(r,9990)
assert (rank,inserted)==(10,False) and r==old  # missed the top ten
for score in (999999,999990,999980,999970,999960,999950,999940,999930,999920,999910):
    assert record_score(r,score)[1]
assert len(r)==10 and r==sorted(r,reverse=True) and r[0]==999999
try:validate_ranking([1]*9)
except ValueError:pass
else:raise AssertionError('ranking length not validated')

stages=read_stages()
def new_player(n):
    s=PlayScene(None,None,stages,lives=3,collisions=False,
                fuel_enabled=False,rockets_enabled=False,aliens_enabled=False)
    s.player_number=n
    return s

def tick(c,frames):
    for _ in range(frames):c.tick(zero)

# One player: final-life crash, 150-frame GAME OVER, then score ranking
p1=new_player(1)
c=CabinetSession([p1])
tick(c,INTRO_FRAMES+READY_FRAMES)
p1.hud.score=22750
p1.remaining_lives=0
p1.kill_player('test')
tick(c,111)
assert c.phase=='game_over_hold' and p1.run_state=='game_over'
tick(c,GAME_OVER_HOLD-1)
assert c.phase=='game_over_hold'
tick(c,1)
assert c.phase=='ranking' and c.timer==RANKING_HOLD
assert c.ranking[0]==22750 and c.last_qualification==(0,0,True)
assert c.ranking_view.ranking[0]==22750 and c.ranking_view.highlight_rank==0
assert c.ranking_view.player_scores==(22750,)
tick(c,RANKING_HOLD)
assert c.phase=='ranking_exit' and c.timer==100
tick(c,100)
assert c.finished and c.ranking[0]==22750

# Two-player: first final-life GAME OVER and score ranking occurs *before*
# second player's entrance, with separate score tables and 100-frame delay.
p1,p2=new_player(1),new_player(2)
c=CabinetSession([p1,p2])
tick(c,INTRO_FRAMES+READY_FRAMES)
p1.hud.score=20430
p1.remaining_lives=0
p1.kill_player('test')
tick(c,111+GAME_OVER_HOLD)
assert c.phase=='ranking' and c.ranking[0]==20430
assert c.ranking_view.player_scores==(20430,0)
tick(c,RANKING_HOLD)
assert c.phase=='between' and c.pending_player==1 and c.timer==100
tick(c,100+WIPE_FRAMES+1)
assert c.phase=='intro' and c.active==1
tick(c,INTRO_FRAMES+READY_FRAMES)
assert c.phase=='playing' and c.active==1
p2.hud.score=21550
p2.remaining_lives=0
p2.kill_player('test')
tick(c,111+GAME_OVER_HOLD)
assert c.phase=='ranking' and c.ranking[:2]==[21550,20430]
assert c.last_qualification==(1,0,True)
assert c.ranking_view.player_scores==(20430,21550)
tick(c,RANKING_HOLD)
assert c.phase=='ranking_exit' and c.timer==100
tick(c,100)
assert c.finished and c.ranking[:2]==[21550,20430]

# No insertion below minimum, but the ranking is still displayed.
p1=new_player(1)
c=CabinetSession([p1]);tick(c,INTRO_FRAMES+READY_FRAMES)
p1.hud.score=1000;p1.remaining_lives=0;p1.kill_player('test')
tick(c,111+GAME_OVER_HOLD)
assert c.phase=='ranking' and c.last_qualification==(0,10,False)
assert c.ranking_view.highlight_rank is None

# Render actual ranking with original char tiles; the selected row must be
# white (colour 0), while the others retain their ROM palette attributes.
class MockSurface:
    def fill(self,*args):pass
    def set_at(self,*args):pass
class Bank:
    def __init__(self): self.characters=[];self.pg=None
    def character(self,surf,x,y,code,col):self.characters.append((x,y,code,col))
    def sprite(self,*args):pass
bank=Bank(); p1.hud.score=1000
c.ranking_view.highlight_rank=3
c.ranking_view.render(MockSurface(),bank)
from scramble_hud import character_xy
x,y=character_xy(0x4987+3*2)
assert any(xx==x and yy==y and col==0 for xx,yy,code,col in bank.characters)
print('PASS: original ten-score insertion, ties, no initials, qualification highlight, 1P/2P GAME OVER flow')
