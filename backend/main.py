from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import os
import shutil
import subprocess
from pathlib import Path
import pandas as pd
import logging
import re
import math
import numpy as np
import json

# Initialize FastAPI
app = FastAPI()

# Enable CORS (adjust origins as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define Upload and Output Folders
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
Path(OUTPUT_FOLDER).mkdir(parents=True, exist_ok=True)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Function to sanitize filenames (removes problematic characters)
def sanitize_filename(filename):
    return re.sub(r'[^\w\-.]', '_', filename)

# Function to clear a folder (used for both uploads and outputs)
def clear_folder(folder):
    if os.path.exists(folder):
        shutil.rmtree(folder)
    os.makedirs(folder)

# Function to delete old output files (including roi_overlay.png)
def clear_output_files():
    for fname in ["roi_overlay.png", "output_metrics.xlsx", "nema_body_metrics.xlsx", "torso_coil_analysis.xlsx"]:
        fpath = os.path.join(OUTPUT_FOLDER, fname)
        if os.path.exists(fpath):
            os.remove(fpath)
            logging.info(f"Deleted old {fname}")

@app.post("/upload-folder/")
async def upload_folder(files: list[UploadFile]):
    """
    Clears the main UPLOAD_FOLDER, then uploads all files directly into it.
    """
    clear_folder(UPLOAD_FOLDER)  # Clear previous uploads
    clear_output_files()
    folder_path = Path(UPLOAD_FOLDER)
    uploaded_files = []
    for file in files:
        sanitized_filename = sanitize_filename(file.filename)
        file_path = folder_path / sanitized_filename
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        uploaded_files.append(str(file_path))
    logging.info(f"Uploaded new files: {uploaded_files}")
    return {"message": "Files uploaded successfully.", "uploaded_files": uploaded_files}

@app.post("/process-folder/")
def process_folder():
    if not os.path.exists(UPLOAD_FOLDER) or not os.listdir(UPLOAD_FOLDER):
        logging.error("Uploads folder is empty or missing.")
        raise HTTPException(status_code=400, detail="No files found in uploads directory.")
    logging.info(f"Processing files in {UPLOAD_FOLDER}")
    try:
        output_excel = os.path.join(OUTPUT_FOLDER, "output_metrics.xlsx")
        output_image = os.path.join(OUTPUT_FOLDER, "roi_overlay.png")
        clear_output_files()
        command = ["python", "script.py", UPLOAD_FOLDER, "--output", output_excel]
        subprocess.run(command, check=True)
        if not os.path.exists(output_excel):
            logging.error("Processing script did not generate an output file.")
            raise HTTPException(status_code=500, detail="Processing failed, no output file found.")
        df = pd.read_excel(output_excel)
        results = df.to_dict(orient="records")
        image_exists = os.path.exists(output_image)
        return {
            "message": "Processing completed.",
            "results": results,
            "image_url": "/roi-overlay" if image_exists else None,
            "excel_url": "/download-metrics"
        }
    except subprocess.CalledProcessError as e:
        logging.error(f"Error running script: {e}")
        raise HTTPException(status_code=500, detail="Error processing folder.")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Unexpected server error.")

def fix_floats(obj):
    """
    Recursively convert any non-finite float (NaN, inf, -inf) in a data structure
    (dict, list, float) to None.
    """
    if isinstance(obj, float):
        # Check if the float is finite
        if not math.isfinite(obj):
            return None
        return obj
    elif isinstance(obj, dict):
        return {k: fix_floats(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [fix_floats(item) for item in obj]
    else:
        return obj

@app.post("/process-nema-body/")
def process_nema_body():
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
        logging.info("Uploads folder did not exist. Created a new one.")
    
    if not os.listdir(UPLOAD_FOLDER):
        logging.error("Uploads folder is empty.")
        raise HTTPException(status_code=400, detail="No files found in uploads directory.")
    try:
        output_excel = os.path.join(OUTPUT_FOLDER, "nema_body_metrics.xlsx")
        clear_output_files()

        # Include the --output parameter if your script expects it:
        command = ["python", "nema_body.py", UPLOAD_FOLDER, "--output", output_excel]
        result = subprocess.run(command, capture_output=True, text=True)
        logging.info("nema_body.py stdout: " + result.stdout)
        logging.error("nema_body.py stderr: " + result.stderr)
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail="Error processing NEMA body folder.")

        if not os.path.exists(output_excel):
            logging.error("NEMA body processing did not generate an output file.")
            raise HTTPException(status_code=500, detail="Processing failed, no output file found.")

        df = pd.read_excel(output_excel)
        # Group the metrics by Orientation
        grouped = df.groupby("Orientation").apply(lambda x: x.to_dict(orient="records")).to_dict()
        
        # Fix any non-finite float values
        grouped_fixed = fix_floats(grouped)

        return {
            "message": "NEMA body processing completed.",
            "results": grouped_fixed,
            "excel_url": "/download-nema-body"
        }
    except subprocess.CalledProcessError as e:
        logging.error(f"Error running nema_body.py: {e}")
        raise HTTPException(status_code=500, detail="Error processing NEMA body folder.")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Unexpected server error.")

@app.post("/process-torso/")
def process_torso():
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
        logging.info("Uploads folder did not exist. Created a new one.")
    
    if not os.listdir(UPLOAD_FOLDER):
        logging.error("Uploads folder is empty.")
        raise HTTPException(status_code=400, detail="No files found in uploads directory.")
    try:
        output_excel = os.path.join(OUTPUT_FOLDER, "torso_coil_analysis.xlsx")
        clear_output_files()

        # Include the --output parameter as expected by torso.py
        command = ["python", "torso.py", UPLOAD_FOLDER, "--output", output_excel]
        result = subprocess.run(command, capture_output=True, text=True)
        logging.info("torso.py stdout: " + result.stdout)
        logging.error("torso.py stderr: " + result.stderr)
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail="Error processing Torso folder.")

        if not os.path.exists(output_excel):
            logging.error("Torso processing did not generate an output file.")
            raise HTTPException(status_code=500, detail="Processing failed, no output file found.")

        # Read both sheets from the Excel file
        combined_df = pd.read_excel(output_excel, sheet_name="Combined Views")
        elements_df = pd.read_excel(output_excel, sheet_name="Individual Elements")
        
        # Convert to dictionaries
        combined_results = combined_df.to_dict(orient="records")
        element_results = elements_df.to_dict(orient="records")
        
        # Fix any non-finite float values
        combined_fixed = fix_floats(combined_results)
        elements_fixed = fix_floats(element_results)

        return {
            "message": "Torso processing completed.",
            "combined_results": combined_fixed,
            "element_results": elements_fixed,
            "excel_url": "/download-torso"
        }
    except subprocess.CalledProcessError as e:
        logging.error(f"Error running torso.py: {e}")
        raise HTTPException(status_code=500, detail="Error processing Torso folder.")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Unexpected server error.")

@app.get("/download-metrics")
def download_metrics():
    excel_path = os.path.join(OUTPUT_FOLDER, "output_metrics.xlsx")
    if not os.path.exists(excel_path):
        raise HTTPException(status_code=404, detail="Metrics file not found.")
    return FileResponse(
        excel_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="output_metrics.xlsx"
    )

@app.get("/download-nema-body")
def download_nema_body():
    excel_path = os.path.join(OUTPUT_FOLDER, "nema_body_metrics.xlsx")
    if not os.path.exists(excel_path):
        raise HTTPException(status_code=404, detail="NEMA body metrics file not found.")
    return FileResponse(
        excel_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="nema_body_metrics.xlsx"
    )

@app.get("/download-torso")
def download_torso():
    excel_path = os.path.join(OUTPUT_FOLDER, "torso_coil_analysis.xlsx")
    if not os.path.exists(excel_path):
        raise HTTPException(status_code=404, detail="Torso analysis file not found.")
    return FileResponse(
        excel_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="torso_coil_analysis.xlsx"
    )

@app.get("/roi-overlay")
def get_roi_overlay():
    image_path = os.path.join(OUTPUT_FOLDER, "roi_overlay.png")
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="ROI overlay image not found.")
    headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    return FileResponse(image_path, media_type="image/png", headers=headers)
