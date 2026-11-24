"""Prepare captured Scramble MAME WAVs (48 kHz mono PCM) for pygame playback.
One-shots are only trimmed at verified quiet tails; continuous tones are kept.
Ambient WAVs receive a short wrap crossfade to avoid playback seam clicks.
"""
from pathlib import Path
import numpy as np
import wave
import json

import argparse

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,default=Path(__file__).resolve().parent/'captures',
                    help='Folder of raw MAME WAV captures')
parser.add_argument('--output',type=Path,default=ROOT/'sounds',
                    help='Folder of playback-ready WAVs')
args=parser.parse_args()
SRC=args.source
DST=args.output
if not SRC.is_dir():
    parser.error(f'No capture directory: {SRC}')
DST.mkdir(parents=True,exist_ok=True)

# These recordings ran longer than the played sound. Do not remove musical tails.
LENGTHS = dict(laser=.54,extra_life=1.38,low_fuel=1.0,
               rocket_explosion=1.64,ufo_explosion=1.71,
               bomb_explosion=1.76,start_music=4.85)
AMBIENTS=('default_ambient','ufo_ambient','fireball_ambient','maze_ambient')
reports={}
for p in sorted(SRC.glob('*.wav')):
    name=p.stem
    if name.startswith('unused_'):continue
    with wave.open(str(p),'rb') as w:
        assert (w.getframerate(),w.getnchannels(),w.getsampwidth(),w.getcomptype())==(48000,1,2,'NONE'),p
        samples=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(np.float64)/32768.0
        rate=w.getframerate()
    raw_len=len(samples)/rate
    if name in AMBIENTS:
        # Standard overlap-add wrap: retain [N:L-N], blend the last N samples
        # into the beginning [0:N], then the next cycle starts at [N]. Thus
        # the output seam is between original samples N-1 and N, click-free.
        N=int(.12*rate)
        tail=samples[-N:];head=samples[:N]
        phase=np.linspace(0,1,N,endpoint=False)
        fade=np.sin(.5*np.pi*phase)**2
        blended=tail*(1-fade)+head*fade
        samples=np.concatenate((samples[N:-N],blended))
        operation='120 ms overlap-add wrap crossfade; loop'
    else:
        limit=LENGTHS.get(name,raw_len)
        samples=samples[:min(len(samples),round(limit*rate))]
        fade_samples=min(len(samples)//2,int(rate*.025))
        if fade_samples:
            ramp=np.linspace(1,0,fade_samples,endpoint=True)**1.25
            samples[-fade_samples:]*=ramp
        operation='quiet tail trimmed; 25 ms fade' if name in LENGTHS else 'original length; 25 ms end fade'
    output=np.round(np.clip(samples,-1,32767/32768)*32767).astype('<i2')
    out=DST/(name+'.wav')
    with wave.open(str(out),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(output.tobytes())
    reports[name]={'original_seconds':round(raw_len,3),'ready_seconds':round(len(samples)/rate,3),
                   'rms':round(float(np.sqrt(np.mean(samples**2))),4),
                   'peak':round(float(np.max(np.abs(samples))),4),
                   'processing':operation}
(DST/'capture_manifest.json').write_text(json.dumps(reports,indent=2)+'\n',encoding='utf-8')
for k,v in reports.items():print(f'{k:21s}: {v["original_seconds"]:5.2f} -> {v["ready_seconds"]:5.2f}s; peak={v["peak"]:5.3f}; {v["processing"]}')
