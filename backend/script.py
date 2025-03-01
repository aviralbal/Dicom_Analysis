import os
import pydicom
import numpy as np
import pandas as pd
import argparse
import logging
from skimage import measure, filters, morphology
from matplotlib import pyplot as plt
from matplotlib.patches import Circle

def configure_logging():
    logging.basicConfig(
        filename='mri_automation.log',
        filemode='w',
        level=logging.DEBUG,
        format='%(asctime)s:%(levelname)s:%(message)s'
    )

def is_dicom_file(file_path):
    try:
        ds = pydicom.dcmread(file_path, stop_before_pixels=True, force=True)
        return True
    except Exception:
        return False

def load_dicom_image(file_path):
    try:
        ds = pydicom.dcmread(file_path)
        image = ds.pixel_array.astype(np.float32)
        if 'RescaleSlope' in ds and 'RescaleIntercept' in ds:
            image = image * ds.RescaleSlope + ds.RescaleIntercept
        return image, ds
    except Exception as e:
        logging.error(f"Failed to load DICOM file {file_path}: {e}", exc_info=True)
        raise e

def find_best_slice(dicom_files):
    slices = []
    for file_path in dicom_files:
        ds = pydicom.dcmread(file_path, stop_before_pixels=True)
        slice_location = getattr(ds, 'SliceLocation', None)
        instance_number = getattr(ds, 'InstanceNumber', None)
        image, _ = load_dicom_image(file_path)
        mean_intensity = np.mean(image)
        slices.append((file_path, slice_location, instance_number, mean_intensity))
    
    slices.sort(key=lambda x: (abs(x[1]) if x[1] is not None else float('inf'), -x[3]))
    best_slice = slices[0]
    print(f"Selected slice: {os.path.basename(best_slice[0])} (Slice Location: {best_slice[1]}, Instance Number: {best_slice[2]}, Mean Intensity: {best_slice[3]:.2f})")
    return best_slice[0]

def compute_metrics(image, ROI_mask):
    signal_values = image[ROI_mask == 1]
    if signal_values.size == 0:
        logging.warning("ROI is empty or incorrectly applied.")
        return None

    metrics = {
        "Mean": np.mean(signal_values),
        "Min": np.min(signal_values),
        "Max": np.max(signal_values),
        "Sum": np.sum(signal_values),
        "StDev": np.std(signal_values),
        "SNR": np.mean(signal_values) / np.std(signal_values) if np.std(signal_values) != 0 else 0,
        "PIU": 100 * (1 - ((np.max(signal_values) - np.min(signal_values)) / (np.max(signal_values) + np.min(signal_values)))) if (np.max(signal_values) + np.min(signal_values)) != 0 else 0
    }

    # Format metrics only when printing
    formatted_metrics = {key: f"{value:.2f}" for key, value in metrics.items()}
    
    print("\n*** Best Slice Metrics ***")
    for key, value in formatted_metrics.items():
        print(f"{key}: {value}")
    print("****************************\n")

    return metrics  # Returning original values for accuracy

def process_directory(directory_path, output_excel='output_metrics.xlsx'):
    results = []
    dicom_files = [os.path.join(directory_path, f) for f in os.listdir(directory_path) if is_dicom_file(os.path.join(directory_path, f))]
    if not dicom_files:
        logging.warning("No DICOM files found in the directory.")
        return
    
    best_slice = find_best_slice(dicom_files)
    try:
        image, ds = load_dicom_image(best_slice)
        pixel_spacing = [float(x) for x in ds.PixelSpacing[:2]]
        ROI_mask = np.ones(image.shape, dtype=np.uint8)  # Placeholder ROI mask
        metrics = compute_metrics(image, ROI_mask)
        
        if metrics:
            results.append({"Filename": os.path.basename(best_slice), **metrics})
            logging.info(f"Processed {best_slice} successfully.")
    except Exception as e:
        logging.error(f"Error processing {best_slice}: {e}", exc_info=True)
    
    if not results:
        logging.warning("No metrics were extracted. Ensure that the DICOM files are valid.")
        return
    
    # Convert to Pandas DataFrame and apply formatting only when saving
    df = pd.DataFrame(results)
    df.to_excel(output_excel, index=False, float_format="%.2f")  # Format numbers in Excel
    print(f"Metrics saved to {output_excel}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process MRI DICOM images in a directory')
    parser.add_argument('input_directory', type=str, help='Path to the DICOM directory')
    parser.add_argument('--output', type=str, default='output_metrics.xlsx', help='Output Excel file')
    args = parser.parse_args()
    
    configure_logging()
    process_directory(args.input_directory, args.output)
