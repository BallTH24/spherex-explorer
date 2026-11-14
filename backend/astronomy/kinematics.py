from typing import Dict, Any, Literal
from astropy.coordinates import SkyCoord
import astropy.units as u

TargetCategory = Literal["moving_object", "variable_star", "anomaly_candidate"]


def compute_kinematics_and_variability(
    ra_ep1_deg: float,
    dec_ep1_deg: float,
    flux_ep1_ujy: float,
    ra_ep2_deg: float,
    dec_ep2_deg: float,
    flux_ep2_ujy: float,
    delta_years: float,
) -> Dict[str, float]:
    """
    คำนวณค่าพารามิเตอร์การเคลื่อนที่และการแปรแสงระหว่าง Epoch 1 และ Epoch 2
    คืนค่าตรงตาม Schema `KinematicsInfo`
    """
    c1 = SkyCoord(ra=ra_ep1_deg * u.deg, dec=dec_ep1_deg * u.deg, frame="icrs")
    c2 = SkyCoord(ra=ra_ep2_deg * u.deg, dec=dec_ep2_deg * u.deg, frame="icrs")

    sep_arcsec = float(c1.separation(c2).to(u.arcsec).value)
    pa_deg = float(c1.position_angle(c2).to(u.deg).value) if sep_arcsec > 1e-4 else 0.0

    dt = delta_years if abs(delta_years) > 1e-5 else 0.5
    pm_arcsec_yr = sep_arcsec / abs(dt)

    # คำนวณเปอร์เซ็นต์การเปลี่ยนแปลงความสว่างสำหรับตรวจจับดาวแปรแสง (เช่น RW Aurigae, R Draconis)
    denom = max(abs(flux_ep1_ujy), 1e-3)
    flux_change_pct = ((flux_ep2_ujy - flux_ep1_ujy) / denom) * 100.0

    return {
        "separation_arcsec": round(sep_arcsec, 3),
        "proper_motion_arcsec_yr": round(pm_arcsec_yr, 3),
        "position_angle_deg": round(pa_deg, 2),
        "flux_change_pct": round(flux_change_pct, 2),
    }


def classify_target_category(
    kinematics: Dict[str, float],
    gaia_dr3_match: bool,
    anomaly_score: float = 0.0,
    pm_threshold_arcsec_yr: float = 0.5,
    variability_threshold_pct: float = 15.0,
) -> TargetCategory:
    """
    จัดหมวดหมู่เป้าหมายตามพฤติกรรมทางฟิสิกส์:
    1. 'anomaly_candidate': เคลื่อนที่ + มองไม่เห็นในกล้องแสงปกติ (Gaia) + Anomaly Score สูง (เช่น Planet X)
    2. 'variable_star': พิกัดแทบไม่ขยับ (< 0.5 "/yr) แต่ความสว่างเปลี่ยนเกิน 15% (เช่น RW Aurigae, R Draconis)
    3. 'moving_object': วัตถุที่มี Proper Motion สูง (เช่น Barnard's Star, WISE 0855, Epsilon Indi B)
    """
    pm = kinematics["proper_motion_arcsec_yr"]
    dflux = abs(kinematics["flux_change_pct"])

    if not gaia_dr3_match and anomaly_score >= 0.85 and pm >= pm_threshold_arcsec_yr:
        return "anomaly_candidate"

    if pm < pm_threshold_arcsec_yr and dflux >= variability_threshold_pct:
        return "variable_star"

    return "moving_object"
