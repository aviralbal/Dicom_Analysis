#!/usr/bin/env python
import os
import datetime
import logging
import argparse
import numpy as np
import pandas as pd
import pydicom
from skimage import measure, filters, morphology

# Configure logging
def configure_logging():
    log_dir = os.path.join(os.getcwd(), 'outputs')
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, 'headneck_automation.log')
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
    "VAP1", "VAP2",
    "VPP1", "VPP2"
]
NOISE_AREA_MM2 = 335 * 100  # 335 cm^2
SIGNAL_RADIUS_MM = 3       # radius in mm for ~3 cm^2 area
SNR_MULTIPLIER = 0.7       # fixed for head/neck analysis

# Helper functions
def is_dicom_file(path: str) -> bool:
    try:
        with open(path, 'rb') as f:
            if f.read(132)[-4:] != b'DICM':
                return False
        pydicom.dcmread(path, stop_before_pixels=True, force=True)
        return True
    except Exception:
        return False


def load_image(path: str):
    ds = pydicom.dcmread(path)
    img = ds.pixel_array.astype(np.float64)
    if 'RescaleSlope' in ds and 'RescaleIntercept' in ds:
        img = img * ds.RescaleSlope + ds.RescaleIntercept
    spacing = getattr(ds, 'PixelSpacing', [1.0, 1.0])
    return img, [float(spacing[0]), float(spacing[1])]


def detect_phantom_center(image):
    thresh = filters.threshold_otsu(image)
    mask = image > thresh
    mask = morphology.remove_small_objects(mask, min_size=500)
    labeled = measure.label(mask)
    regs = measure.regionprops(labeled, intensity_image=image)
    if not regs:
        h, w = image.shape
        return h//2, w//2, min(h, w)//4
    reg = max(regs, key=lambda r: r.area)
    cy, cx = reg.centroid
    rad = np.sqrt(reg.area / np.pi)
    return int(cy), int(cx), int(rad)


def make_combined_signal_roi(img, spacing):
    h, w = img.shape
    cy, cx, _ = detect_phantom_center(img)
    r_mm = SIGNAL_RADIUS_MM
    r_px = max(1, int(round(r_mm / spacing[0])))
    Y, X = np.ogrid[:h, :w]
    mask = ((X - cx)**2 + (Y - cy)**2) <= r_px**2
    return mask


def make_combined_noise_roi(img, spacing):
    h, w = img.shape
    cy, cx = h//2, w//2
    r_mm = np.sqrt(NOISE_AREA_MM2 / np.pi)
    avg_sp = (spacing[0] + spacing[1]) / 2
    r_px = max(1, int(round(r_mm / avg_sp)))
    Y, X = np.ogrid[:h, :w]
    mask = ((X - cx)**2 + (Y - cy)**2) <= r_px**2
    return mask


def compute_snr(sig_mean: float, noise_std: float) -> float:
    return round(SNR_MULTIPLIER * sig_mean / noise_std, 1) if noise_std else 0.0


def classify_files(files: list):
    combined = {}
    individual = {}
    for f in files:
        try:
            ds = pydicom.dcmread(f, stop_before_pixels=True, force=True)
            desc = getattr(ds, 'SeriesDescription', '').lower()
            coil_elem = ds.get((0x0051, 0x100F))
            labels = []
            if coil_elem:
                labels = [c.strip() for c in coil_elem.value.split(';') if c.strip()]
            # detect norm
            is_norm = False
            if hasattr(ds, 'ImageType') and 'NORM' in [t.upper() for t in ds.ImageType]:
                is_norm = True
            # individual elements
            if len(labels) == 1 and labels[0] in ELEMENT_LABELS:
                el = labels[0]
                ftype = 'noise' if 'noise' in desc else 'image'
                individual[(el, ftype)] = f
                continue
            # combined
            ori = next((o for o in ['sag', 'tra', 'cor'] if o in desc), None)
            if ori:
                ftype = 'noise' if 'noise' in desc else 'image'
                combined[(ori, ftype, is_norm)] = f
        except Exception as e:
            logging.error(f"Classification error for {f}: {e}")
    return combined, individual


def process_hn_folder(folder: str):
    paths = []
    for root, _, files in os.walk(folder):
        for name in files:
            full = os.path.join(root, name)
            if is_dicom_file(full):
                paths.append(full)
    logging.info(f"Found {len(paths)} DICOM files")

    comb, indiv = classify_files(paths)
    results_comb = []
    # combined SNR & uniformity
    for ori in ['sag', 'tra', 'cor']:
        key_sig = (ori, 'image', False)
        key_noi = (ori, 'noise', False)
        key_uni = (ori, 'image', True)
        if key_sig in comb and key_noi in comb:
            sig, sp_s = load_image(comb[key_sig])
            noi, sp_n = load_image(comb[key_noi])
            mask_s = make_combined_signal_roi(sig, sp_s)
            mask_n = make_combined_noise_roi(noi, sp_n)
            mean_s = float(np.mean(sig[mask_s]))
            std_n = float(np.std(noi[mask_n]))
            snr = compute_snr(mean_s, std_n)
            # compute uniformity
            if key_uni in comb:
                uni, sp_u = load_image(comb[key_uni])
                mask_u = make_combined_signal_roi(uni, sp_u)
                props = measure.regionprops(measure.label(mask_u), intensity_image=uni)
                if props:
                    reg0 = props[0]
                    mx = float(reg0.max_intensity)
                    mn = float(reg0.min_intensity)
                else:
                    mx = float(np.max(uni[mask_u]))
                    mn = float(np.min(uni[mask_u]))
                uni_pct = round(100.0 * (1 - ((mx - mn) / (mx + mn))), 1) if (mx + mn) else 0.0
            else:
                mx = mn = 0.0
                uni_pct = 0.0
            results_comb.append({
                'Region': ori.upper(),
                'Signal Max': round(mx, 1),
                'Signal Min': round(mn, 1),
                'Signal Mean': round(mean_s, 1),
                'Noise SD': round(std_n, 1),
                'SNR': snr,
                'Uniformity': uni_pct
            })
    # individual elements
    results_ind = []
    for el in ELEMENT_LABELS:
        key_i = (el, 'image')
        key_n = (el, 'noise')
        if key_i in indiv and key_n in indiv:
            img, sp_i = load_image(indiv[key_i])
            noi, sp_n = load_image(indiv[key_n])
            mask_i = make_combined_noise_roi(img, sp_i)
            mask_n = make_combined_noise_roi(noi, sp_n)
            m_i = float(np.mean(img[mask_i]))
            s_n = float(np.std(noi[mask_n]))
            snr = compute_snr(m_i, s_n)
            results_ind.append({
                'Element': el,
                'Signal Mean': round(m_i, 1),
                'Noise SD': round(s_n, 1),
                'SNR': snr
            })
    return results_comb, results_ind


def main():
    parser = argparse.ArgumentParser(description="Head & Neck SNR Analysis")
    parser.add_argument('input_dir', help='Root folder of DICOM files')
    parser.add_argument('--output', default='headneck_analysis.xlsx', help='Excel output file')
    args = parser.parse_args()

    configure_logging()
    logging.info("Starting Head & Neck processing...")
    results_comb, results_ind = process_hn_folder(args.input_dir)

    df_comb = pd.DataFrame(results_comb)
    df_ind = pd.DataFrame(results_ind)
    with pd.ExcelWriter(args.output, engine='openpyxl') as writer:
        df_comb.to_excel(writer, index=False, sheet_name='Combined Views')
        df_ind.to_excel(writer, index=False, sheet_name='Individual Elements')
    print(f"Saved results to {args.output} (Combined: {len(results_comb)} rows, Individual: {len(results_ind)} rows)")

if __name__ == '__main__':
    main()
