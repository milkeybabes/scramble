"""$27E1-$27FC: miss BASE => repeat terrain; real hit => 150-frame cool-off."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scramble_course import ContinuousCourse
from scramble_scroll import read_stages, VIEW_WIDTH
from scramble_game import PlayScene
from scramble_bullets import Bullet, PlayerBullets
from scramble_bombs import PlayerBombs

stages=read_stages(); c=ContinuousCourse(stages)
start=c.base_start; period=c.base_width
assert period == 448
for pos in (c.last_scroll-10,c.last_scroll,c.total_width-1,c.total_width,
            c.total_width+5,c.total_width+period-1,c.total_width+period*2+17):
    parts=list(c.visible_slices(pos))
    assert parts[0].screen_x==0 and sum(x.width for x in parts)==VIEW_WIDTH,(pos,parts)
    assert all(a.screen_x+a.width==b.screen_x for a,b in zip(parts,parts[1:]))
for x in range(start,start+period):
    assert c.record_at(x)==c.record_at(x+period)==c.record_at(x+2*period)
for pos in (start, start+60,start+period-16,start+period+30):
    assert [(s.stage_index,s.source_x,s.width) for s in c.visible_slices(pos)] == [
           (s.stage_index,s.source_x,s.width) for s in c.visible_slices(pos+period)]

base = next(t for t in stages[-1].targets if t.kind == 'BASE')
world=c.target_world_x(5,base)
assert world == start+320
first=[v for v in c.nearby_targets(world-50) if v[1].kind=='BASE']
second=[v for v in c.nearby_targets(world+period-50) if v[1].kind=='BASE']
assert len(first)==len(second)==1
assert first[0][2]==world and second[0][2]==world+period
assert first[0][3]!=(second[0][3])

scene=PlayScene(None,None,stages,start_stage=5,lives=255,
                collisions=False,fuel_enabled=False,auto_complete=False)
scene.speed.pixels=c.last_scroll
for i in range(period*3):
    prev=scene.speed.pixels
    scene.tick()
    assert scene.speed.pixels==prev+1
    assert scene.stage_idx==5 and scene.run_state=='playing'
assert scene.speed.pixels>c.total_width+period
# Ensure previous base could be missed and new copy is still available.
scene.speed.pixels=world+period-100
assert scene.base_visible
# Collision uses new absolute target, rather than first-pass target.
new_base=world+period
bullet=scene.bullets.slots[0]
bullet.active=True
bullet.y=(239-(new_base-scene.speed.pixels+8))&255
bullet.x=(base.y+8)+1
hits=scene.bullets.ground_hits(c,scene.speed.pixels,scene.hit_targets)
assert len(hits)==1 and hits[0][2]==new_base,hits
scene.register_ground_hit(hits[0][1],hits[0][0],hits[0][2])
assert scene.hud.score==800 + 10*(scene.frames//64) and scene.run_state=='cool_off'
assert scene.base_destroyed
old_scroll=scene.speed.pixels
for _ in range(150):scene.tick()
assert scene.speed.pixels==old_scroll+150
assert scene.run_state=='blank'
for _ in range(5):scene.tick()
assert scene.run_state=='message'
for _ in range(256):scene.tick()
assert scene.run_state=='playing' and scene.stage_idx==0
assert scene.hud.missions_completed==1 and scene.hud.score==800 + 10*(period*3//64)
# A missile and a bomb each see the repeated (not first-pass) target.
scene_bomb=PlayScene(None,None,stages,start_stage=5,lives=255,
                     collisions=False,fuel_enabled=False)
scene_bomb.speed.pixels=world+2*period-100
bomb=scene_bomb.bombs.slots[0]
bomb.active=True; bomb.stage=1
bomb.y=(238-108)&255    # top-left center_x=108 in this viewport
bomb.x=base.y+7          # center_y=base.y+8
bomb_hits=scene_bomb.bombs.ground_hits(c,scene_bomb.speed.pixels,scene_bomb.hit_targets)
assert len(bomb_hits)==1 and bomb_hits[0][2]==world+2*period,bomb_hits
scene_bomb.register_ground_hit(bomb_hits[0][1],bomb_hits[0][0],bomb_hits[0][2])
assert scene_bomb.hud.score==800 and scene_bomb.run_state=='cool_off'
# Missing the base and running out of fuel must NOT award a completed mission.
miss=PlayScene(None,None,stages,start_stage=5,lives=3,
               collisions=False,rockets_enabled=False,aliens_enabled=False)
miss.speed.pixels=world+16
miss.hud.fuel=1
for _ in range(650):
    miss.tick()
    if miss.lives_lost and miss.run_state=='playing':break
assert miss.lives_lost==1 and miss.run_state=='playing'
assert miss.stage_idx==5 and miss.hud.missions_completed==0 and miss.loop_number==1
print('PASS: repeating BASE terrain, per-copy targets, missed base, 150-frame post-hit scroll, mission restart')
