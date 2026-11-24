"""Tests real event-to-capture mapping without needing an SDL audio device.

Also verifies all packaged WAV headers and exercises a pygame.mixer test
implementation, so GUI audio integration isn't tested only by headless stubs.
"""
from __future__ import annotations
from pathlib import Path
import wave
import sys
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scramble_game import PlayScene
from scramble_scroll import read_stages
from scramble_player import Joystick
from scramble_audio import ScrambleAudio, SOUNDS_DIR, ONESHOTS, AMBIENTS, stage_ambient

for name in ONESHOTS+AMBIENTS:
    p=SOUNDS_DIR/(name+'.wav')
    assert p.is_file(),p
    with wave.open(str(p),'rb') as w:
        assert w.getframerate()==48000 and w.getnchannels()==1 and w.getsampwidth()==2
        assert 0.3 < w.getnframes()/w.getframerate() < 6

stages=read_stages()
scene=PlayScene(None,None,stages,collisions=False,rockets_enabled=False,aliens_enabled=False)
scene.tick(Joystick(fire=True,bomb=True))
assert scene.audio_events==['laser','bomb_drop'],scene.audio_events
scene.tick(Joystick(fire=True,bomb=True))
assert not scene.audio_events,scene.audio_events
scene.tick(Joystick())
scene.tick(Joystick(fire=True,bomb=True))
assert scene.audio_events==['laser','bomb_drop']
scene.kill_player('terrain')
assert scene.audio_events[-1]=='ship_explosion'

scene=PlayScene(None,None,stages,collisions=False)
obj=next(t for t in stages[0].targets if t.kind=='FUEL')
scene.register_ground_hit(obj,0,weapon='bomb')
assert scene.audio_events[-1]=='bomb_explosion'
obj=next(t for t in stages[0].targets if t.kind=='ROCKET')
scene.register_ground_hit(obj,0,weapon='bullet')
assert scene.audio_events[-1]=='ground_explosion'
scene.award_points(10000)
assert 'extra_life' in scene.audio_events

scene=PlayScene(None,None,stages,collisions=False,rockets_enabled=False,aliens_enabled=False,lives=255)
scene.hud.fuel=79
for _ in range(64):scene.tick(Joystick())
assert 'low_fuel' in scene.audio_events,scene.audio_events
assert stage_ambient(0)=='default_ambient'
assert stage_ambient(2)=='ufo_ambient'
assert stage_ambient(1)=='fireball_ambient'
assert stage_ambient(4)=='maze_ambient'
assert stage_ambient(8)=='default_ambient'

class FakeSound:
    def __init__(self,path): self.name=Path(path).stem; self.volume=None
    def set_volume(self,value):self.volume=value
class FakeChannel:
    def __init__(self,n):self.n=n;self.played=[];self.fades=[];self.busy=False
    def play(self,sound,**kwargs):self.played.append((sound.name,kwargs));self.busy=True
    def fadeout(self,ms):self.fades.append(ms);self.busy=False
    def get_busy(self):return self.busy
class FakeMixer:
    def __init__(self):self.channels={};self.stopped=False;self.paused=False;self.initialised=False;self.number=16
    def get_init(self):return self.initialised
    def init(self,**kwargs):self.initialised=True
    def set_num_channels(self,n):self.number=n
    def get_num_channels(self):return self.number
    def Sound(self,path):return FakeSound(path)
    def Channel(self,n):return self.channels.setdefault(n,FakeChannel(n))
    def stop(self):self.stopped=True
    def pause(self):self.paused=True
    def unpause(self):self.paused=False
mix=FakeMixer();pg=SimpleNamespace(mixer=mix)
audio=ScrambleAudio(pg)
assert audio.enabled and len(audio.sounds)==14
audio.play_effect('start_music')
assert mix.Channel(2).played[-1][0]=='start_music'
audio.play_effect('laser')
assert mix.Channel(3).played[-1][0]=='laser'
scene=PlayScene(None,None,stages,collisions=False)
scene.audio_events=['laser']
audio.sync(scene=scene,active=True)
assert not scene.audio_events
assert any(t[0]=='default_ambient' for t in mix.Channel(1).played)
assert any(t[0]=='laser' for t in mix.Channel(4).played)
scene.goto(1)
scene.audio_events=['rocket_explosion']
audio.sync(scene=scene,active=True)
assert audio.ambient_name=='ufo_ambient'
assert mix.Channel(1).fades and mix.Channel(0).played[-1][0]=='ufo_ambient'
assert mix.Channel(5).played[-1][0]=='rocket_explosion'
audio.toggle_mute()
assert mix.stopped
scene.audio_events=['ship_explosion']
audio.sync(scene=scene,active=True)
assert not scene.audio_events and audio.ambient_name is None
audio.toggle_mute()
audio.sync(scene=scene,active=True)
assert audio.ambient_name=='ufo_ambient'
audio.set_paused(True)
assert mix.paused
audio.set_paused(False)
assert not mix.paused
audio.sync(scene=scene,active=False)
assert audio.ambient_name is None
print('PASS: 14 original WAVs; firing/bombs/explosions/lives/low-fuel events;')
print('      MAME ambient flags, two-channel loop fades, pygame mixer channels, F9 mute, pause.')
