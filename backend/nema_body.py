#!/usr/bin/env python
import os
import pydicom
import numpy as np
import pandas as pd
import argparse
import logging
from matplotlib import pyplot as plt
from matplotlib.patches import Circle
from skimage import measure, filters, morphology
import re

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s:%(levelname)s:%(message)s',
    filename='mri_automation.log',
    filemode='w'
)

def is_dicom_file(file_path):
    """Check if a file is a valid DICOM file by reading its header."""
    try:
        with open(file_path, 'rb') as f:
            preamble = f.read(132)
            if preamble[-4:] != b'DICM':
                return False
        ds = pydicom.dcmread(file_path, stop_before_pixels=True, force=True)
        return True
    except Exception:
        return False

def parse_scan_id(name):
    """
    Parse a folder name (or filename) to extract the Type and Orientation.
    Expected to contain either "noise" or "image" and one of:
      "sag", "cor", "tra" (or "tans").
    """
    s = name.lower()
    type_ = 'Unknown'
    orientation = 'Unknown'
    if 'noise' in s:
        type_ = 'noise'
    elif 'image' in s:
        type_ = 'image'
    if 'sag' in s:
        orientation = 'Sagi'
    elif 'cor' in s:
        orientation = 'Coronal'
    elif 'tra' in s or 'tans' in s:
        orientation = 'Trans'
    logging.debug(f"Parsed '{name}' as Type: {type_}, Orientation: {orientation}")
    return type_, orientation

def load_dicom_image(file_path):
    """Load a DICOM image and return its pixel array and dataset."""
    ds = pydicom.dcmread(file_path)
    image = ds.pixel_array.astype(np.float32)
    if hasattr(ds, 'RescaleSlope') and hasattr(ds, 'RescaleIntercept'):
        image = image * ds.RescaleSlope + ds.RescaleIntercept
    logging.debug(f"Loaded image from {file_path} with shape {image.shape}")
    return image, ds

def detect_circular_object(image):
    """
    Detect the largest circular object in the image using Otsu thresholding.
    Returns the centroid (y,x) and computed radius.
    """
    threshold = filters.threshold_otsu(image)
    binary_mask = image > threshold
    binary_mask = morphology.remove_small_objects(binary_mask, min_size=500)
    labeled_mask = measure.label(binary_mask)
    regions = measure.regionprops(labeled_mask, intensity_image=image)
    if not regions:
        logging.warning("No circular object detected. Using image center as fallback.")
        return image.shape[0] // 2, image.shape[1] // 2, min(image.shape) // 4
    largest_region = max(regions, key=lambda r: r.area)
    center_y, center_x = largest_region.centroid
    radius = np.sqrt(largest_region.area / np.pi)
    return int(center_y), int(center_x), int(radius)

def create_circular_roi(image, pixel_spacing, desired_area_mm2=338 * 100):
    """
    Create a circular ROI based on a desired area (338 cm^2).
    The ROI is placed within the largest circular object detected.
    """
    height, width = image.shape
    x_spacing, y_spacing = pixel_spacing
    radius_mm = np.sqrt(desired_area_mm2 / np.pi)
    radius_pixels = max(1, round(radius_mm / x_spacing))
    center_y, center_x, object_radius = detect_circular_object(image)
    center_y = min(center_y + 3, height - radius_pixels - 1)
    radius_pixels = min(radius_pixels, object_radius - 2)
    if radius_pixels < 1:
        logging.warning("Computed ROI radius is too small, defaulting to 1 pixel.")
        radius_pixels = 1
    # Optional: visualize ROI overlay (can be commented out if not desired)
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.imshow(image, cmap='gray')
    circle = Circle((center_x, center_y), radius_pixels, color='red', fill=False, linewidth=2)
    ax.add_patch(circle)
    ax.set_title(f'ROI Overlay (Center: {center_x}, {center_y}, Radius: {radius_pixels} px)')
    plt.axis('off')
    plt.close(fig)
    Y, X = np.ogrid[:height, :width]
    mask = ((X - center_x) ** 2 + (Y - center_y) ** 2) <= radius_pixels ** 2
    return mask.astype(np.uint8)

def compute_metrics(image, use_roi, pixel_spacing):
    """
    Compute metrics from the image.
      - For 'image' files, apply a circular ROI.
      - For 'noise' files, use the entire image.
    Returns a dictionary with Mean, Min, Max, Sum, and StDev.
    """
    if use_roi:
        roi_mask = create_circular_roi(image, pixel_spacing)
        data = image[roi_mask == 1]
    else:
        data = image.ravel()
    mean_val = float(np.mean(data))
    min_val = float(np.min(data))
    max_val = float(np.max(data))
    sum_val = float(np.sum(data))
    stdev_val = float(np.std(data))
    return {
        "Mean": round(mean_val, 4),
        "Min": round(min_val, 4),
        "Max": round(max_val, 4),
        "Sum": round(sum_val, 4),
        "StDev": round(stdev_val, 4)
    }

def process_directory(input_directory):
    """
    Process the input directory.
    If it contains subdirectories, process each subdirectory as a separate scan.
    Otherwise, process files directly in the directory.
    Returns a list of result dictionaries.
    """
    image_data = {}
    noise_data = {}
    found_subfolders = False

    # Process subdirectories if they exist
    for item in os.listdir(input_directory):
        item_path = os.path.join(input_directory, item)
        if os.path.isdir(item_path):
            found_subfolders = True
            type_, orientation = parse_scan_id(item)
            if orientation == 'Unknown' or type_ == 'Unknown':
                logging.warning(f"Subfolder '{item}' does not follow expected naming. Skipping.")
                continue
            dicom_files = [f for f in os.listdir(item_path) if is_dicom_file(os.path.join(item_path, f))]
            if not dicom_files:
                logging.warning(f"No DICOM files found in {item_path}. Skipping.")
                continue
            dicom_file = dicom_files[0]
            dicom_path = os.path.join(item_path, dicom_file)
            try:
                image, ds = load_dicom_image(dicom_path)
            except Exception as e:
                logging.error(f"Error loading file '{dicom_path}': {e}", exc_info=True)
                continue
            use_roi = (type_.lower() == 'image')
            if hasattr(ds, 'PixelSpacing') and len(ds.PixelSpacing) >= 2:
                pixel_spacing = [float(ds.PixelSpacing[0]), float(ds.PixelSpacing[1])]
            else:
                pixel_spacing = [1.0, 1.0]
            metrics = compute_metrics(image, use_roi, pixel_spacing)
            slice_number = getattr(ds, 'InstanceNumber', 1)
            row = {
                "ScanID": item,
                "Orientation": orientation,
                "Type": type_,
                "Mean": metrics["Mean"],
                "Min": metrics["Min"],
                "Max": metrics["Max"],
                "Sum": metrics["Sum"],
                "StDev": metrics["StDev"],
                "Filename": dicom_file,
                "Slice": slice_number
            }
            if type_.lower() == 'image':
                image_data[orientation] = row
            elif type_.lower() == 'noise':
                noise_data[orientation] = row
            logging.info(f"Processed subfolder '{item}' successfully.")

    # If no subdirectories were found, process files directly in the input directory
    if not found_subfolders:
        for file in os.listdir(input_directory):
            file_path = os.path.join(input_directory, file)
            if not os.path.isfile(file_path):
                continue
            if not is_dicom_file(file_path):
                continue
            type_, orientation = parse_scan_id(file)
            if orientation == 'Unknown' or type_ == 'Unknown':
                logging.warning(f"File '{file}' does not follow expected naming. Skipping.")
                continue
            try:
                image, ds = load_dicom_image(file_path)
            except Exception as e:
                logging.error(f"Error loading file '{file_path}': {e}", exc_info=True)
                continue
            use_roi = (type_.lower() == 'image')
            if hasattr(ds, 'PixelSpacing') and len(ds.PixelSpacing) >= 2:
                pixel_spacing = [float(ds.PixelSpacing[0]), float(ds.PixelSpacing[1])]
            else:
                pixel_spacing = [1.0, 1.0]
            metrics = compute_metrics(image, use_roi, pixel_spacing)
            slice_number = getattr(ds, 'InstanceNumber', 1)
            row = {
                "ScanID": file,
                "Orientation": orientation,
                "Type": type_,
                "Mean": metrics["Mean"],
                "Min": metrics["Min"],
                "Max": metrics["Max"],
                "Sum": metrics["Sum"],
                "StDev": metrics["StDev"],
                "Filename": file,
                "Slice": slice_number
            }
            if type_.lower() == 'image':
                image_data.setdefault(orientation, []).append(row)
            elif type_.lower() == 'noise':
                noise_data.setdefault(orientation, []).append(row)
            logging.info(f"Processed file '{file}' successfully.")

        # For direct files, if multiple rows per orientation exist, take the first one for pairing.
        paired_results = []
        for orientation, rows in image_data.items():
            image_row = rows[0]
            if orientation in noise_data and noise_data[orientation]:
                noise_row = noise_data[orientation][0]
                Mean_image = image_row["Mean"]
                StdDev_noise = noise_row["StDev"]
                snr = 0.66 * (Mean_image / StdDev_noise) if StdDev_noise != 0 else 0.0
                Max_image = image_row["Max"]
                Min_image = image_row["Min"]
                piu = 100.0 * (1 - ((Max_image - Min_image) / (Max_image + Min_image))) if (Max_image + Min_image) != 0 else 0.0
                image_row["SNR"] = round(snr, 2)
                image_row["PIU"] = round(piu, 2)
            paired_results.append(image_row)
        for orientation, rows in noise_data.items():
            paired_results.extend(rows)
        return paired_results

    # For subfolder case, pair image and noise by orientation as before.
    paired_results = []
    for orientation, image_row in image_data.items():
        if orientation in noise_data:
            noise_row = noise_data[orientation]
            Mean_image = image_row["Mean"]
            StdDev_noise = noise_row["StDev"]
            snr = 0.66 * (Mean_image / StdDev_noise) if StdDev_noise != 0 else 0.0
            Max_image = image_row["Max"]
            Min_image = image_row["Min"]
            piu = 100.0 * (1 - ((Max_image - Min_image) / (Max_image + Min_image))) if (Max_image + Min_image) != 0 else 0.0
            image_row["SNR"] = round(snr, 2)
            image_row["PIU"] = round(piu, 2)
        paired_results.append(image_row)
    for orientation, noise_row in noise_data.items():
        paired_results.append(noise_row)
    return paired_results

def main():
    parser = argparse.ArgumentParser(description="Process NEMA Body DICOM Metrics")
    parser.add_argument("input_directory", type=str, help="Folder containing subfolders or files with DICOM files")
    parser.add_argument("--output", type=str, default="nema_body_metrics.xlsx", help="Output Excel file name")
    args = parser.parse_args()
    results = process_directory(args.input_directory)
    if results:
        df = pd.DataFrame(results)
        df.to_excel(args.output, index=False)
        print(f"Metrics saved to {args.output}")
    else:
        print("No results to save. Please check the input directory structure.")

if __name__ == "__main__":
    main()
