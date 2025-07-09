from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import os
import sys
import shutil
import subprocess
from pathlib import Path
import pandas as pd
import logging
import re
import math
import numpy as np
import json
import threading
import uvicorn
from typing import List

class DesktopBackend:
    def __init__(self):
        # Initialize FastAPI
        self.app = FastAPI()
        
        # Enable CORS for local frontend
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Define Upload and Output Folders
        self.UPLOAD_FOLDER = "uploads"
        self.OUTPUT_FOLDER = "outputs"
        Path(self.UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
        Path(self.OUTPUT_FOLDER).mkdir(parents=True, exist_ok=True)
        
        # Configure logging
        logging.basicConfig(level=logging.INFO)
        
        # Setup routes
        self.setup_routes()
    
    def is_pyinstaller(self):
        """Check if running in PyInstaller bundle."""
        return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')
    
    def get_script_path(self, script_name):
        """Get the correct path to a script file."""
        if self.is_pyinstaller():
            # In PyInstaller, scripts are in the temporary directory
            return os.path.join(sys._MEIPASS, script_name)
        else:
            # In development, scripts are in current directory
            return script_name
    
    def run_analysis_script(self, script_name, input_folder, output_file):
        """Run an analysis script with proper handling for PyInstaller environment."""
        try:
            if self.is_pyinstaller():
                # In PyInstaller, we need to run the script directly with Python
                # Get the embedded Python interpreter
                script_path = self.get_script_path(script_name)
                
                # Check if script exists
                if not os.path.exists(script_path):
                    raise FileNotFoundError(f"Script not found: {script_path}")
                
                # Execute the script by importing it as a module
                import importlib.util
                import tempfile
                
                # Create a temporary module from the script file
                spec = importlib.util.spec_from_file_location("analysis_script", script_path)
                module = importlib.util.module_from_spec(spec)
                
                # Set up sys.argv to simulate command line arguments
                original_argv = sys.argv.copy()
                sys.argv = [script_name, input_folder, "--output", output_file]
                
                try:
                    spec.loader.exec_module(module)
                    return_code = 0
                    stdout = "Script executed successfully"
                    stderr = ""
                except SystemExit as e:
                    return_code = e.code if e.code is not None else 0
                    stdout = "Script completed"
                    stderr = ""
                except Exception as e:
                    return_code = 1
                    stdout = ""
                    stderr = str(e)
                finally:
                    # Restore original sys.argv
                    sys.argv = original_argv
                
                return return_code, stdout, stderr
            else:
                # In development, use subprocess as usual
                command = [sys.executable, script_name, input_folder, "--output", output_file]
                result = subprocess.run(command, capture_output=True, text=True)
                return result.returncode, result.stdout, result.stderr
                
        except Exception as e:
            return 1, "", str(e)
    
    def sanitize_filename(self, filename):
        return re.sub(r'[^\w\-.]', '_', filename)
    
    def clear_folder(self, folder):
        if os.path.exists(folder):
            shutil.rmtree(folder)
        os.makedirs(folder)
    
    def clear_output_files(self):
        for fname in ["roi_overlay.png", "output_metrics.xlsx", "nema_body_metrics.xlsx", "torso_coil_analysis.xlsx"]:
            fpath = os.path.join(self.OUTPUT_FOLDER, fname)
            if os.path.exists(fpath):
                os.remove(fpath)
                logging.info(f"Deleted old {fname}")
    
    def fix_floats(self, obj):
        """Convert any non-finite float (NaN, inf, -inf) to None."""
        if isinstance(obj, float):
            if not math.isfinite(obj):
                return None
            return obj
        elif isinstance(obj, dict):
            return {k: self.fix_floats(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.fix_floats(item) for item in obj]
        else:
            return obj
    
    def setup_routes(self):
        @self.app.post("/upload-folder/")
        async def upload_folder(files: List[UploadFile]):
            """Upload files to the processing directory."""
            self.clear_folder(self.UPLOAD_FOLDER)
            self.clear_output_files()
            folder_path = Path(self.UPLOAD_FOLDER)
            uploaded_files = []
            
            for file in files:
                sanitized_filename = self.sanitize_filename(file.filename)
                file_path = folder_path / sanitized_filename
                with file_path.open("wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                uploaded_files.append(str(file_path))
            
            logging.info(f"Uploaded new files: {uploaded_files}")
            return {"message": "Files uploaded successfully.", "uploaded_files": uploaded_files}
        
        @self.app.post("/process-folder/")
        def process_folder():
            """Process files for weekly analysis."""
            if not os.path.exists(self.UPLOAD_FOLDER) or not os.listdir(self.UPLOAD_FOLDER):
                logging.error("Uploads folder is empty or missing.")
                raise HTTPException(status_code=400, detail="No files found in uploads directory.")
            
            try:
                output_excel = os.path.join(self.OUTPUT_FOLDER, "output_metrics.xlsx")
                output_image = os.path.join(self.OUTPUT_FOLDER, "roi_overlay.png")
                self.clear_output_files()
                
                return_code, stdout, stderr = self.run_analysis_script("script.py", self.UPLOAD_FOLDER, output_excel)
                
                logging.info(f"Script stdout: {stdout}")
                if stderr:
                    logging.error(f"Script stderr: {stderr}")
                logging.info(f"Script return code: {return_code}")
                
                if return_code != 0:
                    raise HTTPException(status_code=500, detail=f"Script failed with return code {return_code}: {stderr}")
                
                if not os.path.exists(output_excel):
                    logging.warning(f"Expected output file not found: {output_excel}")
                    logging.info(f"Contents of output folder: {os.listdir(self.OUTPUT_FOLDER) if os.path.exists(self.OUTPUT_FOLDER) else 'Folder does not exist'}")
                    # Create empty output file
                    os.makedirs(self.OUTPUT_FOLDER, exist_ok=True)
                    empty_df = pd.DataFrame(columns=["Filename", "Mean", "Min", "Max", "Sum", "StDev", "SNR", "PIU"])
                    empty_df.to_excel(output_excel, index=False)
                    results = []
                else:
                    df = pd.read_excel(output_excel)
                    results = df.to_dict(orient="records")
                image_exists = os.path.exists(output_image)
                
                return {
                    "message": "Processing completed.",
                    "results": results,
                    "image_url": "/roi-overlay" if image_exists else None,
                    "excel_url": "/download-metrics"
                }
            except Exception as e:
                logging.error(f"Unexpected error: {e}")
                raise HTTPException(status_code=500, detail="Unexpected server error.")
        
        @self.app.post("/process-nema-body/")
        def process_nema_body():
            """Process files for NEMA body analysis."""
            if not os.path.exists(self.UPLOAD_FOLDER) or not os.listdir(self.UPLOAD_FOLDER):
                raise HTTPException(status_code=400, detail="No files found in uploads directory.")
            
            try:
                output_excel = os.path.join(self.OUTPUT_FOLDER, "nema_body_metrics.xlsx")
                self.clear_output_files()
                
                return_code, stdout, stderr = self.run_analysis_script("nema_body.py", self.UPLOAD_FOLDER, output_excel)
                
                logging.info(f"Script stdout: {stdout}")
                if stderr:
                    logging.error(f"Script stderr: {stderr}")
                logging.info(f"Script return code: {return_code}")
                
                if return_code != 0:
                    raise HTTPException(status_code=500, detail=f"NEMA script failed with return code {return_code}: {stderr}")
                
                if not os.path.exists(output_excel):
                    logging.warning(f"Expected output file not found: {output_excel}")
                    logging.info(f"Contents of output folder: {os.listdir(self.OUTPUT_FOLDER) if os.path.exists(self.OUTPUT_FOLDER) else 'Folder does not exist'}")
                    # Create empty output file
                    os.makedirs(self.OUTPUT_FOLDER, exist_ok=True)
                    empty_df = pd.DataFrame(columns=["ScanID", "Orientation", "Type", "Mean", "Min", "Max", "Sum", "StDev", "Filename", "Slice"])
                    empty_df.to_excel(output_excel, index=False)
                    grouped_fixed = {}
                else:
                    df = pd.read_excel(output_excel)
                    grouped = df.groupby("Orientation").apply(lambda x: x.to_dict(orient="records")).to_dict()
                    grouped_fixed = self.fix_floats(grouped)
                
                return {
                    "message": "NEMA body processing completed.",
                    "results": grouped_fixed,
                    "excel_url": "/download-nema-body"
                }
            except Exception as e:
                logging.error(f"Unexpected error: {e}")
                raise HTTPException(status_code=500, detail="Unexpected server error.")
        
        @self.app.post("/process-torso/")
        def process_torso():
            """Process files for torso analysis."""
            if not os.path.exists(self.UPLOAD_FOLDER) or not os.listdir(self.UPLOAD_FOLDER):
                raise HTTPException(status_code=400, detail="No files found in uploads directory.")
            
            try:
                output_excel = os.path.join(self.OUTPUT_FOLDER, "torso_coil_analysis.xlsx")
                self.clear_output_files()
                
                return_code, stdout, stderr = self.run_analysis_script("torso.py", self.UPLOAD_FOLDER, output_excel)
                
                logging.info(f"Script stdout: {stdout}")
                if stderr:
                    logging.error(f"Script stderr: {stderr}")
                logging.info(f"Script return code: {return_code}")
                
                if return_code != 0:
                    raise HTTPException(status_code=500, detail=f"Torso script failed with return code {return_code}: {stderr}")
                
                if not os.path.exists(output_excel):
                    logging.warning(f"Expected output file not found: {output_excel}")
                    logging.info(f"Contents of output folder: {os.listdir(self.OUTPUT_FOLDER) if os.path.exists(self.OUTPUT_FOLDER) else 'Folder does not exist'}")
                    # Create empty output file with multiple sheets
                    os.makedirs(self.OUTPUT_FOLDER, exist_ok=True)
                    
                    with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
                        # Create empty Combined Views sheet
                        combined_df = pd.DataFrame(columns=["Region", "Signal Max", "Signal Min", "Signal Mean", "Noise SD", "SNR", "Uniformity"])
                        combined_df.to_excel(writer, sheet_name="Combined Views", index=False)
                        
                        # Create empty Individual Elements sheet
                        elements_df = pd.DataFrame(columns=["Element", "Signal Mean", "Noise SD", "SNR"])
                        elements_df.to_excel(writer, sheet_name="Individual Elements", index=False)
                    
                    combined_fixed = []
                    elements_fixed = []
                else:
                    combined_df = pd.read_excel(output_excel, sheet_name="Combined Views")
                    elements_df = pd.read_excel(output_excel, sheet_name="Individual Elements")
                    
                    combined_results = combined_df.to_dict(orient="records")
                    element_results = elements_df.to_dict(orient="records")
                    
                    combined_fixed = self.fix_floats(combined_results)
                    elements_fixed = self.fix_floats(element_results)
                
                return {
                    "message": "Torso processing completed.",
                    "combined_results": combined_fixed,
                    "element_results": elements_fixed,
                    "excel_url": "/download-torso"
                }
            except Exception as e:
                logging.error(f"Unexpected error: {e}")
                raise HTTPException(status_code=500, detail="Unexpected server error.")
        
        @self.app.get("/download-metrics")
        def download_metrics():
            output_file = os.path.join(self.OUTPUT_FOLDER, "output_metrics.xlsx")
            if not os.path.exists(output_file):
                raise HTTPException(status_code=404, detail="Metrics file not found.")
            return FileResponse(output_file, filename="output_metrics.xlsx")
        
        @self.app.get("/download-nema-body")
        def download_nema_body():
            output_file = os.path.join(self.OUTPUT_FOLDER, "nema_body_metrics.xlsx")
            if not os.path.exists(output_file):
                raise HTTPException(status_code=404, detail="NEMA body metrics file not found.")
            return FileResponse(output_file, filename="nema_body_metrics.xlsx")
        
        @self.app.get("/download-torso")
        def download_torso():
            output_file = os.path.join(self.OUTPUT_FOLDER, "torso_coil_analysis.xlsx")
            if not os.path.exists(output_file):
                raise HTTPException(status_code=404, detail="Torso analysis file not found.")
            return FileResponse(output_file, filename="torso_coil_analysis.xlsx")
        
        @self.app.get("/roi-overlay")
        def get_roi_overlay():
            image_file = os.path.join(self.OUTPUT_FOLDER, "roi_overlay.png")
            if not os.path.exists(image_file):
                raise HTTPException(status_code=404, detail="ROI overlay image not found.")
            return FileResponse(image_file, media_type="image/png")
    
    def start_server(self, host="127.0.0.1", port=8000):
        """Start the FastAPI server in a separate thread."""
        def run_server():
            uvicorn.run(self.app, host=host, port=port, log_level="error")
        
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        return server_thread

# Global backend instance
backend = DesktopBackend() 