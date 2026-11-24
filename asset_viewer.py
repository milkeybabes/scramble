"""Native pygame-ce asset viewer for Scramble (Konami, 1981).

Usage: py asset_viewer.py
Keys: 1..8 colour group, LEFT/RIGHT change group, TAB for landscape,
      ESC to quit. Click tile/sprite in the grid for a larger preview.

This DOES NOT emulate hardware or play the game yet.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"


def run():
    try:
        import pygame
    except ImportError:
        raise SystemExit("pygame-ce is required: py -m pip install pygame-ce")

    palette_path = DATA / "palettes.json"
    if not palette_path.exists():
        raise SystemExit("Missing data/palettes.json; run tools/extract_assets.py first")
    manifest = json.loads(palette_path.read_text(encoding="utf8"))
    pygame.init()
    screen = pygame.display.set_mode((1150, 800), pygame.RESIZABLE)
    pygame.display.set_caption("Scramble (1981) - graphics asset viewer")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 18)
    small = pygame.font.SysFont("consolas", 14)
    header = pygame.font.SysFont("consolas", 28)
    palette_group = 2  # matches the user's MAME gfxdecode colour 2/8 screenshot
    view = 0
    selected_type, selected = 0, 0

    tile_sheets = [pygame.image.load(str(DATA / f"characters_color_{n}.png")).convert_alpha() for n in range(8)]
    sprite_sheets = [pygame.image.load(str(DATA / f"sprites_color_{n}.png")).convert_alpha() for n in range(8)]
    stages_img = pygame.image.load(str(DATA / "landscape_preview.png")).convert()

    def text_at(label, xy, color=(230, 233, 244), ft=font):
        screen.blit(ft.render(label, True, color), xy)

    def swatch(col, x, y, size=27):
        pygame.draw.rect(screen, col, pygame.Rect(x,y,size,size))
        pygame.draw.rect(screen, (114,118,139), pygame.Rect(x,y,size,size), 1)

    def cell_image(atlas, number, width, per_row):
        return atlas.subsurface(pygame.Rect((number%per_row)*width, (number//per_row)*width, width,width))

    def draw_grid(atlas, grid_x, grid_y, cols, rows, cell_size, zoom, current, is_selected):
        w = cols * cell_size * zoom
        img = pygame.transform.scale(atlas, (w, rows*cell_size*zoom))
        pygame.draw.rect(screen, (0,0,0), (grid_x,grid_y,w,w))
        screen.blit(img, (grid_x,grid_y))
        spacing = cell_size*zoom
        for i in range(cols+1):
            xx = grid_x + i*spacing
            pygame.draw.line(screen,(33,38,57),(xx,grid_y),(xx,grid_y+rows*spacing))
        for i in range(rows+1):
            yy = grid_y + i*spacing
            pygame.draw.line(screen,(33,38,57),(grid_x,yy),(grid_x+w,yy))
        if is_selected:
            rect = pygame.Rect(grid_x+(current%cols)*spacing, grid_y+(current//cols)*spacing,spacing,spacing)
            pygame.draw.rect(screen, (255, 255, 255), rect, 2)

    active = True
    while active:
        win_w, win_h = screen.get_size()
        # Fixed logical 1150x800 viewport so user can resize without distortions
        surface = pygame.Surface((1150,800)).convert()
        oldscreen = screen
        screen = surface
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                active = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    active = False
                elif pygame.K_1 <= event.key <= pygame.K_8:
                    palette_group = event.key - pygame.K_1
                elif event.key == pygame.K_RIGHT:
                    palette_group = (palette_group+1) % 8
                elif event.key == pygame.K_LEFT:
                    palette_group = (palette_group-1) % 8
                elif event.key == pygame.K_TAB:
                    view = 1-view
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and view == 0:
                mx = int(event.pos[0] * 1150 / max(1,win_w))
                my = int(event.pos[1] * 800 / max(1,win_h))
                if 26<=mx<538 and 108<=my<620:
                    selected_type = 0
                    selected = ((my-108)//32)*16 + ((mx-26)//32)
                elif 611<=mx<1123 and 108<=my<620:
                    selected_type = 1
                    selected = ((my-108)//64)*8 + ((mx-611)//64)
        surface.fill((18,20,33))
        text_at("SCRAMBLE / KONAMI 1981",(24,19), ft=header)
        text_at("Native pre-rendered assets; no graphics hardware emulation",(26,58),(150,161,182),small)
        if view == 0:
            text_at("256 CHARACTERS (8x8)",(26,86))
            text_at("64 SPRITES (16x16)",(611,86))
            draw_grid(tile_sheets[palette_group],26,108,16,16,8,4,selected,selected_type==0)
            draw_grid(sprite_sheets[palette_group],611,108,8,8,16,4,selected,selected_type==1)
            text_at(f"PALETTE {palette_group+1}/8 (MAME index {palette_group})",(26,635))
            for i,rgb in enumerate(manifest["palettes"][palette_group]):
                x = 320+i*73
                swatch(rgb,x,636)
                text_at(str(i),(x+32,642),(196,200,214),small)
            text_at(f"SELECTED: {'CHARACTER' if selected_type == 0 else 'SPRITE'} ${selected:02X} / {selected}",(26,683))
            atlas = tile_sheets[palette_group] if selected_type==0 else sprite_sheets[palette_group]
            cell_size, grid_width = (8,16) if selected_type==0 else (16,8)
            cell = cell_image(atlas,selected,cell_size,grid_width)
            scaled = pygame.transform.scale(cell,(80,80))
            pygame.draw.rect(screen,(3,4,8),(825,682,80,80))
            screen.blit(scaled,(825,682))
            pygame.draw.rect(screen,(107,117,151),(825,682,80,80),1)
            text_at("Original pixels",(925,711),(156,165,188),small)
        else:
            text_at("LANDSCAPE DATA - SIX ORIGINAL STAGE STREAMS",(26,87))
            w,h=stages_img.get_size()
            scale = min(1100/w,640/h)
            scaled = pygame.transform.scale(stages_img,(int(w*scale),int(h*scale)))
            screen.blit(scaled,(26,115))
            text_at("Diagnostic height/ceiling plot from ROM records - NOT a gameplay screenshot",(26,760),(170,177,198),small)
        text_at("[1-8] colour   [arrows] cycle   [TAB] landscape   [click] select   [ESC] quit",
                (26,775),(145,157,180),small)
        screen = oldscreen
        final = pygame.transform.scale(surface,(win_w,win_h)) if (win_w,win_h)!=(1150,800) else surface
        screen.blit(final,(0,0))
        pygame.display.flip()
        clock.tick(30)
    pygame.quit()


if __name__ == "__main__":
    run()
