#!/usr/bin/env python3
"""
Cross-platform build script for MRI DICOM Analysis Desktop Application
Works on both macOS and Windows
"""

import os
import sys
import platform
import subprocess
import shutil
from pathlib import Path

def get_platform_specific_args():
    """Get platform-specific PyInstaller arguments"""
    base_args = [
        sys.executable, "-m", "PyInstaller",
        "main.py",
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
    
    if platform.system() == "Windows":
        # Windows-specific optimizations
        base_args.extend([
            "--console",  # Show console for debugging on Windows
            "--icon=NONE",  # Avoid icon issues
        ])
    elif platform.system() == "Darwin":
        # macOS-specific optimizations
        base_args.extend([
            "--windowed",  # Hide console on macOS
        ])
    
    return base_args

def check_dependencies():
    """Check if all required dependencies are installed"""
    required_packages = [
        "PyInstaller",
        "flet",
        "pandas",
        "numpy",
        "pydicom",
        "scikit-image",
        "scipy",
        "openpyxl",
        "fastapi",
        "uvicorn",
        "requests"
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace("-", "_").lower())
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Missing packages: {', '.join(missing_packages)}")
        print("Please install them using:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True

def build_executable():
    """Build the executable using PyInstaller"""
    print(f"🔨 Building executable for {platform.system()} {platform.machine()}...")
    
    # Check dependencies
    if not check_dependencies():
        return False
    
    # Clean previous builds
    build_dirs = ["build", "dist", "__pycache__"]
    for build_dir in build_dirs:
        if os.path.exists(build_dir):
            print(f"🧹 Cleaning {build_dir}...")
            shutil.rmtree(build_dir)
    
    # Get platform-specific arguments
    args = get_platform_specific_args()
    
    print("Building executable with PyInstaller...")
    print(f"Arguments: {' '.join(args[2:])}")  # Skip python and -m PyInstaller
    
    try:
        # Run PyInstaller
        result = subprocess.run(args, check=True, capture_output=True, text=True)
        
        # Check if executable was created
        exe_name = "MRI_DICOM_Analysis.exe" if platform.system() == "Windows" else "MRI_DICOM_Analysis"
        exe_path = Path("dist") / exe_name
        
        if exe_path.exists():
            file_size = exe_path.stat().st_size / (1024 * 1024)  # Size in MB
            print(f"\n✅ Build completed successfully!")
            print(f"📍 Executable location: {exe_path.absolute()}")
            print(f"📏 File size: {file_size:.1f} MB")
            print(f"🖥️  Platform: {platform.system()} {platform.machine()}")
            
            if platform.system() == "Windows":
                print(f"\n📦 To distribute on Windows:")
                print(f"1. Copy the executable to the target Windows machine")
                print(f"2. Double-click '{exe_name}' to run")
                print(f"3. No additional dependencies required!")
            else:
                print(f"\n📦 To run the app:")
                print(f"1. Navigate to the 'dist' folder")
                print(f"2. Double-click '{exe_name}'")
            
            return True
        else:
            print(f"❌ Build failed - executable not found at {exe_path}")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed with error:")
        print(f"Exit code: {e.returncode}")
        print(f"Error output: {e.stderr}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error during build: {e}")
        return False

def main():
    """Main function"""
    print("🚀 MRI DICOM Analysis - Cross-Platform Build Script")
    print(f"📋 Platform: {platform.system()} {platform.release()} ({platform.machine()})")
    print(f"🐍 Python: {sys.version}")
    
    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    print(f"📁 Working directory: {script_dir.absolute()}")
    
    # Build executable
    success = build_executable()
    
    if success:
        print("\n🎉 Build process completed successfully!")
        sys.exit(0)
    else:
        print("\n💥 Build process failed!")
        sys.exit(1)

if __name__ == "__main__":
    main() 