#!/usr/bin/env python3
"""
Debug build script for MRI DICOM Analysis Desktop App
This version shows console output for debugging and includes more comprehensive bundling
"""

import PyInstaller.__main__
import os
import sys
from pathlib import Path

def build_debug_executable():
    """Build the desktop app with debugging enabled."""
    
    # Get the current directory
    current_dir = Path(__file__).parent
    
    # PyInstaller arguments for debug build
    args = [
        str(current_dir / "main.py"),
        "--name=MRI_DICOM_Analysis_Debug",
        "--onefile",
        # Remove --windowed to show console for debugging
        "--console",  # Show console window for error messages
        "--add-data=script.py:.",
        "--add-data=nema_body.py:.",
        "--add-data=torso.py:.",
        "--add-data=desktop_backend.py:.",
        "--add-data=desktop_gui.py:.",
        # Add all potential directories that might be needed
        "--add-data=uploads:uploads",
        "--add-data=outputs:outputs",
        # Hidden imports for all dependencies
        "--hidden-import=flet",
        "--hidden-import=flet.core",
        "--hidden-import=flet.fastapi",
        "--hidden-import=requests",
        "--hidden-import=pandas",
        "--hidden-import=numpy",
        "--hidden-import=pydicom",
        "--hidden-import=pydicom.dataset",
        "--hidden-import=pydicom.filereader",
        "--hidden-import=skimage",
        "--hidden-import=skimage.measure",
        "--hidden-import=skimage.morphology",
        "--hidden-import=skimage.segmentation",
        "--hidden-import=skimage.filters",
        "--hidden-import=skimage.feature",
        "--hidden-import=scipy",
        "--hidden-import=scipy.io",
        "--hidden-import=scipy.ndimage",
        "--hidden-import=scipy.stats",
        "--hidden-import=openpyxl",
        "--hidden-import=openpyxl.workbook",
        "--hidden-import=fastapi",
        "--hidden-import=fastapi.applications",
        "--hidden-import=fastapi.routing",
        "--hidden-import=uvicorn",
        "--hidden-import=uvicorn.main",
        "--hidden-import=uvicorn.server",
        # Additional imports that might be missing
        "--hidden-import=multiprocessing",
        "--hidden-import=threading",
        "--hidden-import=json",
        "--hidden-import=logging",
        "--hidden-import=pathlib",
        "--hidden-import=shutil",
        "--hidden-import=tempfile",
        "--hidden-import=ssl",
        "--hidden-import=certifi",
        # Collect all submodules
        "--collect-all=flet",
        "--collect-all=skimage", 
        "--collect-all=scipy",
        "--collect-all=pandas",
        "--collect-all=numpy",
        "--clean",
        "--noconfirm",
        # Add debug options
        "--debug=all",
        "--log-level=DEBUG"
    ]
    
    print("Building DEBUG executable with PyInstaller...")
    print("This version will show console output for debugging.")
    print(f"Arguments: {' '.join(args)}")
    
    try:
        PyInstaller.__main__.run(args)
        print("\n✅ Debug build completed successfully!")
        print(f"Executable location: {current_dir / 'dist' / 'MRI_DICOM_Analysis_Debug.exe'}")
        print("\nTo debug the app:")
        print("1. Navigate to the 'dist' folder")
        print("2. Run 'MRI_DICOM_Analysis_Debug.exe' from Command Prompt")
        print("3. Console window will show any error messages")
        
    except Exception as e:
        print(f"❌ Build failed: {e}")
        sys.exit(1)

def build_production_executable():
    """Build the production version (no console) after debugging is complete."""
    
    # Get the current directory
    current_dir = Path(__file__).parent
    
    # PyInstaller arguments for production build
    args = [
        str(current_dir / "main.py"),
        "--name=MRI_DICOM_Analysis",
        "--onedir",  # Use onedir instead of onefile for better compatibility
        "--windowed",  # Hide console in production
        "--add-data=script.py:.",
        "--add-data=nema_body.py:.",
        "--add-data=torso.py:.",
        "--add-data=desktop_backend.py:.",
        "--add-data=desktop_gui.py:.",
        # Create required directories
        "--add-data=uploads:uploads",
        "--add-data=outputs:outputs",
        # All the hidden imports from debug version
        "--hidden-import=flet",
        "--hidden-import=flet.core",
        "--hidden-import=flet.fastapi",
        "--hidden-import=requests",
        "--hidden-import=pandas",
        "--hidden-import=numpy",
        "--hidden-import=pydicom",
        "--hidden-import=pydicom.dataset",
        "--hidden-import=pydicom.filereader",
        "--hidden-import=skimage",
        "--hidden-import=skimage.measure",
        "--hidden-import=skimage.morphology",
        "--hidden-import=skimage.segmentation",
        "--hidden-import=skimage.filters",
        "--hidden-import=skimage.feature",
        "--hidden-import=scipy",
        "--hidden-import=scipy.io",
        "--hidden-import=scipy.ndimage",
        "--hidden-import=scipy.stats",
        "--hidden-import=openpyxl",
        "--hidden-import=openpyxl.workbook",
        "--hidden-import=fastapi",
        "--hidden-import=fastapi.applications",
        "--hidden-import=fastapi.routing",
        "--hidden-import=uvicorn",
        "--hidden-import=uvicorn.main",
        "--hidden-import=uvicorn.server",
        "--hidden-import=multiprocessing",
        "--hidden-import=threading",
        "--hidden-import=json",
        "--hidden-import=logging",
        "--hidden-import=pathlib",
        "--hidden-import=shutil",
        "--hidden-import=tempfile",
        "--hidden-import=ssl",
        "--hidden-import=certifi",
        # Collect all submodules
        "--collect-all=flet",
        "--collect-all=skimage", 
        "--collect-all=scipy",
        "--collect-all=pandas",
        "--collect-all=numpy",
        "--clean",
        "--noconfirm"
    ]
    
    print("Building PRODUCTION executable with PyInstaller...")
    print(f"Arguments: {' '.join(args)}")
    
    try:
        PyInstaller.__main__.run(args)
        print("\n✅ Production build completed successfully!")
        print(f"Executable location: {current_dir / 'dist' / 'MRI_DICOM_Analysis' / 'MRI_DICOM_Analysis.exe'}")
        print("\nTo distribute the app:")
        print("1. Copy the entire 'MRI_DICOM_Analysis' folder from 'dist'")
        print("2. Give the entire folder to users")
        print("3. Users double-click 'MRI_DICOM_Analysis.exe' inside the folder")
        
    except Exception as e:
        print(f"❌ Build failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("Choose build type:")
    print("1. Debug build (shows console for troubleshooting)")
    print("2. Production build (clean, no console)")
    
    choice = input("Enter choice (1 or 2): ").strip()
    
    if choice == "1":
        build_debug_executable()
    elif choice == "2":
        build_production_executable()
    else:
        print("Invalid choice. Building debug version by default.")
        build_debug_executable() 