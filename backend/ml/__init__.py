from typing import Dict, Any, List
import numpy as np

from .synthetic_data import WAVELENGTHS_102
from .dipole_cnn import get_or_train_dipole_cnn, predict_dipole_confidence
from .spectral_models import get_or_train_spectral_models, predict_spectral_properties


def ensure_models_trained() -> None:
    """
    ตรวจสอบว่ามีโมเดล AI ทั้ง 2D-CNN และ Spectral/Anomaly Models แล้วหรือยัง
    หากยังไม่มี จะทำการเทรนและบันทึกค่าน้ำหนักลงใน models_weights/ โดยอัตโนมัติ
    """
    get_or_train_dipole_cnn()
    get_or_train_spectral_models()


def run_ai_analysis(
    cutout_16x16: np.ndarray,
    signature_info: Dict[str, Any],
    spectrum_102_bands: List[Dict[str, Any]],
    detected_molecules: List[str],
    kinematics: Dict[str, float],
    gaia_dr3_match: bool,
) -> Dict[str, Any]:
    """
    รัน AI วิเคราะห์ทั้งมิติภาพ (2D-CNN Dipole) และมิติสเปกโตรสโกปี (Spectral & Anomaly)
    คืนค่าที่สอดคล้องกับ Schema `AiAnalysisInfo` 100%
    """
    # 1. 2D-CNN Cutout Analysis
    cnn_model = get_or_train_dipole_cnn()
    is_cnn_dipole, confidence = predict_dipole_confidence(cnn_model, cutout_16x16)

    # ผสานการตัดสินใจจาก WCS/MAD Transient Signature
    if signature_info.get("is_monopole_pattern", False) and not signature_info.get("is_dipole_pattern", False):
        # จุดเดี่ยวแปรแสง ไม่ใช่ Dipole
        is_real_dipole = False
        dipole_conf = float(min(0.20, confidence))
    elif signature_info.get("is_dipole_pattern", False):
        is_real_dipole = True
        dipole_conf = float(max(0.92, confidence))
    else:
        is_real_dipole = is_cnn_dipole
        dipole_conf = confidence

    # 2. Spectral Properties Analysis
    fluxes = np.array([pt["flux_ujy"] for pt in spectrum_102_bands], dtype=np.float32)
    pred_class, est_temp, anomaly_score = predict_spectral_properties(
        spectrum_fluxes=fluxes,
        gaia_dr3_match=gaia_dr3_match,
        kinematics=kinematics,
        detected_molecules=detected_molecules,
    )

    return {
        "is_real_dipole": is_real_dipole,
        "dipole_confidence": round(dipole_conf, 3),
        "predicted_class": pred_class,
        "estimated_temp_k": est_temp,
        "anomaly_score": anomaly_score,
        "detected_molecules": detected_molecules,
    }


__all__ = [
    "WAVELENGTHS_102",
    "ensure_models_trained",
    "run_ai_analysis",
    "predict_dipole_confidence",
]
