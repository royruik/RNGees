@echo off
echo ========================================
echo  RNGees Builder
echo ========================================

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install from https://python.org
    pause
    exit /b 1
)

:: Install dependencies
echo.
echo Installing dependencies...
pip install pywin32 Pillow keyboard pyinstaller pywin32-ctypes --quiet

:: Run pywin32 post-install (fixes ordinal DLL error)
echo.
echo Configuring pywin32...
python -m pywin32_postinstall -install >nul 2>&1

:: Clean previous build
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

:: Build — bundle RNGees.ico as data file so iconphoto works
echo.
echo Building RNGees.exe...
pyinstaller --onefile --windowed --name RNGees --icon=RNGees.ico ^
    --add-data "RNGees.ico;." ^
    --hidden-import=win32api ^
    --hidden-import=win32con ^
    --hidden-import=win32gui ^
    --hidden-import=win32process ^
    --hidden-import=pywintypes ^
    --collect-all=pywin32 ^
    RNGees.py

echo.
if exist dist\RNGees.exe (
    echo SUCCESS: dist\RNGees.exe is ready.
) else (
    echo ERROR: Build failed. Check output above.
)

pause