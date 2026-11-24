"""Headless tests for ROM-derived attract page schedule, addresses, colours and credits."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scramble_attract import AttractMode,BOOT_FRAMES,TITLE_FRAMES,RANKING_FRAMES,SCORE_TOTAL
from scramble_hud import character_xy

a=AttractMode()
assert a.page=='grid'
for _ in range(BOOT_FRAMES):a.tick()
assert a.page=='title' and a.page_frame==0
for _ in range(TITLE_FRAMES):a.tick()
assert a.page=='ranking' and a.page_frame==0
for _ in range(RANKING_FRAMES):a.tick()
assert a.page=='score_table'
assert a.score_visible_characters()==0
for _ in range(SCORE_TOTAL):a.tick()
assert a.page=='title' and a.cycles==1
assert len(a.data['text'])==37
assert [p['char_address'] for p in [a.data['text'][str(i)] for i in (11,12,6,18)]]==[0x4a26,0x4aa9,0x4b51,0x4b54]
assert a.data['text']['26']['char_address']==0x4b04
assert a.data['text']['13']['char_address']==0x4ac7
assert [x[1] for x in a.data['score_sprites']]==[0x1c,0x1e,0x1a,0x10,0x26,0x33]
assert character_xy(0x4a4a)==(88,80)
a.go_to('score_table')
for _ in range(SCORE_TOTAL-1):a.tick()
assert a.score_visible_characters()==66
b=AttractMode(boot_grid=False)
assert b.page=='title'
for _ in range(110):b.insert_coin()
assert b.credits==99
assert a.data['attributes']['title']!=a.data['attributes']['score_table']
print('Attract pages: PASS (boot, title, ranks, score table, 6x11 ROM reveal, credits)')
