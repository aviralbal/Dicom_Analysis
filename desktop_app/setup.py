#!/usr/bin/env python3
"""
Setup script for MRI DICOM Analysis Desktop Application
"""

import subprocess
import sys
import os
from pathlib import Path

def install_dependencies():
    """Install required dependencies."""
    print("📦 Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def run_app():
    """Run the desktop application."""
    print("🚀 Starting MRI DICOM Analysis Desktop App...")
    try:
        subprocess.run([sys.executable, "main.py"])
    except KeyboardInterrupt:
        print("\n👋 Application closed by user")
    except Exception as e:
        print(f"❌ Error running application: {e}")

def build_executable():
    """Build standalone executable."""
    print("🔨 Building standalone executable...")
    try:
        subprocess.check_call([sys.executable, "build_app.py"])
        print("✅ Executable built successfully!")
        print("📁 Check the 'dist' folder for your executable")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to build executable: {e}")

def main():
    """Main setup function."""
    print("=" * 50)
    print("🏥 MRI DICOM Analysis Desktop Application Setup")
    print("=" * 50)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or later is required")
        sys.exit(1)
    
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} detected")
    
    while True:
        print("\nWhat would you like to do?")
        print("1. Install dependencies and run app")
        print("2. Just run app (dependencies already installed)")
        print("3. Build standalone executable")
        print("4. Exit")
        
        choice = input("\nEnter your choice (1-4): ").strip()
        
        if choice == "1":
            if install_dependencies():
                run_app()
            break
        elif choice == "2":
            run_app()
            break
        elif choice == "3":
            build_executable()
            break
        elif choice == "4":
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please enter 1, 2, 3, or 4.")

if __name__ == "__main__":
    main() 