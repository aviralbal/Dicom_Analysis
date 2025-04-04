import os
import pydicom
import numpy as np
import pandas as pd
import argparse
import logging
from matplotlib import pyplot as plt
from matplotlib.patches import Circle
from skimage import measure, filters, morphology

# Configure logging
logging.basicConfig(
    filename='mri_automation.log',
    filemode='w',  # Overwrite the log file each time
    level=logging.DEBUG,
    format='%(asctime)s:%(levelname)s:%(message)s'
)

def is_dicom_file(file_path):
    """
    Check if a file is a valid DICOM file by reading its header.
    """
    try:
        with open(file_path, 'rb') as f:
            preamble = f.read(132)
            if preamble[-4:] != b'DICM':
                return False
        ds = pydicom.dcmread(file_path, stop_before_pixels=True, force=True)
        return True
    except Exception:
        return False

def parse_scan_id(scan_id):
    """
    Parse the subfolder name (ScanID) to extract the Type and Orientation.
    Expected subfolder names end with:
      - noise_sag, noise_trans, noise_cor
      - image_sag, image_trans, image_cor
    Returns:
        type_ (str): 'noise' or 'image' (or 'Unknown')
        orientation (str): 'Sagi', 'Trans', or 'Coronal' (or 'Unknown')
    """
    s = scan_id.lower()
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
    elif 'tra' in s or 'tans' in s:  # accommodate possible typo "tans"
        orientation = 'Trans'
    
    logging.debug(f"Parsed ScanID '{scan_id}' as Type: {type_}, Orientation: {orientation}")
    return type_, orientation

def load_dicom_image(file_path):
    """
    Load a DICOM image and return its pixel array and dataset.
    """
    try:
        ds = pydicom.dcmread(file_path)
        image = ds.pixel_array.astype(np.float32)
        if hasattr(ds, 'RescaleSlope') and hasattr(ds, 'RescaleIntercept'):
            image = image * ds.RescaleSlope + ds.RescaleIntercept
        logging.debug(f"Loaded image from {file_path} with shape {image.shape}")
        return image, ds
    except Exception as e:
        logging.error(f"Failed to load DICOM file {file_path}: {e}", exc_info=True)
        raise e

def detect_circular_object(image):
    """
    Detect the largest circular object in the image using Otsu thresholding.
    Returns center_y, center_x, radius (in pixels).
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
    
    # Detect the largest circular object for better centering
    center_y, center_x, object_radius = detect_circular_object(image)
    center_y = min(center_y + 3, height - radius_pixels - 1)
    radius_pixels = min(radius_pixels, object_radius - 2)
    if radius_pixels < 1:
        logging.warning("Computed ROI radius is too small, defaulting to 1 pixel.")
        radius_pixels = 1
    
    Y, X = np.ogrid[:height, :width]
    mask = ((X - center_x) ** 2 + (Y - center_y) ** 2) <= radius_pixels ** 2
    
    # Optional visualization
    visualize_roi(image, center_x, center_y, radius_pixels)
    
    return mask.astype(np.uint8)

def visualize_roi(image, center_x, center_y, radius_pixels):
    """
    Display and save the image with ROI overlay.
    """
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.imshow(image, cmap='gray')
    circle = Circle((center_x, center_y), radius_pixels, color='red', fill=False, linewidth=2)
    ax.add_patch(circle)
    ax.set_title(f'ROI Overlay (Center: {center_x}, {center_y}, Radius: {radius_pixels} px)')
    plt.axis('off')
    
    save_path = "roi_overlay.png"
    plt.savefig(save_path, bbox_inches='tight', dpi=300)
    print(f"ROI visualization saved as: {save_path}")
    plt.close(fig)

def compute_metrics(image, use_roi, pixel_spacing):
    """
    Compute metrics from the image.
      - For image files (use_roi=True): a circular ROI is applied.
      - For noise files (use_roi=False): the entire image is used.
    Then computes:
      Mean, Min, Max, Sum, StDev
      (SNR and PIU are assigned later only for image subfolders).
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

def process_directory_separately(input_directory, output_excel):
    """
    Process each subfolder independently.
    For each subfolder:
      - Determine type and orientation from the folder name.
      - Load the first valid DICOM file.
      - For 'image' type: compute metrics using a circular ROI.
        Then later compute SNR & PIU by pairing with the corresponding noise subfolder:
          SNR = 0.66 * (Mean_image / StdDev_noise)
          PIU = 100 * (1 - ((Max_image - Min_image) / (Max_image + Min_image)))
        where for pairing, noise metrics are taken from the noise subfolder of the same orientation.
      - For 'noise' type: compute metrics from the entire image,
        but do NOT display SNR and PIU.
    """
    image_data = {}
    noise_data = {}
    
    for subfolder in os.listdir(input_directory):
        subfolder_path = os.path.join(input_directory, subfolder)
        if not os.path.isdir(subfolder_path):
            continue
        
        type_, orientation = parse_scan_id(subfolder)
        if orientation == 'Unknown' or type_ == 'Unknown':
            logging.warning(f"Subfolder '{subfolder}' does not follow expected naming. Skipping.")
            continue
        
        # Get first valid DICOM file in this subfolder
        dicom_files = [f for f in os.listdir(subfolder_path)
                       if is_dicom_file(os.path.join(subfolder_path, f))]
        if not dicom_files:
            logging.warning(f"No DICOM files found in {subfolder_path}. Skipping.")
            continue
        dicom_file = dicom_files[0]
        dicom_path = os.path.join(subfolder_path, dicom_file)
        
        try:
            image, ds = load_dicom_image(dicom_path)
        except Exception as e:
            logging.error(f"Error loading file '{dicom_path}': {e}", exc_info=True)
            continue
        
        # Decide if we apply ROI: for 'image' type we do, for 'noise' type we don't.
        use_roi = (type_.lower() == 'image')
        if hasattr(ds, 'PixelSpacing') and len(ds.PixelSpacing) >= 2:
            pixel_spacing = [float(ds.PixelSpacing[0]), float(ds.PixelSpacing[1])]
        else:
            pixel_spacing = [1.0, 1.0]
        
        metrics = compute_metrics(image, use_roi, pixel_spacing)
        # Get slice number from DICOM header if available, default to 1
        slice_number = getattr(ds, 'InstanceNumber', 1)
        
        # Prepare row of metrics
        row = {
            "ScanID": subfolder,
            "Orientation": orientation,
            "Type": type_,
            "Mean": metrics["Mean"],
            "Min": metrics["Min"],
            "Max": metrics["Max"],
            "Sum": metrics["Sum"],
            "StDev": metrics["StDev"],
            "Filename": dicom_file,
            "Slice": slice_number,
            "SNR": "",
            "PIU": ""
        }
        
        # Instead of computing SNR/PIU immediately for image type, store rows separately.
        if type_.lower() == 'image':
            image_data[orientation] = row
        elif type_.lower() == 'noise':
            noise_data[orientation] = row
        
        logging.info(f"Processed '{subfolder}' successfully.")
    
    # Now, pair image and noise by orientation for computing SNR & PIU.
    paired_results = []
    for orientation, image_row in image_data.items():
        if orientation in noise_data:
            noise_row = noise_data[orientation]
            # Use the image's Mean and the noise's StDev for SNR:
            Mean_image = image_row["Mean"]
            StdDev_noise = noise_row["StDev"]
            
            if StdDev_noise != 0:
                snr = 0.66 * (Mean_image / StdDev_noise)
            else:
                snr = 0.0
            
            # Use the image's Max and Min for PIU:
            Max_image = image_row["Max"]
            Min_image = image_row["Min"]
            if (Max_image + Min_image) != 0:
                piu = 100.0 * (1 - ((Max_image - Min_image) / (Max_image + Min_image)))
            else:
                piu = 0.0
            
            image_row["SNR"] = round(snr, 2)
            image_row["PIU"] = round(piu, 2)
        else:
            logging.warning(f"No corresponding noise metrics found for orientation {orientation}. SNR and PIU not computed for this image folder.")
        paired_results.append(image_row)
    
    # Optionally include noise folder rows as well (without SNR/PIU)
    for orientation, noise_row in noise_data.items():
        paired_results.append(noise_row)
    
    if paired_results:
        df = pd.DataFrame(paired_results)
        df.to_excel(output_excel, index=False)
        print(f"Metrics saved to {output_excel}")
    else:
        logging.warning("No results to save. Please check the input directory structure.")

def main():
    parser = argparse.ArgumentParser(description='Process each subfolder separately for DICOM metrics')
    parser.add_argument('input_directory', type=str, help='Main directory containing subfolders with DICOM files')
    parser.add_argument('--output', type=str, default='separate_metrics.xlsx', help='Output Excel file name')
    args = parser.parse_args()

    try:
        process_directory_separately(args.input_directory, args.output)
    except Exception as e:
        logging.critical(f"Script terminated due to error: {e}", exc_info=True)
        print(f"Script terminated due to error: {e}")

if __name__ == "__main__":
    main()
