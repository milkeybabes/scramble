"""Validate Scramble's actors/tiles without requiring pygame or a window.

Optional --rom performs a pixel-for-pixel composition test against raw ROM
character patterns, including the full-image clockwise rotation.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scramble_objects import AnimationCollection, ROTATED_GROUP_ORDER  # noqa: E402
from scramble_assets import read_original_roms, decode_graphics, palette_from_prom, render_atlas  # noqa: E402
from tools.extract_actor_tables import export_animations  # noqa: E402


def validate(rom_zip: Path | None) -> None:
    catalog=AnimationCollection()
    assert len(catalog.raw)==20
    assert ROTATED_GROUP_ORDER==(2,0,3,1)
    a=catalog.play('player_one')
    assert a.current.code==0x28 and a.current.colour==6
    for i in range(5):
        a.step()
        assert a.current.code==0x28, (i,a.current)
    a.step()
    assert a.current.code==0x2A
    for _ in range(18): a.step()
    assert a.current.code==0x28
    assert [f.code for f in catalog.play('ground_base').frames]==[0x2F,0x26,0x1F]
    assert catalog.play('ground_rocket').current.code==0x1C
    assert catalog.play('ground_fuel').current.code==0x10
    assert catalog.play('ground_mystery').current.code==0x33
    assert catalog.play('player_two_explosion').current.code==0xBC
    manifest=json.loads((ROOT/'data'/'palettes.json').read_text())
    for typ in ['characters','sprites']:
        for group in range(8):
            im=Image.open(ROOT/'data'/f'{typ}_color_{group}.png')
            assert im.mode=='RGBA' and im.size==(128,128)
    if rom_zip:
        rom=read_original_roms(rom_zip)
        raw,_=decode_graphics(rom)
        # MAME drawgfx.cpp gives plane 0 the HIGH bit, plane 1 the LOW.
        assert set(raw[0x3C].getdata())=={2}, "MAME plane-order regression"
        pens=palette_from_prom(rom['c01s.6e'])
        sheet=Image.open(ROOT/'data'/'characters_color_2.png').convert('RGBA')
        def coloured(tile):
            pix=Image.new('RGBA',(8,8))
            colours=[(0,0,0,0),*[(*v,255) for v in pens[2][1:]]]
            pix.putdata([colours[v] for v in tile.getdata()])
            return pix
        for group in (0x10,0x1C,0x2F,0x33,0x38):
            expected=Image.new('RGBA',(16,16))
            # Raw 2x2 in the ORIGINAL unrotated tile map.
            for j in range(4):
                c=raw[group*4+j]
                expected.alpha_composite(coloured(c),((j%2)*8,(j//2)*8))
            expected=expected.transpose(Image.Transpose.ROTATE_270)
            got=Image.new('RGBA',(16,16))
            for j,k in enumerate(ROTATED_GROUP_ORDER):
                code=group*4+k
                part=sheet.crop(((code%16)*8,(code//16)*8,((code%16)+1)*8,((code//16)+1)*8))
                got.alpha_composite(part,((j%2)*8,(j//2)*8))
            assert expected.tobytes()==got.tobytes(), f'2x2 rotated composition error at ${group:02X}'
        print('PASS: ROM-based 2x2 rotated character composition (5 objects)')
    assert Image.open(ROOT/'data'/'actor_preview.png').size==(1240,805)
    print('PASS: original animation codes, delays, 8-colour sprites/tiles, preview')

if __name__=='__main__':
    arg=argparse.ArgumentParser(description=__doc__)
    arg.add_argument('--rom',type=Path,help='Parent or merged Scramble ROM ZIP for extra pixel tests')
    validate(arg.parse_args().rom)
