from fastapi import FastAPI, UploadFile, File, HTTPException
import os
import shutil
import subprocess
from pathlib import Path
import pandas as pd
import logging

app = FastAPI()

UPLOAD_FOLDER = "uploads"
Path(UPLOAD_FOLDER).mkdir(exist_ok=True)  # Ensure the uploads directory exists

# Configure logging
logging.basicConfig(level=logging.INFO)


@app.post("/upload-folder/")
async def upload_folder(files: list[UploadFile]):
    """Uploads multiple files simulating folder upload."""
    folder_path = Path(UPLOAD_FOLDER)
    for file in files:
        file_path = folder_path / file.filename
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

    return {"message": "Folder uploaded successfully."}


@app.post("/process-folder/")
def process_folder():
    """Runs `script.py` on the uploaded folder and returns computed metrics."""
    try:
        # Run script.py with the uploads directory as input
        output_excel = "output_metrics.xlsx"
        command = ["python", "script.py", UPLOAD_FOLDER, "--output", output_excel]
        subprocess.run(command, check=True)

        # Read the Excel file
        df = pd.read_excel(output_excel)
        results = df.to_dict(orient="records")

        return {"message": "Processing completed.", "results": results}

    except subprocess.CalledProcessError as e:
        logging.error(f"Error running script: {e}")
        raise HTTPException(status_code=500, detail="Error processing folder.")

    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Unexpected server error.")
