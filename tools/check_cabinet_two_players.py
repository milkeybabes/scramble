"""Coin/start flow, separate 2P progress and source-style turn introduction.

Tests the Python state machine without relying on an SDL display. The GUI
integration is checked separately by check_attract_gui_startup.py.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scramble_game import PlayScene
from scramble_scroll import read_stages
from scramble_player import Joystick
from scramble_attract import AttractMode
from scramble_cabinet import CabinetSession, draw_scoreboard, INTRO_FRAMES, READY_FRAMES, TURN_DELAY, P2_TURN_DELAY, WIPE_FRAMES

attract=AttractMode(boot_grid=False)
assert attract.page=='title'
assert attract.credits==0
attract.insert_coin()
assert (attract.credits,attract.page)==(1,'credit')
for i in range(500):attract.tick()
assert attract.page=='credit'
attract.insert_coin()
assert attract.credits==2
assert attract.data['text']['24']['codes'] != attract.data['text']['25']['codes']

stages=read_stages()
def player(n):
    s=PlayScene(None,None,stages,lives=3,collisions=False,
                fuel_enabled=False, rockets_enabled=False,aliens_enabled=False)
    s.player_number=n
    return s

one,two=player(1),player(2)
session=CabinetSession([one,two])
assert session.two_player and session.active==0 and session.phase=='intro'
for i in range(INTRO_FRAMES+READY_FRAMES):session.tick(Joystick())
assert session.phase=='playing' and session.active==0
one.goto(4)
one.hud.score=1890
one.kill_player('test')
for i in range(111):session.tick(Joystick())
assert session.phase=='between' and one.run_state=='respawn_delay'
assert one.stage_idx==4 and one.hud.score==1890
for i in range(TURN_DELAY):session.tick(Joystick())
assert session.phase=='wipe' and session.active==0
for i in range(WIPE_FRAMES+1):session.tick(Joystick())
assert session.phase=='intro' and session.active==1
for i in range(INTRO_FRAMES+READY_FRAMES):session.tick(Joystick())
assert session.phase=='playing' and two.run_state=='playing'
assert session.scores==(1890,0)
# Second player has independent score/terrain. When they crash, P1 resumes
# with the current stage and score, but is refuelled at its stage entrance.
two.goto(2)
two.hud.score=620
two.kill_player('test')
for i in range(111+P2_TURN_DELAY):session.tick(Joystick())
assert session.phase=='wipe' and session.active==1
for i in range(WIPE_FRAMES+1):session.tick(Joystick())
assert session.active==0 and session.phase=='intro'
assert one.run_state=='respawn_delay' and one.remaining_lives==2
for i in range(INTRO_FRAMES+READY_FRAMES):session.tick(Joystick())
assert session.phase=='playing' and one.run_state=='playing'
assert one.stage_idx==4 and one.hud.score==1890
assert one.remaining_lives==1 and one.hud.fuel==255
assert two.stage_idx==2 and two.hud.score==620 and two.remaining_lives==2
assert session.scores==(1890,620)

# Original $0223 flashes only the active 1UP/2UP label, not score digits.
class Bank:
    class pg:
        class draw:
            @staticmethod
            def rect(*args):pass
    def __init__(self): self.texts=[]
    def text(self, surface,x,y,msg,c): self.texts.append(msg)
    def character(self,*args):pass
bank=Bank()
session.frame=0x10 # active player one's label is hidden
session.active=0
draw_scoreboard(None,bank,session)
assert '1UP' not in bank.texts and '2UP' in bank.texts
assert any(x.strip()=='1890' for x in bank.texts) and any(x.strip()=='620' for x in bank.texts)
bank.texts.clear()
session.active=1
draw_scoreboard(None,bank,session)
assert '1UP' in bank.texts and '2UP' not in bank.texts
assert any(x.strip()=='1890' for x in bank.texts) and any(x.strip()=='620' for x in bank.texts)

# Finishing one player's game does not terminate the other's.
two.run_state='game_over'
assert not session.other_available() if session.active==0 else True

print('PASS: credits, 1P/2P selection metadata, two independent stage/score/lives, death handoff, score blinking')
