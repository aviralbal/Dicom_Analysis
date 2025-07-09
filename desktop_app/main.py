#!/usr/bin/env python3
"""
MRI DICOM Analysis Desktop Application
Main entry point for the desktop app
"""

import sys
import os
import logging
from pathlib import Path

# Ensure proper working directory
if hasattr(sys, '_MEIPASS'):
    # Running as PyInstaller bundle
    os.chdir(sys._MEIPASS)
else:
    # Running as script
    os.chdir(Path(__file__).parent)

try:
    # Import our modules
    from desktop_backend import backend
    from desktop_gui import MRIAnalysisApp
    import flet as ft
    
    def main():
        """Main function to start the application."""
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('app.log'),
                logging.StreamHandler()
            ]
        )
        
        # Create and run the Flet application
        app = MRIAnalysisApp(backend)
        ft.app(target=app.main, view=ft.AppView.FLET_APP)

    if __name__ == "__main__":
        main()

except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Please ensure all dependencies are installed:")
    print("pip install -r requirements.txt")
    sys.exit(1)
except Exception as e:
    print(f"Error starting application: {e}")
    sys.exit(1) 