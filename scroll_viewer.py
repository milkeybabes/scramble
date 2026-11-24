"""Scramble continuous-course scenery viewer: six original landscapes without cuts.

    py scroll_viewer.py
    py scroll_viewer.py --stage 2 --palette 4 --latch 1

This is a scenery test, not playable game logic. Landscape records, tile codes
and target locations come directly from the Konami program ROM through our
Phase-1 extractor. Rendering is native pygame; no Z80 or graphics emulation.

Original source: Scott Tunstall's scramble.asm $0793-$084A, $15A5-$16A5;
MAME's gfx layout and video init: src/mame/galaxian/scramble.cpp.
"""
from __future__ import annotations
import argparse
from pathlib import Path

from scramble_scroll import (VIEW_WIDTH, VIEW_HEIGHT, read_stages, ScrollClock,
                             colour_after_next_change, reference_jet_y)
from scramble_objects import SpriteCharacterBank, AnimationCollection
from scramble_hud import HUDValues, draw_hud
from scramble_stars import blink_state, star_visible, BLINK_PERIOD_MS
from scramble_course import ContinuousCourse
from scramble_palette import (screen_y_colour, DEFAULT_LANDSCAPE_COLOUR,
                              COLOUR_CYCLE_FRAMES, INITIAL_CHANGE_FRAMES)

ROOT = Path(__file__).resolve().parent
LOGICAL_FPS = 16000.0 / 132 / 2   # 60.606060 Hz, original MAME scramble driver
ZOOM = 3
WIDTH, HEIGHT = 1150, 875
GAME_X, GAME_Y = 30, 60
SIDEBAR = GAME_X + VIEW_WIDTH * ZOOM + 27


def scramble_stars() -> list[tuple[int, int, tuple[int,int,int], int]]:
    """Original Galaxian/Scramble LFSR star positions; rotation and visible clip.

    See MAME galaxold_v.cpp galaxold_init_stars/scrambold_draw_stars.
    Blink timing is reproduced separately using MAME's 555 timer formula.
    Positions and colours are derived from the original LFSR, not Python RNG.
    """
    result = []
    generator = 0
    intensities = (0, 0x88, 0xcc, 0xff)
    for raw_y in range(256):
        for hx in range(512):
            bit0 = (((~generator >> 16) & 1) ^ ((generator >> 4) & 1))
            generator = ((generator << 1) | bit0) & 0xffffffff
            if (((~generator >> 16) & 1) and (generator & 0xff) == 0xff):
                color = (~(generator >> 8)) & 0x3f
                if not color:
                    continue
                x_hw = hx >> 1
                if not (16 <= raw_y <= 239):
                    continue
                if not ((raw_y & 1) ^ ((x_hw >> 3) & 1)):
                    continue
                sx = 239 - raw_y
                sy = x_hw
                result.append((sx, sy, (intensities[color & 3],
                                       intensities[(color >> 2) & 3],
                                       intensities[(color >> 4) & 3]),
                               ((color & 1) != 0) | (((color & 4) != 0) << 1) | (((raw_y & 2) != 0) << 2)))
    return result


class Scene:
    """Native renderer for one UNBROKEN world scroll across the six stages.

    Earlier demos reset scroll at each level. Now the $FF marker selects the
    next record stream while the previous section remains visible on the left.
    """
    def __init__(self, pg, bank, stage_maps, start_stage=0, start_palette=DEFAULT_LANDSCAPE_COLOUR, speed_latch=0):
        self.pg, self.bank = pg, bank
        self.stages = stage_maps
        self.course = ContinuousCourse(stage_maps)
        self.stage_idx = start_stage
        self.colour = start_palette
        self.auto_colour = True
        self.speed = ScrollClock(speed_latch)
        self.speed.pixels = (self.course.starts[start_stage] if start_stage else 0)
        self.frames = 0
        self.colour_ticks = 0
        # Continue the source's 512-frame cadence after an opening phase
        # inferred from the reference recording (attract state is not ported).
        self.next_colour_tick = INITIAL_CHANGE_FRAMES
        self.show_jet = True
        self.show_targets = True
        self.stars = scramble_stars()
        self.sheets = {}
        self.animations = AnimationCollection()
        self.jet_anim = self.animations.play('player_one')
        self.jet_rear_anim = self.animations.play('player_two')
        self.base_anim = self.animations.play('ground_base')
        self.hud = HUDValues()
        self.at_base_end = False
        self.base_destroyed = False
        self.hit_targets = set()

    @property
    def stage(self):
        return self.stages[self.stage_idx]

    @property
    def stage_scroll(self):
        return max(0, self.speed.pixels - self.course.starts[self.stage_idx])

    def goto(self, idx: int):
        """Debug-only seeking: NORMAL flow never calls goto()."""
        self.stage_idx = idx % len(self.stages)
        self.speed.reset()
        self.colour_ticks = 0
        self.next_colour_tick = INITIAL_CHANGE_FRAMES
        self.speed.pixels = (self.course.starts[self.stage_idx] if self.stage_idx else 0)
        self.jet_anim = self.animations.play('player_one')
        self.jet_rear_anim = self.animations.play('player_two')
        self.base_anim = self.animations.play('ground_base')
        self.at_base_end = False
        self.base_destroyed = False
        self.hit_targets.clear()

    def tick(self):
        self.frames += 1
        self.jet_anim.step()
        self.jet_rear_anim.step()
        self.base_anim.step()
        self.colour_ticks += 1
        if self.colour_ticks >= self.next_colour_tick:
            # Keep advancing the phase when C has selected a manual colour;
            # re-enabling P must not fast-forward through missed transitions.
            self.next_colour_tick += COLOUR_CYCLE_FRAMES
            if self.auto_colour:
                self.colour = colour_after_next_change(self.colour)
        # Never stop simply because the end of the first BASE strip arrived.
        # Original $27E1-$27FC restarts the BASE data pointer at its $FF marker.
        self.speed.tick()
        self.at_base_end = self.speed.pixels >= self.course.last_scroll
        self.stage_idx = self.course.producer_stage(self.speed.pixels)

    def _strip(self, stage_index):
        key = (stage_index, self.colour, self.show_targets)
        if key in self.sheets:
            return self.sheets[key]
        stage = self.stages[stage_index]
        pg = self.pg
        strip = pg.Surface((stage.width, VIEW_HEIGHT), pg.SRCALPHA).convert_alpha()
        strip.fill((0,0,0,0))
        for ci, column in enumerate(stage.cols):
            px = ci*8
            for yi in range(5,29):
                code = column[yi]
                if code != 0x10:
                    self.bank.character(strip, px, yi*8, code, screen_y_colour(yi*8, self.colour))
        if len(self.sheets) > 12:
            self.sheets.clear()
        self.sheets[key] = strip
        return strip

    def _flat_strip(self):
        """Game-start prefill from ROM drawing routine $10A1.

        $36 rough edge at character row 25; $39 solid ground beneath.
        The original fills 30 columns, of which 28 are visible after ROT90.
        """
        key=('flat',self.colour)
        if key in self.sheets:
            return self.sheets[key]
        strip=self.pg.Surface((VIEW_WIDTH,VIEW_HEIGHT),self.pg.SRCALPHA).convert_alpha()
        strip.fill((0,0,0,0))
        for x in range(0,VIEW_WIDTH,8):
            self.bank.character(strip,x,25*8,0x36,screen_y_colour(25*8,self.colour))
            for y in range(26,29):
                self.bank.character(strip,x,y*8,0x39,screen_y_colour(y*8,self.colour))
        self.sheets[key]=strip
        return strip

    def render(self, surface):
        # Compositing adjacent stage strips is essential: no cut, no reset.
        pos = self.speed.pixels
        pg = self.pg
        bg = (0,0,0x56) if self.colour in (4,5) else (0,0,0)
        surface.fill(bg)

        rec = self.course.record_at(pos + VIEW_WIDTH)
        if rec['ceiling'] is None:
            blink = blink_state(self.frames)
            for x, y, rgb, flags in self.stars:
                if star_visible(flags, blink):
                    surface.set_at((x,y), rgb)

        for item in self.course.visible_slices(pos):
            strip = (self._flat_strip() if item.stage_index == -1
                     else self._strip(item.stage_index))
            surface.blit(strip,(item.screen_x,0),
                         pg.Rect(item.source_x,0,item.width,VIEW_HEIGHT))

        # Ground objects are independent from the terrain atlas: a bullet can
        # remove one without rebuilding the scenery or breaking stage seams.
        if self.show_targets:
            for idx,target,world_x,key in self.course.nearby_targets(pos):
                if key in self.hit_targets:
                    continue
                if target.kind == 'BASE' and self.base_destroyed:
                    continue
                x = world_x-pos
                if -16 < x < VIEW_WIDTH:
                    group = (self.base_anim.current.code if target.kind=='BASE'
                             else target.group)
                    self.bank.ground_object(surface,x,target.y,group,self.colour)

        draw_hud(surface,self.bank,self.stage_idx,self.frames,self.hud)
        if self.show_jet:
            world_x = pos+32
            stage_index = self.course.find_stage(world_x)
            stage = self.stages[stage_index]
            local = world_x - self.course.starts[stage_index]
            marker_y = reference_jet_y(stage,local,screen_x=0)
            if marker_y is not None:
                self.bank.sprite(surface,16,marker_y,self.jet_rear_anim.current.code,
                                 self.jet_rear_anim.current.colour)
                self.bank.sprite(surface,32,marker_y,self.jet_anim.current.code,
                                 self.jet_anim.current.colour)

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--stage',type=int,default=1,choices=range(1,7))
    ap.add_argument('--palette',type=int,default=DEFAULT_LANDSCAPE_COLOUR,choices=range(8))
    ap.add_argument('--latch',type=int,default=0,choices=range(8),
                    help='Frames between scroll pixel events (0=1 px each frame)')
    args=ap.parse_args()
    try:
        import pygame
    except ImportError:
        raise SystemExit('pygame-ce required: py -m pip install pygame-ce')
    pygame.init()
    window = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption('SCRAMBLE 1981 / Continuous scrolling terrain')
    clock = pygame.time.Clock()
    font = pygame.font.SysFont('consolas',17)
    tiny = pygame.font.SysFont('consolas',14)
    large = pygame.font.SysFont('consolas',25,bold=True)
    stage_maps = read_stages()
    bank=SpriteCharacterBank()
    scene=Scene(pygame,bank,stage_maps,args.stage-1,args.palette,args.latch)
    logical=pygame.Surface((VIEW_WIDTH,VIEW_HEIGHT)).convert()
    accumulated=0.0
    paused=False

    def label(canvas, s, x, y, color=(215,224,240), face=None):
        canvas.blit((face or font).render(str(s),True,color),(x,y))

    def change_stage(i):
        nonlocal accumulated
        scene.goto(i)
        accumulated=0.0

    active=True
    while active:
        elapsed=min(clock.tick(120)/1000.0, 0.08)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                active=False
            elif e.type == pygame.KEYDOWN:
                key=e.key
                if key == pygame.K_ESCAPE: active=False
                elif key == pygame.K_SPACE: paused=not paused; accumulated=0.0
                elif pygame.K_1 <= key <= pygame.K_6: change_stage(key-pygame.K_1)
                elif key == pygame.K_PAGEUP: change_stage(scene.stage_idx-1)
                elif key == pygame.K_PAGEDOWN: change_stage(scene.stage_idx+1)
                elif key == pygame.K_r: change_stage(0)
                elif key == pygame.K_c:
                    scene.colour=(scene.colour+1)%8; scene.auto_colour=False
                elif key == pygame.K_p: scene.auto_colour=not scene.auto_colour
                elif key == pygame.K_j: scene.show_jet=not scene.show_jet
                elif key == pygame.K_t: scene.show_targets=not scene.show_targets
                elif key in (pygame.K_PLUS,pygame.K_EQUALS,pygame.K_KP_PLUS):
                    scene.speed.latch=max(0,scene.speed.latch-1);scene.speed.counter=0
                elif key in (pygame.K_MINUS,pygame.K_KP_MINUS):
                    scene.speed.latch=min(7,scene.speed.latch+1);scene.speed.counter=0
                elif key == pygame.K_n and paused:
                    scene.tick()
                elif key in (pygame.K_LEFT,pygame.K_RIGHT) and paused:
                    delta=-1 if key==pygame.K_LEFT else 1
                    scene.speed.pixels=max(0,scene.speed.pixels+delta)
                    scene.stage_idx=scene.course.producer_stage(scene.speed.pixels)
                    scene.at_base_end=scene.speed.pixels>=scene.course.last_scroll
                elif key == pygame.K_s:
                    scene.render(logical)
                    outfile=ROOT / 'Scramble_Scroll_Screenshot.png'
                    pygame.image.save(logical,str(outfile))
                    print(f'Screenshot: {outfile}')
        if not paused:
            accumulated += elapsed
            updates=0
            while accumulated >= 1/LOGICAL_FPS and updates < 8:
                scene.tick()
                accumulated -= 1/LOGICAL_FPS
                updates += 1
        frame=pygame.Surface((WIDTH,HEIGHT)).convert()
        frame.fill((17,20,32))
        label(frame,'SCRAMBLE / KONAMI 1981 - CONTINUOUS SIX-STAGE SCROLL', 30,18,(243,247,255),large)
        scene.render(logical)
        blown=pygame.transform.scale(logical,(VIEW_WIDTH*ZOOM,VIEW_HEIGHT*ZOOM))
        frame.blit(blown,(GAME_X,GAME_Y))
        pygame.draw.rect(frame,(95,100,125),(GAME_X-1,GAME_Y-1,VIEW_WIDTH*ZOOM+2,VIEW_HEIGHT*ZOOM+2),1)
        x=SIDEBAR
        label(frame,f'STAGE {scene.stage_idx+1} / 6',x,92,(255,218,110),large)
        label(frame,scene.stage.name,x,131,(217,229,247))
        label(frame,f'Records: {len(scene.stage.records)}',x,180)
        label(frame,f'Terrain: {scene.stage.width:,} pixels',x,211)
        label(frame,f'World: {scene.speed.pixels:,} / {scene.course.last_scroll:,} px',x,242)
        label(frame,f'Local stage scroll: {scene.stage_scroll:,} px',x,273)
        label(frame,f'Palette: {scene.colour}  ({"AUTO" if scene.auto_colour else "MANUAL"})',x,318)
        label(frame,f'Scroll latch: {scene.speed.latch}',x,349)
        label(frame,f'Frames: {scene.frames:,}',x,380)
        label(frame,'FIXED UPDATE: 60.606 Hz',x,423,(149,189,226),tiny)
        label(frame,'1px steps, no filtering',x,447,(149,189,226),tiny)
        label(frame,'Original 8x8 tile codes',x,475,(149,189,226),tiny)
        label(frame,'2 columns per ROM record',x,499,(149,189,226),tiny)
        label(frame,'Real 2x2 ground objects',x,523,(149,189,226),tiny)
        label(frame,'ROM-defined colour cycling',x,547,(149,189,226),tiny)
        label(frame,'Scenery / graphics demo',x,601,(255,218,110))
        label(frame,'NO enemies, collisions or',x,635,(165,177,205),tiny)
        label(frame,'gameplay logic yet.',x,655,(165,177,205),tiny)
        label(frame,'[1..6] test seek [PgUp/Dn] test seek',30,839,(173,189,212),tiny)
        label(frame,'[Space] pause  [N] frame  [Left/Right] pixel   [C] palette  [P] auto',30,856,(173,189,212),tiny)
        label(frame,'[+/-] rate  [T] targets  [J] jet  [R] restart course  [S] screenshot  [Esc] quit',700,839,(173,189,212),tiny)
        label(frame,'PAUSED' if paused else 'BASE REPEATING' if scene.at_base_end else 'SCROLLING',x,700,(241,198,101) if paused else (121,222,162),large)
        w,h=window.get_size()
        window.blit(pygame.transform.scale(frame,(w,h)),(0,0))
        pygame.display.flip()
    pygame.quit()


if __name__=='__main__':
    main()
