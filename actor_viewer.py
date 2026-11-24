"""Scramble Phase 2: actual sprites vs four-character objects, animated from ROM.

This is an animation/compositing test, NOT actual Scramble gameplay or movement.
The scene intentionally shows enemies from different stages at once.

Run: py actor_viewer.py
Keys: TAB toggle gallery/2x2 assembly, 1..8 landscape colour (MAME 0..7),
      E explosion comparison, SPACE pause, N single-step, S PNG, ESC exit.
"""
from __future__ import annotations
from pathlib import Path
import sys

from scramble_objects import AnimationCollection, SpriteCharacterBank, ROTATED_GROUP_ORDER

ROOT = Path(__file__).resolve().parent
FPS = 60.606060  # Scramble logical frame rate; fixed-step accumulator
SCREEN_W, SCREEN_H = 256, 224  # post-rotation desktop game-space logical dimensions
SCALE = 3
SCREEN_X, SCREEN_Y = 25, 74
SIDEBAR_X = SCREEN_X + SCREEN_W*SCALE + 28
WINDOW_W, WINDOW_H = 1240, 805

DISPLAYED = [
    ("P1 JET", "player_one", (26, 55)),
    ("P2 JET", "player_two", (26, 90)),
    ("BOMB", "player_bomb", (26, 127)),
    ("ROCKET", "rocket", (170, 56)),
    ("UFO", "ufo", (170, 91)),
    ("FIREBALL", "fireball", (170, 126)),
]
GROUND = [
    ("ROCKET", "ground_rocket", (24, 174)),
    ("FUEL", "ground_fuel", (87, 174)),
    ("MYSTERY", "ground_mystery", (151, 174)),
    ("BASE", "ground_base", (217, 174)),
]


def run() -> None:
    try:
        import pygame
    except ImportError:
        raise SystemExit("Install pygame-ce: py -m pip install pygame-ce")
    pygame.init()
    window = pygame.display.set_mode((WINDOW_W, WINDOW_H), pygame.RESIZABLE)
    pygame.display.set_caption("SCRAMBLE (1981) - sprite and character construction / Phase 2")
    small = pygame.font.SysFont("consolas", 16)
    tiny = pygame.font.SysFont("consolas", 14)
    head = pygame.font.SysFont("consolas", 25, bold=True)
    clock = pygame.time.Clock()
    bank = SpriteCharacterBank()
    catalogue = AnimationCollection()
    names = {name for _, name, _ in DISPLAYED + GROUND}
    # The original ROM's explosion sequences are separate animation tables.
    explosion_for = {
        "player_one": "player_explosion", "player_two": "player_two_explosion",
        "player_bomb": "bomb_explosion", "rocket": "rocket_explosion",
        "ufo": "ufo_explosion", "ground_rocket": "ground_explosion",
        "ground_fuel": "ground_fuel_explosion",
        "ground_mystery": "ground_explosion", "ground_base": "ground_explosion",
    }
    names.update(explosion_for.values())
    animations = {name: catalogue.play(name) for name in names}
    colour = 2
    mode = 0
    paused = False
    exploding = False
    frame_no = 0
    accumulated = 0.0
    logical = pygame.Surface((SCREEN_W, SCREEN_H)).convert()

    def text(label, x, y, color=(222, 227, 245), font=small, target=None):
        (target or stage).blit(font.render(str(label), True, color), (x, y))

    def draw_game_view():
        logical.fill((0,0,0))
        if mode == 0:
            bank.text(logical, 12, 5, "1UP", 2)
            bank.text(logical, 91, 5, "HIGH SCORE", 0)
            bank.text(logical, 12, 16, "001000", 2)
            bank.text(logical, 106, 16, "010000", 2)
            for label, name, (x,y) in DISPLAYED:
                active_name = explosion_for.get(name, name) if exploding else name
                frame = animations[active_name].current
                bank.sprite(logical, x, y, frame.code, frame.colour)
            # The samples have deliberately independent coordinates and show
            # mutually exclusive enemy types; they do not simulate gameplay.
            for label, name, (x,y) in GROUND:
                active_name = explosion_for.get(name, name) if exploding else name
                frame = animations[active_name].current
                bank.ground_object(logical, x, y, frame.code, colour)
            for y in (191,199,207,215):
                for x in range(0,256,8):
                    bank.character(logical,x,y,0x39,colour)
        else:
            bank.text(logical, 12, 10, "4 CHARACTER OBJECTS", 2)
            bank.text(logical, 12, 25, "2X2 TILES EACH", 2)
            for i,(label,name,_) in enumerate(GROUND):
                x=32+(i%2)*125
                y=63+(i//2)*78
                active_name = explosion_for.get(name, name) if exploding else name
                frame=animations[active_name].current
                bank.ground_object(logical,x,y,frame.code,colour)
            bank.text(logical, 15, 213, "CHAR GROUP = CODE X 4", 2)

    def draw_sidebar():
        x = SIDEBAR_X
        text("SPRITES: ONE 16x16 IMAGE", x, 83, (255,230,120))
        text("Code / colour / ROM delay", x, 108, (165,173,198), tiny)
        ypos = 136
        for label, name, xy in DISPLAYED:
            active_name = explosion_for.get(name, name) if exploding else name
            f = animations[active_name].current
            text(f"{label:<12s} ${f.code:02X}  C{f.colour}  D{f.delay:02X}", x, ypos)
            ypos += 34
        text("CHARACTER TARGETS: FOUR 8x8", x, 367, (255,230,120))
        text("Group code x 4 gives first tile", x, 393, (165,173,198), tiny)
        ypos = 423
        for label, name, xy in GROUND:
            active_name = explosion_for.get(name, name) if exploding else name
            f = animations[active_name].current
            text(f"{label:<10s} ${f.code:02X} -> ${f.code*4:02X}-${f.code*4+3:02X}", x, ypos)
            ypos += 36
        text(f"Landscape column colour: {colour} / 7", x, 600, (154,204,255))
        text("Colour is per tilemap column;", x, 626, (163,173,195), tiny)
        text("moving sprites have own colour.", x, 648, (163,173,195), tiny)
        text("Animation codes and delays from", x, 681, (153,167,185), tiny)
        text("original Scramble Z80 ROM tables.", x, 702, (153,167,185), tiny)

    running = True
    while running:
        stage = pygame.Surface((WINDOW_W,WINDOW_H)).convert()
        stage.fill((16, 19, 32))
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False
                elif e.key == pygame.K_TAB:
                    mode = 1-mode
                elif pygame.K_1 <= e.key <= pygame.K_8:
                    colour = e.key - pygame.K_1
                elif e.key == pygame.K_SPACE:
                    paused = not paused
                    accumulated = 0.0
                elif e.key == pygame.K_e:
                    exploding = not exploding
                    for name in set(explosion_for.values()):
                        animations[name] = catalogue.play(name)
                elif e.key == pygame.K_n and paused:
                    for anim in animations.values(): anim.step()
                    frame_no += 1
                elif e.key == pygame.K_s:
                    draw_game_view()
                    pygame.image.save(logical,str(ROOT/"Scramble_Actor_Screenshot.png"))
        dt = min(clock.tick(120) / 1000.0, 0.10)
        if not paused:
            accumulated += dt
            while accumulated >= (1.0 / FPS):
                for a in animations.values():
                    a.step()
                frame_no += 1
                accumulated -= 1.0 / FPS
        text("SCRAMBLE / KONAMI 1981 - GRAPHICS PHASE 2",25,22,(243,246,255),head)
        text("DISPLAY SPECIMENS - NOT GAMEPLAY OR ACCURATE STAGE POSITIONS",25,51,(147,167,192),tiny)
        draw_game_view()
        scaled = pygame.transform.scale(logical,(SCREEN_W*SCALE,SCREEN_H*SCALE))
        stage.blit(scaled,(SCREEN_X,SCREEN_Y))
        pygame.draw.rect(stage,(90,96,130),pygame.Rect(SCREEN_X-1,SCREEN_Y-1,SCREEN_W*SCALE+2,SCREEN_H*SCALE+2),1)
        draw_sidebar()
        text("[1-8] colour  [TAB] 2x2 objects  [E] explosions  [SPACE] pause  [N] frame  [S] PNG  [ESC]",25,766,(171,184,206),tiny)
        text(f"FRAME {frame_no}    {'PAUSED' if paused else 'RUNNING'}    {'EXPLOSIONS' if exploding else 'NORMAL ANIMATIONS'}",25,746,(151,164,188),tiny)
        ww,wh=window.get_size()
        window.blit(pygame.transform.scale(stage,(ww,wh)),(0,0))
        pygame.display.flip()
    pygame.quit()


if __name__ == "__main__":
    run()
