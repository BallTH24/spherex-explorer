from pathlib import Path
from typing import Dict, Any, Tuple
import numpy as np
import joblib
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.neighbors import KNeighborsClassifier

from .synthetic_data import generate_synthetic_spectral_samples

WEIGHTS_DIR = Path(__file__).resolve().parent.parent / "models_weights"
SPECTRAL_BUNDLE_PATH = WEIGHTS_DIR / "spectral_models.joblib"

_SPECTRAL_BUNDLE: Dict[str, Any] | None = None


def get_or_train_spectral_models(force_retrain: bool = False) -> Dict[str, Any]:
    """
    โหลดหรือสร้างโมเดล Machine Learning ด้านสเปกโตรสโกปี:
    1. Temperature Regressor (RandomForest): ประเมินอุณหภูมิยังผล (Effective Temp T_eff [K]) จาก 102 แบนด์
    2. Spectral Classifier (KNN): ระบุประเภทสเปกตรัมตามหลักดาราศาสตร์ฟิสิกส์
    3. Anomaly Detector (Isolation Forest): ให้คะแนนความผิดปกติสำหรับค้นหา Planet X
    """
    global _SPECTRAL_BUNDLE
    if _SPECTRAL_BUNDLE is not None and not force_retrain:
        return _SPECTRAL_BUNDLE

    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    if SPECTRAL_BUNDLE_PATH.exists() and not force_retrain:
        try:
            bundle = joblib.load(str(SPECTRAL_BUNDLE_PATH))
            _SPECTRAL_BUNDLE = bundle
            return bundle
        except Exception:
            pass

    x_train, y_temp, y_cls = generate_synthetic_spectral_samples(n_samples=600)

    # 1. Temperature Regressor
    temp_model = RandomForestRegressor(n_estimators=40, random_state=42, n_jobs=-1)
    temp_model.fit(x_train, y_temp)

    # 2. Classifier
    cls_model = KNeighborsClassifier(n_neighbors=3, weights="distance")
    cls_model.fit(x_train, y_cls)

    # 3. Isolation Forest for Anomaly Detection (ฝึกกับประชากรดาวปกติ T > 200 K)
    normal_mask = (y_temp > 220.0)
    iso_forest = IsolationForest(n_estimators=60, contamination=0.08, random_state=42)
    iso_forest.fit(x_train[normal_mask])

    bundle = {
        "temp_model": temp_model,
        "cls_model": cls_model,
        "iso_forest": iso_forest,
    }

    try:
        joblib.dump(bundle, str(SPECTRAL_BUNDLE_PATH))
    except Exception:
        pass

    _SPECTRAL_BUNDLE = bundle
    return bundle


def predict_spectral_properties(
    spectrum_fluxes: np.ndarray,
    gaia_dr3_match: bool,
    kinematics: Dict[str, float],
    detected_molecules: list[str],
) -> Tuple[str, float, float]:
    """
    วิเคราะห์คุณสมบัติของสเปกตรัม:
    - คืนค่า (predicted_class, estimated_temp_k, anomaly_score)
    """
    bundle = get_or_train_spectral_models()
    max_val = float(np.max(spectrum_fluxes))
    if max_val > 1e-6:
        norm_input = (spectrum_fluxes / max_val).reshape(1, -1)
    else:
        norm_input = np.zeros((1, len(spectrum_fluxes)), dtype=np.float32)

    est_temp = float(bundle["temp_model"].predict(norm_input)[0])
    pred_cls = str(bundle["cls_model"].predict(norm_input)[0])

    # Isolation Forest score: ยิ่งคะแนนดิบลบมาก -> แปลว่ายิ่งผิดปกติ (Anomaly)
    raw_score = float(bundle["iso_forest"].score_samples(norm_input)[0])
    base_anomaly = float(np.clip(1.0 - ((raw_score + 0.55) / 0.40), 0.05, 0.85))

    pm = kinematics.get("proper_motion_arcsec_yr", 0.0)
    dflux = abs(kinematics.get("flux_change_pct", 0.0))

    # กฎฟิสิกส์เสริมความฉลาด (Physics-Informed Prior):
    # 1. วัตถุที่ไม่มีข้อมูลใน Gaia (ตามืด) + อุณหภูมิเย็นเฉียบ (< 200 K) + เคลื่อนที่ได้ -> Planet X Candidate
    if not gaia_dr3_match and est_temp < 200.0 and pm >= 0.4:
        anomaly_score = float(min(0.98, max(0.91, base_anomaly + 0.35)))
        pred_cls = "Uncharted Ultra-Cold Sub-stellar / Planet X Candidate"
    # 2. วัตถุที่ไม่มีข้อมูลใน Gaia + อุณหภูมิ 200 - 400 K (Cold Y-Dwarf)
    elif not gaia_dr3_match and est_temp < 400.0:
        anomaly_score = float(min(0.93, max(0.85, base_anomaly + 0.20)))
        pred_cls = "Cold Y-Dwarf / Sub-stellar Candidate"
    # 3. ดาวแปรแสงที่ความสว่างพุ่งขึ้นสูง
    elif dflux > 25.0:
        pred_cls = "T Tauri Variable Star / Pre-Main Sequence"
        anomaly_score = float(round(base_anomaly, 2))
    # 4. ดาวปกติ (M-Dwarf / Gaia Match)
    else:
        anomaly_score = float(round(base_anomaly, 2))

    return pred_cls, round(est_temp, 1), round(anomaly_score, 2)
