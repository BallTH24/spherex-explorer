from typing import Tuple
import numpy as np

WAVELENGTHS_102 = np.round(np.linspace(0.75, 5.0, 102), 4)


def _planck_continuum_shape(wl: np.ndarray, temp_k: float) -> np.ndarray:
    """คำนวณรูปร่างเส้นความสว่างต่อเนื่องตามกฎการแผ่รังสีของพลังค์ (Planck's Law) สำหรับ SPHEREx"""
    hc_k = 14387.77
    planck = (wl**-3.0) / np.expm1(np.clip(hc_k / (wl * temp_k), 1e-2, 50.0))
    return planck / (planck + 0.05)


def generate_synthetic_dipole_samples(n_samples: int = 400, rng_seed: int = 42) -> Tuple[np.ndarray, np.ndarray]:
    """
    สร้างชุดข้อมูลจำลองภาพ Cutout ขนาด 16x16:
    - คลาส 1 (Real Dipole): มีทั้งยอดบวกและหลุมลบอยู่ใกล้กัน (สัญญาณของวัตถุเคลื่อนที่)
    - คลาส 0 (Artifact / Monopole / Noise): มีเฉพาะจุดเดี่ยว (ดาวแปรแสง/รังสีคอสมิก) หรือสัญญาณรบกวนสุ่ม
    """
    rng = np.random.default_rng(rng_seed)
    y, x = np.mgrid[0:16, 0:16]

    x_data = []
    y_data = []

    for _ in range(n_samples // 2):
        # Real Dipole (Class 1)
        p_x, p_y = rng.uniform(4.0, 11.0, 2)
        angle = rng.uniform(0, 2 * np.pi)
        dist = rng.uniform(2.5, 5.5)
        n_x = np.clip(p_x + dist * np.cos(angle), 1.0, 14.0)
        n_y = np.clip(p_y + dist * np.sin(angle), 1.0, 14.0)

        amp_pos = rng.uniform(6.0, 15.0)
        amp_neg = rng.uniform(6.0, 15.0)

        pos_lobe = amp_pos * np.exp(-((x - p_x) ** 2 + (y - p_y) ** 2) / (2 * 1.2**2))
        neg_lobe = -amp_neg * np.exp(-((x - n_x) ** 2 + (y - n_y) ** 2) / (2 * 1.2**2))
        noise = rng.normal(0.0, 1.0, (16, 16))

        dipole_map = pos_lobe + neg_lobe + noise
        x_data.append(dipole_map.astype(np.float32))
        y_data.append(1)

    for _ in range(n_samples // 2):
        # False / Monopole / Noise (Class 0)
        noise = rng.normal(0.0, 1.0, (16, 16))
        sample_type = rng.choice(["monopole", "cosmic_ray", "pure_noise"])

        if sample_type == "monopole":
            cx, cy = rng.uniform(4.0, 11.0, 2)
            amp = rng.choice([-1.0, 1.0]) * rng.uniform(7.0, 18.0)
            lobe = amp * np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * 1.3**2))
            sample = lobe + noise
        elif sample_type == "cosmic_ray":
            cx, cy = rng.integers(3, 13, 2)
            sample = noise.copy()
            sample[cy, cx] += rng.uniform(15.0, 30.0)
        else:
            sample = noise

        x_data.append(sample.astype(np.float32))
        y_data.append(0)

    x_arr = np.expand_dims(np.array(x_data, dtype=np.float32), axis=1)  # (N, 1, 16, 16)
    y_arr = np.array(y_data, dtype=np.int64)
    return x_arr, y_arr


def generate_synthetic_spectral_samples(n_samples: int = 500, rng_seed: int = 42) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    สร้างสเปกตรัมจำลอง 102 แบนด์ (0.75 - 5.0 um) แบบ Normalized Shape [0, 1]:
    - Ultra-cold / Planet X candidates (100 - 200 K)
    - Cold Y-Dwarfs (200 - 450 K)
    - T/L-Type Brown Dwarfs (500 - 1800 K)
    - M-Dwarf Stars (2400 - 3800 K)
    - T Tauri Variable Stars (3200 - 4200 K)
    คืนค่า (X_spectra_normalized, Y_temperature, Y_classes)
    """
    rng = np.random.default_rng(rng_seed)
    wl = WAVELENGTHS_102

    x_list, temp_list, class_list = [], [], []

    for _ in range(n_samples):
        cat_type = rng.choice(["planet_x", "y_dwarf", "brown_dwarf", "m_dwarf", "variable_star"])

        if cat_type == "planet_x":
            temp = rng.uniform(120.0, 180.0)
            peak_w = rng.uniform(4.60, 4.75)
            cont = 45.0 * np.exp(-((wl - peak_w) ** 2) / (2 * 0.95**2)) + 6.0
            h2o = 1.0 - rng.uniform(0.65, 0.85) * np.exp(-((wl - 3.05) ** 2) / (2 * 0.08**2))
            ch4 = 1.0 - rng.uniform(0.75, 0.92) * np.exp(-((wl - 3.32) ** 2) / (2 * 0.08**2))
            co = 1.0 - rng.uniform(0.2, 0.35) * np.exp(-((wl - 4.45) ** 2) / (2 * 0.12**2))
            cls_name = "Cold Y-Dwarf / Sub-stellar Candidate"
        elif cat_type == "y_dwarf":
            temp = rng.uniform(220.0, 320.0)
            peak_w = rng.uniform(4.45, 4.58)
            cont = 45.0 * np.exp(-((wl - peak_w) ** 2) / (2 * 0.95**2)) + 8.0
            h2o = 1.0 - rng.uniform(0.40, 0.58) * np.exp(-((wl - 3.05) ** 2) / (2 * 0.08**2))
            ch4 = 1.0 - rng.uniform(0.60, 0.78) * np.exp(-((wl - 3.32) ** 2) / (2 * 0.08**2))
            co = 1.0 - rng.uniform(0.12, 0.25) * np.exp(-((wl - 4.45) ** 2) / (2 * 0.12**2))
            cls_name = "Cold Y-Dwarf / Sub-stellar Candidate"
        elif cat_type == "brown_dwarf":
            temp = rng.uniform(600.0, 1600.0)
            cont = 35.0 * np.exp(-((wl - 3.8) ** 2) / (2 * 1.5**2)) + 12.0
            h2o = 1.0 - rng.uniform(0.2, 0.4) * np.exp(-((wl - 3.05) ** 2) / (2 * 0.08**2))
            ch4 = 1.0 - rng.uniform(0.2, 0.4) * np.exp(-((wl - 3.32) ** 2) / (2 * 0.08**2))
            co = 1.0 - rng.uniform(0.1, 0.2) * np.exp(-((wl - 4.45) ** 2) / (2 * 0.12**2))
            cls_name = "T/L-Type Brown Dwarf"
        elif cat_type == "m_dwarf":
            temp = rng.uniform(2800.0, 3600.0)
            cont = 55.0 * _planck_continuum_shape(wl, temp)
            h2o = 1.0 - rng.uniform(0.08, 0.18) * np.exp(-((wl - 3.05) ** 2) / (2 * 0.08**2))
            ch4 = 1.0 - rng.uniform(0.0, 0.04) * np.exp(-((wl - 3.32) ** 2) / (2 * 0.08**2))
            co = 1.0 - rng.uniform(0.08, 0.22) * np.exp(-((wl - 4.45) ** 2) / (2 * 0.12**2))
            cls_name = "M-Dwarf Star / Red Dwarf"
        else:
            temp = rng.uniform(3400.0, 4000.0)
            cont = 55.0 * _planck_continuum_shape(wl, temp) + 22.0 * np.exp(-((wl - 4.7) ** 2) / (2 * 1.4**2))
            h2o = 1.0 - rng.uniform(0.20, 0.35) * np.exp(-((wl - 3.05) ** 2) / (2 * 0.08**2))
            ch4 = 1.0 - rng.uniform(0.0, 0.06) * np.exp(-((wl - 3.32) ** 2) / (2 * 0.08**2))
            co = 1.0 - rng.uniform(0.40, 0.60) * np.exp(-((wl - 4.45) ** 2) / (2 * 0.12**2))
            cls_name = "T Tauri Variable Star / Pre-Main Sequence"

        raw_spec = np.maximum(0.1, cont * h2o * ch4 * co + rng.normal(0.0, 0.6, len(wl)))
        # Normalize ให้เป็น Spectral Shape Vector
        norm_spec = raw_spec / float(np.max(raw_spec))

        x_list.append(norm_spec.astype(np.float32))
        temp_list.append(float(temp))
        class_list.append(cls_name)

    return np.array(x_list, dtype=np.float32), np.array(temp_list, dtype=np.float32), np.array(class_list)
