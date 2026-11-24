# Archived developer notes — Phase 3: Scrolling Landscapes

An educational project to reproduce **Konami's original Scramble gameplay algorithms in native Python** without running or emulating the Z80 or hardware video circuits.

This is a **running scenery demonstration**, not yet a complete playable game. It extends Phases 1 and 2 with all six ROM-derived landscapes, actual 8×8 edge/fill tiles, stationary ground targets made of 2×2 characters, the original colour-index cycling rule, and one-pixel scrolling on a fixed logical clock.

## Quick start (Windows / Python 3.14)

1. Unzip `Scramble_Phase3_Scrolling.zip`.
2. Open a command prompt in the `scramble_phase3` directory (the one with `scroll_viewer.py`).
3. Install pygame-ce if needed: `py -m pip install pygame-ce`
4. Run: `py scroll_viewer.py`

`py scroll_viewer.py --stage 5 --palette 4 --latch 1` starts in the maze stage with a scroll pixel every two logical frames. No arcade ROM ZIP is required to run the viewer; the package uses **pre-extracted tile atlases and landscape records**.

### Keyboard controls

| Keys | Action |
| --- | --- |
| `1`–`6`, `Page Up` / `Page Down` | Jump to any of the six stages |
| `Space` | Pause / resume |
| `N` | Advance a logical frame while paused |
| `Left` / `Right` | Move one terrain pixel while paused |
| `+` / `-` | Faster / slower scrolling (change frame latch) |
| `C` | Manually move to next of eight palettes |
| `P` | Toggle automatic colour cycling (every 512 logical ticks) |
| `T` | Toggle 2×2 ground targets |
| `J` | Toggle a reference-only animated player sprite |
| `R` | Restart current stage |
| `S` | Save the 224×256 pixel scene as `Scramble_Scroll_Screenshot.png` |
| `Esc` | Exit |

You can also run `py actor_viewer.py` and `py asset_viewer.py` from previous phases.

## The original program is wonderfully economical

Scott Tunstall's annotated Scramble disassembly documents the key routines:

- `$15A5`: scrolling control — the scroll counter increments when its latch countdown reaches zero, and **every 16th pixel** loads a new two-character-column landscape record.
- `$15CB`–`$16A5`: six- or nine-byte landscape records — two ground-edge character codes plus optional ceiling edges, and a target ID.
- `$0793`–`$084A`: write edge characters and repeat **rock character `$39`** or the brick patterns to fill the floor/ceiling. The map is original graphics data, not hand-drawn geometry.
- `$085E`: a ground target's group code is **multiplied by four** to get the first of four consecutive 8×8 character codes. The targets occupy 16×16 pixels, but do **not** consume hardware sprite slots.
- `$27C9`: the original stage-layout pointer table, containing 6 stages with 168, 112, 112, 168, 112 and 28 records respectively.
- `$2810`: landscape palette cycles through 0–7, skipping 1 on an increment from 0. The original palette-index behaviour is retained.

We translate those drawing and movement principles into a simple `StageMap` holding tile columns. pygame blits previously decoded 8×8 tile images; scroll offsets are plain pixel coordinates. No need to reproduce VRAM's circular addresses or a Z80 emulator.

**Native upright screen: 224×256 logical pixels**, obtained by rotating MAME's raw 256×224 visible raster. The display is nearest-neighbour scaled without smoothing.

## What's implemented, and what remains

**Already implemented:**
- All six original stage streams and layouts (including cave roofs, the maze and base).
- Two tile columns per record, original landscape edge character codes and brick/rock fills.
- Stationary rocket / fuel / mystery / base drawing, with 2×2 character composition.
- Base colour atlas selection and three-frame base animation from Phase 2.
- One-pixel scrolling with adjustable per-frame counter, fixed **60.606 Hz** logical update.
- MAME Galaxian/Scramble starfield **positions** derived from the same LFSR calculation. Star blink period is only representative at this phase.
- Native HUD/jet *reference graphics* for visual context (not genuine live game state).
- Six landscape positions displayed and visually inspected in a headless Pillow-based gallery (`data/scrolling_preview.png`).

**Not yet implemented:**
- Correct start-of-game, off-screen tile prefill and video-memory wrap/offset, exact scroll-latch initialization and stage-change timing validated against MAME.
- Authentic star blinking/enable timing; initial timing of colour changes may differ from MAME.
- Enemy motion/spawn, player controls and bullets, bombs, fuel consumption, collisions, scoring, lives and sound.
- Full frame-by-frame MAME input and state parity.

The HUD scores and fuel gauge are **display samples only**. The floating jet is a **visual reference** positioned in a nearby clear area, not a playable aircraft. The initial stage palette of **4** was picked to match the user's pink MAME screenshot; the exact game-start palette and its phase must be checked against a running MAME session.

### Tests, previews and extraction

`py tools/check_phase3.py` verifies stage streams, heights, tile indices, star positions, palette changes and scroll-counter behaviour. Requires only Pillow for image checks.

`py tools/preview_scrolling.py` regenerates `data/scrolling_preview.png` without pygame. This preview is a diagnostic composite of scenes at independently selected offsets, **not a recording of MAME or the running viewer**.

To re-extract source data from an original Konami parent ROM set:

`py tools/extract_assets.py --help`

The original ROMs are not bundled with this distribution. Extracted sprite/character atlases and landscape data are educational project assets; original game materials remain the intellectual property of their respective owners. If a rights holder raises a concern, we'll promptly review and amend or remove disputed materials. Such a notice is not a substitute for redistribution rights.

## References & credits

- **Konami**, creators of Scramble (1981), original game and artwork.
- **Scott Tunstall**, detailed reverse-engineering work: https://github.com/ScottTunstall/Scramble/blob/main/scramble.asm
- **MAME project**, original `scramble` driver graphics layout, palette and hardware specifications: https://github.com/mamedev/mame
- Previous project Phase 1/2: the asset decode, 8 palette atlases, 16×16 sprite collection, and ROM-defined animation definitions are retained.
