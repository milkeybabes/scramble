"""Scramble stage death, two-piece explosion, lives and game-over regression."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scramble_game import PlayScene,TRACE_FIELDS,row
from scramble_scroll import read_stages
from scramble_player import Joystick
from scramble_hud import draw_hud

stages=read_stages()
scene=PlayScene(None,None,stages,lives=3)
assert scene.remaining_lives==2 and scene.hud.lives==2
assert len(row(scene))==len(TRACE_FIELDS)
scene.jet.x=0xD7  # deliberate collision with initial floor
scene.tick(Joystick(fire=True,bomb=True))
assert scene.run_state=='dying' and scene.state_timer==111 and scene.death_reason=='terrain'
assert scene.speed.pixels==1 and scene.remaining_lives==2
assert not scene.kill_player('repeat'), 'Double life loss while exploding'
frozen_scroll=scene.speed.pixels
for i in range(111):
    scene.tick(Joystick(right=True,fire=True,bomb=True))
    assert scene.speed.pixels==frozen_scroll
assert scene.run_state=='respawn_delay' and scene.state_timer==192
for _ in range(191):scene.tick()
assert scene.run_state=='respawn_delay' and scene.remaining_lives==2
scene.tick()
assert scene.run_state=='playing' and scene.remaining_lives==1
assert scene.hud.fuel==255 and scene.hud.lives==1
assert scene.jet.screen_xy==(22,81) and scene.speed.pixels==0
assert scene.retry_stage==0
assert scene.hud.score==0 and scene.hud.high_score==10000

# After dying in the maze, original $1151/$10BA reload THAT stage pointer,
# including the flat entrance strip, not the start of the whole game.
scene=PlayScene(None,None,stages,lives=4,start_stage=4)
scene.hud.score=1950
scene.hud.fuel=47
scene.jet.x=0xd7
scene.tick()
assert scene.run_state=='dying' and scene.stage_idx==4
for _ in range(111+192):scene.tick()
assert scene.run_state=='playing' and scene.stage_idx==4
assert scene.speed.pixels==scene.course.starts[4]-224
assert scene.retry_stage==4
assert scene.hud.score==1950 and scene.hud.fuel==255
assert scene.remaining_lives==2
# Move the jet only after terrain has actually entered the viewport.
scene.tick()
assert scene.run_state=='playing' and scene.speed.pixels==scene.course.starts[4]-223

# 255-life testing mode is a real 8-bit style counter but the HUD only
# has space for six reserve icons (original routine $0908).
scene=PlayScene(None,None,stages,lives=255,collisions=False)
assert scene.remaining_lives==254 and scene.hud.lives==254
class FakeSurface:
    def fill(self,*args): pass
    def blit(self,*args): pass
class FakePG:
    class draw:
        @staticmethod
        def rect(*args):pass
class FakeBank:
    pg=FakePG
    def __init__(self):self.chars=[];self.sprites=[];self.words=[]
    def character(self,s,x,y,code,color):self.chars.append(code)
    def text(self,s,x,y,msg,color):self.words.append(msg)
    def sprite(self,s,x,y,code,color):self.sprites.append((code,color))
bank=FakeBank();draw_hud(FakeSurface(),bank,0,0,scene.hud)
assert bank.chars.count(0x0A)==6 and bank.chars.count(0x0B)==6
# Death display must use original body/exhaust explosion patterns.
scene=PlayScene(None,bank,stages,lives=3)
scene.jet.x=0xd7;scene.tick()
assert scene.explosion_front.current.code==0x3c
assert scene.explosion_rear.current.code==0xbc
# Draw just the exploding arms through a renderer spy (no pygame needed).
from scroll_viewer import Scene
orig_render=Scene.render
try:
    Scene.render=lambda self,s: None
    scene.render(FakeSurface())
finally:
    Scene.render=orig_render
assert bank.sprites[-2:]==[(0xBC,4),(0x3C,4)],bank.sprites


# Game-over only when the final life is spent, and scores are preserved.
scene=PlayScene(None,None,stages,lives=3)
scene.hud.score=1200
for life in range(3):
    scene.jet.x=0xd7
    scene.retry_stage=None  # Force immediate test collision, bypass flat safe entrance
    scene.tick()
    assert scene.run_state=='dying'
    for _ in range(111):scene.tick()
    if life < 2:
        for _ in range(192):scene.tick()
        assert scene.run_state=='playing' and scene.remaining_lives==1-life
    else:
        assert scene.run_state=='game_over'
        assert scene.remaining_lives==0 and scene.hud.lives==0
        assert scene.hud.score==1200
        assert not scene.hud.game_in_play
scene.new_game()
assert scene.run_state=='playing' and scene.remaining_lives==2
assert scene.hud.score==0 and scene.hud.fuel==255

# Bonus jet should happen once only on crossing 10,000.
scene=PlayScene(None,None,stages,lives=3)
scene.hud.score=9990
class Target:kind='ROCKET'
scene.register_ground_hit(Target())
assert scene.remaining_lives==3 and scene.bonus_awarded
scene.register_ground_hit(Target())
assert scene.remaining_lives==3
print('PASS: jet explosion 111 frames, frozen scrolling, 192-frame restart sequence,')
print('      reserve lives, stage-5 retry and flat prefill, game over, 255 lives,')
print('      10,000-point extra jet, preserved score and original 2-part debris.')
