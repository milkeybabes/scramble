"""Phase 3 data / frame-stepping checks (no GUI or pygame required)."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scramble_scroll import (read_stages,ScrollClock,colour_after_next_change,
                             visible_columns,reference_jet_y,EMPTY_CHAR,
                             VIEW_WIDTH,VIEW_HEIGHT)
from scroll_viewer import scramble_stars
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
ss=read_stages()
assert len(ss)==6
assert [x.width for x in ss]==[2688,1792,1792,2688,1792,448]
assert [len(x.records) for x in ss]==[168,112,112,168,112,28]
assert [x.flags for x in ss]==[0,2,1,8,4,16]
for s in ss:
    assert len(s.cols)==2*len(s.records)
    for i,column in enumerate(s.cols):
        assert len(column)==32
        assert all(0<=n<=255 for n in column)
        assert all(x==EMPTY_CHAR for x in column[:5]+column[29:])
        r=s.records[i//2]
        f=r['floor'][i%2]
        assert column[(f['x']&0xf8)//8]==f['edge_char']
        if r['ceiling']:
            ceiling=r['ceiling'][i%2]
            assert column[(ceiling['x']&0xf8)//8]==ceiling['edge_char'] or (ceiling['x']&0xf8)==(f['x']&0xf8)
    for t in s.targets:
        assert 0<=t.group<64 and t.x%16==0 and t.y%8==0
        assert 0<=t.record_index<len(s.records)
        assert 0<=t.x<s.width
    for p in [0,1,9,17,88,s.scroll_limit]:
        visible=list(visible_columns(s,p))
        assert visible
        # Two adjacent columns must always be 8px apart, independent of scroll.
        assert all(visible[i+1][0]-visible[i][0]==8 for i in range(len(visible)-1))
        jy=reference_jet_y(s,p)
        assert jy is None or 42<=jy<=224
    print(f'{s.name:22s} {s.width:4d}px  {len(s.records):3d} records  {len(s.targets):3d} targets')

for latch in range(8):
    c=ScrollClock(latch)
    events=[c.tick() for _ in range(3*(latch+1))]
    assert sum(events)==3
    assert c.pixels==3
    c.reset()
    assert c.pixels==c.logical_frames==0
assert colour_after_next_change(0)==2
assert colour_after_next_change(7)==0
assert colour_after_next_change(4)==5

stars=scramble_stars()
assert len(stars)==106 and len({(x,y) for x,y,_,_ in stars})==106
assert all(0<=x<VIEW_WIDTH and 0<=y<VIEW_HEIGHT for x,y,_,_ in stars)
for i in range(8):
    image=Image.open(ROOT/'data'/f'characters_color_{i}.png')
    assert image.size==(128,128)
assert (ROOT/'data'/'scrolling_preview.png').is_file()
print('OK: 6 landscape streams, tile placement, 2x2 targets, scroll ticks, palette cycle, and star positions')
