@echo off
echo Building MRI DICOM Analysis for Windows...

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.11+ from python.org
    pause
    exit /b 1
)

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt
pip install PyInstaller

REM Build the executable
echo Building executable...
python build_app_cross_platform.py

REM Check if build was successful
if exist "dist\MRI_DICOM_Analysis.exe" (
    echo.
    echo ✅ Build completed successfully!
    echo.
    echo Executable location: %CD%\dist\MRI_DICOM_Analysis.exe
    echo.
    echo To distribute:
    echo 1. Copy the entire 'dist' folder to the target Windows machine
    echo 2. Double-click MRI_DICOM_Analysis.exe to run
    echo.
) else (
    echo.
    echo ❌ Build failed! Check the output above for errors.
    echo.
)

pause 