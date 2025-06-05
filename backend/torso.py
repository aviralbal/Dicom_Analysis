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
from matplotlib import pyplot as plt
from skimage import morphology

# Configure logging
today_str = datetime.datetime.now().strftime("%Y_%m_%d")
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s:%(levelname)s:%(message)s',
    filename='torso_automation.log',
    filemode='w'
)

# Constants
ELEMENT_LABELS = ["VAS1", "VAS2", "VAS3", "VPS1", "VPS2", "VPS3", "VAP1", "VAP2", "VAP3", "VPP1", "VPP2", "VPP3"]
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
        r_mm = (area_mm2 / np.pi) ** 0.5
        r_pixels = r_mm / avg_spacing

    # Default center
    center_y, center_x = height // 2, width // 2

    if mode == 'signal' and find_max_intensity:
        # For individual elements: find the absolute maximum within phantom (non-zero)
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

            if len(coil_labels) == 1 and coil_labels[0] in ELEMENT_LABELS:
                elem = coil_labels[0]
                ftype = 'noise' if 'noise' in series_desc or 'noise' in f.lower() else 'image'
                individual[(elem, ftype)] = f
                logging.debug(f"[Individual] {f} -> ({elem}, {ftype})")
            elif orientation:
                ftype = 'noise' if 'noise' in series_desc or 'noise' in f.lower() else 'image'
                combined[(orientation, ftype)] = f
                logging.debug(f"[Combined] {f} -> ({orientation}, {ftype})")
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
    vis_dir = os.path.join(folder, 'visualizations')
    os.makedirs(vis_dir, exist_ok=True)

    dicom_files = []
    for root, _, files in os.walk(folder):
        for f in files:
            full = os.path.join(root, f)
            if is_dicom_file(full):
                dicom_files.append(full)

    if not dicom_files:
        logging.error("No DICOM files found in folder.")
        return [], []

    combined_files, individual_files = classify_files(dicom_files)
    logging.info(f"Classified Combined: {list(combined_files.keys())}")
    logging.info(f"Classified Individual: {list(individual_files.keys())}")

    combined_results = []
    element_results = []

    for (orientation, ftype), filepath in combined_files.items():
        if ftype != 'image':
            continue
        logging.info(f"Processing {orientation.upper()} combined image: {filepath}")
        signal_image, signal_spacing = load_dicom_image(filepath)
        noise_key = (orientation, 'noise')
        if noise_key not in combined_files:
            logging.warning(f"No noise for {orientation}, skipping.")
            continue
        noise_image, noise_spacing = load_dicom_image(combined_files[noise_key])

        # For combined (SAG, COR, TRA), use 340 cm² circle centered in the image for both signal and noise
        sig_mask, sig_cx, sig_cy, sig_r = create_roi_mask(signal_image, signal_spacing, mode='noise')
        noise_mask, noise_cx, noise_cy, noise_r = create_roi_mask(noise_image, noise_spacing, mode='noise')

        # Display and save signal ROI
        plt.figure()
        plt.imshow(signal_image, cmap='gray')
        circle = plt.Circle((sig_cx, sig_cy), sig_r, color='r', fill=False, linewidth=2)
        plt.gca().add_patch(circle)
        plt.title(f"Signal ROI {orientation.upper()}")
        plt.axis('off')
        plt.show()
        vis_path_sig = os.path.join(vis_dir, f"{orientation}_signal_roi.png")
        plt.savefig(vis_path_sig, bbox_inches='tight')
        plt.close()

        # Display and save noise ROI
        plt.figure()
        plt.imshow(noise_image, cmap='gray')
        circle_n = plt.Circle((noise_cx, noise_cy), noise_r, color='b', fill=False, linewidth=2)
        plt.gca().add_patch(circle_n)
        plt.title(f"Noise ROI {orientation.upper()}")
        plt.axis('off')
        plt.show()
        vis_path_noise = os.path.join(vis_dir, f"{orientation}_noise_roi.png")
        plt.savefig(vis_path_noise, bbox_inches='tight')
        plt.close()

        sig_max, sig_min, sig_mean = compute_metrics(signal_image, sig_mask)
        _, _, noise_mean = compute_metrics(noise_image, noise_mask)
        noise_std = float(np.std(noise_image[noise_mask == 1]))

        snr = compute_snr(sig_mean, noise_std)
        uniformity = compute_uniformity(sig_max, sig_min)

        combined_results.append({
            'Region': orientation.upper(),
            'Signal Max': sig_max,
            'Signal Min': sig_min,
            'SNR': snr,
            'Uniformity': uniformity
        })
        logging.info(f"{orientation.upper()} - SNR: {snr}, Uniformity: {uniformity}")

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

        # For individual, place 3 cm ROI at max intensity
        sig_mask, sig_cx, sig_cy, sig_r = create_roi_mask(signal_image, signal_spacing, mode='signal', find_max_intensity=True, is_individual=True, element=elem)
        noise_mask, noise_cx, noise_cy, noise_r = create_roi_mask(noise_image, noise_spacing, mode='noise', is_individual=True, element=elem)

        # Display and save signal ROI
        plt.figure()
        plt.imshow(signal_image, cmap='gray')
        circle_elem = plt.Circle((sig_cx, sig_cy), sig_r, color='r', fill=False, linewidth=2)
        plt.gca().add_patch(circle_elem)
        plt.title(f"Signal ROI {elem}")
        plt.axis('off')
        plt.show()
        vis_path_sig_elem = os.path.join(vis_dir, f"{elem}_signal_roi.png")
        plt.savefig(vis_path_sig_elem, bbox_inches='tight')
        plt.close()

        # Display and save noise ROI
        plt.figure()
        plt.imshow(noise_image, cmap='gray')
        circle_noise_elem = plt.Circle((noise_cx, noise_cy), noise_r, color='b', fill=False, linewidth=2)
        plt.gca().add_patch(circle_noise_elem)
        plt.title(f"Noise ROI {elem}")
        plt.axis('off')
        plt.show()
        vis_path_noise_elem = os.path.join(vis_dir, f"{elem}_noise_roi.png")
        plt.savefig(vis_path_noise_elem, bbox_inches='tight')
        plt.close()

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

    combined, elements = process_torso_folder(args.input_directory)
    df_combined = pd.DataFrame(combined)
    df_elements = pd.DataFrame(elements)
    # Reorder individual elements according to ELEMENT_LABELS
    desired_order = [e for e in ELEMENT_LABELS if e in df_elements['Element'].values]
    df_elements = df_elements.set_index('Element').loc[desired_order].reset_index()

    logging.info(f"Writing {len(df_combined)} combined rows and {len(df_elements)} element rows to Excel.")

    with pd.ExcelWriter(args.output, engine="xlsxwriter") as writer:
        df_combined.to_excel(writer, index=False, sheet_name="Combined Views")
        df_elements.to_excel(writer, index=False, sheet_name="Individual Elements")

    logging.info(f"Saved results to {args.output}")

    if args.matdir and combined:
        snr_list = [r['SNR'] for r in combined]
        piu_list = [r['Uniformity'] for r in combined]
        save_mat_output(args.matdir, 'combined', snr_list, piu_list)
    if args.matdir and elements:
        snr_list = [r['SNR'] for r in elements]
        piu_list = [0] * len(elements)
        save_mat_output(args.matdir, 'individual', snr_list, piu_list)

    print(f"Saved results to {args.output}")

if __name__ == "__main__":
    main()
