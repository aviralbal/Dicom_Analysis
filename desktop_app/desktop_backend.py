# ...
import os
import shutil
import threading
import time
import logging
import socket
import re
import sys
from pathlib import Path
from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import pandas as pd
import numpy as np
import math
import json

class DesktopBackend:
    def __init__(self):
        self.app = FastAPI()
        self.setup_middleware()
        self.setup_routes()
        self.setup_directories()
        self.setup_logging()
        self.server = None
        self.actual_port = None
        self.script_dir = self.get_script_directory()

    def setup_middleware(self):
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def setup_directories(self):
        self.UPLOAD_FOLDER = "uploads"
        self.OUTPUT_FOLDER = "outputs"
        Path(self.UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
        Path(self.OUTPUT_FOLDER).mkdir(parents=True, exist_ok=True)

    def setup_logging(self):
        logging.basicConfig(level=logging.INFO)

    def get_script_directory(self):
        if hasattr(sys, '_MEIPASS'):
            return sys._MEIPASS
        else:
            return os.path.dirname(os.path.abspath(__file__))

    def find_available_port(self, start_port=8000, max_port=8100):
        for port in range(start_port, max_port + 1):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.bind(('127.0.0.1', port))
                sock.close()
                return port
            except OSError:
                continue
        raise Exception("No available ports found")

    def sanitize_filename(self, filename):
        return re.sub(r'[^\w\-.]', '_', filename)

    def clear_folder(self, folder_path):
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)
        os.makedirs(folder_path, exist_ok=True)

    def clear_output_files(self):
        output_files = [
            "output_metrics.xlsx",
            "nema_body_metrics.xlsx",
            "torso_coil_analysis.xlsx",
            "roi_overlay.png"
        ]
        for file in output_files:
            file_path = os.path.join(self.OUTPUT_FOLDER, file)
            if os.path.exists(file_path):
                os.remove(file_path)

    def fix_floats(self, data):
        if isinstance(data, dict):
            return {k: self.fix_floats(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.fix_floats(item) for item in data]
        elif isinstance(data, float):
            if math.isnan(data) or math.isinf(data):
                return 0.0
            return data
        return data

    def setup_routes(self):
        @self.app.get("/")
        async def root():
            return {"message": "MRI DICOM Analysis Backend"}

        @self.app.post("/upload-folder/")
        async def upload_folder(files: list[UploadFile]):
            self.clear_folder(self.UPLOAD_FOLDER)
            self.clear_output_files()
            uploaded_files = []
            for file in files:
                file_path = Path(self.UPLOAD_FOLDER) / file.filename
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with file_path.open("wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                uploaded_files.append(str(file_path))
            logging.info(f"Uploaded {len(uploaded_files)} files with folder structure preserved")
            return {"message": "Files uploaded successfully.", "uploaded_files": uploaded_files}

        @self.app.post("/process-folder/")
        async def process_folder():
            if not os.path.exists(self.UPLOAD_FOLDER) or not os.listdir(self.UPLOAD_FOLDER):
                raise HTTPException(status_code=400, detail="No files found in uploads directory.")
            try:
                output_excel = os.path.join(self.OUTPUT_FOLDER, "output_metrics.xlsx")
                self.clear_output_files()
                
                # Import and call function directly instead of using subprocess
                import script
                script.process_directory(self.UPLOAD_FOLDER, output_excel)
                
                if not os.path.exists(output_excel):
                    raise HTTPException(status_code=500, detail="Processing failed, no output file found.")
                df = pd.read_excel(output_excel)
                results = df.to_dict(orient="records")
                return {
                    "message": "Processing completed.",
                    "results": results,
                    "excel_url": "/download-metrics"
                }
            except Exception as e:
                logging.error(f"Error in process_folder: {e}")
                raise HTTPException(status_code=500, detail="Unexpected server error.")

        @self.app.post("/process-nema-body/")
        async def process_nema_body():
            if not os.path.exists(self.UPLOAD_FOLDER) or not os.listdir(self.UPLOAD_FOLDER):
                raise HTTPException(status_code=400, detail="No files found in uploads directory.")
            try:
                output_excel = os.path.join(self.OUTPUT_FOLDER, "nema_body_metrics.xlsx")
                self.clear_output_files()
                
                # Import and call function directly instead of using subprocess
                import nema_body
                results = nema_body.process_directory(self.UPLOAD_FOLDER, visualize=False)
                
                if not results:
                    raise HTTPException(status_code=500, detail="Processing failed, no results found.")
                
                # Create DataFrame and save to Excel
                df = pd.DataFrame(results)
                df.to_excel(output_excel, index=False)
                
                grouped = df.groupby("Orientation").apply(lambda x: x.to_dict(orient="records")).to_dict()
                grouped_fixed = self.fix_floats(grouped)
                return {
                    "message": "NEMA body processing completed.",
                    "results": grouped_fixed,
                    "excel_url": "/download-nema-body"
                }
            except Exception as e:
                logging.error(f"Error in process_nema_body: {e}")
                raise HTTPException(status_code=500, detail="Unexpected server error.")

        @self.app.post("/process-torso/")
        async def process_torso():
            if not os.path.exists(self.UPLOAD_FOLDER) or not os.listdir(self.UPLOAD_FOLDER):
                raise HTTPException(status_code=400, detail="No files found in uploads directory.")
            try:
                output_excel = os.path.join(self.OUTPUT_FOLDER, "torso_coil_analysis.xlsx")
                self.clear_output_files()
                
                # Import and call function directly instead of using subprocess
                import torso
                combined, elements = torso.process_torso_folder(self.UPLOAD_FOLDER)
                
                # Create DataFrames and save to Excel
                df_combined = pd.DataFrame(combined)
                df_elements = pd.DataFrame(elements)
                
                with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
                    df_combined.to_excel(writer, index=False, sheet_name="Combined Views")
                    df_elements.to_excel(writer, index=False, sheet_name="Individual Elements")
                
                combined_fixed = self.fix_floats(combined)
                elements_fixed = self.fix_floats(elements)
                return {
                    "message": "Torso processing completed.",
                    "combined_results": combined_fixed,
                    "element_results": elements_fixed,
                    "excel_url": "/download-torso"
                }
            except Exception as e:
                logging.error(f"Error in process_torso: {e}")
                raise HTTPException(status_code=500, detail="Unexpected server error.")

        @self.app.get("/download-metrics")
        async def download_metrics():
            excel_path = os.path.join(self.OUTPUT_FOLDER, "output_metrics.xlsx")
            if not os.path.exists(excel_path):
                raise HTTPException(status_code=404, detail="Metrics file not found.")
            return FileResponse(
                excel_path,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                filename="output_metrics.xlsx"
            )

        @self.app.get("/download-nema-body")
        async def download_nema_body():
            excel_path = os.path.join(self.OUTPUT_FOLDER, "nema_body_metrics.xlsx")
            if not os.path.exists(excel_path):
                raise HTTPException(status_code=404, detail="NEMA body metrics file not found.")
            return FileResponse(
                excel_path,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                filename="nema_body_metrics.xlsx"
            )

        @self.app.get("/download-torso")
        async def download_torso():
            excel_path = os.path.join(self.OUTPUT_FOLDER, "torso_coil_analysis.xlsx")
            if not os.path.exists(excel_path):
                raise HTTPException(status_code=404, detail="Torso analysis file not found.")
            return FileResponse(
                excel_path,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                filename="torso_coil_analysis.xlsx"
            )

    def start_server(self):
        self.actual_port = self.find_available_port()

        def run_server():
            uvicorn.run(self.app, host="127.0.0.1", port=self.actual_port, log_level="info")

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        return server_thread, self.actual_port

# Create the backend instance
backend = DesktopBackend()
