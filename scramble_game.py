"""Scramble: continuous course, player, ground targets, flying rockets, UFOs, fireballs and fuel.

This is the implementation module. Launch using scramble.py or Play Scramble.bat.

Run: py scramble.py
     py scramble.py --stage 5 --latch 0
     py scramble.py --trace ship.csv
     py scramble.py --headless 180 --input 'R:50,U+R:30,D:10'

Input moves exactly one original player-coordinate pixel per logical frame,
with no acceleration or filtering. One game update at 16000/264 = 60.606Hz.
The clearance outline is diagnostic, but the same approximate source-derived
terrain bounds now drive deaths; the original circular buffer phase remains
unmatched to MAME and needs a frame-by-frame check.
Ground-to-air rockets (original source stages 1 and 4) now launch, climb,
collide and explode. UFO and fireball motion/spawning are translated; exact R samples need MAME tracing.
Ground/terrain collision uses ROM landscape extents,
with the original ring-buffer alignment not yet proven against MAME.
Player and ground-target explosions, fuel consumption/refill/depletion, lives,
stage respawn and GAME OVER are implemented. Bullets and bombs are retained.
At the BASE the original final terrain loops if the player misses the target.
The Phase A default GUI starts with ROM-derived attract screens; use --skip-attract to play at once.
Press M only for a debug simulation of base destruction while one is visible.
--auto-complete is a debug-only substitute for real bomb collision.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime
from pathlib import Path

from scramble_scroll import VIEW_WIDTH, VIEW_HEIGHT, read_stages
from scramble_objects import SpriteCharacterBank, AnimationCollection
from scramble_player import Joystick, PlayerJet, terrain_clearance_continuous
from scramble_bullets import PlayerBullets
from scramble_bombs import PlayerBombs
from scramble_fuel import FuelTimer
from scramble_ground_effects import GroundEffects
from scramble_rockets import FlyingRockets
from scramble_aliens import FlyingAliens
from scramble_palette import character_colour, DEFAULT_LANDSCAPE_COLOUR
from scramble_attract import AttractMode
from scramble_cabinet import CabinetSession, draw_scoreboard, render_turn_intro, draw_turn_wipe
from scramble_stars import blink_state, star_visible
from scramble_audio import ScrambleAudio
from scramble_display import ScreenPresenter, preferred_window_size
from scroll_viewer import Scene, LOGICAL_FPS, GAME_X, GAME_Y, SIDEBAR, WIDTH, HEIGHT, ZOOM, scramble_stars

ROOT = Path(__file__).resolve().parent


class PlayScene(Scene):
    """Continuous stage-flow test plus the original one-pixel jet movement.

    A real forward-bullet or bomb hit can destroy the base. M remains a test
    shortcut ONLY while the base is visible, for mission-script testing.
    """
    def __init__(self, pg, bank, stages, start_stage=0, start_palette=DEFAULT_LANDSCAPE_COLOUR,
                 speed_latch=0, auto_complete=False, lives=3, collisions=True,
                 fuel_enabled=True, rockets_enabled=True,
                 aliens_enabled=True, enemy_seed=0):
        super().__init__(pg, bank, stages, start_stage, start_palette, speed_latch)
        self.show_jet = False
        self.jet = PlayerJet()
        self.bullets = PlayerBullets()
        self.bombs = PlayerBombs()
        self.fuel_timer = FuelTimer()
        self.fuel_enabled = bool(fuel_enabled)
        self.rockets_enabled = bool(rockets_enabled)
        self.ground_effects = GroundEffects(self.animations)
        self.rockets = FlyingRockets(self.animations)
        self.aliens_enabled = bool(aliens_enabled)
        self.enemy_seed = int(enemy_seed) & 0x7f
        self.aliens = FlyingAliens(self.animations,seed=self.enemy_seed)
        self.last_hit = None
        self.show_clearance = False
        self.last_input = Joystick()
        if lives not in (3, 4, 5, 6, 255):
            raise ValueError('Lives must be one of 3, 4, 5, 6, or 255')
        self.player_number = 1  # cabinet assigns 2 to the other independent PlayScene
        self.initial_lives = lives
        self.remaining_lives = lives - 1  # $10D8 consumes the first life in GAME_INIT
        self.lives_lost = 0
        self.bonus_awarded = False
        self.collision_enabled = bool(collisions)
        self.death_reason = None
        self.explosion_front = None
        self.explosion_rear = None
        self.run_state = 'playing'  # playing, out_of_fuel, dying, respawn_delay, game_over, cool_off, blank, message
        # The original $1288 COOL_OFF still calls ANIMATION_AND_MOVEMENT and
        # COLLISION_DETECTION. Track a powerless jet independently so its
        # 150-frame mission countdown can continue during a fuel-out descent.
        self.cool_off_out_of_fuel = False
        self.retry_stage = None  # after death: temporarily prefill stage entrance
        self.state_timer = 0
        self.auto_complete = auto_complete
        self.first_palette = start_palette
        self.hud.game_in_play = True
        self.hud.lives = self.remaining_lives
        self.loop_number = 1
        # Emitted by the game, consumed by the graphical sound layer once per
        # logical update. Headless runs retain at most the current update.
        self.audio_events = []

    def emit_audio(self, name: str):
        self.audio_events.append(name)

    def goto(self, idx: int):
        super().goto(idx)  # debugging seek, not an arcade stage transition
        self.run_state = 'playing'
        self.cool_off_out_of_fuel = False
        self.state_timer = 0
        self.bullets.reset()
        self.bombs.reset()
        self.fuel_timer.reset()
        self.ground_effects.reset()
        self.rockets.reset()
        self.aliens.reset()
        self.last_hit = None
        self.death_reason = None
        self.explosion_front = None
        self.explosion_rear = None
        self.retry_stage = None
        self.audio_events.clear()

    def new_game(self, start_stage=0):
        """Restart whole game, unlike death which retains stage and score."""
        self.goto(start_stage)
        self.reset_jet()
        self.remaining_lives = self.initial_lives - 1
        self.hud.lives = self.remaining_lives
        self.hud.score = 0
        self.hud.fuel = 255
        self.hud.missions_completed = 0
        self.hud.game_in_play = True
        self.bonus_awarded = False
        self.lives_lost = 0
        self.loop_number = 1
        self.colour = self.first_palette
        self.aliens.refresh.reset()  # Reproduce a fixed Python test seed on NEW GAME only

    def kill_player(self, reason='terrain') -> bool:
        """$214A/$2097: freeze scroll, mark two ship components exploding."""
        if self.run_state not in ('playing', 'out_of_fuel', 'cool_off'):
            return False
        # Death overrides pending mission completion: a destroyed base is not
        # a successful escape if the jet hits the remaining buildings.
        self.cool_off_out_of_fuel = False
        self.run_state = 'dying'
        self.state_timer = 0x6F  # PLAYER_EXPLOSION_INIT $1814: 111 frames
        self.death_reason = reason
        self.explosion_front = self.animations.play('player_explosion')
        self.explosion_rear = self.animations.play('player_two_explosion')
        self.lives_lost += 1
        self.emit_audio('ship_explosion')
        # Discard projectiles, but preserve score, reserve lives and stage pointer.
        self.bullets.reset()
        self.bombs.reset()
        return True

    def restart_stage_after_death(self):
        """$1151 -> $107E -> $10BA: retry current stage from its start."""
        stage = self.stage_idx
        palette = self.colour  # death colour-cycle is deliberately not reset to pink
        self.goto(stage)
        self.reset_jet()
        self.colour = palette
        # $10A1: on every life, a flat 224px terrain strip scrolls off while
        # the selected level's first ROM record comes in from the right.
        self.retry_stage = stage
        self.speed.pixels = max(0, self.course.starts[stage] - VIEW_WIDTH)
        self.at_base_end = False
        self.hud.fuel = 255
        self.remaining_lives -= 1  # GAME_INIT $10D8
        self.hud.lives = self.remaining_lives
        self.run_state = 'playing'
        self.hud.game_in_play = True

    def check_ship_collisions(self) -> bool:
        """Stage geometry and ground objects, before the explosion handler.

        The source checks three terrain extents ($2113), and ground objects
        ($20DE). Our linear-ROM extents are not yet ring-buffer-frame exact;
        no invented pixel-perfect accuracy is claimed.
        """
        if not self.collision_enabled or self.run_state not in ('playing','out_of_fuel','cool_off'):
            return False
        for i,target,wx,key in self.course.nearby_targets(self.speed.pixels):
            if key in self.hit_targets or (target.kind == 'BASE' and self.base_destroyed):
                continue
            if (self.retry_stage is not None and
                    self.speed.pixels < self.course.starts[self.retry_stage] and
                    i != self.retry_stage):
                continue  # earlier stage's scenery replaced by flat prefill
            sx = wx-self.speed.pixels
            if not (-24 < sx < VIEW_WIDTH):
                continue
            # Native-screen projection of original $207A proximity bounds.
            if (self.jet.screen_x-6 < sx+16 and
                    self.jet.screen_x+10 > sx and
                    self.jet.screen_y-4 < target.y+16 and
                    self.jet.screen_y+13 > target.y):
                return self.kill_player('ground_object')
        # $205E/$20C2: UFO/fireball vs jet, before ground and terrain.
        if self.aliens.hit_ship(self.jet):
            return self.kill_player('ufo' if self.stage.flags == 2 else 'fireball')
        # $20F4: flying rocket proximity collision, before terrain $2113.
        if self.rockets.hit_ship(self.jet):
            return self.kill_player('flying_rocket')
        # The first frames of a retry are the original safe, flat strip;
        # the incoming terrain cannot hit the jet until it reaches its nose.
        if not self.clearance()[0]:
            return self.kill_player('terrain')
        return False

    def reset_jet(self):
        self.jet.reset()
        self.jet_anim = self.animations.play('player_one')
        self.jet_rear_anim = self.animations.play('player_two')

    @property
    def base_visible(self) -> bool:
        return any(target.kind == 'BASE' and -16 < wx-self.speed.pixels < VIEW_WIDTH
                   for _,target,wx,key in self.course.nearby_targets(self.speed.pixels))

    def simulate_base_destroyed(self) -> bool:
        """Start the base-complete sequence (real bullet hit or debug M).

        Source: $22C9 mission flag, $232F mission script, $1288 cooldown.
        """
        if self.run_state not in ('playing', 'out_of_fuel') or not self.base_visible:
            return False
        self.cool_off_out_of_fuel = self.run_state == 'out_of_fuel'
        self.run_state = 'cool_off'
        self.state_timer = 150  # original $2338 = $96
        self.base_destroyed = True
        return True

    def restart_loop(self):
        # $12C6: awards a life and restarts via GAME_INIT (consumes a life).
        # Keep earned score; extra lives/turns are not yet fully implemented.
        old_lives = self.hud.lives
        self.goto(0)
        self.reset_jet()
        self.colour = self.first_palette
        self.hud.lives = old_lives
        self.hud.fuel = 255
        self.hud.missions_completed += 1
        self.hud.high_score=max(self.hud.high_score,self.hud.score)
        self.loop_number += 1

    def award_points(self, points: int):
        """Existing arcade score and 10,000 point bonus, also for flying rockets."""
        self.hud.score = min(999999, self.hud.score + points)
        self.hud.high_score = max(self.hud.high_score, self.hud.score)
        if not self.bonus_awarded and self.hud.score >= 10000:
            self.bonus_awarded = True
            self.remaining_lives = min(255, self.remaining_lives + 1)
            self.hud.lives = self.remaining_lives
            self.emit_audio('extra_life')

    def register_ground_hit(self, target, stage_index=None, world_x=None, *, weapon="bullet"):
        """Apply $226D-$22D5 and begin the original character explosion."""
        kind=target.kind
        points={'ROCKET':50, 'FUEL':150, 'BASE':800}
        if kind=='MYSTERY':
            # The original chooses 100/200/300 using the Z80 refresh register.
            # We do not emulate the Z80 R register: deterministic placeholder.
            points_awarded=(100,100,200,300)[self.frames & 3]
        else:
            points_awarded=points[kind]
        self.award_points(points_awarded)
        if kind=='FUEL':
            self.hud.fuel=FuelTimer.refuel(self.hud.fuel)
        if stage_index is not None:
            self.ground_effects.spawn(
                stage_index,target,
                self.course.target_world_x(stage_index,target) if world_x is None else world_x,
                points_awarded)
        self.last_hit=(kind,points_awarded,self.frames)
        self.emit_audio('bomb_explosion' if weapon == 'bomb' else 'ground_explosion')
        if kind=='BASE':
            self.simulate_base_destroyed()

    def tick(self, stick: Joystick | None = None):
        if stick is None: stick = Joystick()
        self.last_input = stick
        # Bound audio queues during unattended/headless runs.
        self.audio_events.clear()
        # The original ground-object animation handler also runs during jet
        # explosions; effects continue to expire while the scenery is frozen.
        self.ground_effects.step()
        if self.run_state in ('dying','respawn_delay','game_over'):
            # $214A sets the scroll control to $FF, stopping the terrain.
            # $1825 cycles the landscape colour every fourth logical update.
            self.frames += 1
            self.bullets.fire_held = stick.fire
            self.bombs.bomb_held = stick.bomb
            if self.run_state == 'game_over':
                return
            if self.run_state == 'dying':
                # $1C98 still updates inflight entities while jet explodes;
                # terrain scroll has been latched off by $214A.
                self.rockets.move(scrolling=False)
                self.aliens.move(stage_flags=self.stage.flags,scrolling=False)
                if self.explosion_front:
                    self.explosion_front.step()
                if self.explosion_rear:
                    self.explosion_rear.step()
                if (self.frames & 3) == 0:
                    self.colour = (self.colour + 1) & 7
                self.state_timer -= 1
                if self.state_timer <= 0:
                    if self.remaining_lives <= 0:
                        self.run_state = 'game_over'
                        self.hud.game_in_play = False
                        self.state_timer = 0
                    else:
                        # $232C 100, $1157 50, $1083 32 and $10BF 10:
                        # staged one-player restart delays; the visuals are
                        # still simplified until MAME frame comparison.
                        self.run_state = 'respawn_delay'
                        self.state_timer = 100 + 50 + 32 + 10
            else:
                self.state_timer -= 1
                if self.state_timer <= 0:
                    self.restart_stage_after_death()
            return
        if self.run_state in ('blank','message'):
            self.bullets.fire_held=stick.fire
            self.bombs.bomb_held=stick.bomb
            self.frames += 1
            self.state_timer -= 1
            if self.state_timer <= 0:
                if self.run_state == 'blank':
                    self.run_state = 'message'
                    self.state_timer = 256  # 0 -> $FF decrement in $12C6
                else:
                    self.restart_loop()
            return

        # Original $1288 COOL_OFF continues to call $13CC (movement, fuel,
        # animations), $2036 (collisions), and $27C2 (landscape change).
        # Mission completion must not disable ship control or make it immune
        # to terrain, rockets, or any surviving ground objects.
        was_out_of_fuel = (self.run_state == 'out_of_fuel' or
                           (self.run_state == 'cool_off' and self.cool_off_out_of_fuel))
        old_scroll = self.speed.pixels
        # $2306 calls GAIN_POINTS_JUST_FOR_STAYING_ALIVE only from PLAY_GAME,
        # not during $1288 COOL_OFF, deaths, or the attract/cabinet scripts.
        # $139C tests TIMING_VARIABLE & $3F == 0 and queues +10 points.
        # Our logical frame counter supplies the 64-update cadence; the
        # hardware NMI phase remains a separate MAME-parity detail.
        survival_scoring = self.run_state in ('playing', 'out_of_fuel')
        super().tick()
        if survival_scoring and (self.frames & 0x3f) == 0:
            self.award_points(10)
        # $1C98 occurs after jet/ground movement and before collision $2036.
        # This frame's scroll event controls rocket X on the upright screen.
        did_scroll = self.speed.pixels != old_scroll
        if self.retry_stage is not None and self.speed.pixels >= self.course.starts[self.retry_stage]:
            self.retry_stage = None
        if was_out_of_fuel:
            # $17D4: no joystick, the unpowered ship descends 1 pixel/update
            # while the world continues to scroll, until raw X reaches $F0.
            self.jet.x = (self.jet.x + 1) & 0xff
            self.jet.other_x = (self.jet.other_x + 1) & 0xff
            self.jet.updates += 1
            if self.jet.x >= 0xf0:
                self.kill_player('out_of_fuel')
                return
        elif self.run_state in ('playing', 'cool_off'):
            if self.fuel_enabled:
                self.hud.fuel, depleted = self.fuel_timer.step(
                    self.hud.fuel, self.hud.missions_completed)
                if depleted:
                    # $1731: no joystick movement on the depletion frame.
                    # A mission cool-off keeps counting while the powerless
                    # jet falls, until either a crash or the completion screen.
                    if self.run_state == 'cool_off':
                        self.cool_off_out_of_fuel = True
                    else:
                        self.run_state = 'out_of_fuel'
                else:
                    self.jet.update(stick)
            else:
                self.jet.update(stick)
        # $1CE3/$1CFC: initialise or climb and drift with the scenery.
        self.rockets.move(scrolling=did_scroll)
        self.aliens.move(stage_flags=self.stage.flags,scrolling=did_scroll)
        # Terrain/ground collision is switched on by default; in the original
        # the per-frame collision handler runs after these movements.
        if self.check_ship_collisions():
            return
        # Arcade update order: $13CC moves bullets, $2036 checks collisions,
        # then $2563/$257F tests the *new* fire-button edge and spawns one.
        self.bombs.move(self.jet, scrolling=did_scroll)  # $1A30 before $16AA
        self.bullets.move()
        if self.run_state in ('playing','out_of_fuel','cool_off'):
            # $2036 order: ground-object bullets ($2217), then rockets ($22D6),
            # then terrain ($238F); bombs hit ground ($2434), rockets ($2494),
            # then terrain ($251E). UFO collision checks precede ground checks.
            # Source $2045: bullet-vs-UFO occurs before bullet-vs-ground.
            for _ in range(self.aliens.hit_bullets(self.bullets)):
                self.emit_audio('ufo_explosion')
                self.award_points(100)  # $21C2 UFO score
            for stage_index,target,world_x in self.bullets.ground_hits(
                    self.course,self.speed.pixels,self.hit_targets):
                self.register_ground_hit(target,stage_index,world_x)
            for _ in range(self.rockets.hit_bullets(self.bullets)):
                self.emit_audio('rocket_explosion')
                self.award_points(80)  # $2387: flying rocket, not 50-point ground rocket
            self.bullets.terrain_hits(self.course,self.speed.pixels)
            # Source $2051: bomb-vs-UFO before bomb-vs-ground; fireballs
            # deliberately have no projectile collision routine in the ROM.
            for _ in range(self.aliens.hit_bombs(self.bombs)):
                self.emit_audio('ufo_explosion')
                self.award_points(100)
            for stage_index,target,world_x in self.bombs.ground_hits(
                    self.course,self.speed.pixels,self.hit_targets):
                self.register_ground_hit(target,stage_index,world_x,weapon='bomb')
            for _ in range(self.rockets.hit_bombs(self.bombs)):
                self.emit_audio('rocket_explosion')
                self.award_points(80)  # $133F: bomb vs flying rocket
            for _ in range(self.bombs.terrain_hits(self.course,self.speed.pixels)):
                self.emit_audio('bomb_explosion')
            if self.run_state in ('playing','out_of_fuel'):
                if self.bullets.spawn_on_press(stick.fire,self.jet):
                    self.emit_audio('laser')
                if self.bombs.spawn_on_press(stick.bomb):
                    self.emit_audio('bomb_drop')
                # Original $2563 spawns flying enemies only after all collision
                # checks. Stage 1/4 only, once per 64 TIMING_VARIABLE ticks.
                if self.run_state == 'playing' and self.rockets_enabled:
                    self.rockets.launch(
                        stage_flags=self.stage.flags, timing=self.frames,
                        course=self.course, world_scroll=self.speed.pixels,
                        destroyed=self.hit_targets, stage_idx=self.stage_idx)
                # $2566 UFO, then $260C rockets, then $2674 fireballs. The
                # stage gates mean at most one of these spawn routines acts.
                if self.run_state == 'playing' and self.aliens_enabled:
                    reserved=sum(r.active or r.exploding for r in self.rockets.slots)
                    self.aliens.spawn(stage_flags=self.stage.flags,
                                      timing=self.frames,reserved_slots=reserved)
            elif self.run_state == 'cool_off':
                # $1288 deliberately does NOT call SPAWN_ENEMIES ($2563),
                # which also handles new player bullet and bomb presses.
                # Existing shots still move and collide; no new ones spawn.
                self.bullets.fire_held = stick.fire
                self.bombs.bomb_held = stick.bomb
        else:
            # Match the input latch when the shooting part of gameplay is off.
            self.bullets.fire_held=stick.fire
            self.bombs.bomb_held=stick.bomb
        # $2980: ambient scheduler also queues the low-fuel warning once per
        # 64 TIMING_VARIABLE ticks when CURRENT_PLAYER_FUEL < $50.
        if self.fuel_enabled and self.hud.fuel < 0x50 and not (self.frames & 0x3f):
            if self.run_state in ('playing','out_of_fuel','cool_off'):
                self.emit_audio('low_fuel')
        if self.run_state == 'cool_off':
            # Death (handled above) takes priority over this countdown.
            self.state_timer -= 1
            if self.state_timer <= 0:
                self.run_state = 'blank'
                self.state_timer = 5  # $1299 cool-off ends, before $12AB text
        elif self.auto_complete and self.at_base_end and self.base_visible:
            self.simulate_base_destroyed()

    def clearance(self):
        # The original $10A1 flat prefill is safe until a new stage actually
        # reaches the jet's nose; do not report old-stage collision boundaries.
        nose=self.speed.pixels+self.jet.screen_x+15
        if self.retry_stage is not None and nose < self.course.starts[self.retry_stage]:
            indices=tuple((nose-8*i)//8 for i in range(3))
            return True,(0x28,0xC9),indices
        return terrain_clearance_continuous(self.course, self.speed.pixels, self.jet)

    def render(self, surface):
        if self.run_state in ('blank', 'message'):
            surface.fill((0,0,0))
            if self.run_state == 'message':
                # Original text locations from ROM strings at $0528,$053A,$0556.
                # $12BD loads the ROM $0B89 per-column message palette table.
                def mission_text(address, message):
                    self.bank.text(surface, *character_xy(address), message,
                                   character_colour(address, mission_complete=True))
                from scramble_hud import character_xy, score_digits
                mission_text(0x4B40, '1UP')
                mission_text(0x4A80, 'HIGH SCORE')
                mission_text(0x4B81, score_digits(self.hud.score))
                mission_text(0x4A41, score_digits(self.hud.high_score))
                mission_text(0x4ACC, 'CONGRATULATIONS')
                mission_text(0x4B6E, 'YOU COMPLETED YOUR DUTIES')
                mission_text(0x4B70, 'GOOD LUCK NEXT TIME AGAIN')
            return
        if self.run_state == 'game_over':
            surface.fill((0, 0, 0))
            from scramble_hud import character_xy, score_digits
            self.bank.text(surface,*character_xy(0x4B40),'1UP',0)
            self.bank.text(surface,*character_xy(0x4A80),'HIGH SCORE',0)
            self.bank.text(surface,*character_xy(0x4B81),score_digits(self.hud.score),1)
            self.bank.text(surface,*character_xy(0x4A41),score_digits(self.hud.high_score),1)
            # $073E / $075F ROM strings: original character-RAM positions.
            # Both lines start in the same character column.  On the upright
            # screen PLAYER ONE is *above* GAME  OVER, not below it.
            self.bank.text(surface,*character_xy(0x4A94),
                           'PLAYER TWO' if self.player_number==2 else 'PLAYER ONE',6)
            self.bank.text(surface,*character_xy(0x4A96),'GAME  OVER',4)
            return
        super().render(surface)
        # Hit targets are suppressed by the terrain renderer; their original
        # four-character explosion/points frames are overlaid in world-space.
        self.ground_effects.render(self.bank,surface,self.speed.pixels,self.colour)
        # $10A1 restart strip: replaces the outgoing previous stage for a
        # normal, safe approach to the selected stage's first terrain record.
        if self.retry_stage is not None and self.run_state == 'playing':
            distance = self.course.starts[self.retry_stage] - self.speed.pixels
            if distance > 0:
                width = min(VIEW_WIDTH, distance)
                bg = (0,0,0x56) if self.colour in (4,5) else (0,0,0)
                self.pg.draw.rect(surface,bg,(0,40,width,200))
                from scroll_viewer import blink_state, star_visible
                if self.stage.flags & 0x1c == 0:
                    phase=blink_state(self.frames)
                    for x,y,rgb,flags in self.stars:
                        if x < width and star_visible(flags,phase):
                            surface.set_at((x,y),rgb)
                surface.blit(self._flat_strip(),(0,0),
                             self.pg.Rect(VIEW_WIDTH-width,0,width,VIEW_HEIGHT))
            else:
                self.retry_stage = None
        if self.run_state == 'respawn_delay':
            # Preserve HUD during the inter-life script; don't draw a jet.
            return
        if self.run_state == 'dying':
            if self.explosion_rear is not None:
                rear=self.explosion_rear.current
                self.bank.sprite(surface,*self.jet.rear_screen_xy,rear.code,rear.colour)
            if self.explosion_front is not None:
                front=self.explosion_front.current
                self.bank.sprite(surface,*self.jet.screen_xy,front.code,front.colour)
            return
        # Arcade $1FE3 (bullet registers) + Scramble's 1-pixel yellow pen.
        # Screen positions are calculated from original raw bullet X/Y bytes.
        for bullet in self.bullets.slots:
            if bullet.active:
                sx,sy=bullet.screen_xy
                if 0<=sx<VIEW_WIDTH and 40<=sy<240:
                    surface.set_at((sx,sy),(239,239,0))
        # $1F94: up to four in-flight rocket sprites (and explosions).
        # They share the landscape colour while active; explosion uses colour 6.
        self.rockets.render(self.bank,surface,self.colour)
        self.aliens.render(self.bank,surface)
        # Original $1F8A sprite slots: bombs behind the two-piece jet.
        for bomb in self.bombs.slots:
            if (bomb.active or bomb.exploding) and bomb.visible and bomb.animation is not None:
                f_bomb = bomb.animation.current
                self.bank.sprite(surface,*bomb.screen_xy,f_bomb.code,f_bomb.colour)
        rear = self.jet_rear_anim.current
        self.bank.sprite(surface, *self.jet.rear_screen_xy, rear.code, rear.colour)
        f = self.jet_anim.current
        self.bank.sprite(surface, *self.jet.screen_xy, f.code, f.colour)
        if self.show_clearance:
            ok, _, _ = self.clearance()
            if not ok:
                self.pg.draw.rect(surface, (255,65,65),
                                  (*self.jet.screen_xy,16,16), 1)
                self.pg.draw.rect(surface, (150,0,0), (0,240,VIEW_WIDTH,2))

def joystick_from_keys(pg, pressed, held_keys=None) -> Joystick:
    """Use BOTH keyboard-state polling and event-tracked keys for robust input.

    This is the main game input path, including after stage transitions.
    Arrows/WASD still feed original PlayerJet.update() every logical tick.
    """
    held_keys = held_keys or set()
    def down(key):
        return bool(pressed[key] or key in held_keys)
    return Joystick(
        up=down(pg.K_UP) or down(pg.K_w),
        down=down(pg.K_DOWN) or down(pg.K_s),
        left=down(pg.K_LEFT) or down(pg.K_a),
        right=down(pg.K_RIGHT) or down(pg.K_d),
        fire=down(pg.K_LCTRL) or down(pg.K_RCTRL) or down(pg.K_z),
        bomb=down(pg.K_LALT) or down(pg.K_RALT) or down(pg.K_x),
    )


def parse_input_script(text: str) -> list[Joystick]:
    """Frame-exact test input: R:30,U+R:20,N:10,L+D:10 (N=neutral)."""
    if not text:
        return []
    frames = []
    valid = {'U':'up','D':'down','L':'left','R':'right','F':'fire','B':'bomb','N':None}
    for part in text.split(','):
        keys, count = part.strip().upper().split(':', 1)
        n = int(count)
        if n <= 0 or n > 100000:
            raise ValueError('Each input duration must be between 1 and 100000 frames')
        parts = keys.split('+')
        if any(x not in valid for x in parts):
            raise ValueError(f'Bad input segment: {part!r}')
        args = {valid[k]:True for k in parts if valid[k]}
        frames.extend([Joystick(**args)]*n)
    return frames


def row(scene: PlayScene):
    ok, (ceil, floor), samples = scene.clearance()
    j=scene.jet
    s=scene.last_input
    return (scene.frames,scene.stage_idx+1,scene.speed.pixels,
            f'{j.x:02X}',f'{j.y:02X}',j.screen_x,j.screen_y,
            int(s.up),int(s.down),int(s.left),int(s.right),
            int(ok),ceil,floor,':'.join(map(str,samples)),
            scene.stage_scroll,scene.speed.pixels+VIEW_WIDTH,
            scene.run_state,scene.loop_number,int(s.fire),int(s.bomb),
            scene.bullets.active_count,scene.bullets.shots_fired,
            scene.bullets.hits,scene.hud.score,
            scene.bombs.active_count,scene.bombs.bombs_dropped,
            scene.bombs.hits,scene.bombs.terrain_impacts,
            scene.remaining_lives,scene.lives_lost,scene.death_reason or '',
            scene.hud.fuel,scene.fuel_timer.counter,len(scene.ground_effects.active),
            scene.rockets.active_count,scene.rockets.launches,
            scene.rockets.bullet_hits,scene.rockets.bomb_hits,scene.rockets.ship_hits,
            scene.aliens.active_count,scene.aliens.ufo_spawns,
            scene.aliens.fireball_spawns,scene.aliens.bullet_hits,
            scene.aliens.bomb_hits,scene.aliens.ship_hits)


TRACE_FIELDS=('frame','stage','scroll_px','player_x_hex','player_y_hex',
              'screen_x','screen_y','up','down','left','right',
              'clearance_advisory','ceiling_limit','floor_limit','sampled_columns',
              'stage_relative_px','producer_head_px','course_state','loop',
              'fire','bomb','bullets_active','shots_fired','targets_hit','score',
              'bombs_active','bombs_dropped','bomb_hits','bomb_terrain_hits',
              'reserve_lives','deaths','death_reason',
              'fuel','fuel_counter','ground_effects',
              'rockets_active','rockets_launched','rocket_bullet_hits',
              'rocket_bomb_hits','rocket_ship_hits',
              'aliens_active','ufo_spawns','fireball_spawns',
              'ufo_bullet_hits','ufo_bomb_hits','alien_ship_hits')


def run_headless(args):
    # No pygame or graphical display necessary, but use the SAME class as GUI.
    scene = PlayScene(None,None,read_stages(),args.stage-1,args.palette,args.latch,
                      auto_complete=args.auto_complete,lives=args.lives,
                      collisions=not args.no_collisions,
                      fuel_enabled=not args.no_fuel,
                      rockets_enabled=not args.no_rockets,
                      aliens_enabled=not args.no_aliens, enemy_seed=args.enemy_seed)
    scene.show_clearance=False
    scene.hud.score=args.hud_score
    scene.hud.high_score=args.hud_high_score
    scene.hud.fuel=args.hud_fuel
    # --lives controls actual game state; the reserve icon count is derived.
    script=parse_input_script(args.input)
    if args.trace:
        with open(args.trace,'w',newline='',encoding='utf-8') as fp:
            writer=csv.writer(fp);writer.writerow(TRACE_FIELDS)
            for f in range(args.headless):
                scene.tick(script[f] if f<len(script) else Joystick())
                writer.writerow(row(scene))
    else:
        for f in range(args.headless):
            scene.tick(script[f] if f<len(script) else Joystick())
    if args.trace: print('Wrote trace:',args.trace)
    print(f'After {scene.frames} frames: stage {scene.stage_idx+1}, '
          f'world scroll {scene.speed.pixels}/{scene.course.last_scroll}, '
          f'state {scene.run_state}, loop {scene.loop_number}, '
          f'jet X=${scene.jet.x:02X} Y=${scene.jet.y:02X}, '
          f'clearance={scene.clearance()[0]} (advisory), '
        f'shots={scene.bullets.shots_fired}, bullet hits={scene.bullets.hits}, '
        f'bombs={scene.bombs.bombs_dropped}, bomb hits={scene.bombs.hits}, score={scene.hud.score}, '
        f'landscape palette={scene.colour}, next colour at frame {scene.next_colour_tick}, '
        f'fuel={scene.hud.fuel}/255, reserves={scene.remaining_lives}, deaths={scene.lives_lost}, '
        f'death_reason={scene.death_reason}, '
        f'rockets_launched={scene.rockets.launches}, rockets_active={scene.rockets.active_count}, '
        f'rocket_hits={scene.rockets.bullet_hits+scene.rockets.bomb_hits}, '
        f'UFOs={scene.aliens.ufo_spawns}, fireballs={scene.aliens.fireball_spawns}, '
        f'aliens_active={scene.aliens.active_count}')

def main():
    ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--stage',type=int,default=1,choices=range(1,7))
    ap.add_argument('--palette',type=int,default=DEFAULT_LANDSCAPE_COLOUR,choices=range(8))
    ap.add_argument('--latch',type=int,default=0,choices=range(8))
    ap.add_argument('--auto-complete',action='store_true',
                    help='TEST ONLY: hit a visible BASE in the repeating final landscape; M is manual debug hit')
    ap.add_argument('--trace',type=Path,default=None,help='Save per-update CSV movement/scroll state')
    ap.add_argument('--headless',type=int,default=0,help='Run N deterministic updates without pygame')
    ap.add_argument('--skip-attract',action='store_true',help='Launch gameplay immediately (testing/convenience)')
    ap.add_argument('--no-grid',action='store_true',help='Skip initial hardware-style grid')
    ap.add_argument('--mute',action='store_true',help='Start with MAME-captured sound muted (F9 toggles)')
    ap.add_argument('--artwork',choices=('none','bezel'),default='none',
                    help='Optional user-supplied KONAMI arcade front-plate artwork')
    ap.add_argument('--debug',action='store_true',
                    help='Display the previous developer telemetry sidebar and enable stage/debug keys')
    ap.add_argument('--input',default='',help='Headless controls, e.g. R+F+B:1,R:30,N:1,F:1,B:1')
    ap.add_argument('--hud-score',type=int,default=0,help='HUD preview P1 score, not gameplay scoring')
    ap.add_argument('--hud-high-score',type=int,default=10000,help='HUD preview high score')
    ap.add_argument('--hud-fuel',type=int,default=255,help='HUD preview 0..255 fuel')
    ap.add_argument('--lives',type=int,default=3,choices=(3,4,5,6,255),
                    help='Starting lives (255 is the original free-play/test setting)')
    ap.add_argument('--no-collisions',action='store_true',
                    help='TEST ONLY: disable ship/terrain/ground-object collisions')
    ap.add_argument('--no-fuel',action='store_true',
                    help='TEST ONLY: disable fuel consumption for uninterrupted scrolling checks')
    ap.add_argument('--no-rockets',action='store_true',
                    help='TEST ONLY: keep ground rockets stationary while checking other systems')
    ap.add_argument('--no-aliens',action='store_true',
                    help='TEST ONLY: disable UFO/fireball spawning without changing other enemies')
    ap.add_argument('--enemy-seed',type=int,default=0,
                    help='0..127: repeatable native R-sample approximation (not MAME CPU R parity)')
    args=ap.parse_args()
    if not 0 <= args.hud_score <= 999999 or not 0 <= args.hud_high_score <= 999999:
        ap.error('--hud-score and --hud-high-score must be 0..999999')
    if not 0 <= args.hud_fuel <= 255:
        ap.error('--hud-fuel must be 0..255')
    if not 0 <= args.enemy_seed <= 127:
        ap.error('--enemy-seed must be 0..127')
    if args.headless:
        run_headless(args)
        return
    try:
        import pygame
    except ImportError:
        raise SystemExit('pygame-ce required: py -m pip install pygame-ce')
    # Use the WAV capture rate and mono mix, before SDL opens the audio device.
    try:
        pygame.mixer.pre_init(frequency=48000,size=-16,channels=1,buffer=512)
    except (AttributeError, pygame.error if hasattr(pygame,'error') else RuntimeError):
        # SDL audio may be unavailable (or a graphical test double may omit
        # mixer support). Audio is optional; video/gameplay must still work.
        pass
    pygame.init()
    bezel_enabled = args.artwork == 'bezel'
    fullscreen = False
    presenter = ScreenPresenter(pygame, ROOT, VIEW_WIDTH, VIEW_HEIGHT, debug=args.debug)
    window=pygame.display.set_mode(
        preferred_window_size(VIEW_WIDTH,VIEW_HEIGHT,bezel=bezel_enabled,debug=args.debug),
        pygame.RESIZABLE)
    pygame.display.set_caption('Scramble (Konami, 1981)')
    clock=pygame.time.Clock()
    font=pygame.font.SysFont('consolas',17)
    tiny=pygame.font.SysFont('consolas',14)
    large=pygame.font.SysFont('consolas',25,bold=True)
    bank=SpriteCharacterBank()
    audio=ScrambleAudio(pygame, muted=args.mute)
    scene=PlayScene(pygame, bank, read_stages(),args.stage-1,args.palette,args.latch,
                    auto_complete=args.auto_complete,lives=args.lives,
                    collisions=not args.no_collisions,
                    fuel_enabled=not args.no_fuel,
                    rockets_enabled=not args.no_rockets,
                    aliens_enabled=not args.no_aliens, enemy_seed=args.enemy_seed)
    scene.hud.score=args.hud_score
    scene.hud.high_score=args.hud_high_score
    scene.hud.fuel=args.hud_fuel
    # The attract state belongs to the GRAPHICAL run path, before advance() is
    # defined or called. Keeping this next to the scene prevents unbound
    # closure errors that headless-only tests otherwise miss.
    attract = (None if args.skip_attract or args.stage != 1
               else AttractMode(boot_grid=not args.no_grid))
    cabinet = None  # Paid single- or two-player cabinet session. Debug bypass remains direct.
    intro_stars = scramble_stars()
    wipe_snapshot = None  # frozen outgoing VRAM during the 32-strip MAME wipe
    # --lives controls actual game state; the reserve icon count is derived.
    logical=pygame.Surface((VIEW_WIDTH,VIEW_HEIGHT)).convert()
    accumulation=0.0
    paused=False
    screenshot_pending=False
    trace_fp=None
    trace_writer=None
    if args.trace:
        trace_fp=args.trace.open('w',newline='',encoding='utf-8')
        trace_writer=csv.writer(trace_fp);trace_writer.writerow(TRACE_FIELDS)

    def label(cv,txt,x,y,c=(215,224,240),face=None):
        cv.blit((face or font).render(str(txt),True,c),(x,y))

    def begin_cabinet_game(two_player=False):
        nonlocal attract, cabinet, scene, accumulation, paused, wipe_snapshot
        # Source $0F3B-$0F88: 1P costs one credit; 2P requires two.
        if attract is None: return False
        cost=2 if two_player else 1
        if attract.credits < cost: return False
        attract.credits -= cost
        high=max(10000,attract.high_score)
        first=scene
        first.player_number=1
        players=[first]
        if two_player:
            other=PlayScene(pygame,bank,read_stages(),0,args.palette,args.latch,
                            auto_complete=args.auto_complete,lives=args.lives,
                            collisions=not args.no_collisions,
                            fuel_enabled=not args.no_fuel,
                            rockets_enabled=not args.no_rockets,
                            aliens_enabled=not args.no_aliens,enemy_seed=args.enemy_seed)
            other.player_number=2
            players.append(other)
        cabinet=CabinetSession(players,ranking=attract.ranking)
        wipe_snapshot=None
        cabinet.high_score=high
        for player in cabinet.scenes: player.hud.high_score=high
        attract=None
        scene=cabinet.scene
        accumulation=0
        paused=False
        audio.stop()
        audio.play_effect('start_music')
        return True

    def advance(stick):
        nonlocal scene, attract, cabinet
        if attract is not None:
            attract.tick()
            audio.sync(scene=None,active=False)
        elif cabinet is not None:
            # The final PLAY_GAME tick may immediately switch the cabinet to
            # a death/inter-turn phase. Keep that tick's explosion sound.
            was_playing = cabinet.phase == 'playing'
            sound_scene = cabinet.scene
            cabinet.tick(stick)
            scene=cabinet.scene
            audio.sync(scene=sound_scene,active=was_playing)
            if trace_writer:trace_writer.writerow(row(scene))
            if cabinet.finished:
                # The arcade returns to the attract loop, retaining credits
                # inserted during play and the highest score in this session.
                credits=available_credits[0]
                attract=AttractMode(credits=credits,boot_grid=False)
                attract.high_score=max(10000,cabinet.high_score)
                attract.ranking=list(cabinet.ranking)
                if credits: attract.go_to('credit')
                cabinet=None
                audio.stop()
        else:
            scene.tick(stick)
            audio.sync(scene=scene,active=True)
            if trace_writer:trace_writer.writerow(row(scene))

    def reset_machine():
        """F3: reset the full arcade session, not just the active player's jet."""
        nonlocal scene, cabinet, attract, paused, accumulation, wipe_snapshot
        audio.stop()
        scene=PlayScene(pygame,bank,read_stages(),args.stage-1,args.palette,args.latch,
                        auto_complete=args.auto_complete,lives=args.lives,
                        collisions=not args.no_collisions,
                        fuel_enabled=not args.no_fuel,
                        rockets_enabled=not args.no_rockets,
                        aliens_enabled=not args.no_aliens,enemy_seed=args.enemy_seed)
        scene.hud.score=args.hud_score
        scene.hud.high_score=args.hud_high_score
        scene.hud.fuel=args.hud_fuel
        cabinet=None
        attract=(None if args.skip_attract or args.stage!=1
                 else AttractMode(boot_grid=not args.no_grid))
        available_credits[0]=0
        paused=False
        accumulation=0.0
        wipe_snapshot=None
        audio.set_paused(False)
        if attract is None:
            audio.play_effect('start_music')

    def draw_arcade():
        """Render exactly the original game picture, including cabinet transitions."""
        nonlocal wipe_snapshot
        if attract is not None:
            attract.render(logical,bank)
            return
        if cabinet is not None and cabinet.phase == 'ranking':
            cabinet.ranking_view.credits=available_credits[0]
            cabinet.ranking_view.render(logical,bank)
        elif cabinet is not None and cabinet.phase == 'wipe':
            if wipe_snapshot is None:
                scene.render(logical)
                draw_scoreboard(logical,bank,cabinet)
                wipe_snapshot=logical.copy()
            draw_turn_wipe(logical,wipe_snapshot,cabinet,intro_stars,
                           blink_state(cabinet.frame),star_visible,pygame)
        else:
            wipe_snapshot=None
            if cabinet is not None and cabinet.phase in ('intro','prepare'):
                render_turn_intro(logical,bank,cabinet,intro_stars,
                                  blink_state(cabinet.frame),star_visible,
                                  prepare=(cabinet.phase=='prepare'))
            else:
                scene.render(logical)
            if cabinet is not None:
                draw_scoreboard(logical,bank,cabinet,
                                intro=cabinet.phase in ('intro','prepare'))

    def save_screenshot():
        path=ROOT/'screenshots'
        path.mkdir(parents=True,exist_ok=True)
        dest=path/('Scramble_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.png')
        pygame.image.save(window,str(dest))
        print('Saved screenshot:',dest)

    if attract is None:
        audio.play_effect('start_music')
    running=True
    available_credits=[0]
    held_keys=set()
    try:
        while running:
            elapsed=min(clock.tick(120)/1000.0,0.08)
            for event in pygame.event.get():
                if event.type==pygame.QUIT:
                    running=False
                    continue
                if event.type==getattr(pygame,'WINDOWFOCUSLOST',-1):
                    held_keys.clear()
                    continue
                if event.type==pygame.KEYUP:
                    held_keys.discard(event.key)
                    continue
                if event.type != pygame.KEYDOWN:continue
                k=event.key
                held_keys.add(k)
                # Common cabinet controls work on ALL screens and are not
                # dependent on the original developer/test input shortcuts.
                if k == getattr(pygame,'K_F3',None):
                    reset_machine()
                    continue
                if k in (getattr(pygame,'K_F5',None), pygame.K_SPACE):
                    paused=not paused;accumulation=0
                    continue
                if k == getattr(pygame,'K_F12',None):
                    screenshot_pending=True
                    continue
                if k == getattr(pygame,'K_F8',None) and not args.debug:
                    bezel_enabled=not bezel_enabled
                    if not fullscreen:
                        window=pygame.display.set_mode(
                            preferred_window_size(VIEW_WIDTH,VIEW_HEIGHT,bezel=bezel_enabled),
                            pygame.RESIZABLE)
                    continue
                if k == getattr(pygame,'K_F11',None):
                    fullscreen=not fullscreen
                    if fullscreen:
                        window=pygame.display.set_mode((0,0),getattr(pygame,'FULLSCREEN',0))
                    else:
                        window=pygame.display.set_mode(
                            preferred_window_size(VIEW_WIDTH,VIEW_HEIGHT,
                                                  bezel=bezel_enabled,debug=args.debug),
                            pygame.RESIZABLE)
                    continue
                # F9 always works, including intro/attract, without changing
                # player input or simulation state.
                if k == getattr(pygame, 'K_F9', None):
                    audio.toggle_mute()
                    continue
                if attract is not None:
                    if k == pygame.K_ESCAPE:
                        running=False
                    elif k == pygame.K_5:
                        attract.insert_coin()
                        available_credits[0]=attract.credits
                    elif k in (pygame.K_1,pygame.K_2):
                        if begin_cabinet_game(two_player=(k==pygame.K_2)):
                            available_credits[0] -= (2 if k==pygame.K_2 else 1)
                    elif k == pygame.K_RETURN:
                        # Explicit convenience: enter starts free 1P test,
                        # unlike the genuine credit-gated 1/2 keys.
                        attract.credits=max(attract.credits,1)
                        begin_cabinet_game(False)
                    elif k == pygame.K_n and paused and args.debug:
                        advance(Joystick())
                    continue
                if k==pygame.K_ESCAPE:running=False
                elif k==pygame.K_5 and cabinet is not None:
                    available_credits[0]=min(99,available_credits[0]+1)
                elif args.debug and pygame.K_1<=k<=pygame.K_6:
                    scene.goto(k-pygame.K_1);scene.reset_jet();accumulation=0
                elif args.debug and k==pygame.K_PAGEUP:
                    scene.goto(scene.stage_idx-1);scene.reset_jet();accumulation=0
                elif args.debug and k==pygame.K_PAGEDOWN:
                    scene.goto(scene.stage_idx+1);scene.reset_jet();accumulation=0
                elif args.debug and k==pygame.K_r:
                    scene.new_game();accumulation=0
                elif k==pygame.K_RETURN and scene.run_state=='game_over':
                    scene.new_game();accumulation=0
                elif args.debug and k==pygame.K_m:
                    if scene.simulate_base_destroyed():
                        print('TEST: base hit simulated; original mission script started')
                elif args.debug and k==pygame.K_c:
                    scene.colour=(scene.colour+1)%8;scene.auto_colour=False
                elif args.debug and k==pygame.K_p:scene.auto_colour=not scene.auto_colour
                elif args.debug and k==pygame.K_h:scene.show_clearance=not scene.show_clearance
                elif args.debug and k==pygame.K_t:scene.show_targets=not scene.show_targets
                elif args.debug and k in (pygame.K_EQUALS,pygame.K_PLUS,pygame.K_KP_PLUS):
                    scene.speed.latch=max(0,scene.speed.latch-1);scene.speed.counter=0
                elif args.debug and k in (pygame.K_MINUS,pygame.K_KP_MINUS):
                    scene.speed.latch=min(7,scene.speed.latch+1);scene.speed.counter=0
                elif args.debug and k==pygame.K_n and paused:
                    advance(joystick_from_keys(pygame,pygame.key.get_pressed(),held_keys))
            audio.set_paused(paused)
            if not paused:
                accumulation+=elapsed
                steps=0
                while accumulation>=1.0/LOGICAL_FPS and steps<8:
                    advance(joystick_from_keys(pygame,pygame.key.get_pressed(),held_keys))
                    accumulation-=1.0/LOGICAL_FPS;steps+=1
            if not args.debug:
                draw_arcade()
                frame=presenter.compose(logical,bezel=bezel_enabled)
                presenter.present(window,frame)
                if screenshot_pending:
                    save_screenshot()
                    screenshot_pending=False
                pygame.display.flip()
                continue
            # Diagnostics are explicitly opt-in with --debug.
            frame=pygame.Surface((WIDTH,HEIGHT)).convert()
            frame.fill((17,20,32))
            if attract is not None:
                label(frame,'SCRAMBLE 1981  /  ORIGINAL ATTRACT PAGES',30,18,(244,246,255),large)
                attract.render(logical,bank)
                blown=pygame.transform.scale(logical,(VIEW_WIDTH*ZOOM,VIEW_HEIGHT*ZOOM))
                frame.blit(blown,(GAME_X,GAME_Y))
                pygame.draw.rect(frame,(108,111,134),(GAME_X-1,GAME_Y-1,VIEW_WIDTH*ZOOM+2,VIEW_HEIGHT*ZOOM+2),1)
                x=SIDEBAR
                label(frame,'ARCADE ATTRACT MODE',x,92,(255,219,118),large)
                label(frame,attract.page.replace('_',' ').upper(),x,134)
                label(frame,f'FRAME {attract.frames:5d}  CYCLE {attract.cycles}',x,169)
                label(frame,f'CREDITS {attract.credits}',x,207,(241,210,111),large)
                label(frame,'5: INSERT COIN',x,267,(165,230,177))
                label(frame,'1: ONE-PLAYER START (1 CREDIT)',x,301,(165,230,177))
                label(frame,'2: TWO-PLAYER START (2 CREDITS)',x,335,(165,230,177))
                label(frame,'ENTER: FREE ONE-PLAYER TEST',x,376,(213,187,172),tiny)
                label(frame,'DEMO PLAY: NEXT PHASE',x,406,(213,187,172),tiny)
                label(frame,'SPACE: PAUSE   N: STEP',x,473,(180,192,212),tiny)
                label(frame,'F12: SAVE ATTRACT PNG',x,501,(180,192,212),tiny)
                label(frame,'ROM-DERIVED TEXT, COLOURS, SPRITES',x,567,(149,200,244),tiny)
                label(frame,'BOOT GRID / TITLE / RANKING / POINTS',x,597,(149,200,244),tiny)
                label(frame,'F9: SOUND ON / OFF    MAME WAV AUDIO',x,660,(225,196,146),tiny)
                label(frame,'5: COIN   1: 1P   2: 2P   ENTER: TEST START   SPACE: PAUSE',30,831,(180,192,212),tiny)
                label(frame,'--skip-attract: DIRECT GAMEPLAY   --no-grid: SKIP POWER-ON GRID',30,853,(180,192,212),tiny)
                win_w,win_h=window.get_size()
                window.blit(pygame.transform.scale(frame,(win_w,win_h)),(0,0))
                if screenshot_pending:
                    save_screenshot()
                    screenshot_pending=False
                pygame.display.flip()
                continue
            label(frame,'SCRAMBLE 1981  /  CONTINUOUS LANDSCAPE COURSE',30,18,(244,246,255),large)
            if cabinet is not None and cabinet.phase == 'ranking':
                cabinet.ranking_view.credits=available_credits[0]
                cabinet.ranking_view.render(logical,bank)
            elif cabinet is not None and cabinet.phase == 'wipe':
                if wipe_snapshot is None:
                    # Save the outgoing hardware frame once. The Z80's
                    # $1A18 then clears one 8-pixel strip per logical frame.
                    scene.render(logical)
                    draw_scoreboard(logical,bank,cabinet)
                    wipe_snapshot=logical.copy()
                draw_turn_wipe(logical,wipe_snapshot,cabinet,intro_stars,
                               blink_state(cabinet.frame),star_visible,pygame)
            else:
                wipe_snapshot=None
                if cabinet is not None and cabinet.phase in ('intro','prepare'):
                    render_turn_intro(logical,bank,cabinet,intro_stars,
                                      blink_state(cabinet.frame),star_visible,
                                      prepare=(cabinet.phase=='prepare'))
                else:
                    # During the post-death $32/$64 wait, show the actual
                    # departing scene, NOT another PLAYER ONE/TWO intro.
                    scene.render(logical)
                if cabinet is not None:
                    draw_scoreboard(logical,bank,cabinet,
                                    intro=cabinet.phase in ('intro','prepare'))
            blown=pygame.transform.scale(logical,(VIEW_WIDTH*ZOOM,VIEW_HEIGHT*ZOOM))
            frame.blit(blown,(GAME_X,GAME_Y))
            pygame.draw.rect(frame,(108,111,134),(GAME_X-1,GAME_Y-1,VIEW_WIDTH*ZOOM+2,VIEW_HEIGHT*ZOOM+2),1)
            x=SIDEBAR
            label(frame,(f'PLAYER {cabinet.active+1} / {len(cabinet.scenes)}' if cabinet else f'STAGE {scene.stage_idx+1} / 6'),x,92,(255,219,118),large)
            label(frame,f'LOOP {scene.loop_number}   STATE {cabinet.phase if cabinet else scene.run_state}',x,165,(160,195,200),tiny)
            label(frame,scene.stage.name,x,132)
            label(frame,f'WORLD {scene.speed.pixels:5d}  BASE REPEATS AFTER {scene.course.last_scroll}',x,189)
            label(frame,f'SCROLL LATCH {scene.speed.latch}',x,221)
            label(frame,f'FRAMES {scene.frames:6d}',x,254)
            label(frame,f'RESERVES {scene.remaining_lives} / {scene.initial_lives}  DEATHS {scene.lives_lost}',x,286,(244,207,148),tiny)
            label(frame,f'FUEL {scene.hud.fuel:3d}/255  TICK {scene.fuel_timer.counter:2d}  FX {len(scene.ground_effects.active)}',x,424,(241,210,111),tiny)
            label(frame,'SHIP COORDINATES',x,310,(149,200,244))
            label(frame,f'Z80 X=${scene.jet.x:02X}  Y=${scene.jet.y:02X}',x,340)
            label(frame,f'SCREEN X={scene.jet.screen_x:3d} Y={scene.jet.screen_y:3d}',x,371)
            label(frame,f'FRAME #{scene.jet.updates:6d}',x,401)
            label(frame,'1 PIXEL/AXIS/UPDATE',x,445,(149,200,244))
            label(frame,'NO ACCELERATION / INERTIA',x,472,(149,200,244),tiny)
            ok,(ceil,floor),_=scene.clearance()
            label(frame,'MAZE GEOMETRY (ADVISORY)',x,522,(149,200,244))
            label(frame,f'CLEARANCE: {"CLEAR" if ok else "CONTACT"}',x,556,
                  (135,228,169) if ok else (255,115,105))
            label(frame,f'Ceiling ${ceil:02X}  Floor ${floor:02X}',x,584)
            label(frame,f'BULLETS {scene.bullets.active_count}/4  SHOTS {scene.bullets.shots_fired}',
                  x,617,(165,230,177),tiny)
            label(frame,f'HITS {scene.bullets.hits}   SCORE {scene.hud.score}',
                  x,641,(165,177,205),tiny)
            label(frame,f'BOMBS {scene.bombs.active_count}/2  DROPPED {scene.bombs.bombs_dropped}',
                  x,667,(165,230,177),tiny)
            label(frame,f'ROCKETS {scene.rockets.active_count}/4  LAUNCHED {scene.rockets.launches}',
                  x,693,(245,194,132),tiny)
            label(frame,f'UFO {scene.aliens.ufo_spawns}  FIREBALLS {scene.aliens.fireball_spawns}  LIVE {scene.aliens.active_count}',x,725,(235,192,148),tiny)
            label(frame,('BASE REPEATING  /  M = HIT' if scene.at_base_end and scene.run_state=='playing'
                         else scene.run_state.upper() if scene.run_state!='playing'
                         else 'PAUSED' if paused else 'LIVE 60.606 Hz'),x,765,
                  (250,208,107) if paused else (131,231,167),large)
            label(frame,'ARROWS / WASD: MOVE    CTRL / Z: FIRE    ALT / X: BOMB    SPACE: PAUSE',30,831,(180,192,212),tiny)
            label(frame,'1-6: SEEK (DEBUG)   R: RESET   F9: MUTE   F12: PNG',30,853,(180,192,212),tiny)
            win_w,win_h=window.get_size()
            window.blit(pygame.transform.scale(frame,(win_w,win_h)),(0,0))
            if screenshot_pending:
                save_screenshot()
                screenshot_pending=False
            pygame.display.flip()
    finally:
        if trace_fp:trace_fp.close()
        audio.stop()
        pygame.quit()


if __name__=='__main__':
    main()
