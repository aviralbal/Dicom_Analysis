#!/usr/bin/env python3
"""
Simple Windows-only build script for MRI DICOM Analysis Desktop Application
Creates a single Windows executable with all functionality included.
"""

import os
import sys
import platform
import subprocess
import shutil
from pathlib import Path

def check_platform():
    """Ensure we're building for Windows"""
    if platform.system() != "Windows":
        print("⚠️  This script is designed for Windows only!")
        print("   If you're on macOS/Linux, use build_app_cross_platform.py instead")
        return False
    return True

def check_dependencies():
    """Check if all required packages are installed"""
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
    
    missing = []
    for package in required_packages:
        try:
            if package == "PyInstaller":
                result = subprocess.run([sys.executable, "-m", "PyInstaller", "--version"], 
                                      capture_output=True, text=True)
                if result.returncode != 0:
                    missing.append(package)
            elif package == "scikit-image":
                __import__("skimage")
            else:
                __import__(package.replace("-", "_").lower())
        except (ImportError, Exception):
            missing.append(package)
    
    if missing:
        print(f"❌ Missing packages: {', '.join(missing)}")
        print("📦 Install them with:")
        print(f"   pip install {' '.join(missing)}")
        return False
    
    print("✅ All required packages are installed!")
    return True

def clean_build():
    """Clean previous build files"""
    build_dirs = ["build", "dist", "__pycache__"]
    for build_dir in build_dirs:
        if os.path.exists(build_dir):
            print(f"🧹 Cleaning {build_dir}...")
            shutil.rmtree(build_dir)

def build_windows_exe():
    """Build Windows executable using PyInstaller"""
    print("🔨 Building Windows executable...")
    
    # Windows-specific PyInstaller arguments
    args = [
        sys.executable, "-m", "PyInstaller",
        "main.py",
        "--name=MRI_DICOM_Analysis",
        "--onefile",
        "--windowed",
        "--console",  # Show console for debugging
        
        # Add all Python scripts
        "--add-data=script.py;.",
        "--add-data=nema_body.py;.",
        "--add-data=torso.py;.",
        "--add-data=head_neck.py;.",
        "--add-data=desktop_backend.py;.",
        "--add-data=desktop_gui.py;.",
        
        # Hidden imports for all dependencies
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
        
        # Windows-specific options
        "--clean",
        "--noconfirm",
        "--icon=NONE"  # Avoid icon issues
    ]
    
    print("🔧 Running PyInstaller...")
    print(f"   Command: {' '.join(args[2:])}")  # Skip python and -m PyInstaller
    
    try:
        result = subprocess.run(args, check=True, capture_output=True, text=True)
        
        # Check if executable was created
        exe_path = Path("dist") / "MRI_DICOM_Analysis.exe"
        
        if exe_path.exists():
            file_size = exe_path.stat().st_size / (1024 * 1024)  # Size in MB
            print(f"\n🎉 SUCCESS! Windows executable created!")
            print(f"📍 Location: {exe_path.absolute()}")
            print(f"📏 Size: {file_size:.1f} MB")
            print(f"🖥️  Platform: Windows {platform.machine()}")
            
            print(f"\n📦 How to distribute:")
            print(f"1. Copy 'MRI_DICOM_Analysis.exe' to any Windows computer")
            print(f"2. Double-click the .exe file to run")
            print(f"3. No Python installation needed on target computer!")
            
            print(f"\n⚠️  First-time users may see:")
            print(f"   - Windows security warning (click 'More info' → 'Run anyway')")
            print(f"   - Antivirus warning (add to exclusions if needed)")
            
            return True
        else:
            print(f"❌ Build failed - executable not found at {exe_path}")
            print(f"PyInstaller output: {result.stdout}")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed with error:")
        print(f"Exit code: {e.returncode}")
        print(f"Error output: {e.stderr}")
        if e.stdout:
            print(f"Standard output: {e.stdout}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error during build: {e}")
        return False

def main():
    """Main build process"""
    print("🚀 MRI DICOM Analysis - Windows Build Script")
    print("=" * 50)
    
    # Check if we're on Windows
    if not check_platform():
        sys.exit(1)
    
    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    print(f"📁 Working directory: {script_dir.absolute()}")
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Clean previous builds
    clean_build()
    
    # Build executable
    success = build_windows_exe()
    
    if success:
        print("\n✅ Windows build completed successfully!")
        print("🎯 Your app is ready to distribute!")
        sys.exit(0)
    else:
        print("\n❌ Windows build failed!")
        print("💡 Try installing missing dependencies or check the error messages above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
