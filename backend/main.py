from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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

# Define Upload Folder
UPLOAD_FOLDER = "uploads"
Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)  # Ensure the uploads directory exists

# Configure logging
logging.basicConfig(level=logging.INFO)

# Function to sanitize filenames (removes problematic characters)
def sanitize_filename(filename):
    return re.sub(r'[^\w\-.]', '_', filename)

@app.post("/upload-folder/")
async def upload_folder(files: list[UploadFile]):
    """Uploads multiple files simulating folder upload."""
    folder_path = Path(UPLOAD_FOLDER)

    # Ensure uploads directory exists
    folder_path.mkdir(parents=True, exist_ok=True)

    uploaded_files = []
    
    for file in files:
        sanitized_filename = sanitize_filename(file.filename)

        # Extract subdirectory name if needed
        subfolder = os.path.dirname(sanitized_filename)
        if subfolder:
            full_subfolder_path = folder_path / subfolder
            full_subfolder_path.mkdir(parents=True, exist_ok=True)

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
        output_excel = "output_metrics.xlsx"

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

        return {"message": "Processing completed.", "results": results}

    except subprocess.CalledProcessError as e:
        logging.error(f"Error running script: {e}")
        raise HTTPException(status_code=500, detail="Error processing folder.")

    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Unexpected server error.")
