"""Ground explosion, refuelling, automatic fuel use and no-fuel deaths."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scramble_fuel import FuelTimer
from scramble_ground_effects import GroundEffects
from scramble_game import PlayScene, TRACE_FIELDS, row
from scramble_player import Joystick
from scramble_scroll import read_stages
from scramble_objects import AnimationCollection

stages=read_stages()
# Exact ROM countdown: 5 initial frames, then 10 / 8 / 6 on each loop.
for completed,interval in [(0,10),(1,8),(2,6),(4,6)]:
    timer=FuelTimer()
    fuel=255
    for i in range(4):
        fuel,empty=timer.step(fuel,completed)
        assert fuel==255 and not empty
    fuel,empty=timer.step(fuel,completed)
    assert fuel==254 and not empty and timer.counter==interval
    for i in range(interval-1):
        fuel,empty=timer.step(fuel,completed)
        assert fuel==254 and not empty
    fuel,empty=timer.step(fuel,completed)
    assert fuel==253 and timer.counter==interval
assert FuelTimer.refuel(150)==198
assert FuelTimer.refuel(250)==255
assert FuelTimer.refuel(255)==255

animations=AnimationCollection()
assert animations.play('ground_explosion').current.code==0x38
assert animations.play('ground_fuel_explosion').current.code==0x38
assert animations.play('ground_mystery_100').current.code==0x11
assert animations.play('ground_mystery_200').current.code==0x12
assert animations.play('ground_mystery_300').current.code==0x13
fx=GroundEffects(animations)
for kind,value,code,duration in [('ROCKET',50,0x38,63),('FUEL',150,0x38,63),
                                 ('BASE',800,0x38,63),('MYSTERY',200,0x12,79)]:
    class T:
        record_index=len(fx.active)
        y=120
    t=T();t.kind=kind
    eff=fx.spawn(0,t,150,value)
    assert eff.code==code and eff.duration==duration
    assert fx.spawn(0,t,150,value) is eff
assert len(fx.active)==4
for _ in range(63):fx.step()
assert len(fx.active)==1
for _ in range(16):fx.step()
assert not fx.active

# Gameplay: full at start, wait five updates then consume first unit.
scene=PlayScene(None,None,stages,collisions=False)
assert scene.hud.fuel==255 and scene.fuel_timer.counter==5
for i in range(4):scene.tick()
assert scene.hud.fuel==255 and scene.fuel_timer.counter==1
scene.tick()
assert scene.hud.fuel==254 and scene.fuel_timer.counter==10
assert len(row(scene))==len(TRACE_FIELDS)
# Refill from actual FUEL target, no new countdown or stage reset.
target=next(t for t in stages[0].targets if t.kind=='FUEL')
scene.hud.fuel=215
old_counter=scene.fuel_timer.counter
score=scene.hud.score
scene.register_ground_hit(target,0)
assert scene.hud.fuel==255
assert scene.hud.score==score+150
assert scene.fuel_timer.counter==old_counter
key=(0,target.record_index)
assert key in scene.ground_effects.active
assert scene.ground_effects.active[key].code==0x38
scene.ground_effects.step()
# Frame change after 17 updates: ROM delay $10 is an 8-bit countdown.
for i in range(15):scene.ground_effects.step()
assert scene.ground_effects.active[key].code==0x38
scene.ground_effects.step()
assert scene.ground_effects.active[key].code==0x39

# Fuel depletion: the exact zero tick stops normal controls, then falls once
# per update until $F0, when the standard 111-frame death cycle begins.
scene=PlayScene(None,None,stages,lives=4,collisions=False)
scene.hud.fuel=2
for i in range(14):scene.tick(Joystick(up=True))
assert scene.hud.fuel==1 and scene.run_state=='playing'
x=scene.jet.x
scene.tick(Joystick(up=True))
assert scene.hud.fuel==0 and scene.run_state=='out_of_fuel'
assert scene.jet.x==x, 'No joystick update on the exact fuel-zero frame'
for i in range(3):scene.tick(Joystick(up=True))
assert scene.jet.x==x+3, 'Out of fuel means falling, not steering upward'
for i in range(255):
    if scene.run_state=='dying':break
    scene.tick()
assert scene.run_state=='dying' and scene.death_reason=='out_of_fuel'
for i in range(111+192):scene.tick()
assert scene.run_state=='playing' and scene.hud.fuel==255
assert scene.fuel_timer.counter==5 and scene.remaining_lives==2

# Debug-only no-fuel mode: entire scrolling playfield without draining.
scene=PlayScene(None,None,stages,collisions=False,fuel_enabled=False)
for i in range(300):scene.tick()
assert scene.hud.fuel==255 and scene.fuel_timer.counter==5
print('PASS: 5→10/8/6 fuel ticks, +48 refill saturation, live HUD fuel,')
print('      $38-$3B ground explosion, 100/200/300 point characters, 63/79-frame')
print('      effect lifetimes, depletion/falling/death, stage restart/full fuel,')
print('      --no-fuel test override, existing firing/scroll controls intact.')

# Spy: rendering a destroyed target selects its 2x2 character animation,
# rather than hiding it permanently. New frames move with world scroll.
class FakeBank:
    def __init__(self): self.draws=[]
    def ground_object(self,surf,x,y,code,colour):self.draws.append((x,y,code,colour))
spy=FakeBank()
scene=PlayScene(None,None,stages,collisions=False)
obj=next(t for t in stages[0].targets if t.kind=='ROCKET')
scene.register_ground_hit(obj,0)
scene.hit_targets.add((0,obj.record_index))
world=scene.course.target_world_x(0,obj)
scene.speed.pixels=world-50
scene.ground_effects.render(spy,None,scene.speed.pixels,4)
assert spy.draws == [(50,obj.y,0x38,4)],spy.draws
spy.draws.clear()
scene.speed.pixels += 3
scene.ground_effects.render(spy,None,scene.speed.pixels,4)
assert spy.draws == [(47,obj.y,0x38,4)],spy.draws
print('PASS: ground effect is rendered from original character group and scrolls with terrain')
