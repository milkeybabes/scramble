"""One-time developer extractor; requires the original parent ROM ZIP (not redistributed).

Usage: py tools/export_attract_data.py /path/to/scramble_parent_only.zip
The game uses the generated JSON, not the ROM ZIP.
"""
from __future__ import annotations
import json, sys, zipfile
from pathlib import Path
PARTS = ['s1.2d','s2.2e','s3.2f','s4.2h','s5.2j','s6.2l','s7.2m','s8.2p']
ROOT=Path(__file__).resolve().parents[1]
def export(path):
    with zipfile.ZipFile(path) as z:
        rom=b''.join(z.read(n) for n in PARTS)
    assert len(rom)==0x4000
    assert rom[0x073e:0x0741] == bytes([0x96,0x4a,0x47]),'Unexpected parent set; verify ROM version'
    records={}
    for i in range(0x25):
        lo,hi=rom[0x04a2+2*i:0x04a4+2*i]
        ptr=lo | hi<<8
        addr=rom[ptr] | (rom[ptr+1]<<8)
        cur=ptr+2
        codes=[]
        while rom[cur]!=0x3f:
            codes.append((rom[cur]-0x30)&0xff)
            cur+=1
            assert cur < ptr+80,'Unterminated ROM text'
        records[str(i)]={'char_address':addr,'codes':codes,'rom_address':ptr}
    # Four independent original per-row colour tables (source $0B29, etc).
    attrs={n:list(rom[addr:addr+32]) for n,addr in
           (('title',0x0b29),('ranking',0x0b69),('score_table',0x0b49),('default',0x0ae9))}
    # Original score table: [Y, sprite, palette, X], score-table glyph rows.
    sprites=[list(rom[0x0d54+i*4:0x0d58+i*4]) for i in range(6)]
    points=[list(rom[0x0d6c+i*11:0x0d77+i*11]) for i in range(6)]
    data={'source':'Konami Scramble parent set (1981); Scott Tunstall annotated disassembly',
          'text':records,'attributes':attrs,'score_sprites':sprites,'score_text':points,
          'note':'Graphics and text code/position data exported without any ROM or emulation'}
    dst=ROOT/'data'/'attract_layout.json'
    dst.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    print('Written',dst,'texts',len(records),'sprites',len(sprites))
if __name__=='__main__':
    if len(sys.argv)!=2: raise SystemExit('Usage: py tools/export_attract_data.py path/to/rom.zip')
    export(sys.argv[1])
