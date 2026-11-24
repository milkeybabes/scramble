# Scramble (Konami, 1981) — Native Python arcade translation

A native Python graphics/game-logic translation study. The **normal run now scrolls continuously through all six original landscape streams**. There is no stage-end jump to a separate screenshot. The 8×8 character graphics, 16×16 sprites, 2-sprite jet, HUD and starfield use the earlier project's extracted, indexed assets. No Z80 instruction emulation or arcade video-hardware emulation.

**The complete core gameplay, two-player cabinet handling, ranking screens and MAME-recorded sound are playable.** The ship moves, fires, bombs, collides with scenery and ground objects, explodes, loses lives and retries the current stage. Player bullets and bombs can hit stationary rockets, fuel tanks, mystery targets and the base. Stationary ground targets now play the ROM character-based explosion or points-display sequences. Fuel drains during play; fuel tanks replenish it. Ground rockets now launch and fly upward in their original stages, can hit the jet, and can be shot/bombed for 80 points using original rocket explosion sprites. **Final frame-perfect MAME timing comparisons** remain outside the claimed scope. Original MAME-captured sound effects are now wired into pygame. Exact MAME collision timing is NOT yet claimed, since the 32-column landscape extent buffer has not been fully aligned.


## Final gameplay parity: survival points and bomb explosions (2026-11-25)

- **Survival points:** Source `$139C` called from PLAY_GAME `$2306` awards 10
  points when `TIMING_VARIABLE & $3F == 0`. The Python game now awards +10 on
  each 64th gameplay update, updating the high-score counter and 10,000-point
  extra-life threshold as usual. No survival points accrue during player death,
  GAME OVER, attract pages, or the 150-frame mission cool-off. The exact common
  Z80-NMI timer phase across player switches remains to be trace-matched.
- **Bomb explosion sprites:** On collision with terrain, a ground object, a
  flying rocket or a UFO, a bomb switches from its `$1AD8` flying animation to
  the ROM-derived `$1AF0` explosion (`$38,$39,$3A,$3B` with 9-update frame
  delays). The separate `$23` (35-update) explosion counter starts on the next
  update, and the sprite drifts with the scenery when scrolling. The slot
  remains occupied until the explosion completes, as required by the original
  `$26E3` allocation test. Normal bomb scoring, target explosions and audio
  triggers remain unchanged.

Both are covered by `py tools/check_survival_score_bomb_explosions.py` in
addition to the existing regression scripts.

## Finished-game display, Konami bezel and MAME-style function keys

Double-click **`Play Scramble.bat`** for the clean 224×256-pixel arcade
presentation (enlarged 3×, no developer telemetry/sidebar). Or double-click
**`Play Scramble - Konami Bezel.bat`** to play inside the optional 16:9
KONAMI front-plate artwork supplied by the user. Both use exactly the same
renderer and game simulation; artwork never affects gameplay or timing.

```bat
py scramble.py
py scramble.py --artwork bezel
py scramble.py --debug
```

**F3** resets the complete cabinet (including credit/high-score RAM), **F5**
pauses/resumes, **F9** mutes sound, **F11** toggles fullscreen and **F12** saves
an image of the displayed window to `screenshots/`. **F8** switches the bezel
on/off without restarting. `Space` is retained as a pause alias. There is no
AVI recorder in this version.

The development HUD and extra stage-seek controls are now available **only**
when explicitly launched with `--debug`. This includes keys 1–6 for stage
seek, PgUp/PgDn, M for the artificial base-hit test and the C/P/H/T and
scroll-latch debugging controls. Normal gameplay still uses 5=coin, 1=one
player and 2=two players on the title/credit screens. F12 never captures
or prints the development sidebar unless `--debug` was deliberately enabled.

The included `artwork/Konami_Scramble_Divemaster.png` is supplied artwork,
selected because it bears the Konami name (unlike some Stern-themed designs
in the user artwork ZIP). Do not redistribute it, the MAME-captured WAVs, or
other protected game material in a public GitHub release without appropriate
rights or permission.

## Original ten-place high-score ranking (new)

When the **last reserve life** has been lost, GAME OVER remains visible for
`$96` (150) logical updates. The original `$1346` routine then compares the
completed player's six-digit BCD score against the ten-entry score table:

- A strictly higher score is inserted in descending order, shifting lower
  entries down and dropping the previous tenth score.
- An *equal* score highlights its existing position without making an extra
  duplicate. A score below tenth place leaves the table unchanged.
- The qualifying row (rank and points) is displayed in **white** using the
  original `$130E` colour-attribute override; the other rows retain the ROM
  colours. The ranking appears for `$80` (128) updates, then the game waits
  another `$64` (100) updates before switching players or returning to attract.
- In two-player mode, each player gets their own GAME OVER and ranking phase,
  and both contribute to the same table. The latest ranking is carried back
  to the normal attract screen and through subsequent games in that run.

**The original 1981 Scramble does not request initials**: the player enters
this score table automatically. High scores are kept in running Python state,
not saved to disk, because the original table was reset by a power cycle.
The ranking is silent, as in the original; gameplay uses the MAME-captured sound library. Sources: `$130E`–`$139B`, `$12F0` and `$0283`.

## Cabinet credit/start and two-player hand-off

The regular **`Play Scramble.bat`** startup shows the power-on grid, title,
ranking and score table, and now responds to original-style credit input.
This update adds the ROM-defined paid-game selection and two-player alternation;
the autonomous attract demo is still **to be implemented**.

- **`5`** adds one credit, up to 99. The credit prompt reads **PUSH START BUTTON**
  and **ONE PLAYER ONLY** with one credit; after a second coin it reads
  **ONE OR TWO PLAYERS**. The bonus-life line uses ROM text, digits and the
  exact `$0B09` colour-attribute table.
- **`1`** spends one credit and starts 1-player mode. **`2`** spends two credits
  and starts 2-player mode. Insufficient credits do nothing.
- **`Enter`** remains a convenient *free 1P test shortcut*, not an authentic
  coin mechanism.
- Original **PLAYER ONE / PLAYER TWO** announcement screens precede turns.
  The first stage of each turn is safe until gameplay begins.
- Both player sessions independently retain stage, score, lives, mission count
  and fuel; they swap after a death while the other still has lives, then retry
  the relevant stage from its entrance.
- Both scores appear in the original ROM locations: P1 at `$4B81` and P2 at
  `$4921`. The active **1UP/2UP label** flashes using bit 4 of a logical
  16-frame timing cycle, matching `$0223` (score *digits* stay visible).
- Final GAME OVER for both players returns to the attract pages, preserving
  any credits inserted during play.

**2026-11-24 player-change correction:** The MAME AVI `scramble_2player.avi`
shows a progressive leftward wipe after death, not an immediate new intro.
The original `$1A18` routine writes the **blank `$10` character** to 32
character-RAM strips in 32 logical frames. This project now holds the
outgoing scene through the hand-off wait, renders an 8-pixel strip clear
per update (right-to-left in the rotated view), then introduces the
**incoming** player only. No stale PLAYER ONE/TWO overlay appears during the
wipe. Sources: P1 hand-off `$115F` = `$32` updates; P2 `$123C` = `$64`;
`$0356/$1039` introduction = `$96`; `$1083` flat-ground preparation = `$20`.
One-player retries use the same visible wipe/intro. Each player's score,
lives, current level and accumulated missions remain independent. The
background-colour value of the outgoing playfield can carry into the incoming
intro, including blue as seen in the MAME video.

The initial **power-on tile grid** now lasts about 160 frames before the
32-frame visible erase; the video has the grid for about 2.6 seconds.
This is a visual reconstruction of the startup character pattern, not Z80
CPU or video-hardware emulation; don't confuse blank character code `$10`
with writing literal zeroes to screen RAM.

**Accuracy notes:** The two-player state machine follows the original turn
semantics, and its wipe/announcement durations are source-based, but total
frame-perfect MAME hand-off parity is not yet claimed. The original hardware's cocktail cabinet screen
flip and full coinage DIP matrix are not in this build. The original autonomous
demo remains forthcoming; authentic captured sound is included. This release is compatible with the
existing direct-stage and headless test options.

## Start Scramble (Windows)

**Double-click `Play Scramble.bat`** (clean screen) or `Play Scramble - Konami Bezel.bat` (cabinet artwork) in the `Scramble` folder. It finds Python,
starts the game from the correct working directory (even if the path contains
spaces), and keeps the command window open if an error occurs.

Alternatively, run `py scramble.py`. This is the **only main entry point**;
`scramble_game.py` holds the gameplay code, and `scroll_viewer.py`,
`actor_viewer.py`, and `asset_viewer.py` are older developer-only viewers.
The scripts in `tools/` are regression tests and asset utilities.

If required, install the runtime dependency once:

```bat
py -m pip install pygame-ce
```

Extra commands or a start stage for testing can be passed to the same game
entry point: `py scramble.py --stage 5`,
`py scramble.py --lives 255` or `py scramble.py --headless 120`. The batch file also forwards command-line
arguments when launched from a command prompt.

## Game controls and testing

```bat
py -m pip install pygame-ce
py scramble.py
```

Use arrows or WASD for the original 1-pixel-per-axis jet movement; **Left/Right Ctrl or Z fires**, and **Left/Right Alt or X drops a bomb** (Space still pauses). Its position **is not reset when the landscape changes**. You can steer through the cave and the maze as before.

The six ROM-derived landscapes and their 16-pixel records are arranged in one world. The original `DRAW_FLAT_STRIP_OF_LAND` (`$10A1`) supplies a 224px start-of-game visible prefill, after which the first mountain section arrives naturally from the right.

At each ROM `$FF` stage marker (`$27C9`), the next landscape starts entering from the right while the outgoing landscape remains on-screen to the left. Stage/progress display follows the scenery being generated at the right-hand edge. Continuous scrolling, including the 8-pixel tile seams, happens with integer pixels and nearest-neighbour scaling.

### UFOs and fireballs (new)

The remaining airborne enemies are now available in the normal game using the
original Z80 spawn gates, signed movement tables and ROM sprite animations.

* **Stage 2 (UFOs)**: one spawn opportunity per 64 updates (`$25CC`), maximum
  four entries in the arcade `INFLIGHT_ENEMIES` pool. The initial raw coordinates
  are `X=$88` and `Y=(R & $0F)+9`. A UFO follows **74 signed ROM delta pairs**
  (`$1E2F`), looping through them. The sprite is code `$1A` in colour group 5.
  Shooting or bombing one awards **100 points**, followed by the original
  43-update explosion (colour 4, sprites `$38`–`$3B`).
* **Stage 3 (fireballs)**: one spawn opportunity per 16 updates (`$2674`), up
  to four entries. Initial raw coordinates are `X=(R & $7F)+$30`, `Y=$08`.
  Their movement is the original repeating `(0,+4)` raw-coordinate delta,
  corresponding to **four screen pixels to the left per update**. The
  six-frame fireball animation uses sprite codes `$35,$36,$37,$30,$37,$36`.
  Fireballs collide with the jet. **They are not shot down by bullets or
  bombs**, matching the absence of those collision handlers in the ROM.
* **Both** use the existing player explosion/lives/stage retry system. Spawns
  and animations are processed in the same update structure as the ground
  rockets. Stage changes release the old enemy type's native Python slots;
  rendering remains index-based, not hardware emulation.

**R register accuracy note:** Scramble reads the Z80 **refresh register** to
choose UFO and fireball starting positions. Its exact value depends on the
Z80 instruction fetch history, including interruptions and game inputs.
Our no-emulator translation **does not yet reproduce those exact R values**.
Instead a repeatable 7-bit seeded test sequence supplies plausible values
that obey the original bit masks and coordinate ranges. Attack **paths**, spawn
periods, score awards and collision inequalities are source-driven; *exact*
per-frame positions are not yet claimed to match MAME. Use the saved MAME AVI
for a later `R`-sequence/timing comparison.

Try either enemy stage directly:

```bat
py scramble.py --stage 2 --lives 255
py scramble.py --stage 3 --lives 255
py scramble.py --stage 2 --enemy-seed 17 --no-collisions --no-fuel
```

`--enemy-seed` accepts 0–127 (default 0) to repeat a Python test sequence.
Use `--no-aliens` only to disable the new handler for regression comparison.
`--trace filename.csv` now includes active alien/spawn/hit counts.

### Flying rockets (new)

Konami's original `TRY_SPAWN_INFLIGHT_ROCKET` routine (`$260C`) runs in
**stages 1 and 4 only** (`LANDSCAPE_FLAGS` 0 or 8). On every 64th update of
`TIMING_VARIABLE`, it looks for an eligible stationary rocket and an unused
slot in the **four-entry** `INFLIGHT_ENEMIES` array. The ground rocket is
removed and replaced by a flying sprite. The animation alternates the ROM
sprite codes `$1D/$1E` (delay `$10` each); the path at `$1D70` moves the
rocket **up one logical pixel per update**, while scrolling moves it left.

Its original source-byte proximity tests now handle player collisions,
forward-bullet hits and bomb hits. A flying rocket awards **80 points**, unlike
a stationary rocket (**50 points**), then uses the original `$38-$3B` sprite
explosion animation for **63 updates**. Both source-verified rocket and ship
explosions use their normal life-cycle and stage-retry logic.

**Left-edge clipping fix:** A rocket now continues partly off the left edge of
screen as its 16x16 sprite crosses x=0.  The sprite coordinate is kept signed
for Pygame clipping; only the source's own raw-byte end-of-flight condition
(`INFLIGHT_ENEMY.Y >= $F0` at `$1D11`) removes it, approximately x=-10 in
our display projection.  Previously a `% 256` conversion made it jump to x=255
and disappear at the edge.  No launch or movement timing has been changed.

The **start phase** of the original interrupt timing variable and the original
**eight-slot ground-object allocation** are not fully traced yet. This version
uses the existing indexed world targets: select among the first eight visible
active ground targets at each 64-update check. Positions are projected to the
original raw Z80 coordinate system, and collisions preserve the exact byte
inequalities. This is a grounded approximation, not yet frame-perfect MAME
launch selection. Original ship movement, weapons, scrolling and fuel remain
unchanged.

For uninterrupted stage testing:

```bat
py scramble.py --lives 255 --stage 4 --no-fuel --no-collisions
```

Use `--no-rockets` **only when testing the earlier stationary-target systems**.

### Player deaths, lives, and stage restart

The source's `$2113` three-column terrain extent check now activates life loss; the
ship can also collide with ground targets. The full two-part ship explosion
uses the ROM's `PLAYER_ONE_EXPLOSION_ANIMATION_TABLE` and
`PLAYER_TWO_EXPLOSION_ANIMATION_TABLE` (`$187E`/`$1896`) over **111 logical
updates** (`$1814`). Scrolling and controls stop while the jet explodes;
the source's landscape colour-flash behaviour runs every fourth update.
After a simplified inter-life sequence of **192 frames**, the player restarts
at **the beginning of the stage they died in**, with a fresh flat landscape
entrance and full fuel (the fuel countdown also restarts at five frames). The score, high score and completed-mission count
are preserved; projectiles and destroyed scenery are reset. Three deaths
with the default three starting lives lead to GAME OVER. Press **Enter** or
**R** to start a new game.

Use `--lives` to select **3, 4, 5, 6 or 255**:

```bat
py scramble.py --lives 3
py scramble.py --lives 255 --stage 5
```

`--lives 255` is the especially useful long-running test mode (254 reserve
lives on starting the first ship, with at most six reserve-ship icons shown
as in `$0908`). The original **Konami MAME parent DIP** has 3/4/5 and a
**Free Play** selection that initialises the lives byte to `$FF` (255).
`--lives 6` is an additional practical Python setting, **not a parent-ROM
DIP position**. The score bonus life at 10,000 points is implemented once,
per `$13A7`. The existing `--hud-score`, `--hud-high-score`, and `--hud-fuel`
are available for diagnostics; HUD lives now reflect actual game state.

**Accuracy caveat:** The original logical collision comparisons are used,
but this build still reads unwrapped terrain records instead of a fully
reconstructed original circular extent buffer. Ground-target collision boxes
are also a projection. These death thresholds should be compared with the
newly captured MAME recording before claiming maze-perfect parity. For
unattended rendering checks that deliberately fly into terrain, pass
`--no-collisions` as a **testing-only** override.

### What happens at the BASE?

The original game **only completes the mission when the BASE is destroyed**, not simply at the end of the scenery data. This is confirmed in the disassembly at `$22C9`/`$232F`. When the final BASE stream reaches its $FF terminator, the original game reloads the same BASE layout instead of stopping ($27E1–$27FC). If you miss the base, its scenery and target repeat indefinitely while fuel continues to drain. A **bullet or bomb that hits the base** now awards 800 points and starts the mission-complete sequence. Alternatively press **M** with the base visible to simulate a hit for testing. The bullet-vs-target coordinate projection still needs MAME comparison. After a successful hit the game continues to scroll during the original 150-frame cool-off, before displaying the completion messages. **The ship remains fully steerable during these 150 frames**: the original `$1288` routine still calls `$13CC` (`ANIMATION_AND_MOVEMENT`) and `$2036` (`COLLISION_DETECTION`). Buildings and terrain can still kill the player. If this happens, the impending completion is cancelled; the ship explodes and either retries stage 6 (if reserve lives remain) or goes to GAME OVER (if it was the last life). The score, including the 800 base points, remains. The base uses the ROM ground-object explosion sequence. Existing bullets/bombs continue to move and collide, but no *new* shots are spawned in the cool-off because the original script no longer calls `$2563` (`SPAWN_ENEMIES`). Fuel continues to run down, and the ship can still run out of fuel.  This correction is regression-tested by `py tools/check_base_cooloff_controls.py`.

The simplified mission script follows the original basic countdowns: 150 logical frames of cool-off (`$2338`, `$1288`), 5 frames until the message, then about 256 frames showing the original “CONGRATULATIONS / YOU COMPLETED YOUR DUTIES / GOOD LUCK NEXT TIME AGAIN” texts (`$12AB`, `$12C6`). Then it begins stage 1 again and increments the completed-mission flag. The original message colour assignments are now applied through the ROM attribute table; precise text placement and full turn management still need the MAME comparison pass. Scores now update when ground targets are shot; the original full scoring and mission logic still need final parity checks.

To watch repeated full loops without intervening, use the **explicitly non-arcade test shortcut**:

```bat
py scramble.py --auto-complete
```

That simulates the BASE hit when the scroll ends. It is off by default. Normal play requires an actual base hit (or the explicit M testing shortcut).

### Controls

| Key | Behaviour |
| --- | --- |
| Arrows / WASD | Move jet |
| Left/Right Ctrl / Z | Fire forward |
| Left/Right Alt / X | Drop bomb |
| `5` on attract screen | Insert coin |
| `1` / `2` on attract screen | Start one / two players (credits required) |
| `Enter` on attract screen | Free one-player convenience start |
| **F3** | Reset the cabinet to power-up/attract state |
| **F5** / Space | Pause / resume |
| **F8** | Toggle optional Konami bezel |
| **F9** | Sound mute / unmute |
| **F11** | Fullscreen / windowed |
| **F12** | Save displayed PNG to `screenshots/` |
| Esc | Quit |

Development-only: `--debug` restores the old diagnostic sidebar plus stage
seeking with 1–6 and PgUp/PgDn; R reset, M base-hit simulation, N single-step,
C/P palette controls, H clearance overlay, T target toggle and +/- scroll speed.
These extra functions do not interfere with normal arcade play.

### Original landscape colour sequence (first-stage fix)

The arcade does **not** begin on green! The opening is landscape colour 0
(pink ground on black). Code `$2810-$281F` advances in order
`0 → 2 → 3 → 4 → 5 → 6 → 7 → 0`, explicitly skipping group 1.
`$2842` enables the blue background **only** for groups 4 and 5 (when
stars/ceiling flags permit it). The ordinary launcher now defaults to
`--palette 0`; `--palette N` is retained only for manually starting a
particular colour during development.

`$2804` checks the 8-bit `TIMING_VARIABLE` for zero and changes colour on
**every second** counter event, so changes are 512 logical game frames apart.
Our earlier scenery viewer incorrectly used palette 4 and changed every 512
frames from startup; this is why it initially showed green terrain and a blue
sky instead of the pink opening.

The supplied original-game recording shows pink → blue at approximately
30.67 s, blue → purple at 39.10 s and purple → green at 47.57 s on the
video timeline. The active-play initial phase is calibrated to approximately
120 logical frames before the first change; subsequent changes are 512 frames
apart. The exact *initial* timer phase varies with the attract/startup state,
which is not yet modelled, so this first-change delay is video-matched, not
claimed to be a precise cold-boot MAME frame count. See
`py tools/check_palette_sequence.py` for automatic verification. The four stages
of the opening colour cycle are also previewed in
`data/opening_palette_sequence.png`. The original `$139C` survival-scoring
routine now grants **10 points every 64 logical PLAY_GAME updates**, including
when no objects are destroyed. The 64-update cadence is exact; our Python
per-player frame counter does not yet reproduce the Z80's continually running
NMI `TIMING_VARIABLE` phase during two-player hand-offs.

### Original per-column palette attributes

The original Konami video program does **not** switch the entire display
between eight palettes. `scramble_palette.py` preserves its two 32-byte colour
attribute tables from program ROM offsets `$0AE9` (gameplay HUD) and `$0B89`
(mission-complete display), independently verified byte-for-byte against the
Konami parent program ROM. In `SCROLL_AND_SPRITES` (`$1F44`), only raw video
columns **5–29** receive the changing `LANDSCAPE_COLOUR`; after the rotated
portrait display, these are the playfield's horizontal 8-pixel rows.

The HUD has fixed original colour indices: 1UP and HIGH SCORE labels 0,
score numerals 5, stage/progress headers 7, **FUEL label and fuel gauge 1
(yellow)**, remaining ships/mission flag 6. This remains true for every
landscape colour, including when the landscape is red, blue, pink or purple.
The ground fuel-tank object is different: it is composed of four character
tiles in the moving playfield, and legitimately inherits the changing
landscape palette. It may sometimes have less contrast against the scenery;
we deliberately do not recolour it artificially.

Completion text now uses its original row-dependent colours from `$0B89`:
`CONGRATULATIONS` orange/red, `YOU COMPLETED YOUR DUTIES` yellow, and
`GOOD LUCK NEXT TIME AGAIN` cyan. A reference sheet generated directly from
our exported ROM graphics is at `data/palette_attribute_preview.png`. Verify
these rules with `py tools/check_palette_attributes.py`.

### Player bullets, bombs and basic hits

Bullets follow the original Konami routines: `$257F` fires on the button **press edge** (hold does not autofire), `$25B5-$25C1` starts at raw `(jet.X+2, jet.Y-7)`, `$16AA-$16CF` moves three pixels per logical update and removes the bullet when its original Y coordinate falls below `$1F`. The 1-pixel yellow projectile is drawn using the original register-to-ROT90 coordinate mapping. Four active shot slots are provided (`$4500` through `$450B`).

Hits on fixed ground targets remove the bullet and the **one target** from the continuous world; no stage/sprite cache reset occurs. The score updates using original hit values: rocket 50, fuel 150 (+48 fuel units), base 800. Mystery target awards 100/200/300 points using a **temporary deterministic choice**; the Z80 refresh-register source of that choice is not yet reconstructed. A hit now draws the ROM-defined four-character explosion in place for 63 logical updates; mystery targets show the awarded 100/200/300-point characters for 79 updates. The effects remain attached to the scrolling landscape. Terrain blocks shots based on the original boundary inequalities, but the precise 32-entry terrain-extent circular-buffer phase needs a MAME timing check. **Terrain contacts can now kill the ship**, pending exact MAME extent-buffer alignment.

**Bombs ($26B1 / $1A30 / $1AFF):** The original game has two bomb slots and uses button 2 on a **new press** (holding does not autofire). On the following game update the bomb initialises to raw `(jet.X+4, jet.Y+8)`, then follows one pair of signed X/Y deltas per logical frame. The complete **203-pair path** was extracted and independently verified byte-for-byte against the Konami parent ROM (CRC32 `522AA357`); at runtime the game reads `data/bomb_path.json`, not arcade ROMs. The bomb's palette-6 sprite frames `$21-$25` come from the existing original graphics and animation tables. It curves forward, then falls almost vertically. A ground-target hit scores and refills fuel (for fuel tanks) using the same shared scoring routine as bullets; a base hit starts mission completion. Terrain and target hit-region alignment use the same current unwrapped-world approximations as the bullets, pending frame-by-frame MAME validation. **Ground targets now animate their original explosion frames.** The bomb itself still disappears on impact; separate bomb-explosion sprites will follow in a later phase.

### Fuel depletion and ground-target explosions

Normal gameplay now uses the original fuel countdown. Each stage **starts with
255 fuel units** (but fuel does **not** reset at ordinary landscape boundaries
on the same life). On each new life, `$1113` sets the first countdown to **five
updates**. After that, `$29B5` chooses **10**, **8** or **6** updates per fuel
unit according to completed mission loops (zero, one, or two-or-more loops),
not according to the current stage number. The HUD uses the existing 16-cell
ROM fuel display, so it updates automatically as fuel drains.

Destroying a **FUEL** tank with a bullet or bomb adds `$30` (**48**) fuel units,
with saturation at `$FF` (**255**) and awards **150 points**. It does not reset
the countdown. When the last unit is consumed, `$1731` enters the out-of-fuel
state: joystick control is lost, the plane descends one pixel per game update
while scenery scrolls, and it eventually explodes using the normal 111-frame
player death sequence. The next life starts at the same stage with a full tank.

The ground-target death handler now uses the existing original four-character
graphic groups. Rockets, fuel tanks and the base cycle through groups
`$38/$39/$3A/$3B` for **63 updates** (`$1964-$19C3`). Mystery targets
replace themselves with the appropriate `100`, `200`, or `300` point group
`$11/$12/$13` for **79 updates**. These are **character** animations, not
hardware sprites, and remain world-anchored while scrolling. Flying enemies
use their original sprite explosion routines. Player bombs now also explode
using ROM sprite codes `$38`–`$3B`, a **35-update** counter, and one-pixel
horizontal drift with scenery scrolling, following `$1AAC`–`$1AD5`. A bomb
continues to occupy its slot while exploding, so at most two bombs (including
explosions) can exist simultaneously.

For uninterrupted **developer-only** landscape tests, `--no-fuel` turns off
consumption. It is **not** arcade gameplay and is independent of the 255-lives
mode, which still uses fuel normally. Examples:

```bat
py scramble.py --lives 255 --stage 5
py scramble.py --headless 12000 --auto-complete --no-collisions --no-fuel
py tools/check_ground_explosions_fuel.py
```

For reproducible frame-exact tests without pygame, run:

```bat
py scramble.py --headless 90 --input "D:29,N:1,R+F+B:1,R:50,N:9" --trace shots_bombs_test.csv
py tools/check_player_fire.py
py tools/check_player_bombs.py
```

The game runs at the MAME driver's nominal **60.606 Hz**, with a default scroll latch of 0 (one pixel per update). Scroll latch/state at initial real arcade boot is **not yet fully verified**. We keep each stage's original terrain lengths, codes, positions and data. The star positions use MAME's Galaxian LFSR, and the four-phase blinking timer uses MAME's ~831ms phase.

### Data-only verification

```bat
py tools/check_course_flow.py
py tools/check_phase4.py
py tools/check_jet_stars.py
py tools/check_hud.py
py tools/check_phase3.py
```

Or run a full course and a dummy base hit in headless mode:

```bat
py scramble.py --headless 11700 --auto-complete --no-collisions --no-fuel --trace whole_course.csv
```

The trace records **global** scroll pixels, stage-relative scroll pixels, producer head position, player registers, input flags (including fire and bomb), active shots, bombs dropped, hits, score, loop number, reserve lives, deaths, cause of death, **fuel, fuel countdown, active ground effects**, and mission state. You can test the life-loss logic with `py tools/check_player_death.py`. The static seam preview is in `data/continuous_course_preview.png`. Render it again with `py tools/preview_course_flow.py` (Pillow only).

The developer-only `scroll_viewer.py` is still included as a *scenery-only* viewer. It now uses the same continuous course but does not emulate the mission script; it also repeats the final BASE landscape indefinitely, without running the mission script. The 1–6 keys remain test seeks only.

### Deliberate limitations

- Flying rockets, UFOs and fireballs now have their source-derived movement and collision handlers; the dedicated 35-update bomb explosion animation is also implemented. Exact final timing/refresh-register comparison remains. Ground-target and **player** explosions, fuel consumption/depletion/replenishment, lives, GAME OVER, 10,000-point extra life, scoring and stage retry are live.
- The stage-to-stage geometry and viewport are continuous, but **source/texture tile correctness does not prove frame-perfect timing**. In particular, the original hardware's 32-column circular video buffer and precise stage prefetch/scroll-start latency still need verification with MAME.
- Mission completion can be triggered by forward-bullet or bomb hit on the base (source `$2217-$22D5`, `$2434-$2491`) or debug M shortcut. The base uses the original ground explosion characters, while the player's bomb uses the original sprite explosion; the corresponding sound is present.
- Initial HUD scores/fuel may be set using `--hud-score`, `--hud-high-score`, and `--hud-fuel`; reserve lives now come exclusively from `--lives` and game state. `--no-collisions` and `--no-fuel` are explicit testing overrides.

## Credits and rights

**Konami** made the original 1981 arcade game, including code, graphics and sound. **Scott Tunstall** produced the exceptionally useful [annotated Z80 disassembly](https://github.com/ScottTunstall/Scramble/blob/main/scramble.asm). **MAME contributors** provide the Galaxian/Scramble video and timing reference: [MAME on GitHub](https://github.com/mamedev/mame).

This is a non-commercial educational reverse-engineering and AI-assisted native Python translation study, unaffiliated with those parties. Original rights remain with their respective owners. No MAME ROM ZIP is included. Any disputed copyrighted materials will be reviewed promptly and removed or amended if requested by the rights holder; this statement does not confer redistribution rights.

### Rebuilding bomb path data (optional)

The runtime ZIP already contains all the necessary data. For verifying the source-extraction process only, if you independently possess the original Konami parent ROM ZIP:

```bat
py tools/extract_bomb_path.py C:\roms\scramble.zip
```

This is a development utility, **not** a runtime dependency. It validates the original Konami parent file CRCs and the path byte CRC. Do not add ROM archives to the Python game's distribution.

### Game-over placement correction

`PLAYER ONE` and `GAME  OVER` now use the exact ROM text-addresses `$4A94` and `$4A96` (upright screen X=72, Y=160 and 176). Both strings occupy 10 tiles and are centred. The updated `tools/check_game_over_layout.py` prevents reverting to hand-positioned text.

## Attract Mode — Phase A (November 2026)

The launcher now opens with the short **power-on character grid**, followed by the
**PLAY / SCRAMBLE** title, **SCORE RANKING** (1ST–10TH), and **SCORE TABLE**
(six enemy/object graphics with progressively drawn point values). The pages
repeat while idle. The grid appears once per launch; the score-table text
comes in a character at a time, using the original ROM codes and screen
addresses. Colours come from the appropriate source-ROM 32-byte tables.

- Double-click `Play Scramble.bat`, or run `py scramble.py`.
- `5` inserts a credit on the preview screens; `1` starts one-player gameplay
  when a credit is available. `Enter` starts a **free single-player test game**
  without inserting a credit (temporary development convenience).
- `--skip-attract` immediately enters the existing game for routine testing.
- `--no-grid` skips only the startup grid, not the attract pages.
- `Space` pauses, `N` steps one frame while paused, and `F12` saves a screenshot.
- `py tools/check_attract_gui_startup.py` checks GUI startup, coin/start handoff,
  `--no-grid`, `--skip-attract`, and stage bypass with a lightweight window mock.
- `py tools/check_attract_pages.py` verifies the page states, source positions,
  sprite IDs, character-reveal sequence and credit counter.
- `py tools/preview_attract.py` generates the four-screen preview (Pillow needed).

**Scope note:** This is Phase A only. The power-on test grid is a visual
reconstruction; the full original boot-test timing has not yet been matched.
The page-counter timings are source-based but not yet frame-aligned against
MAME. The original autonomous demo and the full DIP coinage matrix remain later work; the 1P/2P start-and-turn system and MAME WAV audio have since been integrated.
The Phase A credit input and Enter shortcut are not claimed to reproduce
Konami's complete coin-handling code.

The 37 text records, four colour tables, six score-table sprites and six
11-character point lines were extracted from the parent `scramble` ROM once
into `data/attract_layout.json`. The runtime does **not** ship with, request,
or emulate the copyrighted ROM. The optional developer-only extractor is
`tools/export_attract_data.py` and requires the developer's own ROM ZIP.

## Authentic MAME sound playback (November 2026)

**This build includes 14 WAV groups captured from MAME by the user**, as opposed
 to a Python AY-3-8910 emulator or synthetic approximations. They are in the
`sounds/` directory, with duration/level/processing notes in
`sounds/capture_manifest.json`. Two normally unused jingles are archived in
`tools/sound_capture/unused/`, but are not played in the game.

The original source at `$2877`–`$29B4` drives the event mapping:

| Sound | Trigger in Python | Original command(s) |
|---|---|---|
| laser | New forward bullet | `$06` |
| bomb_drop | New bomb | `$20` |
| ground_explosion | Bullet destroys stationary target | `$01,$13,$14,$15` |
| bomb_explosion | Bomb hits object/ground | `$30,$02,$13,$14,$15` |
| rocket_explosion | Shot/bomb destroys launched rocket | `$03,$13,$14,$15` |
| ufo_explosion | Shot/bomb destroys UFO | `$04,$13,$14,$15` |
| ship_explosion | Jet collision or fuel-out death | `$05,$13,$14,$15` |
| extra_life | First 10,000-point bonus ship | `$08` |
| low_fuel | Fuel below `$50`, on source's 64-frame cadence | `$07` |
| start_music | 1P/2P game started | `$09,$0A` |
| four ambient tracks | Stage-specific ambient scheduler | `$12,$21,$22+$23,$24` |

The short effects have only their proven trailing silence trimmed. The bomb
drop has a *long descending tone*, so it was kept to its full capture length.
Ambient files are 4.7–4.8 s and use a 120 ms loop wrap crossfade to avoid
sharp seams. Sound levels are *conservative initial mix values*, not a claim
of exact MAME output gain. One-shot effects can overlap, and stage ambience
crossfades at stage changes. It stops for the attract/ranking/player-transition
screens, while the game-start melody plays over the introduction.

- **`Play Scramble.bat`** starts with audio enabled.
- **F9** toggles sound without changing gameplay or scores.
- **`py scramble.py --mute`** starts silently (F9 still works).
- If no sound device is available, the game continues normally and prints a
  warning; no audio backend is required for headless tests.
- `py tools/check_sound_events.py` tests sound event mapping, all WAV headers,
  mute/loop/pause operation using a mixer double (no SDL needed).

The original capture toolkit is retained under
[`tools/sound_capture/`](tools/sound_capture/README_AUDIO_CAPTURE.md) should
more samples be required. **The sound files belong to the original rights
holders; including them in a private local build does not imply permission to
publish them**. If you put the code on GitHub, exclude the `sounds/*.wav`
files (and unused WAVs) unless redistribution is authorised. No ROM is bundled.

**Still to verify by ear on Windows:** effect balances and the ambient-loop
crossfades. MAME's AY mixing and an in-game Python mixer are not necessarily
identical when several sounds compete for channels; final sound parity requires
an actual gameplay listening comparison, not only waveform inspection.

### Audition the WAVs without playing

Double-click **`tools/sound_capture/Preview_Scramble_Sounds.bat`**. Enter a
number 1–14 to hear a captured effect, then Enter to stop and choose another.
This lets you judge MAME fidelity and relative volumes before changing the mix.
