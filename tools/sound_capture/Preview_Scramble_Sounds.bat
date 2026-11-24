@echo off
cd /d "%~dp0"
where py >nul 2>&1
if not errorlevel 1 (
    py -3 preview_sounds.py
) else (
    python preview_sounds.py
)
if errorlevel 1 pause
