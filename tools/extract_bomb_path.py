"""Optional development utility: rebuild exact 203-entry bomb path from parent ROM.

Run from project root:
  py tools/extract_bomb_path.py C:\\path\\to\\scramble.zip

The game itself requires no ROMs. The generated JSON matches the checked-in
`data/bomb_path.json`; do not package the original ROM archive.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scramble_assets import read_original_roms, MAIN_ROM_FILES


def extract(zip_path: Path, destination: Path) -> None:
    roms = read_original_roms(zip_path)
    rom = b''.join(roms[name] for name in MAIN_ROM_FILES)
    start, end = 0x1aff, 0x1c95
    raw = rom[start:end]
    if len(raw) != 406 or rom[end:end+3] != b'\x80\xff\x1a':
        raise ValueError('Original Konami Scramble bomb path has changed')
    records = [[x if x<128 else x-256,y if y<128 else y-256]
               for x,y in zip(raw[::2],raw[1::2])]
    expected = 0x522aa357
    if zlib.crc32(raw) != expected:
        raise ValueError('Unexpected bomb path CRC32')
    data = {'source': 'Original Konami Scramble parent main ROM, Scott Tunstall scramble.asm PLAYER_BOMB_PATH at $1AFF; path terminates $1C95',
            'source_address': '1AFF', 'terminator_address': '1C95',
            'path_crc32': f'{expected:08X}', 'deltas': records}
    destination.write_text(json.dumps(data,indent=1)+'\n',encoding='utf-8')
    print(f'Wrote {destination} ({len(records)} delta pairs, CRC {expected:08X})')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('rom_zip',type=Path,help='Konami Scramble parent or merged MAME ZIP')
    ap.add_argument('--output',type=Path,default=ROOT/'data'/'bomb_path.json')
    a=ap.parse_args()
    extract(a.rom_zip,a.output)
