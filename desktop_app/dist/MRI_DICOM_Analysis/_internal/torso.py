#!/usr/bin/env python
import os
import re
import datetime
import logging
import argparse
import numpy as np
import pandas as pd
import scipy.io as sio
import pydicom
# matplotlib imports removed for desktop app
from skimage import measure, filters, morphology

# Configure logging
today_str = datetime.datetime.now().strftime("%Y_%m_%d")
log_dir = os.path.join(os.getcwd(), 'outputs')
os.makedirs(log_dir, exist_ok=True)
log_path = os.path.join(log_dir, 'torso_automation.log')
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s:%(levelname)s:%(message)s',
    filename=log_path,
    filemode='w'
)

# Constants
ELEMENT_LABELS = [
    "VAS1", "VAS2", "VAS3",
    "VPS1", "VPS2", "VPS3",
    "VAP1", "VAP2", "VAP3",
    "VPP1", "VPP2", "VPP3"
]
NOISE_AREA_MM2 = 340 * 100  # 340 cm^2 = 34000 mm^2
SIGNAL_RADIUS_MM = 3

# Helper Functions
def is_dicom_file(file_path: str) -> bool:
    try:
        with open(file_path, 'rb') as f:
            preamble = f.read(132)
            if preamble[-4:] != b'DICM':
                return False
        _ = pydicom.dcmread(file_path, stop_before_pixels=True, force=True)
        return True
    except Exception:
        return False

def load_dicom_image(file_path: str):
    ds = pydicom.dcmread(file_path)
    image = ds.pixel_array.astype(np.float64)
    pixel_spacing = get_pixel_spacing(ds)
    return image, pixel_spacing

def get_pixel_spacing(ds) -> list:
    if hasattr(ds, 'PixelSpacing') and len(ds.PixelSpacing) >= 2:
        return [float(ds.PixelSpacing[0]), float(ds.PixelSpacing[1])]
    return [1.0, 1.0]

def normalize_label(label: str) -> str:
    return re.sub(r'[^a-z]', '', label.lower())

def compute_metrics(image: np.ndarray, mask: np.ndarray):
    data = image[mask == 1]
    return float(np.max(data)), float(np.min(data)), float(np.mean(data))

def compute_snr(signal_mean: float, noise_std: float, is_individual: bool = False) -> float:
    multiplier = 0.66 if is_individual else 0.7
    return round(multiplier * signal_mean / noise_std, 1)

def compute_uniformity(signal_max: float, signal_min: float) -> float:
    denom = signal_max + signal_min
    if denom == 0:
        return 0.0
    return round(100.0 * (1 - ((signal_max - signal_min) / denom)), 1)

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

def create_circular_roi_nema_style(image, pixel_spacing, desired_area_mm2=338*100, show_plot=False):
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
    # Visualization removed for desktop app
    Y, X = np.ogrid[:height, :width]
    mask = ((X - center_x) ** 2 + (Y - center_y) ** 2) <= radius_pixels ** 2
    return mask.astype(np.uint8)

def create_central_circle_roi(image, pixel_spacing, desired_area_mm2=NOISE_AREA_MM2, show_plot=False):
    height, width = image.shape
    center_y, center_x = height // 2, width // 2
    r_mm = np.sqrt(desired_area_mm2 / np.pi)
    avg_spacing = (pixel_spacing[0] + pixel_spacing[1]) / 2
    r_pixels = r_mm / avg_spacing
    # Visualization removed for desktop app
    Y, X = np.ogrid[:height, :width]
    mask = ((X - center_x) ** 2 + (Y - center_y) ** 2) <= r_pixels ** 2
    return mask.astype(np.uint8)

def create_roi_mask(
    image: np.ndarray,
    pixel_spacing: list,
    mode: str = 'noise',
    radius_mm: int = SIGNAL_RADIUS_MM,
    area_mm2: int = NOISE_AREA_MM2,
    find_max_intensity: bool = False,
    is_individual: bool = False,
    element: str = None
) -> tuple:
    height, width = image.shape
    avg_spacing = (pixel_spacing[0] + pixel_spacing[1]) / 2

    if mode == 'signal':
        r_pixels = radius_mm / avg_spacing
    else:
        r_mm = np.sqrt(area_mm2 / np.pi)
        r_pixels = r_mm / avg_spacing

    center_y, center_x = height // 2, width // 2

    if mode == 'signal' and find_max_intensity:
        phantom_mask = image > 0
        if np.any(phantom_mask):
            masked_image = np.where(phantom_mask, image, 0)
            max_idx = np.unravel_index(np.argmax(masked_image), masked_image.shape)
            center_y, center_x = max_idx
        else:
            logging.warning("Signal fallback: no phantom detected.")

    margin = int(r_pixels) + 5
    center_x = max(margin, min(width - margin, center_x))
    center_y = max(margin, min(height - margin, center_y))

    Y, X = np.ogrid[:height, :width]
    mask = ((X - center_x) ** 2 + (Y - center_y) ** 2) <= r_pixels ** 2

    if mode == 'signal':
        logging.debug(f"Signal ROI at ({center_x}, {center_y}), radius: {r_pixels:.1f} pixels")
        data = image[mask]
        if data.size > 0:
            logging.debug(f"Signal ROI values - min: {np.min(data):.1f}, max: {np.max(data):.1f}, mean: {np.mean(data):.1f}")
    else:
        logging.debug(f"Noise ROI at center ({center_x}, {center_y}), radius: {r_pixels:.1f} pixels")
        data = image[mask]
        if data.size > 0:
            logging.debug(f"Noise ROI stats - mean: {np.mean(data):.1f}, std: {np.std(data):.1f}, min: {np.min(data):.1f}, max: {np.max(data):.1f}")

    return mask.astype(np.uint8), center_x, center_y, r_pixels

def classify_files(files: list) -> tuple:
    combined = {}
    individual = {}

    for f in files:
        try:
            ds = pydicom.dcmread(f, stop_before_pixels=True)
            series_desc = getattr(ds, "SeriesDescription", "").lower()
            coil_elem = ds.get((0x0051, 0x100F))
            coil_string = coil_elem.value if coil_elem is not None else ""

            orientation = next((ori for ori in ['tra', 'sag', 'cor'] if ori in series_desc), None)
            coil_labels = [c.strip() for c in coil_string.split(';') if c.strip()]

            # detect Norm filter from ImageType tag
            is_norm = False
            if hasattr(ds, 'ImageType'):
                types = [t.upper() for t in ds.ImageType]
                if 'NORM' in types:
                    is_norm = True

            if len(coil_labels) == 1 and coil_labels[0] in ELEMENT_LABELS:
                elem = coil_labels[0]
                ftype = 'noise' if 'noise' in series_desc or 'noise' in f.lower() else 'image'
                individual[(elem, ftype)] = f
                logging.debug(f"[Individual] {f} -> ({elem}, {ftype})")
            elif orientation:
                ftype = 'noise' if 'noise' in series_desc or 'noise' in f.lower() else 'image'
                combined[(orientation, ftype, is_norm)] = f
                logging.debug(f"[Combined] {f} -> ({orientation}, {ftype}, norm={is_norm})")
            else:
                logging.warning(f"Unclassified file: {f}")
        except Exception as e:
            logging.error(f"Error reading {f}: {e}")
    return combined, individual

def save_mat_output(results_dir: str, coil_type: str, snr_list: list, piu_list: list):
    mat_data = {
        "SNR": snr_list,
        "PIU": piu_list,
        "date": today_str,
        "coil_type": coil_type,
        "filter_used": "no_prescan"
    }
    os.makedirs(results_dir, exist_ok=True)
    mat_path = os.path.join(results_dir, f"SNR_PIU_{today_str}_{coil_type}_no_prescan.mat")
    sio.savemat(mat_path, mat_data)
    logging.info(f"Saved .mat to {mat_path}")

def process_torso_folder(folder: str) -> tuple:

    dicom_files = []
    for root, _, files in os.walk(folder):
        for f in files:
            full = os.path.join(root, f)
            if is_dicom_file(full):
                dicom_files.append(full)

    if not dicom_files:
        logging.info("No DICOM files found in folder.")
        return [], []

    combined_files, individual_files = classify_files(dicom_files)
    logging.info(f"Classified Combined keys: {list(combined_files.keys())}")
    logging.info(f"Classified Individual keys: {list(individual_files.keys())}")

    combined_results = []
    element_results = []

    # Process combined views: SNR from Norm-off images; Uniformity from Norm-on images
    for orientation in ['sag', 'tra', 'cor']:
        snr_key = (orientation, 'image', False)
        noise_key = (orientation, 'noise', False)
        uniform_key = (orientation, 'image', True)

        if snr_key not in combined_files:
            logging.warning(f"No SNR image for {orientation.upper()}, skipping.")
            continue
        if noise_key not in combined_files:
            logging.warning(f"No noise for {orientation.upper()}, skipping.")
            continue

        signal_path = combined_files[snr_key]
        noise_path = combined_files[noise_key]

        logging.info(f"Processing {orientation.upper()} combined SNR image: {signal_path}")
        signal_image, signal_spacing = load_dicom_image(signal_path)
        noise_image, noise_spacing = load_dicom_image(noise_path)

        # SNR calculation using Norm-off (signal) and noise
        sig_mask = create_circular_roi_nema_style(signal_image, signal_spacing, show_plot=False)
        noise_mask = create_central_circle_roi(noise_image, noise_spacing, show_plot=False)
        sig_mean = float(np.mean(signal_image[sig_mask == 1]))  # only for SNR
        noise_std = float(np.std(noise_image[noise_mask == 1]))
        snr = compute_snr(sig_mean, noise_std)

        # Uniformity and signal stats using Norm-on image
        if uniform_key in combined_files:
            uniform_path = combined_files[uniform_key]
            logging.info(f"Processing {orientation.upper()} combined uniformity image: {uniform_path}")
            uniform_image, uniform_spacing = load_dicom_image(uniform_path)
            u_mask = create_circular_roi_nema_style(uniform_image, uniform_spacing, show_plot=False)
            u_sig_max, u_sig_min, u_sig_mean = compute_metrics(uniform_image, u_mask)
            uniformity = compute_uniformity(u_sig_max, u_sig_min)
        else:
            logging.warning(f"No uniformity image for {orientation.upper()}, setting uniformity=0.0 and signal stats to 0.")
            uniformity = 0.0
            u_sig_max = 0.0
            u_sig_min = 0.0
            u_sig_mean = 0.0

        combined_results.append({
            'Region': orientation.upper(),
            'Signal Max': u_sig_max,
            'Signal Min': u_sig_min,
            'Signal Mean': u_sig_mean,
            'Noise SD': noise_std,
            'SNR': snr,
            'Uniformity': uniformity
        })
        logging.info(f"{orientation.upper()} - SNR: {snr}, Uniformity: {uniformity}, Max: {u_sig_max}, Min: {u_sig_min}, Mean: {u_sig_mean}")


    # Process individual elements (unchanged)
    for (elem, ftype), filepath in individual_files.items():
        if ftype != 'image':
            continue
        logging.info(f"Processing individual element {elem}: {filepath}")
        signal_image, signal_spacing = load_dicom_image(filepath)
        noise_key = (elem, 'noise')
        if noise_key not in individual_files:
            logging.warning(f"No noise for {elem}, skipping.")
            continue
        noise_image, noise_spacing = load_dicom_image(individual_files[noise_key])

        sig_mask, sig_cx, sig_cy, sig_r = create_roi_mask(
            signal_image, signal_spacing,
            mode='signal', find_max_intensity=True,
            is_individual=True, element=elem
        )
        noise_mask, noise_cx, noise_cy, noise_r = create_roi_mask(
            noise_image, noise_spacing,
            mode='noise', is_individual=True, element=elem
        )

        # Visualization removed for desktop app

        _, _, sig_mean = compute_metrics(signal_image, sig_mask)
        noise_std = float(np.std(noise_image[noise_mask == 1]))
        snr = compute_snr(sig_mean, noise_std, is_individual=True)

        element_results.append({
            'Element': elem,
            'Signal Mean': sig_mean,
            'Noise SD': noise_std,
            'SNR': snr
        })
        logging.info(f"{elem} - SNR: {snr}")

    logging.info(f"Combined Results: {combined_results}")
    logging.info(f"Element Results: {element_results}")
    return combined_results, element_results

def main():
    parser = argparse.ArgumentParser(description="Process Torso DICOM metrics")
    parser.add_argument("input_directory", type=str, help="Folder containing DICOM files")
    parser.add_argument("--output", type=str, default="torso_coil_analysis.xlsx", help="Excel output file")
    parser.add_argument("--matdir", type=str, default=None, help="Directory to save .mat files")
    args = parser.parse_args()

    logging.info(f"Starting torso analysis...")
    logging.info(f"Input directory: {args.input_directory}")
    logging.info(f"Output file: {args.output}")

    # Ensure output directory exists FIRST
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        logging.info(f"Created output directory: {output_dir}")

    try:
        combined, elements = process_torso_folder(args.input_directory)
        
        # ALWAYS create DataFrames and output file, even if empty
        if combined:
            df_combined = pd.DataFrame(combined)
            logging.info(f"Created combined DataFrame with {len(df_combined)} rows")
        else:
            # Create empty DataFrame with proper columns
            df_combined = pd.DataFrame(columns=["Region", "Signal Max", "Signal Min", "Signal Mean", "Noise SD", "SNR", "Uniformity"])
            logging.warning("No combined results found, creating empty DataFrame")
            
        if elements:
            df_elements = pd.DataFrame(elements)
            desired_order = [e for e in ELEMENT_LABELS if e in df_elements['Element'].values]
            if desired_order:
                df_elements = df_elements.set_index('Element').loc[desired_order].reset_index()
            logging.info(f"Created elements DataFrame with {len(df_elements)} rows")
        else:
            # Create empty DataFrame with proper columns
            df_elements = pd.DataFrame(columns=["Element", "Signal Mean", "Noise SD", "SNR"])
            logging.warning("No element results found, creating empty DataFrame")

        logging.info(f"Writing {len(df_combined)} combined rows and {len(df_elements)} element rows to Excel.")
        
        # ALWAYS create the Excel file
        with pd.ExcelWriter(args.output, engine="openpyxl") as writer:
            df_combined.to_excel(writer, index=False, sheet_name="Combined Views")
            df_elements.to_excel(writer, index=False, sheet_name="Individual Elements")
        
        logging.info(f"Successfully saved results to {args.output}")
        print(f"Successfully processed. Results saved to {args.output}")
        
        # Verify file was created
        if os.path.exists(args.output):
            file_size = os.path.getsize(args.output)
            logging.info(f"Output file verified: {args.output} ({file_size} bytes)")
        else:
            logging.error(f"Output file was not created: {args.output}")
            print(f"Error: Output file was not created: {args.output}")

        if args.matdir and combined:
            snr_list = [r['SNR'] for r in combined]
            piu_list = [r['Uniformity'] for r in combined]
            save_mat_output(args.matdir, 'combined', snr_list, piu_list)
        if args.matdir and elements:
            snr_list = [r['SNR'] for r in elements]
            piu_list = [0] * len(elements)
            save_mat_output(args.matdir, 'individual', snr_list, piu_list)
            
    except Exception as e:
        logging.error(f"Error in main processing: {e}")
        print(f"Error during processing: {e}")
        
        # Still try to create an empty output file
        try:
            logging.info("Creating empty output file as fallback...")
            with pd.ExcelWriter(args.output, engine="openpyxl") as writer:
                empty_combined = pd.DataFrame(columns=["Region", "Signal Max", "Signal Min", "Signal Mean", "Noise SD", "SNR", "Uniformity"])
                empty_elements = pd.DataFrame(columns=["Element", "Signal Mean", "Noise SD", "SNR"])
                empty_combined.to_excel(writer, index=False, sheet_name="Combined Views")
                empty_elements.to_excel(writer, index=False, sheet_name="Individual Elements")
            logging.info(f"Created empty fallback file: {args.output}")
            print(f"Created empty output file: {args.output}")
        except Exception as fallback_error:
            logging.error(f"Failed to create fallback file: {fallback_error}")
            print(f"Failed to create output file: {fallback_error}")
            raise

if __name__ == "__main__":
    main()
