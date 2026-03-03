@echo off
title GTO RNG Launcher
echo.
echo  GTO RNG — Poker Decision Overlay
echo  ==================================
echo.

REM Check for pywin32
python -c "import win32gui" 2>nul
if errorlevel 1 (
    echo  Installing pywin32 for window auto-detection...
    pip install pywin32 --quiet
    echo  Done.
    echo.
)

echo  Starting GTO RNG...
start /B pythonw RNGees.py
exit