"""Presentation layer only: arcade viewport, optional Konami cabinet artwork.

All gameplay remains rendered at its original 224 x 256 logical resolution.
The bezel image is original user-supplied artwork, not generated sprites.
"""
from __future__ import annotations
from pathlib import Path

# The Divemaster bezel is transparent in the monitor aperture. These are the
# measured monitor bounds in the original 1920 x 1080 supplied image.
BEZEL_ORIGINAL_SIZE = (1920, 1080)
BEZEL_ORIGINAL_MONITOR = (555, 76, 810, 926)
BEZEL_SIZE = (1280, 720)
GAME_ZOOM = 3


def preferred_window_size(view_w: int, view_h: int, bezel=False, debug=False):
    if debug:
        return (1150, 875)  # Original diagnostic-only composition.
    return BEZEL_SIZE if bezel else (view_w * GAME_ZOOM, view_h * GAME_ZOOM)


class ScreenPresenter:
    def __init__(self, pygame, root: Path, view_w: int, view_h: int, debug=False):
        self.pg = pygame
        self.root = Path(root)
        self.view_w = view_w
        self.view_h = view_h
        self.debug = debug
        self._bezel = None

    def _load_bezel(self):
        if self._bezel is None:
            path = self.root / 'artwork' / 'Konami_Scramble_Divemaster.png'
            if not path.is_file():
                raise FileNotFoundError(f'Optional Konami artwork not found: {path}')
            self._bezel = self.pg.transform.scale(
                self.pg.image.load(str(path)).convert_alpha(), BEZEL_SIZE)
        return self._bezel

    def compose(self, logical, bezel=False):
        """Return the arcade-only or composited cabinet surface.

        No font rendering, game logic, or debug information enters this layer.
        """
        if not bezel:
            return self.pg.transform.scale(
                logical, (self.view_w * GAME_ZOOM, self.view_h * GAME_ZOOM))
        canvas = self.pg.Surface(BEZEL_SIZE).convert()
        canvas.fill((0, 0, 0))
        scale = BEZEL_SIZE[0] / BEZEL_ORIGINAL_SIZE[0]
        x, y, w, h = BEZEL_ORIGINAL_MONITOR
        rect = tuple(round(v * scale) for v in (x, y, w, h))
        canvas.blit(self.pg.transform.scale(logical, (rect[2], rect[3])), (rect[0], rect[1]))
        canvas.blit(self._load_bezel(), (0, 0))
        return canvas

    def present(self, window, frame):
        """Aspect-correct letterboxing; pygame.scale is nearest-neighbour."""
        dw, dh = window.get_size()
        sw, sh = frame.get_size()
        factor = min(dw / sw, dh / sh)
        nw = max(1, round(sw * factor))
        nh = max(1, round(sh * factor))
        window.fill((0, 0, 0))
        window.blit(self.pg.transform.scale(frame, (nw, nh)), ((dw - nw)//2, (dh - nh)//2))
