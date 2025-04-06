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
import uuid

# Initialize FastAPI
app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (for production, restrict as needed)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define Upload and Output Folders
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
Path(OUTPUT_FOLDER).mkdir(parents=True, exist_ok=True)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Global variable to store the current upload folder
current_upload_folder = None

# Function to sanitize filenames (removes problematic characters)
def sanitize_filename(filename):
    return re.sub(r'[^\w\-.]', '_', filename)

# Function to clear a folder (for outputs only, not for uploads now)
def clear_folder(folder):
    if os.path.exists(folder):
        shutil.rmtree(folder)
    os.makedirs(folder)

# Function to delete old output files (including roi_overlay.png)
def clear_output_files():
    roi_image = os.path.join(OUTPUT_FOLDER, "roi_overlay.png")
    output_excel = os.path.join(OUTPUT_FOLDER, "output_metrics.xlsx")
    nema_body_excel = os.path.join(OUTPUT_FOLDER, "nema_body_metrics.xlsx")
    for f in [roi_image, output_excel, nema_body_excel]:
        if os.path.exists(f):
            os.remove(f)
            logging.info(f"Deleted old {os.path.basename(f)}")

@app.post("/process-nema-body/")
def process_nema_body():
    """
    Processes the uploaded folder using the nema_body.py script.
    Returns the metrics grouped by Orientation (Sagi, Coronal, Trans).
    """
    global current_upload_folder
    if current_upload_folder is None or not os.path.exists(current_upload_folder) or not os.listdir(current_upload_folder):
        logging.error("Uploads folder is empty.")
        raise HTTPException(status_code=400, detail="No files found in uploads directory.")
    try:
        output_excel = os.path.join(OUTPUT_FOLDER, "nema_body_metrics.xlsx")
        clear_output_files()

        # Run the nema_body.py script. Adjust the command if necessary.
        command = ["python", "nema_body.py", current_upload_folder]
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

        return {
            "message": "NEMA body processing completed.",
            "results": grouped,
            "excel_url": "/download-nema-body"
        }
    except subprocess.CalledProcessError as e:
        logging.error(f"Error running nema_body.py: {e}")
        raise HTTPException(status_code=500, detail="Error processing NEMA body folder.")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Unexpected server error.")

@app.get("/download-nema-body")
def download_nema_body():
    """Returns the NEMA body Excel file for downloading."""
    excel_path = os.path.join(OUTPUT_FOLDER, "nema_body_metrics.xlsx")
    if not os.path.exists(excel_path):
        raise HTTPException(status_code=404, detail="NEMA body metrics file not found.")
    return FileResponse(
        excel_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="nema_body_metrics.xlsx"
    )

@app.post("/upload-folder/")
async def upload_folder(files: list[UploadFile]):
    """
    Creates a new subfolder in the uploads folder and saves the files there.
    This subfolder name is stored in the global variable 'current_upload_folder'
    so that subsequent processing endpoints use the newly created folder.
    """
    global current_upload_folder
    clear_output_files()
    # Create a new unique subfolder inside UPLOAD_FOLDER
    current_upload_folder = os.path.join(UPLOAD_FOLDER, str(uuid.uuid4()))
    Path(current_upload_folder).mkdir(parents=True, exist_ok=True)
    uploaded_files = []
    for file in files:
        sanitized_filename = sanitize_filename(file.filename)
        file_path = Path(current_upload_folder) / sanitized_filename
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        uploaded_files.append(str(file_path))
    logging.info(f"Uploaded new files to {current_upload_folder}: {uploaded_files}")
    return {"message": "Files uploaded successfully.", "uploaded_files": uploaded_files, "folder": current_upload_folder}

@app.post("/process-folder/")
def process_folder():
    global current_upload_folder
    if current_upload_folder is None or not os.path.exists(current_upload_folder) or not os.listdir(current_upload_folder):
        logging.error("Uploads directory is empty or missing.")
        raise HTTPException(status_code=400, detail="No files found in uploads directory.")
    logging.info(f"Processing files in {current_upload_folder}")
    try:
        output_excel = os.path.join(OUTPUT_FOLDER, "output_metrics.xlsx")
        output_image = os.path.join(OUTPUT_FOLDER, "roi_overlay.png")
        clear_output_files()
        command = ["python", "script.py", current_upload_folder, "--output", output_excel]
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
