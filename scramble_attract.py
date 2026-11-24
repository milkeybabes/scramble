"""Scramble original arcade attract pages — ROM-derived screen codes, no CPU emulation.

Phase A: power-on grid, title, 10-entry score ranking and six-entry score table.
Cabinet addendum: source-based coin/credit prompt, 1P or 2P selection.

The text strings, VRAM coordinates, palettes, and score-table sprite definitions
are extracted from the original program ROM to data/attract_layout.json.
Attract page timing is a source-informed initial approximation; exact startup
and the subsequent demonstration script will be checked against MAME later.
"""
from __future__ import annotations
import json
from pathlib import Path
from scramble_hud import character_xy, score_digits
from scramble_highscores import initial_ranking
from scramble_stars import blink_state, star_visible
from scroll_viewer import scramble_stars

LAYOUT_PATH=Path(__file__).resolve().parent/'data'/'attract_layout.json'

# The original $0C86 sets the title-page countdown to $00 (256 ticks); $0CC7
# does likewise for the rank page. The point table uses $32 initial delay,
# $05 per glyph and $14 per-row breaks; then $96 before demo init.
# MAME two-player capture: test-looking power-on tile repeats until ~2.65s,
# then $0AA8/$1A18-style blank tiles progressively erase the screen over
# 32 logical updates. No Z80 emulation or imagined literal zero-RAM writes.
BOOT_WIPE_START=160
BOOT_WIPE_FRAMES=32
BOOT_FRAMES=BOOT_WIPE_START+BOOT_WIPE_FRAMES
TITLE_FRAMES=256
RANKING_FRAMES=256
SCORE_FIRST_DELAY=50
SCORE_CHAR_DELAY=5
SCORE_ROW_DELAY=20
SCORE_END_HOLD=150
SCORE_ROWS=6
SCORE_COLUMNS=11
SCORE_TOTAL=SCORE_FIRST_DELAY+SCORE_ROWS*SCORE_COLUMNS*SCORE_CHAR_DELAY+5*SCORE_ROW_DELAY+SCORE_END_HOLD


class AttractMode:
    """Four-screen native 224x256 presentation, renderer independent of game state."""
    def __init__(self, credits=0, boot_grid=True):
        self.data=json.loads(LAYOUT_PATH.read_text(encoding='utf-8'))
        self.stars=scramble_stars()
        self.page='grid' if boot_grid else 'title'
        self.page_frame=0
        self.frames=0
        self.credits=min(99,max(0,int(credits)))
        self.high_score=10000
        self.ranking=initial_ranking()
        self.cycles=0
        # During the $130E post-GAME OVER score display, retain the player
        # score counters and highlight the qualified ranking row in WHITE.
        self.player_scores=(0,)
        self.highlight_rank=None

    def insert_coin(self):
        self.credits=min(99,self.credits+1)
        self.go_to('credit')

    def go_to(self,page):
        if page not in ('grid','title','ranking','score_table','credit'):
            raise ValueError(page)
        self.page=page
        self.page_frame=0

    def tick(self):
        self.frames+=1
        self.page_frame+=1
        if self.page=='credit':
            return  # $0F2D: wait for 1P/2P start, retain credits
        if self.page=='grid' and self.page_frame>=BOOT_FRAMES:
            self.go_to('title')
        elif self.page=='title' and self.page_frame>=TITLE_FRAMES:
            self.go_to('ranking')
        elif self.page=='ranking' and self.page_frame>=RANKING_FRAMES:
            self.go_to('score_table')
        elif self.page=='score_table' and self.page_frame>=SCORE_TOTAL:
            # Phase B inserts authentic demo gameplay before cycling to title.
            self.cycles+=1
            self.go_to('title')

    def _render_stars(self,surface):
        state=blink_state(self.frames)
        for x,y,rgb,flags in self.stars:
            if star_visible(flags,state):
                if 0<=x<224 and 0<=y<256:
                    surface.set_at((x,y),rgb)

    def _color(self,addr:int) -> int:
        return self.data['attributes'][('default' if self.page=='grid' else self.page)][(addr-0x4800)&31]

    def _tile(self,bank,surface,addr,code,color=None):
        x,y=character_xy(addr)
        if 0<=x<224 and 0<=y<256:
            bank.character(surface,x,y,code,self._color(addr) if color is None else color)

    def _rom_text(self,bank,surface,text_id,color=None):
        record=self.data['text'][str(text_id)]
        addr=record['char_address']
        for code in record['codes']:
            self._tile(bank,surface,addr,code,color)
            addr-=0x20

    def _digits(self,bank,surface,addr,s):
        for c in s:
            self._tile(bank,surface,addr,0x10 if c==' ' else ord(c)-ord('0'))
            addr-=0x20

    def _scores_header(self,bank,surface):
        # $0AA8 initially draws HIGH SCORE and the player/high-score counters.
        self._rom_text(bank,surface,4)
        for a,word in ((0x4b40,'1UP'),):
            for c in word:
                code=ord(c)-ord('0') if c.isdigit() else ord(c)-ord('A')+0x11
                self._tile(bank,surface,a,code)
                a-=0x20
        self._digits(bank,surface,0x4b81,score_digits(self.player_scores[0]))
        if len(self.player_scores) > 1:
            a=0x48E0
            for c in "2UP":
                code=ord(c)-ord("0") if c.isdigit() else ord(c)-ord("A")+0x11
                self._tile(bank,surface,a,code)
                a-=0x20
            self._digits(bank,surface,0x4921,score_digits(self.player_scores[1]))
        self._digits(bank,surface,0x4a41,score_digits(self.high_score))

    def _credits(self,bank,surface):
        self._rom_text(bank,surface,5)
        if self.credits>=10:
            self._digits(bank,surface,0x4a9f,str(self.credits//10))
        self._digits(bank,surface,0x4a7f,str(self.credits%10))

    def _copyright(self,bank,surface):
        self._rom_text(bank,surface,14)

    def _title(self,bank,surface):
        for id_ in (11,12,6,18):
            self._rom_text(bank,surface,id_)
        self._copyright(bank,surface)

    def _credit_prompt(self,bank,surface):
        # $0F0F/$0F13/$0F2D: PUSH START, BONUS JET and 1P/2P prompt.
        self._rom_text(bank,surface,1)
        self._rom_text(bank,surface,22)
        self._rom_text(bank,surface,23)
        # $0F21/$0F29 fill the two preceding digits of "000 PTS".
        self._tile(bank,surface,0x4998,1)
        self._tile(bank,surface,0x4978,0)
        self._rom_text(bank,surface,25 if self.credits>=2 else 24)

    def _ranking(self,bank,surface):
        self._rom_text(bank,surface,26)
        for i in range(10):
            self._rom_text(bank,surface,27+i,
                           0 if i == self.highlight_rank else None)
        for i,value in enumerate(self.ranking):
            digits=f'{value:06d}'
            for j in range(6):
                # $0291/$02D5: BCD pairs are read LSB-first and written to
                # VRAM in +$20 steps; each new row advances two raw columns (low bits only).
                if j==5 and digits[0]=='0':
                    continue
                self._tile(bank,surface,0x4987+0x02*i+0x20*j,int(digits[5-j]),
                           0 if i == self.highlight_rank else None)
        self._copyright(bank,surface)

    def score_visible_characters(self):
        """How many of the 66 score glyphs original $0DAE has revealed."""
        elapsed=self.page_frame-SCORE_FIRST_DELAY
        if elapsed<0:return 0
        count=0
        for row in range(SCORE_ROWS):
            for col in range(SCORE_COLUMNS):
                if elapsed < SCORE_CHAR_DELAY:return count
                elapsed-=SCORE_CHAR_DELAY
                count+=1
            if row!=SCORE_ROWS-1:
                if elapsed<SCORE_ROW_DELAY:return count
                elapsed-=SCORE_ROW_DELAY
        return count

    def _score_table(self,bank,surface):
        self._rom_text(bank,surface,13)
        for raw_y,code,color,raw_x in self.data['score_sprites']:
            # $0D54: six ROM sprite-register records in hardware order.
            # ROT90 -> left-hand icons, 24px apart vertically.
            bank.sprite(surface,raw_y-8,raw_x-8,code,color)
        remaining=self.score_visible_characters()
        for row,record in enumerate(self.data['score_text']):
            for j,code in enumerate(record[:min(SCORE_COLUMNS,remaining)]):
                self._tile(bank,surface,0x4a4a+row*3-j*0x20,code)
            remaining-=min(remaining,SCORE_COLUMNS)
        self._copyright(bank,surface)

    def render(self,surface,bank):
        surface.fill((0,0,0))
        if self.page=='grid':
            # Original 8x8 character test appearance: a black centre and a
            # one-pixel pale border. A visual reconstruction, not a Z80 test.
            grid=(170,177,200)
            pg=bank.pg
            cleared=min(224,max(0,self.page_frame-BOOT_WIPE_START)*8)
            for y in range(0,256,8):
                for x in range(0,224-cleared,8):
                    pg.draw.rect(surface,grid,(x,y,8,8),1)
            self._render_stars(surface)
            return
        self._render_stars(surface)
        self._scores_header(bank,surface)
        if self.page=='title':self._title(bank,surface)
        elif self.page=='ranking':self._ranking(bank,surface)
        elif self.page=='score_table':self._score_table(bank,surface)
        elif self.page=='credit':self._credit_prompt(bank,surface)
        self._credits(bank,surface)
