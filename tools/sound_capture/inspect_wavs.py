"""Inspect MAME-captured WAVs without third-party dependencies (Python 3.14)."""
from __future__ import annotations
from array import array
from pathlib import Path
import math
import struct
import sys
import wave


def stats(path: Path) -> tuple[float, float, float, int]:
    with wave.open(str(path), 'rb') as wav:
        rate, channels, sample_bytes = wav.getframerate(), wav.getnchannels(), wav.getsampwidth()
        frames = wav.getnframes()
        data = wav.readframes(frames)
    if frames == 0:
        return (0.0, 0.0, 0.0, rate)
    if sample_bytes == 2:
        vals = array('h')
        vals.frombytes(data)
        if sys.byteorder != 'little':
            vals.byteswap()
        peak = max((abs(s) for s in vals), default=0) / 32768.0
        rms = math.sqrt(sum(int(s)*int(s) for s in vals) / max(len(vals), 1)) / 32768.0
    elif sample_bytes == 1:
        vals = (b - 128 for b in data)
        xs = list(vals)
        peak = max((abs(v) for v in xs), default=0) / 128.0
        rms = math.sqrt(sum(v*v for v in xs) / max(len(xs), 1)) / 128.0
    else:
        # MAME normally records 16-bit PCM. Report length but avoid guessing amplitude.
        peak, rms = -1.0, -1.0
    return (frames / rate if rate else 0.0, peak, rms, rate)


def main() -> int:
    files = sorted((Path(__file__).parent / 'captures').glob('*.wav'))
    if not files:
        print('No WAVs found. Run Capture_Laser_Test.bat first.')
        return 1
    print(f'{"File":24} {"Seconds":>7} {"Peak":>8} {"RMS":>8} {"Hz":>8} Status')
    any_audible = False
    for path in files:
        try:
            seconds, peak, rms, rate = stats(path)
            audible = rms >= 0.0001
            any_audible |= audible
            status = 'OK' if audible else ('SILENT/VERY QUIET' if peak >= 0 else 'UNSUPPORTED FORMAT')
            print(f'{path.name:24} {seconds:7.2f} {peak:8.4f} {rms:8.4f} {rate:8} {status}')
        except Exception as exc:
            print(f'{path.name:24} ERROR {exc}')
    if not any_audible:
        print('\nNo audible samples detected. Check MAME startup, sound, or PPI command injection.')
        return 2
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
