"""Generate a static example from the actual exported ROM graphics (Pillow only)."""
from pathlib import Path
import json
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
sys.path.insert(0,str(ROOT))
from scramble_objects import ROTATED_GROUP_ORDER  # noqa: E402


def font(size, bold=False):
    base='/usr/share/fonts/truetype/dejavu/DejaVuSansMono'
    try:
        return ImageFont.truetype(base+('-Bold' if bold else '')+'.ttf',size)
    except OSError:
        return ImageFont.load_default()


def make_preview(out: Path):
    tables=json.loads((DATA/'animations.json').read_text())['animations']
    chars=[Image.open(DATA/f'characters_color_{i}.png').convert('RGBA') for i in range(8)]
    sprites=[Image.open(DATA/f'sprites_color_{i}.png').convert('RGBA') for i in range(8)]
    screen=Image.new('RGBA',(256,224),(0,0,0,255))
    def tile(x,y,code,pal):
        part=chars[pal].crop(((code%16)*8,(code//16)*8,(code%16+1)*8,(code//16+1)*8))
        screen.alpha_composite(part,(x,y))
    def sprite(x,y,name):
        frame=tables[name]['frames'][0]
        code=frame['code']; pal=frame['colour']
        part=sprites[pal].crop(((code&63)%8*16,((code&63)//8)*16,((code&63)%8+1)*16,((code&63)//8+1)*16))
        if code&0x80: part=part.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if code&0x40: part=part.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        screen.alpha_composite(part,(x,y))
    def ground(x,y,name,pal=2):
        frame=tables[name]['frames'][0]
        codes=[frame['code']*4+i for i in ROTATED_GROUP_ORDER]
        for i,code in enumerate(codes):tile(x+(i%2)*8,y+(i//2)*8,code,pal)
    def game_text(x,y,string,pal=2):
        for i,ch in enumerate(string):
            code=0x10 if ch==' ' else (ord(ch)-ord('0') if ch.isdigit() else ord(ch)-ord('A')+0x11)
            tile(x+i*8,y,code,pal)

    game_text(12,5,'1UP',2);game_text(91,5,'HIGH SCORE',0)
    game_text(12,16,'001000');game_text(106,16,'010000')
    listed=[('P1 JET','player_one',(26,55)),('P2 JET','player_two',(26,90)),
            ('BOMB','player_bomb',(26,127)),('ROCKET','rocket',(170,56)),
            ('UFO','ufo',(170,91)),('FIREBALL','fireball',(170,126))]
    for _,name,pos in listed:sprite(*pos,name)
    objects=[('ROCKET','ground_rocket',(24,174)),('FUEL','ground_fuel',(87,174)),
             ('MYSTERY','ground_mystery',(151,174)),('BASE','ground_base',(217,174))]
    for _,name,pos in objects:ground(*pos,name)
    for y in (191,199,207,215):
        for x in range(0,256,8):tile(x,y,0x39,2)
    out_img=Image.new('RGB',(1240,805),(16,19,32))
    d=ImageDraw.Draw(out_img)
    h=font(25,True);sm=font(16);tiny=font(14)
    d.text((25,21),'SCRAMBLE / KONAMI 1981 - GRAPHICS PHASE 2',font=h,fill=(243,246,255))
    d.text((25,51),'DISPLAY SPECIMENS - NOT GAMEPLAY OR ACCURATE STAGE POSITIONS',font=tiny,fill=(147,167,192))
    out_img.paste(screen.convert('RGB').resize((768,672),Image.Resampling.NEAREST),(25,74))
    d.rectangle((24,73,793,746),outline=(90,96,130),width=1)
    x=821
    d.text((x,83),'SPRITES: ONE 16x16 IMAGE',font=sm,fill=(255,230,120))
    d.text((x,108),'Code / colour / ROM delay',font=tiny,fill=(165,173,198))
    y=136
    for label,name,_ in listed:
        f=tables[name]['frames'][0]
        d.text((x,y),f'{label:<12s} ${f["code"]:02X}  C{f["colour"]}  D{f["delay"]:02X}',font=sm,fill=(222,227,245));y+=34
    d.text((x,367),'CHARACTER TARGETS: FOUR 8x8',font=sm,fill=(255,230,120))
    d.text((x,393),'Group code x 4 gives first tile',font=tiny,fill=(165,173,198))
    y=423
    for label,name,_ in objects:
        f=tables[name]['frames'][0];code=f['code']*4
        d.text((x,y),f'{label:<10s} ${f["code"]:02X} -> ${code:02X}-${code+3:02X}',font=sm,fill=(222,227,245));y+=36
    d.text((x,600),'Landscape column colour: 2 / 7',font=sm,fill=(154,204,255))
    d.text((x,626),'Colour is per tilemap column;',font=tiny,fill=(163,173,195))
    d.text((x,648),'moving sprites have own colour.',font=tiny,fill=(163,173,195))
    d.text((x,681),'Animation codes and delays from',font=tiny,fill=(153,167,185))
    d.text((x,702),'original Scramble Z80 ROM tables.',font=tiny,fill=(153,167,185))
    d.text((25,766),'[1-8] target colour  [TAB] 2x2 assembly  [SPACE] pause  [N] frame  [S] PNG  [ESC] quit',font=tiny,fill=(171,184,206))
    out.parent.mkdir(parents=True,exist_ok=True)
    out_img.save(out)
    print(f'Wrote {out}')

if __name__=='__main__':
    make_preview(DATA/'actor_preview.png')
