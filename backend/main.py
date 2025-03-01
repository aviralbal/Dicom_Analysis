from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import os
import shutil
import subprocess
from pathlib import Path
import pandas as pd
import logging
import re

# Initialize FastAPI
app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (use ["http://localhost:3000"] for security)
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
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

@app.post("/upload-folder/")
async def upload_folder(files: list[UploadFile]):
    """Uploads multiple files simulating folder upload."""
    folder_path = Path(UPLOAD_FOLDER)
    folder_path.mkdir(parents=True, exist_ok=True)

    uploaded_files = []
    
    for file in files:
        sanitized_filename = sanitize_filename(file.filename)
        file_path = folder_path / sanitized_filename

        # Save file
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        uploaded_files.append(file_path)

    logging.info(f"Uploaded files: {[str(f) for f in uploaded_files]}")

    return {"message": "Folder uploaded successfully.", "files": [str(f) for f in uploaded_files]}

@app.post("/process-folder/")
def process_folder():
    """Runs `script.py` on the uploaded folder and returns computed metrics."""
    
    # Check if the uploads folder exists
    if not os.path.exists(UPLOAD_FOLDER) or not os.listdir(UPLOAD_FOLDER):
        logging.error("Uploads directory is empty or missing.")
        raise HTTPException(status_code=400, detail="No files found in uploads directory.")

    logging.info(f"Processing files in {UPLOAD_FOLDER}")

    try:
        output_excel = os.path.join(OUTPUT_FOLDER, "output_metrics.xlsx")
        output_image = os.path.join(OUTPUT_FOLDER, "roi_overlay.png")

        # Run script.py with the uploads directory as input
        command = ["python", "script.py", UPLOAD_FOLDER, "--output", output_excel]
        subprocess.run(command, check=True)

        # Ensure the output file was created
        if not os.path.exists(output_excel):
            logging.error("Processing script did not generate an output file.")
            raise HTTPException(status_code=500, detail="Processing failed, no output file found.")

        # Read the Excel file and return results
        df = pd.read_excel(output_excel)
        results = df.to_dict(orient="records")

        # Check if the output image exists
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
    """Returns the ROI overlay image if it exists."""
    image_path = os.path.join(os.getcwd(), OUTPUT_FOLDER, "roi_overlay.png")  # Ensure absolute path

    if not os.path.exists(image_path):
        logging.error(f"ROI overlay image not found at: {image_path}")
        raise HTTPException(status_code=404, detail="ROI overlay image not found.")

    return FileResponse(image_path, media_type="image/png")

@app.get("/download-metrics")
def download_metrics():
    """Returns the Excel file for downloading."""
    excel_path = os.path.join(OUTPUT_FOLDER, "output_metrics.xlsx")
    if not os.path.exists(excel_path):
        raise HTTPException(status_code=404, detail="Metrics file not found.")
    return FileResponse(excel_path, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename="output_metrics.xlsx")
