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
from skimage import measure, filters, morphology

# --------------------------- Logging ---------------------------
def configure_logging():
    today_str = datetime.datetime.now().strftime("%Y_%m_%d")
    log_dir = os.path.join(os.getcwd(), 'outputs')
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, 'headneck_automation.log')
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s:%(levelname)s:%(message)s',
        filename=log_path,
        filemode='w'
    )

# --------------------------- Constants ---------------------------
# Head & Neck elements (10): same names as torso minus VAP3, VPP3
ELEMENT_LABELS = [
    "VAS1", "VAS2", "VAS3",
    "VPS1", "VPS2", "VPS3",
    "VAP1", "VAP2",
    "VPP1", "VPP2"
]

NOISE_AREA_MM2 = 340 * 100        # 340 cm^2 = 34000 mm^2 (noise)
NEMA_SIGNAL_AREA_MM2 = 338 * 100  # 338 cm^2 (combined signal ROI)
SIGNAL_RADIUS_MM = 3              # 3 mm individual signal radius
SNR_MULTIPLIER = 0.7              # HN uses 0.7 everywhere

# --------------------------- Helpers ---------------------------
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
    if 'RescaleSlope' in ds and 'RescaleIntercept' in ds:
        image = image * ds.RescaleSlope + ds.RescaleIntercept
    pixel_spacing = get_pixel_spacing(ds)
    return image, pixel_spacing

def get_pixel_spacing(ds) -> list:
    if hasattr(ds, 'PixelSpacing') and len(ds.PixelSpacing) >= 2:
        return [float(ds.PixelSpacing[0]), float(ds.PixelSpacing[1])]
    return [1.0, 1.0]

def compute_metrics(image: np.ndarray, mask: np.ndarray):
    data = image[mask == 1]
    if data.size == 0:
        return 0.0, 0.0, 0.0
    return float(np.max(data)), float(np.min(data)), float(np.mean(data))

def compute_snr(signal_mean: float, noise_std: float) -> float:
    if noise_std == 0:
        return 0.0
    return round(SNR_MULTIPLIER * signal_mean / noise_std, 1)

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
    largest = max(regions, key=lambda r: r.area)
    center_y, center_x = largest.centroid
    radius = np.sqrt(largest.area / np.pi)
    return int(center_y), int(center_x), int(radius)

def create_circular_roi_nema_style(image, pixel_spacing, desired_area_mm2=NEMA_SIGNAL_AREA_MM2):
    height, width = image.shape
    radius_mm = np.sqrt(desired_area_mm2 / np.pi)
    avg_spacing = (pixel_spacing[0] + pixel_spacing[1]) / 2
    radius_px = max(1, round(radius_mm / avg_spacing))
    cy, cx, obj_r = detect_circular_object(image)
    cy = min(cy + 3, height - radius_px - 1)
    radius_px = min(radius_px, max(1, obj_r - 2))
    Y, X = np.ogrid[:height, :width]
    mask = ((X - cx) ** 2 + (Y - cy) ** 2) <= radius_px ** 2
    return mask.astype(np.uint8)

def create_central_circle_roi(image, pixel_spacing, desired_area_mm2=NOISE_AREA_MM2):
    height, width = image.shape
    cy, cx = height // 2, width // 2
    r_mm = np.sqrt(desired_area_mm2 / np.pi)
    avg_spacing = (pixel_spacing[0] + pixel_spacing[1]) / 2
    r_px = max(1, int(round(r_mm / avg_spacing)))
    Y, X = np.ogrid[:height, :width]
    mask = ((X - cx) ** 2 + (Y - cy) ** 2) <= r_px ** 2
    return mask.astype(np.uint8)

def create_roi_mask(image: np.ndarray, pixel_spacing: list,
                    mode: str = 'noise',
                    radius_mm: int = SIGNAL_RADIUS_MM,
                    area_mm2: int = NOISE_AREA_MM2,
                    find_max_intensity: bool = False) -> tuple:
    height, width = image.shape
    avg_spacing = (pixel_spacing[0] + pixel_spacing[1]) / 2
    if mode == 'signal':
        r_pixels = max(1, radius_mm / avg_spacing)
    else:
        r_mm = np.sqrt(area_mm2 / np.pi)
        r_pixels = max(1, r_mm / avg_spacing)
    cy, cx = height // 2, width // 2
    if mode == 'signal' and find_max_intensity:
        phantom = image > 0
        if np.any(phantom):
            masked = np.where(phantom, image, -np.inf)
            cy, cx = np.unravel_index(np.argmax(masked), masked.shape)
    margin = int(r_pixels) + 5
    cx = max(margin, min(width - margin, cx))
    cy = max(margin, min(height - margin, cy))
    Y, X = np.ogrid[:height, :width]
    mask = ((X - cx) ** 2 + (Y - cy) ** 2) <= r_pixels ** 2
    return mask.astype(np.uint8), cx, cy, r_pixels

# --------------------------- Classification ---------------------------
def classify_files(files: list) -> tuple:
    """
    Return:
      combined[(orientation, ftype, is_norm)] = path
      individual[(elem, ftype, is_norm)] = path
    ftype: 'image' or 'noise'
    is_norm: True if ImageType contains 'NORM'
    """
    combined = {}
    individual = {}

    for f in files:
        try:
            ds = pydicom.dcmread(f, stop_before_pixels=True, force=True)
            series_desc = getattr(ds, "SeriesDescription", "")
            sdl = series_desc.lower()
            coil_elem = ds.get((0x0051, 0x100F))
            coil_string = coil_elem.value if coil_elem is not None else ""

            # skip pure black frames (HN has 2)
            try:
                arr = pydicom.dcmread(f).pixel_array
                if np.max(arr) == 0:
                    logging.info(f"Skipping black image: {f}")
                    continue
            except Exception:
                pass

            # norm flag
            is_norm = False
            if hasattr(ds, 'ImageType'):
                try:
                    types = [t.upper() for t in ds.ImageType]
                    is_norm = 'NORM' in types
                except Exception:
                    pass

            # element vs combined
            coil_labels = [c.strip() for c in coil_string.split(';') if c.strip()]
            orientation = next((ori for ori in ['tra', 'sag', 'cor'] if ori in sdl), None)

            if len(coil_labels) == 1 and coil_labels[0] in ELEMENT_LABELS:
                elem = coil_labels[0]
                ftype = 'noise' if ('noise' in sdl or 'noise' in f.lower()) else 'image'
                individual[(elem, ftype, is_norm)] = f
                logging.debug(f"[Individual] {f} -> ({elem}, {ftype}, norm={is_norm})")
            elif orientation:
                ftype = 'noise' if ('noise' in sdl or 'noise' in f.lower()) else 'image'
                combined[(orientation, ftype, is_norm)] = f
                logging.debug(f"[Combined] {f} -> ({orientation}, {ftype}, norm={is_norm})")
            else:
                logging.debug(f"Unclassified file: {f} | SeriesDescription='{series_desc}'")
        except Exception as e:
            logging.error(f"Error reading {f}: {e}")
    return combined, individual

# --------------------------- Processing ---------------------------
def process_hn_folder(folder: str) -> tuple:
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
    logging.info(f"Combined keys: {list(combined_files.keys())}")
    logging.info(f"Individual keys: {list(individual_files.keys())}")

    combined_results = []
    element_results = []

    # ----- Combined views -----
    # HN: SNR signal = normalized (is_norm=True); noise = unnormalized (False)
    for orientation in ['sag', 'tra', 'cor']:
        sig_key = (orientation, 'image', True)     # prefer normalized
        noi_key = (orientation, 'noise', False)    # prefer unnormalized
        uni_key = (orientation, 'image', True)

        if sig_key not in combined_files or noi_key not in combined_files:
            logging.warning(f"Missing SNR pair for {orientation.upper()}, skipping.")
            continue

        sig_img, sig_sp = load_dicom_image(combined_files[sig_key])
        noi_img, noi_sp = load_dicom_image(combined_files[noi_key])

        sig_mask = create_circular_roi_nema_style(sig_img, sig_sp)
        noi_mask = create_central_circle_roi(noi_img, noi_sp)
        sig_mean = float(np.mean(sig_img[sig_mask == 1]))
        noi_std  = float(np.std(noi_img[noi_mask == 1]))
        snr = compute_snr(sig_mean, noi_std)

        # Uniformity from normalized image
        if uni_key in combined_files:
            uni_img, uni_sp = load_dicom_image(combined_files[uni_key])
            u_mask = create_circular_roi_nema_style(uni_img, uni_sp)
            u_max, u_min, u_mean = compute_metrics(uni_img, u_mask)
            uniformity = compute_uniformity(u_max, u_min)
        else:
            u_max = u_min = u_mean = 0.0
            uniformity = 0.0

        combined_results.append({
            'Region': orientation.upper(),
            'Signal Max': u_max,
            'Signal Min': u_min,
            'Signal Mean': u_mean,
            'Noise SD': noi_std,
            'SNR': snr,
            'Uniformity': uniformity
        })

    # ----- Individual elements -----
    # Prefer normalized image if present, else fall back; prefer unnormalized noise.
    for el in ELEMENT_LABELS:
        img_path = individual_files.get((el, 'image', True))  # normalized
        if img_path is None:
            img_path = individual_files.get((el, 'image', False))
        noise_path = individual_files.get((el, 'noise', False))  # unnormalized preferred
        if noise_path is None:
            noise_path = individual_files.get((el, 'noise', True))

        if not img_path or not noise_path:
            logging.warning(f"Missing individual pair for {el}: image={bool(img_path)}, noise={bool(noise_path)}")
            continue

        img, sp_i = load_dicom_image(img_path)
        noi, sp_n = load_dicom_image(noise_path)

        sig_mask, *_ = create_roi_mask(img, sp_i, mode='signal', find_max_intensity=True)
        noi_mask, *_ = create_roi_mask(noi, sp_n, mode='noise')

        _, _, sig_mean = compute_metrics(img, sig_mask)
        noi_sd = float(np.std(noi[noi_mask == 1]))
        snr = compute_snr(sig_mean, noi_sd)

        element_results.append({
            'Element': el,
            'Signal Mean': sig_mean,
            'Noise SD': noi_sd,
            'SNR': snr
        })

    logging.info(f"Combined n={len(combined_results)} | Individual n={len(element_results)}")
    return combined_results, element_results

# --------------------------- CLI ---------------------------
def main():
    parser = argparse.ArgumentParser(description="Process Head & Neck DICOM metrics (HN)")
    parser.add_argument("input_directory", type=str, help="Folder containing DICOM files")
    parser.add_argument("--output", type=str, default="headneck_coil_analysis.xlsx", help="Excel output file")
    parser.add_argument("--matdir", type=str, default=None, help="Directory to save .mat files")
    args = parser.parse_args()

    configure_logging()
    logging.info(f"Starting HN analysis...")
    logging.info(f"Input directory: {args.input_directory}")
    logging.info(f"Output file: {args.output}")

    # Ensure output directory exists FIRST
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        logging.info(f"Created output directory: {output_dir}")

    try:
        combined, elements = process_hn_folder(args.input_directory)

        # ALWAYS create DataFrames and output file, even if empty
        df_combined = pd.DataFrame(combined) if combined else pd.DataFrame(
            columns=["Region", "Signal Max", "Signal Min", "Signal Mean", "Noise SD", "SNR", "Uniformity"])
        df_elements = pd.DataFrame(elements) if elements else pd.DataFrame(
            columns=["Element", "Signal Mean", "Noise SD", "SNR"])

        # Order elements like torso
        if not df_elements.empty and "Element" in df_elements:
            desired_order = [e for e in ELEMENT_LABELS if e in df_elements["Element"].values]
            if desired_order:
                df_elements = df_elements.set_index("Element").loc[desired_order].reset_index()

        with pd.ExcelWriter(args.output, engine="openpyxl") as writer:
            df_combined.to_excel(writer, index=False, sheet_name="Combined Views")
            df_elements.to_excel(writer, index=False, sheet_name="Individual Elements")

        print(f"Successfully processed. Results saved to {args.output}")

        if args.matdir and combined:
            today_str = datetime.datetime.now().strftime("%Y_%m_%d")
            os.makedirs(args.matdir, exist_ok=True)
            sio.savemat(os.path.join(args.matdir, f"SNR_PIU_{today_str}_combined_no_prescan.mat"), {
                "SNR": df_combined["SNR"].to_numpy() if "SNR" in df_combined else np.array([]),
                "PIU": df_combined["Uniformity"].to_numpy() if "Uniformity" in df_combined else np.array([]),
                "date": today_str, "coil_type": "combined", "filter_used": "no_prescan"
            })
        if args.matdir and elements:
            today_str = datetime.datetime.now().strftime("%Y_%m_%d")
            os.makedirs(args.matdir, exist_ok=True)
            sio.savemat(os.path.join(args.matdir, f"SNR_PIU_{today_str}_individual_no_prescan.mat"), {
                "SNR": df_elements["SNR"].to_numpy() if "SNR" in df_elements else np.array([]),
                "PIU": np.zeros(len(df_elements)), "date": today_str, "coil_type": "individual", "filter_used": "no_prescan"
            })

    except Exception as e:
        logging.error(f"Error in main processing: {e}")
        print(f"Error during processing: {e}")
        # still create empty output so downstream doesn't break
        try:
            with pd.ExcelWriter(args.output, engine="openpyxl") as writer:
                empty_combined = pd.DataFrame(columns=["Region", "Signal Max", "Signal Min", "Signal Mean", "Noise SD", "SNR", "Uniformity"])
                empty_elements = pd.DataFrame(columns=["Element", "Signal Mean", "Noise SD", "SNR"])
                empty_combined.to_excel(writer, index=False, sheet_name="Combined Views")
                empty_elements.to_excel(writer, index=False, sheet_name="Individual Elements")
            print(f"Created empty output file: {args.output}")
        except Exception as fallback_error:
            logging.error(f"Failed to create fallback file: {fallback_error}")
            print(f"Failed to create output file: {fallback_error}")
            raise

if __name__ == "__main__":
    main()