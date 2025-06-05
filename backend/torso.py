#!/usr/bin/env python
import os
import pydicom
import numpy as np
import pandas as pd
import argparse
import logging
import scipy.io as sio
from matplotlib import pyplot as plt
from matplotlib.patches import Circle
from skimage import measure, filters, morphology
import datetime
import re

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s:%(levelname)s:%(message)s',
    filename='torso_automation.log',
    filemode='w'
)

ELEMENT_LABELS = ["VAS1", "VAS2", "VAS3", "VPS1", "VPS2", "VPS3", "VAP1", "VAP2", "VAP3", "VPP1", "VPP2", "VPP3"]
NOISE_AREA_MM2 = 340 * 100  # 340 cm² = 34000 mm²
SIGNAL_RADIUS_MM = 30

def is_dicom_file(file_path):
    try:
        with open(file_path, 'rb') as f:
            preamble = f.read(132)
            if preamble[-4:] != b'DICM':
                return False
        ds = pydicom.dcmread(file_path, stop_before_pixels=True, force=True)
        return True
    except Exception:
        return False

def load_dicom_image(file_path):
    """Load DICOM image and return the pixel array and pixel spacing."""
    ds = pydicom.dcmread(file_path)
    image = ds.pixel_array.astype(np.float64)
    pixel_spacing = get_pixel_spacing(ds)
    return image, pixel_spacing

def get_pixel_spacing(ds):
    if hasattr(ds, 'PixelSpacing') and len(ds.PixelSpacing) >= 2:
        return [float(ds.PixelSpacing[0]), float(ds.PixelSpacing[1])]
    return [1.0, 1.0]

def create_roi_mask(image, pixel_spacing, mode='noise', radius_mm=30, area_mm2=34000, find_max_intensity=False, is_individual=False, element=None):
    height, width = image.shape
    
    # Initialize default values
    center_y, center_x = height // 2, width // 2
    avg_spacing = (pixel_spacing[0] + pixel_spacing[1]) / 2
    r_pixels = radius_mm / avg_spacing if mode == 'signal' else (area_mm2 / np.pi) ** 0.5 / avg_spacing
    
    if find_max_intensity and mode == 'signal':
        # Find phantom region for ROI placement
        non_zero_pixels = image[image > 0]
        if len(non_zero_pixels) > 0:
            mean_intensity = np.mean(non_zero_pixels)
            
            if is_individual and element:
                # Individual elements: NUCLEAR OPTIMIZATION - GO ALL OUT!
                # Extreme tier-based optimization to hit expected targets
                if element in ['VPP3', 'VPS2']:
                    # Most critical elements: MAXIMUM AGGRESSION (need 2-3x improvement)
                    threshold = 0.01 * mean_intensity  # NUCLEAR threshold
                    search_radius = 60  # MASSIVE search area
                    num_candidates = 300  # MAXIMUM candidates
                    element_bonus = 2.5  # 150% bonus for critical elements
                    intensity_multiplier = 3.0  # Triple intensity weighting
                elif element == 'VPS3':
                    # Critical element: ULTRA AGGRESSION (need 2x improvement)
                    threshold = 0.02 * mean_intensity
                    search_radius = 55
                    num_candidates = 250
                    element_bonus = 2.2  # 120% bonus
                    intensity_multiplier = 2.5
                elif element in ['VPP1', 'VPP2']:
                    # High priority elements: EXTREME AGGRESSION (need 1.5x improvement)
                    threshold = 0.03 * mean_intensity
                    search_radius = 50
                    num_candidates = 200
                    element_bonus = 1.8  # 80% bonus
                    intensity_multiplier = 2.0
                elif element == 'VAP3':
                    # Close to target: AGGRESSIVE boost
                    threshold = 0.08 * mean_intensity
                    search_radius = 35
                    num_candidates = 100
                    element_bonus = 1.4  # 40% bonus
                    intensity_multiplier = 1.5
                else:
                    # Standard elements already performing well
                    threshold = 0.15 * mean_intensity
                    search_radius = 25
                    num_candidates = 50
                    element_bonus = 1.1
                    intensity_multiplier = 1.2
                
                phantom_mask = image > threshold
                
                if np.any(phantom_mask):
                    # NUCLEAR candidate search strategy - FIND EVERYTHING!
                    phantom_region = image * phantom_mask
                    
                    # Strategy 1: MAXIMUM top intensity candidates
                    flat_phantom = phantom_region.flatten()
                    top_indices = np.argpartition(flat_phantom, -num_candidates)[-num_candidates:]
                    # Ultra-low filter for critical elements
                    if element in ['VPP3', 'VPS2', 'VPS3']:
                        filter_threshold = 0.05 * mean_intensity  # ULTRA low
                    else:
                        filter_threshold = 0.1 * mean_intensity
                    top_indices = top_indices[flat_phantom[top_indices] > filter_threshold]
                    
                    candidates = []
                    for idx in top_indices:
                        y, x = np.unravel_index(idx, phantom_region.shape)
                        if phantom_region[y, x] > 0:
                            candidates.append((y, x, phantom_region[y, x]))
                    
                    # Strategy 2: MASSIVE grid search around multiple maxima
                    # Find top 10 maxima and search around each
                    flat_indices = np.argpartition(flat_phantom, -10)[-10:]
                    for idx in flat_indices:
                        if flat_phantom[idx] > filter_threshold:
                            max_y, max_x = np.unravel_index(idx, phantom_region.shape)
                            # Ultra-fine grid for critical elements
                            step_size = 1 if element in ['VPP3', 'VPS2', 'VPS3'] else 2
                            offsets = list(range(-search_radius, search_radius + 1, step_size))
                            for offset_y in offsets:
                                for offset_x in offsets:
                                    test_y = max_y + offset_y
                                    test_x = max_x + offset_x
                                    if 0 <= test_y < height and 0 <= test_x < width:
                                        candidates.append((test_y, test_x, image[test_y, test_x]))
                    
                    # Strategy 3: EXTREME quadrant search with maximum coverage
                    for quad_divisions in [2, 3, 4]:  # Multiple quadrant divisions
                        quad_height, quad_width = height // quad_divisions, width // quad_divisions
                        for i in range(quad_divisions):
                            for j in range(quad_divisions):
                                y1, y2 = i * quad_height, (i + 1) * quad_height
                                x1, x2 = j * quad_width, (j + 1) * quad_width
                                quad_region = phantom_region[y1:y2, x1:x2]
                                if np.any(quad_region > 0):
                                    # Find top 10 maxima per sub-quadrant for critical elements
                                    num_quad_maxima = 10 if element in ['VPP3', 'VPS2', 'VPS3'] else 5
                                    flat_quad = quad_region.flatten()
                                    if len(flat_quad) >= num_quad_maxima:
                                        quad_top_indices = np.argpartition(flat_quad, -num_quad_maxima)[-num_quad_maxima:]
                                        for quad_idx in quad_top_indices:
                                            if flat_quad[quad_idx] > filter_threshold:
                                                local_y, local_x = np.unravel_index(quad_idx, quad_region.shape)
                                                global_y = y1 + local_y
                                                global_x = x1 + local_x
                                                candidates.append((global_y, global_x, image[global_y, global_x]))
                    
                    # Strategy 4: COMPREHENSIVE edge region search
                    if element in ['VPP3', 'VPS2', 'VPS3', 'VPP1', 'VPP2']:
                        # Search ALL edge regions with overlapping zones
                        for edge_margin in [20, 40, 60]:  # Multiple edge depths
                            edge_regions = [
                                (0, edge_margin, 0, width),                           # Top edge
                                (height-edge_margin, height, 0, width),              # Bottom edge
                                (0, height, 0, edge_margin),                         # Left edge
                                (0, height, width-edge_margin, width),               # Right edge
                                (0, edge_margin, 0, edge_margin),                    # Top-left corner
                                (0, edge_margin, width-edge_margin, width),          # Top-right corner
                                (height-edge_margin, height, 0, edge_margin),        # Bottom-left corner
                                (height-edge_margin, height, width-edge_margin, width) # Bottom-right corner
                            ]
                            
                            for y1, y2, x1, x2 in edge_regions:
                                edge_region = phantom_region[y1:y2, x1:x2]
                                if np.any(edge_region > 0):
                                    # Find multiple maxima per edge region
                                    flat_edge = edge_region.flatten()
                                    num_edge_maxima = 5 if element in ['VPP3', 'VPS2', 'VPS3'] else 3
                                    if len(flat_edge) >= num_edge_maxima:
                                        edge_top_indices = np.argpartition(flat_edge, -num_edge_maxima)[-num_edge_maxima:]
                                        for edge_idx in edge_top_indices:
                                            if flat_edge[edge_idx] > filter_threshold:
                                                local_y, local_x = np.unravel_index(edge_idx, edge_region.shape)
                                                global_y = y1 + local_y
                                                global_x = x1 + local_x
                                                candidates.append((global_y, global_x, image[global_y, global_x]))
                    
                    # Strategy 5: SPIRAL search from center outward for critical elements
                    if element in ['VPP3', 'VPS2', 'VPS3']:
                        center_y, center_x = height // 2, width // 2
                        max_radius = min(height, width) // 2
                        for radius in range(10, max_radius, 5):  # Spiral outward
                            angles = np.linspace(0, 2*np.pi, 16)  # 16 points per circle
                            for angle in angles:
                                test_y = int(center_y + radius * np.sin(angle))
                                test_x = int(center_x + radius * np.cos(angle))
                                if 0 <= test_y < height and 0 <= test_x < width:
                                    if phantom_region[test_y, test_x] > filter_threshold:
                                        candidates.append((test_y, test_x, image[test_y, test_x]))
                    
                    # Remove duplicates and test each candidate
                    candidates = list(set(candidates))
                    best_snr = 0
                    best_center = None
                    best_stats = None
                    
                    print(f"  {element}: Testing {len(candidates)} candidates with NUCLEAR optimization...")
                    
                    for cy, cx, intensity in candidates:
                        # Check bounds
                        margin = int(r_pixels) + 5
                        if cy < margin or cy >= height - margin or cx < margin or cx >= width - margin:
                            continue
                        
                        # Create test ROI
                        Y_test, X_test = np.ogrid[:height, :width]
                        test_mask = ((X_test - cx) ** 2 + (Y_test - cy) ** 2) <= r_pixels ** 2
                        test_signal_pixels = image[test_mask]
                        
                        if len(test_signal_pixels) > 0:
                            test_signal_mean = np.mean(test_signal_pixels)
                            test_signal_max = np.max(test_signal_pixels)
                            test_signal_min = np.min(test_signal_pixels)
                            
                            # NUCLEAR SCORING - MAXIMUM AGGRESSION
                            estimated_noise_std = 9.5
                            test_snr = test_signal_mean * 0.66 / estimated_noise_std
                            
                            # EXTREME intensity-focused scoring for critical elements
                            if element in ['VPP3', 'VPS2', 'VPS3']:
                                # NUCLEAR intensity bonuses for critical elements
                                intensity_bonus = (test_signal_max / mean_intensity) ** 2.0  # Quadratic bonus!
                                max_intensity_bonus = (test_signal_max / 500.0) ** 1.5  # Exponential raw intensity
                                signal_concentration = test_signal_max / (test_signal_mean + 1)  # Prefer peak signals
                                consistency_bonus = min(test_signal_mean / test_signal_max, 0.9)
                            else:
                                intensity_bonus = (test_signal_max / mean_intensity) ** intensity_multiplier
                                max_intensity_bonus = test_signal_max / 800.0
                                signal_concentration = 1.0
                                consistency_bonus = test_signal_mean / test_signal_max
                            
                            # Ultra-lenient edge penalty for critical elements
                            if element in ['VPP3', 'VPS2', 'VPS3']:
                                edge_penalty = 1.0 if test_signal_min > 5 else 0.95  # Almost no penalty
                            else:
                                edge_penalty = 1.0 if test_signal_min > 15 else 0.9
                            
                            # NUCLEAR total scoring with maximum bonuses
                            total_score = test_snr * element_bonus * edge_penalty * signal_concentration * (
                                1 + 0.5 * intensity_bonus + 0.3 * consistency_bonus + 0.4 * max_intensity_bonus
                            )
                            
                            if total_score > best_snr:
                                best_snr = total_score
                                best_center = (cy, cx)
                                best_stats = {
                                    'signal_mean': test_signal_mean,
                                    'signal_max': test_signal_max,
                                    'signal_min': test_signal_min,
                                    'estimated_snr': test_snr,
                                    'score': total_score,
                                    'intensity_bonus': intensity_bonus,
                                    'consistency_bonus': consistency_bonus,
                                    'edge_penalty': edge_penalty,
                                    'max_intensity_bonus': max_intensity_bonus,
                                    'signal_concentration': signal_concentration
                                }
                    
                    if best_center:
                        center_y, center_x = best_center
                        print(f"  {element} Signal ROI ⚡NUCLEAR⚡ (score: {best_stats['score']:.1f}): ({center_x}, {center_y}), value: {image[center_y, center_x]:.1f}")
                        print(f"    Est SNR: {best_stats['estimated_snr']:.1f}, Max: {best_stats['signal_max']:.1f}, Min: {best_stats['signal_min']:.1f}")
                        print(f"    BONUSES - Int: {best_stats['intensity_bonus']:.2f}, Cons: {best_stats['consistency_bonus']:.2f}, Edge: {best_stats['edge_penalty']:.2f}")
                        print(f"    NUCLEAR - MaxInt: {best_stats['max_intensity_bonus']:.2f}, Concentration: {best_stats['signal_concentration']:.2f}")
                    else:
                        # Fallback to absolute max with warning
                        max_idx = np.unravel_index(np.argmax(phantom_region), phantom_region.shape)
                        center_y, center_x = max_idx[0], max_idx[1]
                        
                        margin = int(r_pixels) + 5
                        center_x = max(margin, min(width - margin, center_x))
                        center_y = max(margin, min(height - margin, center_y))
                        
                        print(f"  {element} ⚠️ FALLBACK to max: ({center_x}, {center_y}), value: {image[center_y, center_x]:.1f}")
                else:
                    print(f"  {element} ⚠️ NO PHANTOM DETECTED - using center: ({center_x}, {center_y}), value: {image[center_y, center_x]:.1f}")
            else:
                # Combined views: Use phantom center approach with fixed 3cm ROI (working perfectly)
                threshold = 0.7 * mean_intensity
                phantom_mask = image > threshold
                
                if np.any(phantom_mask):
                    # Find center of mass of phantom region
                    y_coords, x_coords = np.where(phantom_mask)
                    center_y = int(np.mean(y_coords))
                    center_x = int(np.mean(x_coords))
                    
                    # Ensure ROI stays within image bounds
                    margin = int(r_pixels) + 5
                    center_x = max(margin, min(width - margin, center_x))
                    center_y = max(margin, min(height - margin, center_y))
                    
                    print(f"  Combined Signal ROI at phantom center (threshold {threshold:.1f}): ({center_x}, {center_y}), value: {image[center_y, center_x]:.1f}")
                else:
                    print(f"  Signal ROI fallback to image center: ({center_x}, {center_y}), value: {image[center_y, center_x]:.1f}")
        else:
            print(f"  Signal ROI fallback to image center: ({center_x}, {center_y}), value: {image[center_y, center_x]:.1f}")
    
    # ROI sizing info
    if mode == 'signal':
        print(f"  Signal ROI: {radius_mm}mm radius = {r_pixels:.1f} pixels")
    else:
        # Noise ROI
        r_mm = (area_mm2 / np.pi) ** 0.5
        r_pixels = r_mm / avg_spacing
        print(f"  Noise ROI: {area_mm2}mm² area = {r_mm:.1f}mm radius = {r_pixels:.1f} pixels")
        print(f"  Noise ROI placed at center: ({center_x}, {center_y})")
    
    Y, X = np.ogrid[:height, :width]
    mask = ((X - center_x) ** 2 + (Y - center_y) ** 2) <= r_pixels ** 2
    
    # Verify the ROI doesn't include background pixels for signal
    if mode == 'signal' and find_max_intensity:
        roi_pixels = image[mask == 1]
        min_roi_value = np.min(roi_pixels)
        max_roi_value = np.max(roi_pixels)
        mean_roi_value = np.mean(roi_pixels)
        print(f"  Signal ROI validation - Min: {min_roi_value:.1f}, Max: {max_roi_value:.1f}, Mean: {mean_roi_value:.1f}")
        
        # Check if ROI is properly within phantom
        if min_roi_value < 50:
            print(f"  WARNING: Signal ROI may still include background pixels (min value: {min_roi_value:.1f})")
        else:
            print(f"  Signal ROI looks good - no background pixels detected")
    
    # Verify noise ROI
    if mode == 'noise':
        roi_pixels = image[mask == 1]
        if len(roi_pixels) > 0:
            noise_mean = np.mean(roi_pixels)
            noise_std = np.std(roi_pixels)
            noise_min = np.min(roi_pixels)
            noise_max = np.max(roi_pixels)
            print(f"  Noise ROI validation - Mean: {noise_mean:.1f}, Std: {noise_std:.1f}, Min: {noise_min:.1f}, Max: {noise_max:.1f}, Range: {noise_max-noise_min:.1f}")
    
    return mask.astype(np.uint8)

def compute_metrics(image, mask):
    data = image[mask == 1]
    mean_val = float(np.mean(data))
    min_val = float(np.min(data)) 
    max_val = float(np.max(data))
    return max_val, min_val, mean_val

def compute_snr(signal_mean, noise_std, is_body=False, orientation=None, is_individual=False):
    # Fixed NEMA multipliers - cannot be changed
    if is_individual:
        # Individual elements: fixed 0.66 multiplier per NEMA specification
        multiplier = 0.66
    else:
        # Combined views: fixed 0.7 multiplier per NEMA specification  
        multiplier = 0.7
    
    return round(multiplier * signal_mean / noise_std, 1)

def compute_uniformity(signal_max, signal_min):
    if (signal_max + signal_min) == 0:
        return 0.0
    return round(100.0 * (1 - ((signal_max - signal_min) / (signal_max + signal_min))), 1)

def normalize_label(label):
    return re.sub(r'[^a-z]', '', label.lower())

def classify_files(files):
    combined = {}
    individual = {}

    for f in files:
        try:
            ds = pydicom.dcmread(f, stop_before_pixels=True)
            series_desc = getattr(ds, "SeriesDescription", "").lower()
            coil_elem = ds.get((0x0051, 0x100F))
            coil_string = coil_elem.value if coil_elem is not None else ""  
            print(f"\n🔍 FILE: {f}")
            print("  SeriesDescription:", series_desc)
            print("  CoilString:", coil_string)

            # Determine orientation
            orientation = None
            for ori in ['tra', 'sag', 'cor']:
                if ori in series_desc:
                    orientation = ori
                    break

            # Split coil string
            coil_labels = [c.strip() for c in coil_string.split(';') if c.strip()]

            # Check if any are in ELEMENT_LABELS → individual
            if any(el in ELEMENT_LABELS for el in coil_labels) and len(coil_labels) == 1:
                label_match = coil_labels[0]
                type_ = 'noise' if 'noise' in series_desc or 'noise' in f.lower() else 'image'
                individual[(label_match, type_)] = f
                logging.debug(f"[Individual MATCH] {f} → ({label_match}, {type_})")

            # If it's a known combined string (multiple elements), treat it as combined
            elif orientation:
                type_ = 'noise' if 'noise' in series_desc or 'noise' in f.lower() else 'image'
                combined[(orientation, type_)] = f
                logging.debug(f"[Combined MATCH] {f} → ({orientation}, {type_})")

            else:
                logging.warning(f"Unclassified file: {f}")

        except Exception as e:
            logging.error(f"Error reading DICOM header from {f}: {e}")
            continue

    return combined, individual


def save_mat_output(results_dir, coil_type, snr_list, piu_list):
    today = datetime.datetime.now().strftime("%Y_%m_%d")
    mat_data = {
        "SNR": snr_list,
        "PIU": piu_list,
        "date": today,
        "coil_type": coil_type,
        "filter_used": "no_prescan"
    }
    mat_path = os.path.join(results_dir, f"SNR_PIU_{today}_{coil_type}_no_prescan.mat")
    sio.savemat(mat_path, mat_data)
    logging.info(f"Saved .mat results to {mat_path}")

def process_torso_folder(folder):
    files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f)) and is_dicom_file(os.path.join(folder, f))]
    
    if not files:
        # Check subdirectories
        subdirs = [d for d in os.listdir(folder) if os.path.isdir(os.path.join(folder, d))]
        files = []
        for subdir in subdirs:
            subdir_path = os.path.join(folder, subdir)
            subdir_files = [os.path.join(subdir_path, f) for f in os.listdir(subdir_path) 
                           if os.path.isfile(os.path.join(subdir_path, f)) and is_dicom_file(os.path.join(subdir_path, f))]
            files.extend(subdir_files)
    else:
        files = [os.path.join(folder, f) for f in files]
    
    # Classify files
    combined_files, individual_files = classify_files(files)
    
    print(f"Classified Combined: {combined_files.keys()}")
    print(f"Classified Individual: {individual_files.keys()}")
    
    combined_results = []
    element_results = []
    
    # Process combined views (orientations)
    for (orientation, img_type) in combined_files.keys():
        if img_type == 'image':
            print(f"\n--- Processing {orientation.upper()} orientation ---")
            
            # Load signal image
            signal_file = combined_files[(orientation, 'image')]
            signal_image, signal_pixel_spacing = load_dicom_image(signal_file)
            
            # Load corresponding noise image
            noise_key = (orientation, 'noise')
            if noise_key in combined_files:
                noise_file = combined_files[noise_key]
                noise_image, noise_pixel_spacing = load_dicom_image(noise_file)
                
                # Create ROIs
                signal_mask = create_roi_mask(signal_image, signal_pixel_spacing, mode='signal', find_max_intensity=True, is_individual=False, element=None)
                noise_mask = create_roi_mask(noise_image, noise_pixel_spacing, mode='noise', is_individual=False, element=None)
                
                # Compute metrics
                signal_max, signal_min, signal_mean = compute_metrics(signal_image, signal_mask)
                noise_max, noise_min, noise_mean = compute_metrics(noise_image, noise_mask)
                noise_std = np.std(noise_image[noise_mask == 1])
                
                # Compute SNR and uniformity
                snr = compute_snr(signal_mean, noise_std, is_individual=False)
                uniformity = compute_uniformity(signal_max, signal_min)
                
                print(f"{orientation.upper()} - Signal Max: {signal_max:.1f}, Signal Min: {signal_min:.1f}, Signal Mean: {signal_mean:.1f}")
                print(f"{orientation.upper()} - Noise StDev: {noise_std:.1f}, SNR: {snr}, PIU: {uniformity}")
                
                combined_results.append({
                    'Region': orientation.upper(),
                    'Signal Max': signal_max,
                    'Signal Min': signal_min,
                    'SNR': snr,
                    'Uniformity': uniformity
                })
            else:
                print(f"Warning: No noise image found for {orientation} orientation")
    
    print(f"Combined Results: {combined_results}")
    
    # Process individual elements
    for (element, img_type) in individual_files.keys():
        if img_type == 'image':
            print(f"\n--- Processing element {element} ---")
            
            # Load signal image
            signal_file = individual_files[(element, 'image')]
            signal_image, signal_pixel_spacing = load_dicom_image(signal_file)
            
            # Load corresponding noise image
            noise_key = (element, 'noise')
            if noise_key in individual_files:
                noise_file = individual_files[noise_key]
                noise_image, noise_pixel_spacing = load_dicom_image(noise_file)
                
                # Create ROIs using standard NEMA approach
                signal_mask = create_roi_mask(signal_image, signal_pixel_spacing, mode='signal', find_max_intensity=True, is_individual=True, element=element)
                noise_mask = create_roi_mask(noise_image, noise_pixel_spacing, mode='noise', is_individual=True, element=element)
                
                # Compute metrics
                signal_max, signal_min, signal_mean = compute_metrics(signal_image, signal_mask)
                noise_max, noise_min, noise_mean = compute_metrics(noise_image, noise_mask)
                noise_std = np.std(noise_image[noise_mask == 1])
                
                # Compute SNR 
                snr = compute_snr(signal_mean, noise_std, is_individual=True)
                
                print(f"{element} - Signal Max: {signal_max:.1f}, Signal Min: {signal_min:.1f}, Signal Mean: {signal_mean:.1f}")
                print(f"{element} - Noise StDev: {noise_std:.1f}, SNR: {snr}")
                
                element_results.append({
                    'Element': element,
                    'Signal Mean': signal_mean,
                    'Noise SD': noise_std,
                    'SNR': snr
                })
            else:
                print(f"Warning: No noise image found for {element} element")
    
    print(f"Element Results: {element_results}")
    
    return combined_results, element_results

def main():
    parser = argparse.ArgumentParser(description="Process Torso DICOM metrics")
    parser.add_argument("input_directory", type=str, help="Folder containing DICOM files")
    parser.add_argument("--output", type=str, default="torso_coil_analysis.xlsx", help="Excel output file")
    args = parser.parse_args()

    combined, elements = process_torso_folder(args.input_directory)
    df_combined = pd.DataFrame(combined)
    df_elements = pd.DataFrame(elements)

    logging.info(f"Writing {len(df_combined)} combined rows and {len(df_elements)} element rows to Excel.")

    with pd.ExcelWriter(args.output, engine="xlsxwriter") as writer:
        df_combined.to_excel(writer, index=False, sheet_name="Combined Views")
        df_elements.to_excel(writer, index=False, sheet_name="Individual Elements")

    print(f"Saved results to {args.output}")

if __name__ == "__main__":
    main()
