"""Scramble (1981) MAME-captured sound playback. No sound CPU emulation.

All WAV assets were recorded from the original sound CPU and AY-3-8910s by
MAME. Sound commands in the main Z80 source are mapped to gameplay events.
The GUI owns this mixer; the native game logic remains pygame-free/headless.

F9 mutes/unmutes; --mute starts muted. Missing mixer or WAVs never crash play.
"""
from __future__ import annotations
from pathlib import Path

SOUNDS_DIR = Path(__file__).resolve().parent / 'sounds'

ONESHOTS = (
    'laser', 'bomb_drop', 'rocket_explosion', 'ufo_explosion',
    'ship_explosion', 'ground_explosion', 'bomb_explosion',
    'extra_life', 'low_fuel', 'start_music',
)
AMBIENTS = ('default_ambient', 'ufo_ambient', 'fireball_ambient', 'maze_ambient')
VOLUME = {
    'laser': .95, 'bomb_drop': .70,
    'rocket_explosion': .80, 'ufo_explosion': .80,
    'ship_explosion': .75, 'ground_explosion': .78,
    'bomb_explosion': .72, 'extra_life': .80,
    'low_fuel': .55, 'start_music': .78,
    'default_ambient': .35, 'ufo_ambient': .36,
    'fireball_ambient': .72, 'maze_ambient': .40,
}


def stage_ambient(stage_flags: int) -> str:
    """Z80 $2980-$29B4: by LANDSCAPE_FLAGS, not stage number."""
    return {
        0: 'default_ambient', 8: 'default_ambient',
        2: 'ufo_ambient', 1: 'fireball_ambient', 4: 'maze_ambient',
    }.get(stage_flags, 'default_ambient')


class ScrambleAudio:
    """Mix one-shot effects while independently looping stage ambience.

    Two ambience channels allow crossfades. The sound-driver layer is optional
    and deliberately does not influence any gameplay update or input timing.
    """
    def __init__(self, pg, *, muted: bool = False, sounds_dir: Path = SOUNDS_DIR):
        self.pg = pg
        self.muted = bool(muted)
        self.enabled = False
        self.paused = False
        self.sounds = {}
        self.ambient_name = None
        self.ambient_index = 0
        self.next_effect_channel = 3
        self.last_status = 'Audio disabled'
        try:
            mixer = pg.mixer
            if not mixer.get_init():
                mixer.init(frequency=48000, size=-16, channels=1, buffer=512)
            mixer.set_num_channels(max(16, mixer.get_num_channels()))
            for name in ONESHOTS + AMBIENTS:
                path = sounds_dir / (name + '.wav')
                if not path.is_file():
                    raise FileNotFoundError(path)
                snd = mixer.Sound(str(path))
                snd.set_volume(VOLUME.get(name, .75))
                self.sounds[name] = snd
            self.enabled = True
            self.last_status = f'Authentic MAME WAV audio: {len(self.sounds)} sounds'
        except Exception as exc:
            self.enabled = False
            self.sounds.clear()
            self.last_status = 'Sound unavailable: ' + str(exc)
            print('Scramble:',self.last_status)
        if self.enabled:
            print('Scramble:', self.last_status, '(F9: mute/unmute)')

    def _channel(self, n: int):
        return self.pg.mixer.Channel(n)

    def play_effect(self, name: str):
        if not self.enabled or self.muted or self.paused:
            return
        snd = self.sounds.get(name)
        if snd is None:
            return
        if name == 'start_music':
            self._channel(2).play(snd)
            return
        # Keep sound effects off the reserved ambience/music channels; allow
        # overlapping shots and explosions without aborting the looping hum.
        candidates = list(range(3, min(16, self.pg.mixer.get_num_channels())))
        if not candidates:
            return
        start = self.next_effect_channel
        ordered = [c for c in candidates if c >= start] + [c for c in candidates if c < start]
        channel_number = next((c for c in ordered if not self._channel(c).get_busy()), ordered[0])
        self.next_effect_channel = 3 + (channel_number - 2) % len(candidates)
        self._channel(channel_number).play(snd)

    def _set_ambient(self, target: str | None):
        if target == self.ambient_name:
            return
        old_index = self.ambient_index
        next_index = 1 - old_index
        if self.enabled:
            if self.ambient_name is not None:
                self._channel(old_index).fadeout(160)
            if target and not self.muted and not self.paused:
                snd=self.sounds.get(target)
                if snd is not None:
                    self._channel(next_index).play(snd, loops=-1, fade_ms=160)
        self.ambient_index=next_index
        self.ambient_name=target

    def sync(self, *, scene=None, active: bool = False):
        """Once per logical frame, after that frame's game update."""
        events=[]
        if scene is not None:
            events=list(getattr(scene, 'audio_events', ()))
            # Consume events even when sound is muted or the audio device is
            # missing; no events can accidentally play after switching on.
            scene.audio_events.clear()
        target=None
        if active and scene is not None and scene.run_state in (
                'playing','out_of_fuel','cool_off'):
            target=stage_ambient(scene.stage.flags)
        self._set_ambient(target if not self.muted else None)
        if active:
            for name in events:
                self.play_effect(name)

    def toggle_mute(self):
        self.muted = not self.muted
        if self.enabled and self.muted:
            self.pg.mixer.stop()
        self.ambient_name=None
        print('Scramble sound:', 'MUTED' if self.muted else 'ON')
        return self.muted

    def set_paused(self, paused: bool):
        paused=bool(paused)
        if paused == self.paused:
            return
        self.paused=paused
        if self.enabled:
            (self.pg.mixer.pause if paused else self.pg.mixer.unpause)()

    def stop(self):
        if self.enabled:
            self.pg.mixer.stop()
        self.ambient_name=None

