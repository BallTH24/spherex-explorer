from typing import Dict, Any, Tuple
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from astropy.time import Time
from astropy.stats import mad_std
import astropy.units as u
from reproject import reproject_interp


def asinh_stretch_to_list(img_array: np.ndarray, scale: float = 0.15) -> list[list[float]]:
    """
    ย่อ Dynamic Range ของภาพดาราศาสตร์ด้วยฟังก์ชัน Inverse Hyperbolic Sine (ASINH)
    ให้อยู่ในช่วง [0.0, 1.0] แล้วแปลงเป็น 2D List สำหรับเรนเดอร์บน HTML5 Canvas
    """
    clean = np.nan_to_num(img_array, nan=0.0)
    stretched = np.arcsinh(clean * scale)
    ptp = float(np.ptp(stretched))
    if ptp > 1e-12:
        stretched = (stretched - float(np.min(stretched))) / ptp
    else:
        stretched = np.zeros_like(stretched)
    return np.round(stretched, 4).tolist()


def extract_16x16_cutout(snr_map: np.ndarray, center_xy: Tuple[float, float] | Tuple[int, int] | None = None) -> np.ndarray:
    """
    ตัดภาพ Difference SNR ขนาด 16x16 พิกเซล รอบจุดที่มีการเปลี่ยนแปลงสูงสุด
    สำหรับส่งเข้าโมเดล PyTorch 2D-CNN (Real Dipole vs Cosmic Ray Classifier)
    """
    h, w = snr_map.shape
    if center_xy is None:
        # หาพิกเซลที่ค่าสัมบูรณ์ |SNR| สูงสุดในภาพ
        flat_idx = int(np.argmax(np.abs(snr_map)))
        cy, cx = divmod(flat_idx, w)
    else:
        cx, cy = int(round(center_xy[0])), int(round(center_xy[1]))

    half = 8
    padded = np.pad(snr_map, pad_width=half, mode="constant", constant_values=0.0)
    py, px = cy + half, cx + half
    cutout = padded[py - half : py + half, px - half : px + half]
    return cutout.astype(np.float32)


def detect_transient_signature(snr_map: np.ndarray, threshold_sigma: float = 4.5) -> Dict[str, Any]:
    """
    วิเคราะห์รูปแบบสัญญาณบนแผนที่ Difference SNR:
    - Dipole (ทั้งยอดบวกและหลุมลบเกิน Threshold ใกล้กัน) -> วัตถุเคลื่อนที่ (Moving Object)
    - Monopole (มียอดบวกหรือหลุมลบอย่างเดียว) -> ดาวแปรแสง (Variable Star) หรือ Transient
    """
    max_snr = float(np.max(snr_map))
    min_snr = float(np.min(snr_map))

    max_y, max_x = np.unravel_index(int(np.argmax(snr_map)), snr_map.shape)
    min_y, min_x = np.unravel_index(int(np.argmin(snr_map)), snr_map.shape)

    pixel_dist = float(np.hypot(max_x - min_x, max_y - min_y))
    has_pos_peak = max_snr >= threshold_sigma
    has_neg_trough = abs(min_snr) >= threshold_sigma

    # Dipole แท้จะมีจุดมืด (ตำแหน่ง Epoch 1) และจุดสว่าง (ตำแหน่ง Epoch 2) ห่างกันไม่เกิน ~20 พิกเซล
    is_dipole_pattern = bool(has_pos_peak and has_neg_trough and (1.0 <= pixel_dist <= 25.0))
    is_monopole_pattern = bool((has_pos_peak ^ has_neg_trough) or (pixel_dist < 1.0 and (has_pos_peak or has_neg_trough)))

    return {
        "is_dipole_pattern": is_dipole_pattern,
        "is_monopole_pattern": is_monopole_pattern,
        "max_snr": round(max_snr, 2),
        "min_snr": round(min_snr, 2),
        "pos_peak_xy": (float(max_x), float(max_y)),
        "neg_trough_xy": (float(min_x), float(min_y)),
        "dipole_pixel_separation": round(pixel_dist, 2),
    }


def align_and_subtract_epochs(fits_epoch1_path: str, fits_epoch2_path: str) -> Dict[str, Any]:
    """
    อ่านไฟล์ FITS 2 ช่วงเวลา ทำ WCS Reprojection ให้ Epoch 2 ตรงกับ Epoch 1
    คำนวณทั้ง Difference Image (Epoch 2 - Epoch 1) และ Co-added Stack ((Epoch 1 + Epoch 2) / 2)
    """
    with fits.open(fits_epoch1_path) as hdu1, fits.open(fits_epoch2_path) as hdu2:
        data1 = np.nan_to_num(hdu1[0].data.astype(np.float64), nan=0.0)
        hdr1 = hdu1[0].header
        wcs1 = WCS(hdr1, naxis=2)

        data2 = np.nan_to_num(hdu2[0].data.astype(np.float64), nan=0.0)
        hdr2 = hdu2[0].header
        wcs2 = WCS(hdr2, naxis=2)

        t1 = Time(float(hdr1.get("MJD-OBS", 60700.0)), format="mjd")
        t2 = Time(float(hdr2.get("MJD-OBS", 60882.5)), format="mjd")

    # จัดพิกัด Epoch 2 ให้ตรงกับตารางพิกเซลของ Epoch 1
    data2_aligned, footprint = reproject_interp((data2, wcs2), wcs1, shape_out=data1.shape)
    data2_aligned = np.nan_to_num(data2_aligned, nan=0.0)

    # 1. Image Subtraction (จับการเคลื่อนที่และการแปรแสง)
    diff_img = data2_aligned - data1

    # 2. Image Addition / Stacking (เพิ่ม SNR สำหรับวัตถุจางมากตามโจทย์ NASA)
    stacked_img = 0.5 * (data1 + data2_aligned)

    # ประเมินระดับ Noise พื้นหลังด้วย Median Absolute Deviation (MAD)
    sigma_noise = float(mad_std(diff_img, ignore_nan=True))
    if sigma_noise < 1e-9:
        sigma_noise = 1.0

    snr_map = diff_img / sigma_noise
    signature_info = detect_transient_signature(snr_map)
    cutout_16x16 = extract_16x16_cutout(snr_map, center_xy=signature_info["pos_peak_xy"])

    delta_years = float((t2 - t1).to(u.yr).value)

    return {
        "wcs_ref": wcs1,
        "epoch1_mjd": round(float(t1.mjd), 3),
        "epoch2_mjd": round(float(t2.mjd), 3),
        "delta_years": delta_years if abs(delta_years) > 1e-6 else 0.5,
        "sigma_noise": round(sigma_noise, 4),
        "epoch1_raw": data1,
        "epoch2_aligned_raw": data2_aligned,
        "stacked_raw": stacked_img,
        "snr_map_raw": snr_map,
        "cutout_16x16": cutout_16x16,
        "signature_info": signature_info,
        "image_layers_64x64": {
            "epoch1_asinh": asinh_stretch_to_list(data1),
            "epoch2_asinh": asinh_stretch_to_list(data2_aligned),
            "difference_snr": np.round(snr_map, 2).tolist(),
        },
    }
