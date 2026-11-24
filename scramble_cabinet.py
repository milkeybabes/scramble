"""Scramble coin/start/turn control, independent of player physics.

Original Z80 sources: $1A18 (32-strip VRAM clear), $0356/$1039 (player
intro, $96 frames), $107E (32-frame entrance preparation), $115A/$11BA
(player-1 hand-off), $1237/$123F (player-2 hand-off), $0223 (UP blink).

This deliberately recreates *visible* character-RAM changes, not a Z80/VRAM
emulator. Every player's PlayScene remains independent and unchanged while
that player is not flying.
"""
from __future__ import annotations
from scramble_hud import character_xy, score_digits
from scramble_palette import character_colour
from scramble_highscores import initial_ranking, validate_ranking, record_score
from scramble_attract import AttractMode

INTRO_FRAMES = 0x96       # $0368 / $1055: incoming PLAYER ONE/TWO message
TURN_DELAY = 0x32        # $115F: P1 -> P2 after P1 dies
P2_TURN_DELAY = 0x64     # $123C: P2 -> P1 after P2 dies
WIPE_FRAMES = 0x20       # $1A18: 32 character strips, one per update
READY_FRAMES = 0x20      # $1083: flat starting landscape preparation
GAME_OVER_HOLD = 0x96   # $113C / $1228
RANKING_HOLD = 0x80    # $1328: show ranking for 128 updates


class CabinetSession:
    """Source-directed one- and two-player front end."""
    def __init__(self, scenes, ranking=None):
        if not 1 <= len(scenes) <= 2:
            raise ValueError('Expected one or two PlayScene objects')
        self.scenes = list(scenes)
        self.active = 0
        self.phase = 'intro'  # intro / prepare / playing / between / wipe / game_over_hold / ranking / ranking_exit / ended
        self.timer = INTRO_FRAMES
        self.pending_player = None
        self.wipe_progress = 0
        self.intro_background = (0, 0, 0)
        self.frame = 0
        self.ranking = validate_ranking(ranking if ranking is not None else initial_ranking())
        self.high_score = max(self.ranking[0], *(s.hud.high_score for s in self.scenes))
        self.ranking_view = None
        self.last_qualification = None
        for s in self.scenes:
            s.new_game(0)
            s.hud.high_score = self.high_score

    @property
    def two_player(self):
        return len(self.scenes) == 2

    @property
    def scene(self):
        return self.scenes[self.active]

    @property
    def finished(self):
        return self.phase == 'ended'

    @property
    def scores(self):
        return tuple(s.hud.score for s in self.scenes)

    def other_available(self):
        return self.two_player and self.scenes[1-self.active].run_state != 'game_over'

    def _start_between(self, player, *, after_ranking=False):
        self.pending_player = player
        self.phase = 'between'
        # $1338 uses 100 frames following the post-GAME OVER ranking,
        # unlike the ordinary player-death delays at $115F/$123C.
        self.timer = (0x64 if after_ranking else
                      (TURN_DELAY if self.active == 0 else P2_TURN_DELAY))

    def _begin_wipe(self):
        # Preserve the outgoing hardware background colour, including the
        # original blue-background quirk on palettes 4 and 5. The incoming
        # turn starts with the *new* name, not the old one.
        self.intro_background = ((0, 0, 0x56) if self.scene.colour in (4, 5)
                                 else (0, 0, 0))
        self.phase = 'wipe'
        self.wipe_progress = 0

    def _switch(self):
        self.active = self.pending_player
        self.pending_player = None
        self.phase = 'intro'
        self.timer = INTRO_FRAMES
        self.scene.hud.high_score = self.high_score

    def _begin_ranking(self):
        """Original $130E/$1346: update RAM table and highlight qualifying row."""
        rank,inserted = record_score(self.ranking,self.scene.hud.score)
        self.last_qualification=(self.active,rank,inserted)
        self.high_score=max(self.high_score,self.ranking[0])
        self.ranking_view=AttractMode(boot_grid=False)
        self.ranking_view.go_to("ranking")
        self.ranking_view.ranking=list(self.ranking)
        self.ranking_view.high_score=self.high_score
        self.ranking_view.player_scores=self.scores
        self.ranking_view.highlight_rank=rank if rank < 10 else None
        self.phase="ranking"
        self.timer=RANKING_HOLD

    def _after_player_death(self):
        scene = self.scene
        if scene.run_state == 'respawn_delay':
            # Single-player retries also show the turn introduction; do NOT
            # render the outgoing player's announcement during the delay.
            next_player = 1-self.active if self.other_available() else self.active
            self._start_between(next_player)
        elif scene.run_state == 'game_over':
            self.phase = 'game_over_hold'
            self.timer = GAME_OVER_HOLD

    def tick(self, stick):
        self.frame += 1
        if self.phase == 'intro':
            self.timer -= 1
            if self.timer <= 0:
                self.phase = 'prepare'
                self.timer = READY_FRAMES
            return
        if self.phase == 'prepare':
            self.timer -= 1
            if self.timer <= 0:
                # The current stage's flat opening strip and fuel are rebuilt
                # on resume, not while another player is on screen.
                if self.scene.run_state == 'respawn_delay':
                    self.scene.restart_stage_after_death()
                self.phase = 'playing'
            return
        if self.phase == 'between':
            self.timer -= 1
            if self.timer <= 0:
                self._begin_wipe()
            return
        if self.phase == 'wipe':
            self.wipe_progress += 1
            if self.wipe_progress > WIPE_FRAMES:
                self._switch()
            return
        if self.phase == 'game_over_hold':
            self.timer -= 1
            if self.timer <= 0:
                self._begin_ranking()
            return
        if self.phase == 'ranking':
            self.ranking_view.tick()
            self.timer -= 1
            if self.timer <= 0:
                if self.other_available():
                    self._start_between(1-self.active,after_ranking=True)
                else:
                    # $1338: the post-score-table script still waits 100
                    # ticks before returning to the attract loop.
                    self.phase = 'ranking_exit'
                    self.timer = 0x64
            return
        if self.phase == 'ranking_exit':
            self.timer -= 1
            if self.timer <= 0:
                self.phase = 'ended'
            return
        if self.phase != 'playing':
            return
        scene = self.scene
        scene.tick(stick)
        self.high_score = max(self.high_score, scene.hud.high_score, scene.hud.score)
        for s in self.scenes:
            s.hud.high_score = self.high_score
        self._after_player_death()


def wipe_clear_width(progress):
    """Original $1A18 erases one 8-pixel-wide hardware column per frame.

    Scramble's native VRAM has 32 rows, of which 28 columns are visible in
    the ROT90 image. The last four updates therefore erase off-screen rows.
    """
    return min(224, max(0, int(progress)) * 8)


def draw_turn_wipe(surface, old_frame, session, stars, blink_phase, visible_func, pg):
    """Reveal the ROM-style strip erase of the outgoing character display.

    `old_frame` is a frozen copy of the outgoing game, captured by the GUI
    at the beginning of the $1A18 script. GPU stars are independent of the
    erased character RAM and remain visible over cleared strips.
    """
    surface.blit(old_frame, (0, 0))
    width = wipe_clear_width(session.wipe_progress)
    if width == 0:
        return
    x0 = 224-width
    pg.draw.rect(surface, (0,0,0), (x0,0,width,24))
    pg.draw.rect(surface, session.intro_background, (x0,24,width,216))
    pg.draw.rect(surface, (0,0,0), (x0,240,width,16))
    for x,y,rgb,flags in stars:
        if x0 <= x < 224 and 24 <= y < 240 and visible_func(flags,blink_phase):
            surface.set_at((x,y),rgb)


def draw_scoreboard(surface, bank, session:CabinetSession, *, intro=False):
    """Render ROM scoreboard positions; flash only the active 1UP/2UP label.

    Z80 $0223 blinks the label (not the numeric score):
    $4B40 1UP, $48E0 2UP, $4A80 HIGH SCORE,
    $4B81 P1, $4921 P2, $4A41 high score.
    """
    bank.pg.draw.rect(surface,(0,0,0),(0,0,224,24))
    def put(addr,text,color=None):
        bank.text(surface,*character_xy(addr),text,
                  character_colour(addr) if color is None else color)
    active_blink=((session.frame & 0x10)==0) if not intro else True
    if session.active != 0 or active_blink or session.phase == 'ended':
        put(0x4B40,'1UP')
    if session.two_player and (session.active != 1 or active_blink or session.phase == 'ended'):
        put(0x48E0,'2UP')
    put(0x4A80,'HIGH SCORE')
    put(0x4B81,score_digits(session.scenes[0].hud.score))
    if session.two_player:
        put(0x4921,score_digits(session.scenes[1].hud.score))
    put(0x4A41,score_digits(session.high_score))


def render_turn_intro(surface,bank,session,stars,blink_phase,visible_func,*,prepare=False):
    """Show *incoming* PLAYER label, then the $10A1 flat-ground prefill."""
    surface.fill(session.intro_background)
    bank.pg.draw.rect(surface,(0,0,0),(0,240,224,16))
    for x,y,rgb,flags in stars:
        if visible_func(flags,blink_phase) and 0<=x<224 and 0<=y<256:
            surface.set_at((x,y),rgb)
    draw_scoreboard(surface,bank,session,intro=True)
    if prepare:
        # $107E / $10A1: draw the flat strip before enabling the ship,
        # leaving the incoming player's name off-screen at this point.
        scene=session.scene
        if scene.pg is not None:
            surface.blit(scene._flat_strip(),(0,0))
        return
    name='PLAYER ONE' if session.active==0 else 'PLAYER TWO'
    bank.text(surface,*character_xy(0x4A94),name,0)
    scene=session.scene
    for i in range(min(max(scene.remaining_lives,0),6)):
        bank.character(surface,*character_xy(0x4BBF-i*0x40),0x0A,
                       character_colour(0x4BBF))
        bank.character(surface,*character_xy(0x4BBF-i*0x40-0x20),0x0B,
                       character_colour(0x4BBF))
    bank.character(surface,*character_xy(0x485F),0x0E,character_colour(0x485F))
