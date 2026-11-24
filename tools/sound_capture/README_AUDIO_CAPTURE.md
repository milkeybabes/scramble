# Scramble — MAME WAV capture toolkit (sound phase)

This folder contains **no sound files, ROMs or CPU emulation**. It asks the original Scramble sound CPU, via MAME, to play its real sound commands, recording the emulated output as WAVs. Nothing here changes the working Scramble Python game until the resulting audio has been checked.

Tested offline: Lua 5.4 syntax, the state-machine callback under a mocked MAME runtime, and the existing Python game regressions. **Not yet tested against a real Windows MAME 0.282 executable**; listen to the laser test before the full batch.

## Running it on Windows

1. Use your existing **original Scramble** MAME ROM set and MAME 0.282 (other recent releases should be similar). The set must run normally in MAME first.
2. If `mame.exe` isn't on your PATH, set its location once in a Command Prompt and launch the batch from that same prompt:
   ```bat
   set "MAME_EXE=W:\MAME\mame.exe"
   cd /d "W:\Python\Scamble\Scramble\tools\sound_capture"
   Capture_Laser_Test.bat
   ```
   Replace those example paths with your real locations. Alternatively add the `set "MAME_EXE=..."` line near the top of `Capture_Scramble_Audio.bat` so the batch can be double-clicked.
3. **First double-click `Capture_Laser_Test.bat`**. It should create `captures\laser.wav`. Play it. If the result is silent, send the displayed MAME output or the WAV rather than capturing everything.
4. If the laser sounds correct, double-click **`Capture_Scramble_Audio.bat`**. It starts a fresh MAME session for each of the 14 normal-game effects, capturing separate files in `captures\`.
5. Optional: `Capture_All_Including_Unused.bat` captures two additional, normally unused musical cues. You can ignore them for the playable Python game.
6. Zip the WAV files in `captures\` and send them back. The next step is to trim, normalise *only if needed*, establish seamless loops, and hook the 14 sound groups into pygame.

The batch runs from your MAME executable directory so its existing `mame.ini` ROM paths are respected. It uses `-autoboot_script`, `-autoboot_delay 3`, and `-nothrottle`. For capture, MAME itself exits at the end of each file.

**Important:** The script writes to the original parent-set PPI port addresses `$8200/$8201`. This is intended for `scramble`, not a bootleg or Super Cobra variant. It uses the documented MAME `manager.machine.sound:start_recording(...)` function; WAV filenames are absolute and generated from `SCRAMBLE_AUDIO_DIR`.

## Command catalogue

| WAV filename | Main Z80 command(s) | Original behaviour |
|---|---|---|
| laser.wav | 06 | Forward shot |
| bomb_drop.wav | 20 | Bomb release |
| rocket_explosion.wav | 03, 13, 14, 15 | Flying rocket destroyed |
| ufo_explosion.wav | 04, 13, 14, 15 | UFO destroyed |
| ship_explosion.wav | 05, 13, 14, 15 | Ship collision/death |
| ground_explosion.wav | 01, 13, 14, 15 | Generic ground target explosion |
| bomb_explosion.wav | 30, 02, 13, 14, 15 | Bomb/ground hit sequence |
| start_music.wav | 09, 0A | Two-voice game-start jingle |
| extra_life.wav | 08 | New ship awarded |
| low_fuel.wav | 07 | Low fuel warning |
| default_ambient.wav | 12 (every 64 frames) | Stage 1/4/default ambient |
| ufo_ambient.wav | 21 (every 128 frames) | Stage 2 UFO ambient |
| fireball_ambient.wav | 22, 23 (every 64 frames) | Stage 3 fireballs |
| maze_ambient.wav | 24 (every 64 frames) | Stage 5 maze |
| unused_jingle_1.wav | 0B, 0C, 0D | Unused music, curiosity only |
| unused_jingle_2.wav | 0E, 0F | Unused music, curiosity only |

The ambient repeat intervals are based on the source's `$2980` sound scheduler. Some commands sustain or overlap; the raw capture may not yet loop seamlessly. Compound commands are sent two video frames apart to mimic the main Z80's queued execution, rather than dumping the bytes instantaneously.

### Diagnostics

Run `py inspect_wavs.py` in this folder for durations, PCM peak/RMS, and warnings about silent files. A file can be nonzero and still contain the *wrong* sound, so listen to the laser smoke test.

If MAME errors or creates no WAV:
- Confirm `mame scramble` launches successfully using your ROM directory and your normal mame.ini.
- Confirm you can manually record audio with MAME `-wavwrite`.
- Check the MAME terminal text for `Scramble audio: capturing ...`; if no message, the Lua autoboot script didn't run.
- If the capture is silent, send **laser.wav**, your MAME version, and console output. The PPI interrupt bit or sound firmware timing may need a minor adjustment for your MAME build.

## Source references

- Scott Tunstall, `scramble.asm`: queue `$2855`, command dispatcher `$28B2`, commands `$28CE-$297D`, ambient scheduler `$2980-$29B4`.
- MAME original Scramble hardware: two AY-3-8910 sound generators and second Z80 sound CPU (MAME Galaxian/Scramble driver).
- MAME Lua documentation: `machine.sound:start_recording` / `stop_recording`, `emu.add_machine_frame_notifier`, and `space:write_u8`.

No copyrighted ROM or recorded sound is distributed by this toolkit. Only capture assets you are authorised to use and distribute.

## Captures returned and integrated (November 2026)

The user provided 16 valid 48 kHz, 16-bit mono WAV captures. The fourteen
in-game groups are now included in the parent project's `sounds/` directory,
with event playback in `scramble_audio.py`. Use
`py prepare_wavs.py --source captures` to re-run the WAV preparation step.
This trims only quiet tails and overlap-add crossfades the ambience loops;
see `sounds/capture_manifest.json` for per-file durations. To audition without
gameplay, double-click `Preview_Scramble_Sounds.bat`.

The two unused jingles are kept separately under `unused/`, never loaded by
normal play. Publishing these copyrighted game sounds requires permission.
