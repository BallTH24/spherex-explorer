import json
from pathlib import Path
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.schemas import SpherexTargetBundle
from backend.ml import ensure_models_trained, predict_dipole_confidence
from backend.pipeline import generate_all_benchmarks, BENCHMARK_SPECS, CONTRACTS_DIR
from backend.main import app


@pytest.fixture(scope="session", autouse=True)
def setup_models_and_benchmarks():
    """เตรียมน้ำหนักโมเดลและสร้างไฟล์ JSON ทั้ง 4 เคสก่อนเริ่มรันชุดทดสอบ"""
    ensure_models_trained()
    generate_all_benchmarks(use_real_nasa=False, use_live_vizier=False)


# =====================================================================
# 1. ทดสอบโมเดล AI (2D-CNN Dipole Detector)
# =====================================================================
def test_dipole_cnn_distinguishes_real_vs_bogus():
    y, x = np.mgrid[0:16, 0:16]

    # จำลอง Real Moving Dipole (ยอดบวกที่ (8,8) และหลุมลบที่ (12,9))
    pos_lobe = 14.0 * np.exp(-((x - 8.0) ** 2 + (y - 8.0) ** 2) / (2 * 1.4**2))
    neg_lobe = -13.5 * np.exp(-((x - 12.0) ** 2 + (y - 9.0) ** 2) / (2 * 1.4**2))
    real_cutout = (pos_lobe + neg_lobe).astype(np.float32)

    is_real, conf_real = predict_dipole_confidence(
        real_cutout,
        signature_info={"is_dipole_pattern": True, "is_monopole_pattern": False, "max_snr": 14.0, "min_snr": -13.5},
    )
    assert is_real is True
    assert conf_real >= 0.80

    # จำลอง Cosmic Ray / Monopole (จุดสว่างเดี่ยว ไม่มีหลุมลบ)
    bogus_cutout = np.zeros((16, 16), dtype=np.float32)
    bogus_cutout[8, 8] = 25.0
    is_bogus_real, conf_bogus = predict_dipole_confidence(
        bogus_cutout,
        signature_info={"is_dipole_pattern": False, "is_monopole_pattern": True, "max_snr": 25.0, "min_snr": -1.1},
    )
    assert is_bogus_real is False
    assert conf_bogus < 0.25


# =====================================================================
# 2. ทดสอบฟิสิกส์และ Schema ของไฟล์ JSON ทั้ง 4 เคสมาตรฐาน
# =====================================================================
def test_all_four_benchmark_jsons_and_physics():
    for target_id, spec in BENCHMARK_SPECS.items():
        json_path = Path(CONTRACTS_DIR) / spec["filename"]
        assert json_path.exists(), f"ไม่พบไฟล์ {json_path}"

        raw_data = json.loads(json_path.read_text(encoding="utf-8"))
        bundle = SpherexTargetBundle(**raw_data)

        # ตรวจมิติข้อมูลภาพ 64x64 และสเปกตรัม 102 แบนด์
        assert len(bundle.spectrum_102_bands) == 102
        assert len(bundle.image_layers_64x64.epoch1_asinh) == 64
        assert len(bundle.image_layers_64x64.difference_snr[0]) == 64

        # ตรวจพฤติกรรมทางฟิสิกส์เฉพาะตัวของแต่ละเป้าหมาย
        if target_id == "WISE_0855_0714":
            assert bundle.target_category == "moving_object"
            assert bundle.ai_analysis.is_real_dipole is True
            assert bundle.catalog_crossmatch.gaia_dr3_match is False
            assert bundle.ai_analysis.estimated_temp_k < 500.0
            assert any("CH4" in m for m in bundle.ai_analysis.detected_molecules)

        elif target_id == "BARNARDS_STAR":
            assert bundle.target_category == "moving_object"
            assert bundle.ai_analysis.is_real_dipole is True
            assert bundle.catalog_crossmatch.gaia_dr3_match is True
            assert bundle.ai_analysis.estimated_temp_k > 2500.0

        elif target_id == "RW_AURIGAE":
            assert bundle.target_category == "variable_star"
            assert bundle.ai_analysis.is_real_dipole is False
            assert bundle.kinematics.flux_change_pct > 50.0

        elif target_id == "PLANET_X_CANDIDATE":
            assert bundle.target_category == "anomaly_candidate"
            assert bundle.ai_analysis.anomaly_score >= 0.85
            assert bundle.catalog_crossmatch.gaia_dr3_match is False


# =====================================================================
# 3. ทดสอบ FastAPI Endpoints (/health, /api/targets, /api/analyze)
# =====================================================================
def test_fastapi_endpoints_end_to_end():
    with TestClient(app) as client:
        # 1. Health Check
        res_health = client.get("/health")
        assert res_health.status_code == 200
        assert res_health.json()["status"] == "ok"

        # 2. List Targets (ต้องมีครบทั้ง 4 เคส)
        res_list = client.get("/api/targets")
        assert res_list.status_code == 200
        targets = res_list.json()
        assert len(targets) == 4

        # 3. Get Target Detail
        res_wise = client.get("/api/targets/wise0855")
        assert res_wise.status_code == 200
        assert res_wise.json()["target_id"] == "WISE_0855_0714"

        # 4. Live Coordinate Analysis (จำลองการคลิกพิกัดบนเว็บ)
        res_analyze = client.post(
            "/api/analyze",
            json={
                "ra": 133.7783,
                "dec": -7.2400,
                "base_target_id": "WISE_0855_0714",
                "use_live_vizier": False,
            },
        )
        assert res_analyze.status_code == 200
        analyzed = res_analyze.json()
        assert len(analyzed["spectrum_102_bands"]) == 102
        assert "anomaly_score" in analyzed["ai_analysis"]
