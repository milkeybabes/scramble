-- Scramble (1981) — MAME 0.282 sound capture, one sound per MAME process.
-- From Scott Tunstall's scramble.asm, routines $2855-$29B4.
-- The main CPU delivers sound command bytes through 8255 PPI #1:
--   write port A ($8200) = sound ID
--   pulse port B bit 3 low then high ($8201): Z80 audio interrupt.
-- This is NOT Z80 emulation; MAME's real audio program and AY-3-8910
-- emulation produce the WAV data. No ROM bytes or audio are bundled.
--
-- SETUP (Windows): use Capture_Scramble_Audio.bat, which supplies
-- SCRAMBLE_AUDIO_SOUND and SCRAMBLE_AUDIO_DIR environment variables.
-- Modes: one named sound per invocation to avoid sound carry-over.

local jobs = {
  laser             = {cmds={0x06},                     frames=105},
  bomb_drop         = {cmds={0x20},                     frames=125},
  rocket_explosion  = {cmds={0x03,0x13,0x14,0x15},      frames=155},
  ufo_explosion     = {cmds={0x04,0x13,0x14,0x15},      frames=155},
  ship_explosion    = {cmds={0x05,0x13,0x14,0x15},      frames=190},
  ground_explosion  = {cmds={0x01,0x13,0x14,0x15},      frames=155},
  bomb_explosion    = {cmds={0x30,0x02,0x13,0x14,0x15}, frames=180},
  start_music       = {cmds={0x09,0x0A},                frames=425},
  extra_life        = {cmds={0x08},                     frames=160},
  low_fuel          = {cmds={0x07},                     frames=165},
  default_ambient   = {cmds={0x12},                     frames=290, repeat_frames=64},
  ufo_ambient       = {cmds={0x21},                     frames=300, repeat_frames=128},
  fireball_ambient  = {cmds={0x22,0x23},                frames=300, repeat_frames=64},
  maze_ambient      = {cmds={0x24},                     frames=300, repeat_frames=64},
  unused_jingle_1   = {cmds={0x0B,0x0C,0x0D},           frames=400},
  unused_jingle_2   = {cmds={0x0E,0x0F},                frames=400},
}

local name = os.getenv("SCRAMBLE_AUDIO_SOUND") or "laser"
local output_dir = os.getenv("SCRAMBLE_AUDIO_DIR") or "captures"
local job = jobs[name]
if not job then
  error("Unknown SCRAMBLE_AUDIO_SOUND=" .. name)
end

local machine = manager.machine
local maincpu = assert(machine.devices[":maincpu"], "Scramble main CPU not found")
local mem = assert(maincpu.spaces["program"], "Scramble program memory not found")
local sound = assert(machine.sound, "MAME sound manager not found")
local path = output_dir .. "/" .. name .. ".wav"

local tick = 0
local start_tick = nil
local done = false
local prime_frames = 30 -- after -autoboot_delay (let the sound PPI settle)
local command_spacing = 2 -- queue the compound commands a couple of frames apart

local function send_command(code)
  -- Mirrors original EXEC_AUDIO_COMMAND at $28B2-$28C9.
  mem:write_u8(0x8200, code)
  mem:write_u8(0x8201, 0x00) -- sound IRQ bit 3 falling edge
  mem:write_u8(0x8201, 0x08) -- restore bit 3 high for next command
end

local function frame()
  if done then return end
  tick = tick + 1

  if not start_tick then
    if tick < prime_frames then return end
    local started = sound:start_recording(path)
    if not started then
      emu.print_error("Scramble audio: could not create WAV: " .. path)
      done = true
      machine:exit()
      return
    end
    start_tick = tick
    emu.print_info(string.format("Scramble audio: capturing %s (%d frames) -> %s", name, job.frames, path))
  end

  local frame_no = tick - start_tick
  -- A single effect may be a chain of commands, not a single byte.
  -- For repeated ambience, trigger the same chain on the source's cadence.
  local period = job.repeat_frames
  local in_sequence = period and (frame_no % period) or frame_no
  if (in_sequence % command_spacing) == 0 then
    local index = math.floor(in_sequence / command_spacing) + 1
    local code = job.cmds[index]
    if code then send_command(code) end
  end

  if frame_no >= job.frames then
    sound:stop_recording()
    done = true
    emu.print_info("Scramble audio: finished " .. name)
    machine:exit()
  end
end

-- Retain the notifier subscription; losing it to Lua GC would stop capturing.
_G.scramble_audio_frame_subscription = emu.add_machine_frame_notifier(frame)
_G.scramble_audio_stop_subscription = emu.add_machine_stop_notifier(function()
  if sound.recording then sound:stop_recording() end
end)
