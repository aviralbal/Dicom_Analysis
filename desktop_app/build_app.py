#!/usr/bin/env python3
"""
Build script for creating a standalone executable of the MRI DICOM Analysis Desktop App
"""

import PyInstaller.__main__
import os
import sys
from pathlib import Path

def build_executable():
    """Build the desktop app as a standalone executable."""
    
    # Get the current directory
    current_dir = Path(__file__).parent
    
    # PyInstaller arguments
    args = [
        str(current_dir / "main.py"),
        "--name=MRI_DICOM_Analysis",
        "--onefile",
        "--windowed",
        "--add-data=script.py:.",
        "--add-data=nema_body.py:.",
        "--add-data=torso.py:.",
        "--add-data=desktop_backend.py:.",
        "--add-data=desktop_gui.py:.",
        "--hidden-import=flet",
        "--hidden-import=flet.core",
        "--hidden-import=requests",
        "--hidden-import=pandas",
        "--hidden-import=numpy",
        "--hidden-import=pydicom",
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
        "--hidden-import=fastapi",
        "--hidden-import=uvicorn",
        "--clean",
        "--noconfirm"
    ]
    
    # Add icon if available (you can add an icon file later)
    # if (current_dir / "icon.ico").exists():
    #     args.extend(["--icon=icon.ico"])
    
    print("Building executable with PyInstaller...")
    print(f"Arguments: {' '.join(args)}")
    
    try:
        PyInstaller.__main__.run(args)
        print("\n✅ Build completed successfully!")
        print(f"Executable location: {current_dir / 'dist' / 'MRI_DICOM_Analysis.exe'}")
        print("\nTo run the app:")
        print("1. Navigate to the 'dist' folder")
        print("2. Double-click 'MRI_DICOM_Analysis.exe'")
        
    except Exception as e:
        print(f"❌ Build failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build_executable() 