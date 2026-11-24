@echo off
setlocal EnableExtensions
rem Always run from the directory containing this batch file.
cd /d "%~dp0"
if errorlevel 1 (
    echo Cannot open the Scramble folder.
    pause
    exit /b 1
)

rem Prefer the Windows Python launcher, but support normal Python installs too.
where py >nul 2>&1
if not errorlevel 1 (
    py -3 scramble.py %*
) else (
    where python >nul 2>&1
    if not errorlevel 1 (
        python scramble.py %*
    ) else (
        echo Python 3 is not installed or is not available in PATH.
        echo Install Python and pygame-ce to run this project.
        pause
        exit /b 1
    )
)
set "GAME_EXIT=%ERRORLEVEL%"
if not "%GAME_EXIT%"=="0" (
    echo.
    echo Scramble exited with error code %GAME_EXIT%.
    echo If pygame-ce is missing, run: py -m pip install pygame-ce
    pause
)
exit /b %GAME_EXIT%
