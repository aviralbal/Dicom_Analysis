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

def detect_circular_object(image):
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
    height, width = image.shape
    x_spacing, y_spacing = pixel_spacing
    radius_mm = np.sqrt(desired_area_mm2 / np.pi)
    radius_pixels = max(1, round(radius_mm / x_spacing))

    # Detect the actual circular object
    center_y, center_x, object_radius = detect_circular_object(image)

    center_y = min(center_y + 2.5, height - radius_pixels - 1)

    # Adjust ROI size if it's exceeding detected object size
    radius_pixels = min(radius_pixels, object_radius - 2)  

    # Ensure the ROI remains fully inside the detected object
    if radius_pixels < 1:
        logging.warning("Computed radius is too small, defaulting to minimum 1 pixel.")
        radius_pixels = 1

    Y, X = np.ogrid[:height, :width]
    mask = ((X - center_x) ** 2 + (Y - center_y) ** 2) <= radius_pixels ** 2

    print(f"ROI Debug -> Center: ({center_x}, {center_y}), Radius: {radius_pixels} pixels")

    # **Visualize and Save ROI Overlay**
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
    
    # Save visualization
    save_path = "outputs/roi_overlay.png"
    plt.savefig(save_path, bbox_inches='tight', dpi=300)
    print(f"ROI visualization saved as: {save_path}")

    plt.show()

def compute_metrics(image, ROI_mask):
    signal_values = image[ROI_mask == 1]
    if signal_values.size == 0:
        logging.warning("ROI is empty or incorrectly applied.")
        return None

    metrics = {
        "Mean": round(np.mean(signal_values), 2),
        "Min": round(np.min(signal_values), 2),
        "Max": round(np.max(signal_values), 2),
        "Sum": round(np.sum(signal_values), 2),
        "StDev": round(np.std(signal_values), 2),
        "SNR": round(np.mean(signal_values) / np.std(signal_values), 2) if np.std(signal_values) != 0 else 0,
        "PIU": round(100 * (1 - ((np.max(signal_values) - np.min(signal_values)) / (np.max(signal_values) + np.min(signal_values)))), 2) if (np.max(signal_values) + np.min(signal_values)) != 0 else 0
    }
    
    return metrics

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
        ROI_mask = create_circular_roi(image, pixel_spacing)
        metrics = compute_metrics(image, ROI_mask)
        
        if metrics:
            results.append({"Filename": os.path.basename(best_slice), **metrics})
            logging.info(f"Processed {best_slice} successfully.")
    except Exception as e:
        logging.error(f"Error processing {best_slice}: {e}", exc_info=True)
    
    if not results:
        logging.warning("No metrics were extracted. Ensure that the DICOM files are valid.")
        return
    
    # Convert to Pandas DataFrame and round all values to 2 decimal places
    df = pd.DataFrame(results).round(2)
    df.to_excel(output_excel, index=False)
    print(f"Metrics saved to {output_excel}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process MRI DICOM images in a directory')
    parser.add_argument('input_directory', type=str, help='Path to the DICOM directory')
    parser.add_argument('--output', type=str, default='output_metrics.xlsx', help='Output Excel file')
    args = parser.parse_args()
    
    configure_logging()
    process_directory(args.input_directory, args.output)
