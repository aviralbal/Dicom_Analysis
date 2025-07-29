@echo off
echo ============================================
echo  MRI DICOM Analysis - Windows Test Script
echo ============================================
echo.

echo Checking current directory...
echo Current directory: %CD%
echo.

echo Checking files in current directory...
dir /b
echo.

echo Checking if required folders exist...
if exist "uploads" (
    echo ✓ uploads folder exists
) else (
    echo ✗ uploads folder missing - creating it...
    mkdir uploads
)

if exist "outputs" (
    echo ✓ outputs folder exists  
) else (
    echo ✗ outputs folder missing - creating it...
    mkdir outputs
)
echo.

echo Checking for executable files...
if exist "MRI_DICOM_Analysis.exe" (
    echo ✓ Found MRI_DICOM_Analysis.exe
    set "EXE_FILE=MRI_DICOM_Analysis.exe"
) else if exist "MRI_DICOM_Analysis_Debug.exe" (
    echo ✓ Found MRI_DICOM_Analysis_Debug.exe
    set "EXE_FILE=MRI_DICOM_Analysis_Debug.exe"
) else (
    echo ✗ No executable found!
    echo Please make sure you're in the correct directory.
    pause
    exit /b 1
)
echo.

echo Testing Python dependencies...
echo (This test will start the app - close it after it loads)
echo.
echo Press any key to start the app test...
pause >nul

echo Starting %EXE_FILE%...
echo (If you see errors, note them down!)
echo.

start "" "%EXE_FILE%"

echo.
echo App started! If it opened successfully:
echo 1. Try uploading some DICOM files
echo 2. Check if processing works
echo 3. Look for any error messages
echo.
echo If it didn't open or crashed:
echo 1. Note any error messages above
echo 2. Check Windows Event Viewer
echo 3. Try running as Administrator
echo.
pause 