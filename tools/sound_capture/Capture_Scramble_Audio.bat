@echo off
setlocal EnableExtensions EnableDelayedExpansion
pushd "%~dp0"
if not exist "captures" mkdir "captures"

rem Override this before running, e.g. set MAME_EXE=W:\MAME\mame.exe
if not defined MAME_EXE (
  for /f "delims=" %%M in ('where mame.exe 2^>nul') do (
    if not defined MAME_EXE set "MAME_EXE=%%M"
  )
)
if not defined MAME_EXE (
  echo MAME executable not found in PATH.
  echo Set MAME_EXE to the full path of your mame.exe, e.g.:
  echo   set "MAME_EXE=W:\MAME\mame.exe"
  echo Then rerun this BAT file from that Command Prompt.
  popd
  pause
  exit /b 1
)
if not exist "!MAME_EXE!" (
  echo Could not find "!MAME_EXE!"
  popd
  pause
  exit /b 1
)

set "SCRAMBLE_AUDIO_DIR=%~dp0captures"
set "SCRIPT=%~dp0scramble_capture.lua"
if "%~1"=="" (
  set "SOUNDS=laser bomb_drop rocket_explosion ufo_explosion ship_explosion ground_explosion bomb_explosion start_music extra_life low_fuel default_ambient ufo_ambient fireball_ambient maze_ambient"
) else if /i "%~1"=="all" (
  set "SOUNDS=laser bomb_drop rocket_explosion ufo_explosion ship_explosion ground_explosion bomb_explosion start_music extra_life low_fuel default_ambient ufo_ambient fireball_ambient maze_ambient unused_jingle_1 unused_jingle_2"
) else (
  set "SOUNDS=%~1"
)

for %%M in ("!MAME_EXE!") do set "MAME_DIR=%%~dpM"
pushd "!MAME_DIR!"
for %%S in (!SOUNDS!) do (
  set "SCRAMBLE_AUDIO_SOUND=%%S"
  echo.
  echo ===== Capturing %%S =====
  "!MAME_EXE!" scramble -window -skip_gameinfo -autoboot_script "!SCRIPT!" -autoboot_delay 3 -nothrottle
  if errorlevel 1 (
    echo.
    echo MAME failed on sound %%S; check ROM path and the Lua error above.
    popd
    popd
    pause
    exit /b 1
  )
)
popd

echo.
echo Finished. Inspect the files in captures\ and send them back for integration.
where py.exe >nul 2>nul && py inspect_wavs.py
popd
pause
