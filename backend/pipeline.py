from pathlib import Path
from typing import Dict, Any
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS

from backend.schemas import SpherexTargetBundle
from backend.astronomy import (
    STANDARD_ABSORPTION_MARKERS,
    align_and_subtract_epochs,
    measure_single_band_flux,
    extract_102band_spectrum,
    detect_molecular_absorption_bands,
    query_gaia_and_wise_catalogs,
    compute_kinematics_and_variability,
    classify_target_category,
)
from backend.ml import (
    WAVELENGTHS_102,
    ensure_models_trained,
    run_ai_analysis,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
FITS_DIR = ROOT_DIR / "backend" / "data_fits"
CONTRACTS_DIR = ROOT_DIR / "contracts"
FRONTEND_DATA_DIR = ROOT_DIR / "frontend" / "public" / "data"


# =====================================================================
# รายละเอียดเป้าหมายมาตรฐานทั้ง 4 เคส (ตรงกับ Path ที่แจ้งโมกิไว้)
# =====================================================================
BENCHMARK_SPECS: Dict[str, Dict[str, Any]] = {
    "WISE_0855_0714": {
        "filename": "sample_wise0855.json",
        "title": "WISE J085510.83-071442.5 (Y-Type Brown Dwarf)",
        "crval1_ra": 133.7800,
        "crval2_dec": -7.2400,
        "ep1_xy": (28.0, 30.0),
        "ep2_xy": (33.0, 32.0),
        "amp_ep1": 92.0,
        "amp_ep2": 94.0,
        "temp_k": 260.0,
        "h2o_depth": 0.48,
        "ch4_depth": 0.68,
        "co_depth": 0.18,
        "optical_invisible": True,
        "forced_category": "moving_object",
    },
    "BARNARDS_STAR": {
        "filename": "barnards_star.json",
        "title": "Barnard's Star (GJ 699 — Fastest Proper Motion M4V Dwarf)",
        "crval1_ra": 269.4520,
        "crval2_dec": 4.6930,
        "ep1_xy": (26.0, 25.0),
        "ep2_xy": (34.0, 35.0),
        "amp_ep1": 185.0,
        "amp_ep2": 184.0,
        "temp_k": 3220.0,
        "h2o_depth": 0.12,
        "ch4_depth": 0.02,
        "co_depth": 0.15,
        "optical_invisible": False,
        "forced_category": "moving_object",
    },
    "RW_AURIGAE": {
        "filename": "rw_aurigae.json",
        "title": "RW Aurigae (T Tauri Variable Star — High Photometric Surge)",
        "crval1_ra": 76.9560,
        "crval2_dec": 30.4010,
        "ep1_xy": (32.0, 32.0),
        "ep2_xy": (32.0, 32.0),  # ดาวแปรแสงอยู่นิ่งกับที่ แต่ความสว่างพุ่งสูงขึ้น
        "amp_ep1": 65.0,
        "amp_ep2": 142.0,
        "temp_k": 3650.0,
        "h2o_depth": 0.28,
        "ch4_depth": 0.04,
        "co_depth": 0.52,
        "optical_invisible": False,
        "forced_category": "variable_star",
    },
    "PLANET_X_CANDIDATE": {
        "filename": "planet_x_candidate.json",
        "title": "SPHEREx- J0248-1831 (Uncharted Ultra-Cold Methane Anomaly)",
        "crval1_ra": 42.1500,
        "crval2_dec": -18.5200,
        "ep1_xy": (29.5, 31.0),
        "ep2_xy": (32.5, 32.5),
        "amp_ep1": 78.0,
        "amp_ep2": 79.0,
        "temp_k": 145.0,
        "h2o_depth": 0.72,
        "ch4_depth": 0.84,
        "co_depth": 0.25,
        "optical_invisible": True,
        "forced_category": "anomaly_candidate",
    },
}


def _create_wcs_header(crval1: float, crval2: float, mjd_obs: float) -> fits.Header:
    """สร้าง FITS Header มาตรฐานระบบพิกัด ICRS TAN Projection สำหรับ SPHEREx"""
    hdr = fits.Header()
    hdr["NAXIS"] = 2
    hdr["CTYPE1"] = "RA---TAN"
    hdr["CTYPE2"] = "DEC--TAN"
    hdr["CRVAL1"] = crval1
    hdr["CRVAL2"] = crval2
    hdr["CRPIX1"] = 32.0
    hdr["CRPIX2"] = 32.0
    hdr["CDELT1"] = -0.00028  # ~1.0 arcsec/pixel สำหรับ Cutout ความละเอียดสูง
    hdr["CDELT2"] = 0.00028
    hdr["MJD-OBS"] = mjd_obs
    return hdr


def generate_target_fits_files(target_id: str, spec: Dict[str, Any]) -> Dict[str, str]:
    """
    สร้างไฟล์ FITS 3 ไฟล์ (Epoch 1, Epoch 2, และ 102-Band Spectral Cube)
    ลงในโฟลเดอร์ backend/data_fits/ สำหรับแต่ละเป้าหมาย
    """
    FITS_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(abs(hash(target_id)) % (2**32))

    ny, nx = 64, 64
    y, x = np.mgrid[0:ny, 0:nx]

    # ดาวพื้นหลังที่อยู่นิ่ง (ตรงกับตำแหน่งใน catalogs.py fallback)
    static_stars = np.zeros((ny, nx), dtype=np.float64)
    for sx, sy, amp in [(15.0, 20.0, 110.0), (48.0, 14.0, 85.0), (22.0, 50.0, 125.0), (52.0, 45.0, 75.0)]:
        static_stars += amp * np.exp(-((x - sx) ** 2 + (y - sy) ** 2) / (2 * 1.35**2))

    x1, y1 = spec["ep1_xy"]
    x2, y2 = spec["ep2_xy"]

    psf_ep1 = spec["amp_ep1"] * np.exp(-((x - x1) ** 2 + (y - y1) ** 2) / (2 * 1.4**2))
    psf_ep2 = spec["amp_ep2"] * np.exp(-((x - x2) ** 2 + (y - y2) ** 2) / (2 * 1.4**2))

    img_ep1 = static_stars + psf_ep1 + rng.normal(10.0, 1.2, (ny, nx))
    img_ep2 = static_stars + psf_ep2 + rng.normal(10.0, 1.2, (ny, nx))

    ep1_path = str(FITS_DIR / f"{target_id.lower()}_ep1.fits")
    ep2_path = str(FITS_DIR / f"{target_id.lower()}_ep2.fits")
    cube_path = str(FITS_DIR / f"{target_id.lower()}_cube102.fits")

    hdr1 = _create_wcs_header(spec["crval1_ra"], spec["crval2_dec"], mjd_obs=60700.0)
    hdr2 = _create_wcs_header(spec["crval1_ra"], spec["crval2_dec"], mjd_obs=60882.5)

    fits.PrimaryHDU(data=img_ep1.astype(np.float32), header=hdr1).writeto(ep1_path, overwrite=True)
    fits.PrimaryHDU(data=img_ep2.astype(np.float32), header=hdr2).writeto(ep2_path, overwrite=True)

    # สร้าง Spectral Cube 102 แบนด์ (0.75 - 5.0 um) ตามฟิสิกส์ของวัตถุนั้น
    wl = WAVELENGTHS_102
    cube = np.zeros((102, ny, nx), dtype=np.float32)
    temp_k = spec["temp_k"]

    for i, w in enumerate(wl):
        if temp_k < 500.0:
            # ดาวแคระน้ำตาล Y-Dwarf / Planet X: พุ่งสูงที่หน้าต่างความโปร่งแสง 4.5 - 4.65 um
            peak_w = 4.50 if temp_k > 200.0 else 4.65
            cont = 45.0 * np.exp(-((w - peak_w) ** 2) / (2 * 0.95**2)) + 8.0
        else:
            # ดาวฤกษ์ M-Dwarf / Variable Star: สว่างช่วงอินฟราเรดใกล้สั้น + Dust Excess
            hc_k = 14387.77
            planck = (w**-3.0) / np.expm1(np.clip(hc_k / (w * temp_k), 1e-2, 50.0))
            cont = 55.0 * (planck / (planck + 0.05))
            if spec["forced_category"] == "variable_star":
                cont += 22.0 * np.exp(-((w - 4.7) ** 2) / (2 * 1.4**2))

        h2o = 1.0 - spec["h2o_depth"] * np.exp(-((w - 3.05) ** 2) / (2 * 0.09**2))
        ch4 = 1.0 - spec["ch4_depth"] * np.exp(-((w - 3.32) ** 2) / (2 * 0.08**2))
        co = 1.0 - spec["co_depth"] * np.exp(-((w - 4.45) ** 2) / (2 * 0.14**2))

        band_flux = cont * h2o * ch4 * co
        target_slice = band_flux * np.exp(-((x - x2) ** 2 + (y - y2) ** 2) / (2 * 1.4**2))
        cube[i] = (static_stars * 0.25) + target_slice + rng.normal(5.0, 0.45, (ny, nx))

    fits.PrimaryHDU(data=cube, header=hdr2).writeto(cube_path, overwrite=True)

    return {
        "ep1_path": ep1_path,
        "ep2_path": ep2_path,
        "cube_path": cube_path,
    }


def run_target_pipeline(
    target_id: str,
    title: str,
    fits_ep1_path: str,
    fits_ep2_path: str,
    fits_cube_path: str,
    ep1_xy: tuple[float, float],
    ep2_xy: tuple[float, float],
    use_live_vizier: bool = False,
    fallback_optical_invisible: bool = True,
    forced_category: str | None = None,
) -> SpherexTargetBundle:
    """
    รัน Pipeline เชื่อมโมดูล Astronomy และ ML เข้าด้วยกัน
    และ Validate ข้อมูลทั้งหมดผ่าน Pydantic Schema `SpherexTargetBundle`
    """
    # 1. WCS Alignment & Difference SNR Map
    align_res = align_and_subtract_epochs(fits_ep1_path, fits_ep2_path)
    wcs_ref: WCS = align_res["wcs_ref"]

    # แปลงพิกัดพิกเซลเป้าหมายใน Epoch 1 และ Epoch 2 เป็น (RA, Dec)
    sky_ep1 = wcs_ref.pixel_to_world(ep1_xy[0], ep1_xy[1])
    sky_ep2 = wcs_ref.pixel_to_world(ep2_xy[0], ep2_xy[1])
    ra1, dec1 = float(sky_ep1.ra.deg), float(sky_ep1.dec.deg)
    ra2, dec2 = float(sky_ep2.ra.deg), float(sky_ep2.dec.deg)

    # 2. วัดค่าความสว่าง (Aperture Photometry) ในแต่ละช่วงเวลา
    flux_ep1, _, _ = measure_single_band_flux(align_res["epoch1_raw"], wcs_ref, ra1, dec1)
    flux_ep2, _, _ = measure_single_band_flux(align_res["epoch2_aligned_raw"], wcs_ref, ra2, dec2)

    # 3. คำนวณ Proper Motion และการแปรแสง
    kinematics = compute_kinematics_and_variability(
        ra_ep1_deg=ra1,
        dec_ep1_deg=dec1,
        flux_ep1_ujy=flux_ep1,
        ra_ep2_deg=ra2,
        dec_ep2_deg=dec2,
        flux_ep2_ujy=flux_ep2,
        delta_years=align_res["delta_years"],
    )

    # 4. สกัดสเปกตรัม 102 แบนด์ (0.75 - 5.0 um) และตรวจจับแถบดูดกลืนโมเลกุล
    spectrum_102 = extract_102band_spectrum(fits_cube_path, ra2, dec2)
    detected_molecules = detect_molecular_absorption_bands(spectrum_102)

    # 5. Cross-Match กับแคตตาล็อก Gaia DR3 และ AllWISE
    catalog_info = query_gaia_and_wise_catalogs(
        wcs_ref=wcs_ref,
        target_ra_deg=ra2,
        target_dec_deg=dec2,
        use_live_vizier=use_live_vizier,
        fallback_optical_invisible=fallback_optical_invisible,
    )

    # 6. รันโมเดล AI (2D-CNN จับ Dipole + Spectral Classifier + Isolation Forest)
    ai_info = run_ai_analysis(
        cutout_16x16=align_res["cutout_16x16"],
        signature_info=align_res["signature_info"],
        spectrum_102_bands=spectrum_102,
        detected_molecules=detected_molecules,
        kinematics=kinematics,
        gaia_dr3_match=catalog_info["gaia_dr3_match"],
    )

    # 7. จัดหมวดหมู่วัตถุและตรวจสอบด้วย Pydantic Schema
    category = forced_category or classify_target_category(
        kinematics=kinematics,
        gaia_dr3_match=catalog_info["gaia_dr3_match"],
        anomaly_score=ai_info["anomaly_score"],
    )

    bundle = SpherexTargetBundle(
        target_id=target_id,
        title=title,
        target_category=category,
        epochs={
            "epoch1": {
                "mjd": align_res["epoch1_mjd"],
                "ra": round(ra1, 5),
                "dec": round(dec1, 5),
                "flux_ujy": flux_ep1,
            },
            "epoch2": {
                "mjd": align_res["epoch2_mjd"],
                "ra": round(ra2, 5),
                "dec": round(dec2, 5),
                "flux_ujy": flux_ep2,
            },
        },
        kinematics=kinematics,
        ai_analysis=ai_info,
        catalog_crossmatch=catalog_info,
        spectral_absorption_markers=STANDARD_ABSORPTION_MARKERS,
        spectrum_102_bands=spectrum_102,
        image_layers_64x64=align_res["image_layers_64x64"],
    )
    return bundle


def generate_all_benchmarks(use_live_vizier: bool = False) -> Dict[str, SpherexTargetBundle]:
    """
    เทรนโมเดล AI, สร้างไฟล์ FITS และส่งออกไฟล์ JSON ทั้ง 4 เคส
    ไปยัง contracts/ และ frontend/public/data/ พร้อมกัน
    """
    ensure_models_trained()
    CONTRACTS_DIR.mkdir(parents=True, exist_ok=True)
    FRONTEND_DATA_DIR.mkdir(parents=True, exist_ok=True)

    results: Dict[str, SpherexTargetBundle] = {}

    for target_id, spec in BENCHMARK_SPECS.items():
        paths = generate_target_fits_files(target_id, spec)
        bundle = run_target_pipeline(
            target_id=target_id,
            title=spec["title"],
            fits_ep1_path=paths["ep1_path"],
            fits_ep2_path=paths["ep2_path"],
            fits_cube_path=paths["cube_path"],
            ep1_xy=spec["ep1_xy"],
            ep2_xy=spec["ep2_xy"],
            use_live_vizier=use_live_vizier,
            fallback_optical_invisible=spec["optical_invisible"],
            forced_category=spec["forced_category"],
        )

        json_str = bundle.model_dump_json(indent=2)
        fname = spec["filename"]

        # บันทึกลงทั้ง contracts/ และ frontend/public/data/
        (CONTRACTS_DIR / fname).write_text(json_str, encoding="utf-8")
        (FRONTEND_DATA_DIR / fname).write_text(json_str, encoding="utf-8")

        results[target_id] = bundle
        print(
            f"[OK] {target_id} -> {fname} | "
            f"Category: {bundle.target_category} | "
            f"Class: {bundle.ai_analysis.predicted_class} | "
            f"Temp: {bundle.ai_analysis.estimated_temp_k} K | "
            f"Anomaly: {bundle.ai_analysis.anomaly_score}"
        )

    return results


if __name__ == "__main__":
    generate_all_benchmarks(use_live_vizier=False)
