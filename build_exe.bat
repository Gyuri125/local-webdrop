@echo off
setlocal enabledelayedexpansion
title Webdrop - Standalone EXE Generator
chcp 65001 >nul

echo =====================================================================
echo                 WEBDROP STANDALONE EXE GENERATOR
echo =====================================================================
echo.

:: Detect Python from virtual environment or system PATH
set "PYTHON_EXE="
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
    echo [*] Using local virtual environment (.venv)
) else if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXE=venv\Scripts\python.exe"
    echo [*] Using local virtual environment (venv)
) else (
    where python >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_EXE=python"
        echo [*] Using system Python
    ) else (
        echo [ERROR] Python was not found in .venv or system PATH!
        echo Please ensure Python is installed and available.
        pause
        exit /b 1
    )
)

echo [*] Python executable: !PYTHON_EXE!
echo.

:: Install/update dependencies and PyInstaller
echo [*] Checking and updating dependencies from requirements.txt...
!PYTHON_EXE! -m pip install -r requirements.txt pyinstaller >nul 2>&1
if !errorlevel! neq 0 (
    echo [!] Warning: Pip dependency check had non-zero exit code. Continuing build...
) else (
    echo [OK] Dependencies are up to date.
)
echo.

:: Clean old build artifacts to avoid stale files
echo [*] Cleaning previous build artifacts...
if exist "build" rmdir /s /q "build"
if exist "dist\Webdrop.exe" del /f /q "dist\Webdrop.exe"
echo [OK] Clean completed.
echo.

:: Execute PyInstaller using main.spec
echo [*] Compiling Webdrop into standalone executable (please wait)...
!PYTHON_EXE! -m PyInstaller main.spec --clean --noconfirm

if !errorlevel! equ 0 (
    echo.
    echo =====================================================================
    echo [SUCCESS] Build completed successfully!
    echo Standalone executable located at: dist\Webdrop.exe
    echo =====================================================================
    echo.
    if exist "dist" (
        explorer dist
    )
) else (
    echo.
    echo =====================================================================
    echo [FAILED] PyInstaller build failed with exit code !errorlevel!.
    echo Please review the error log above.
    echo =====================================================================
    echo.
)

pause
