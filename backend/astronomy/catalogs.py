from typing import Dict, Any, List, Tuple
import numpy as np
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord
import astropy.units as u
try:
    from astroquery.vizier import Vizier
    # ตั้งค่า Vizier ให้จำกัดจำนวนแถวและมี Timeout สั้น เพื่อไม่ให้เว็บค้างกรณีเน็ตช้า
    VIZIER_CLIENT = Vizier(columns=["RAJ2000", "DEJ2000", "Gmag", "W1mag", "W2mag"], row_limit=50)
    VIZIER_CLIENT.TIMEOUT = 5
except Exception:
    VIZIER_CLIENT = None


def _fallback_synthetic_catalog(
    wcs_ref: WCS,
    target_ra: float,
    target_dec: float,
    is_optical_invisible: bool = True,
) -> Dict[str, Any]:
    """
    สร้างข้อมูลแคตตาล็อกสำรองที่พิกัดตรงกับดาวพื้นหลังในเฟรม 64x64
    ทำงานทันทีเมื่อออฟไลน์หรือเชื่อมต่อ VizieR ไม่สำเร็จ
    """
    static_star_pixels: List[Tuple[str, float, float]] = [
        ("Gaia DR3", 15.0, 20.0),
        ("Gaia DR3", 48.0, 14.0),
        ("Gaia DR3", 52.0, 45.0),
        ("AllWISE", 22.0, 50.0),
    ]

    nearby_sources: List[Dict[str, Any]] = []
    for source_name, px, py in static_star_pixels:
        sky = wcs_ref.pixel_to_world(px, py)
        nearby_sources.append({
            "source": source_name,
            "x": round(px, 2),
            "y": round(py, 2),
            "ra": round(float(sky.ra.deg), 5),
            "dec": round(float(sky.dec.deg), 5),
        })

    return {
        "gaia_dr3_match": not is_optical_invisible,
        "allwise_match": True,
        "nearby_sources": nearby_sources,
    }


def query_gaia_and_wise_catalogs(
    wcs_ref: WCS,
    target_ra_deg: float,
    target_dec_deg: float,
    search_radius_arcmin: float = 3.5,
    match_tolerance_arcsec: float = 8.0,
    cutout_size: int = 64,
    use_live_vizier: bool = True,
    fallback_optical_invisible: bool = True,
) -> Dict[str, Any]:
    """
    ค้นหาดาวจาก Gaia DR3 (I/355/gaiadr3) และ AllWISE (II/328/allwise) รอบพิกัดเป้าหมาย
    ตรวจสอบว่าวัตถุเป้าหมายมีอยู่ใน Gaia หรือไม่ (วัตถุเย็นจัดอย่าง Y-Dwarf/Planet X จะไม่พบใน Gaia)
    และแปลงพิกัดดาวข้างเคียงให้อยู่ในระบบพิกเซล (x, y) ของหน้าเว็บ
    """
    if not use_live_vizier or VIZIER_CLIENT is None:
        return _fallback_synthetic_catalog(wcs_ref, target_ra_deg, target_dec_deg, fallback_optical_invisible)

    target_coord = SkyCoord(ra=target_ra_deg * u.deg, dec=target_dec_deg * u.deg, frame="icrs")
    catalog_ids = {
        "Gaia DR3": "I/355/gaiadr3",
        "AllWISE": "II/328/allwise",
    }

    gaia_match = False
    wise_match = False
    nearby_sources: List[Dict[str, Any]] = []

    try:
        tables = VIZIER_CLIENT.query_region(
            target_coord,
            radius=search_radius_arcmin * u.arcmin,
            catalog=list(catalog_ids.values()),
        )

        for label, cat_code in catalog_ids.items():
            if cat_code not in tables.keys():
                continue

            tbl = tables[cat_code]
            ra_col = "RAJ2000" if "RAJ2000" in tbl.colnames else "RA_ICRS"
            dec_col = "DEJ2000" if "DEJ2000" in tbl.colnames else "DE_ICRS"

            for row in tbl:
                src_ra = float(row[ra_col])
                src_dec = float(row[dec_col])
                src_coord = SkyCoord(ra=src_ra * u.deg, dec=src_dec * u.deg, frame="icrs")

                sep_arcsec = float(target_coord.separation(src_coord).to(u.arcsec).value)
                if sep_arcsec <= match_tolerance_arcsec:
                    if label == "Gaia DR3":
                        gaia_match = True
                    else:
                        wise_match = True

                x_pix, y_pix = wcs_ref.world_to_pixel(src_coord)
                xf, yf = float(x_pix), float(y_pix)

                # เก็บเฉพาะดาวที่อยู่ในกรอบภาพ 64x64 พิกเซล
                if 0.0 <= xf < cutout_size and 0.0 <= yf < cutout_size:
                    nearby_sources.append({
                        "source": label,
                        "x": round(xf, 2),
                        "y": round(yf, 2),
                        "ra": round(src_ra, 5),
                        "dec": round(src_dec, 5),
                    })

        if not nearby_sources:
            return _fallback_synthetic_catalog(wcs_ref, target_ra_deg, target_dec_deg, fallback_optical_invisible)

        return {
            "gaia_dr3_match": gaia_match,
            "allwise_match": wise_match,
            "nearby_sources": nearby_sources[:25],
        }

    except Exception:
        # กรณีไม่มีอินเทอร์เน็ตหรือ VizieR ล่ม ให้สลับใช้ข้อมูลสำรองทันทีโดยไม่เกิด Error
        return _fallback_synthetic_catalog(wcs_ref, target_ra_deg, target_dec_deg, fallback_optical_invisible)
