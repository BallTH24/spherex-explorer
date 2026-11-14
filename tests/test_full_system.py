import json
import time
from pathlib import Path
import numpy as np
import pytest
from astropy.wcs import WCS
from fastapi.testclient import TestClient

from backend.schemas import SpherexTargetBundle
from backend.main import LiveAnalyzeRequest, app
from backend.astronomy.alignment import (
    asinh_stretch_to_list,
    extract_16x16_cutout,
    detect_transient_signature,
)
from backend.astronomy.kinematics import (
    compute_kinematics_and_variability,
    classify_target_category,
)
from backend.astronomy.photometry import (
    measure_single_band_flux,
    extract_102band_spectrum,
    detect_molecular_absorption_bands,
)
from backend.astronomy.catalogs import query_gaia_and_wise_catalogs
from backend.ml import (
    ensure_models_trained,
    get_or_train_dipole_cnn,
    predict_dipole_confidence,
    get_or_train_spectral_models,
    run_ai_analysis,
    WAVELENGTHS_102,
)
from backend.pipeline import (
    generate_all_benchmarks,
    BENCHMARK_SPECS,
    CONTRACTS_DIR,
)

WORKSPACE_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session", autouse=True)
def prepare_environment():
    """เตรียมความพร้อมโมเดลและ Benchmark JSONs ก่อนเริ่มชุดทดสอบทั้งหมด"""
    ensure_models_trained()
    generate_all_benchmarks(use_real_nasa=False, use_live_vizier=False)


# =====================================================================
# 1. ทดสอบระบบฟิสิกส์ดาราศาสตร์ (Astrophysics Subsystem)
# =====================================================================
class TestAstrophysicsSubsystem:
    """ทดสอบโมดูลการประมวลผลทางดาราศาสตร์ ความถูกต้องทางคณิตศาสตร์และพิกัดท้องฟ้า"""

    def test_asinh_stretch_properties(self):
        """ตรวจสอบว่า ASINH Stretch ปรับสเกลข้อมูลให้อยู่ในช่วง [0.0, 1.0] อย่างถูกต้อง"""
        raw_image = np.array([[-100.0, 0.0, 50.0], [500.0, 10000.0, 50000.0]], dtype=np.float32)
        stretched = asinh_stretch_to_list(raw_image, scale=0.15)
        arr = np.array(stretched)

        assert arr.shape == (2, 3)
        assert np.min(arr) >= 0.0
        assert np.max(arr) <= 1.0
        # ยืนยันว่าค่าที่สว่างกว่าต้องมีสเกลมากกว่าหลังแปลง
        assert arr[1, 2] > arr[0, 1]

    def test_cutout_extraction_and_bounds(self):
        """ทดสอบการตัดภาพ Cutout 16x16 พิกเซลรอบจุด SNR สูงสุด พร้อมขอบ Padding"""
        snr_map = np.zeros((64, 64), dtype=np.float32)
        snr_map[10, 12] = 20.0  # จุดพีคใกล้ขอบ

        cutout = extract_16x16_cutout(snr_map, center_xy=(12, 10))
        assert cutout.shape == (16, 16)
        assert cutout[8, 8] == 20.0  # จุดพีคต้องอยู่กึ่งกลาง Cutout พอดี

    def test_transient_signature_detection_modes(self):
        """ทดสอบการตรวจจับ Dipole (คู่บวก/ลบ) เทียบกับ Monopole (ดาวแปรแสงเดี่ยว)"""
        # 1. เคส Dipole: มียอดบวกที่ (20, 20) และหลุมลบที่ (23, 21)
        dipole_map = np.zeros((64, 64), dtype=np.float32)
        dipole_map[20, 20] = 12.0
        dipole_map[23, 21] = -11.5
        sig_dipole = detect_transient_signature(dipole_map, threshold_sigma=4.5)

        assert sig_dipole["is_dipole_pattern"] is True
        assert sig_dipole["is_monopole_pattern"] is False
        assert sig_dipole["dipole_pixel_separation"] > 0.0

        # 2. เคส Monopole: มียอดบวกเดี่ยว ไม่มีหลุมลบ
        monopole_map = np.zeros((64, 64), dtype=np.float32)
        monopole_map[30, 30] = 18.0
        sig_monopole = detect_transient_signature(monopole_map, threshold_sigma=4.5)

        assert sig_monopole["is_dipole_pattern"] is False
        assert sig_monopole["is_monopole_pattern"] is True

    def test_kinematics_and_position_angle(self):
        """ทดสอบการคำนวณการเคลื่อนที่เฉพาะ (Proper Motion) และมุมทิศ (Position Angle)"""
        # วัตถุขยับจาก RA=10.0, Dec=20.0 ไป RA=10.005, Dec=20.005 ในเวลา 2.0 ปี
        res = compute_kinematics_and_variability(
            ra_ep1_deg=10.0,
            dec_ep1_deg=20.0,
            flux_ep1_ujy=100.0,
            ra_ep2_deg=10.005,
            dec_ep2_deg=20.005,
            flux_ep2_ujy=105.0,
            delta_years=2.0,
        )

        assert res["separation_arcsec"] > 10.0
        assert res["proper_motion_arcsec_yr"] > 5.0
        assert 0.0 <= res["position_angle_deg"] <= 360.0
        assert abs(res["flux_change_pct"] - 5.0) < 0.1

    def test_target_categorization_logic(self):
        """ทดสอบการจำแนกเป้าหมายเป็น moving_object, variable_star, หรือ anomaly_candidate"""
        # เคส Moving Object (Proper Motion สูง)
        cat_moving = classify_target_category(
            kinematics={"proper_motion_arcsec_yr": 8.5, "flux_change_pct": 2.0},
            gaia_dr3_match=True,
            anomaly_score=0.3,
        )
        assert cat_moving == "moving_object"

        # เคส Variable Star (Proper Motion ต่ำ แต่ความสว่างเปลี่ยนเกิน 15%)
        cat_variable = classify_target_category(
            kinematics={"proper_motion_arcsec_yr": 0.05, "flux_change_pct": 65.0},
            gaia_dr3_match=True,
            anomaly_score=0.4,
        )
        assert cat_variable == "variable_star"

        # เคส Anomaly Candidate (คะแนนความผิดปกติสูง และตาบอดใน Gaia DR3)
        cat_anomaly = classify_target_category(
            kinematics={"proper_motion_arcsec_yr": 5.0, "flux_change_pct": 4.0},
            gaia_dr3_match=False,
            anomaly_score=0.92,
        )
        assert cat_anomaly == "anomaly_candidate"

    def test_synthetic_gaia_crossmatch(self):
        """ทดสอบฟังก์ชัน Crossmatch ฐานข้อมูล Gaia DR3 และ AllWISE"""
        wcs_sample = WCS(naxis=2)
        wcs_sample.wcs.crpix = [32.0, 32.0]
        wcs_sample.wcs.cdelt = [-0.0005, 0.0005]
        wcs_sample.wcs.crval = [269.452, 4.693]
        wcs_sample.wcs.ctype = ["RA---TAN", "DEC--TAN"]

        # 1. วัตถุที่สว่างใน Optical/Gaia (เช่น Barnard's Star หรือดาวทั่วไป)
        res_optical = query_gaia_and_wise_catalogs(
            wcs_ref=wcs_sample,
            target_ra_deg=269.452,
            target_dec_deg=4.693,
            use_live_vizier=False,
            fallback_optical_invisible=False,
        )
        assert res_optical["gaia_dr3_match"] is True
        assert res_optical["allwise_match"] is True
        assert len(res_optical["nearby_sources"]) > 0

        # 2. วัตถุที่มืดใน Optical (ตาบอดใน Gaia DR3 เช่น WISE 0855 หรือ Planet X)
        res_blind = query_gaia_and_wise_catalogs(
            wcs_ref=wcs_sample,
            target_ra_deg=133.7783,
            target_dec_deg=-7.2400,
            use_live_vizier=False,
            fallback_optical_invisible=True,
        )
        assert res_blind["gaia_dr3_match"] is False
        assert res_blind["allwise_match"] is True


# =====================================================================
# 2. ทดสอบระบบ AI & Machine Learning Subsystem
# =====================================================================
class TestMachineLearningSubsystem:
    """ทดสอบโมเดล PyTorch 2D-CNN, สเปกโตรสโกปี KNN/RandomForest และ Isolation Forest"""

    def test_dipole_cnn_inference_contract(self):
        """ตรวจสอบความแม่นยำของ 2D-CNN ในการจำแนก Dipole และ Output Probabilities"""
        cnn = get_or_train_dipole_cnn()
        assert cnn is not None

        # 1. ทดสอบด้วยอินพุต Dipole ชัดเจน
        y, x = np.mgrid[0:16, 0:16]
        pos = 15.0 * np.exp(-((x - 8.0) ** 2 + (y - 8.0) ** 2) / (2 * 1.5**2))
        neg = -14.0 * np.exp(-((x - 12.0) ** 2 + (y - 9.0) ** 2) / (2 * 1.5**2))
        dipole_cutout = (pos + neg).astype(np.float32)

        is_dipole, conf = predict_dipole_confidence(cnn, dipole_cutout)
        assert isinstance(is_dipole, bool)
        assert isinstance(conf, float)
        assert 0.0 <= conf <= 1.0

    def test_spectral_models_bundle(self):
        """ตรวจสอบโมเดลสเปกตรัมทั้ง 3 ตัว: Temperature Regressor, Classifier, Anomaly Detector"""
        bundle = get_or_train_spectral_models()
        assert "temp_model" in bundle
        assert "cls_model" in bundle
        assert "iso_forest" in bundle

        # จำลองสเปกตรัมวัตถุเย็นจัด (~180 K) ยอดพีคเลื่อนไปย่านอินฟราเรดคลื่นยาว
        x_cold = np.exp(-((WAVELENGTHS_102 - 4.5) ** 2) / 0.8).astype(np.float32)
        norm_cold = (x_cold / np.max(x_cold)).reshape(1, -1)

        predicted_temp = float(bundle["temp_model"].predict(norm_cold)[0])
        predicted_class = str(bundle["cls_model"].predict(norm_cold)[0])

        assert predicted_temp < 600.0  # ต้องทำนายว่าเป็นวัตถุอุณหภูมิต่ำ
        assert any(kw in predicted_class for kw in ["Candidate", "Y-Dwarf", "Planet X", "Sub-stellar"])

    def test_molecular_absorption_markers(self):
        """ตรวจสอบการตรวจจับแถบดูดกลืนโมเลกุลน้ำ (H2O) และมีเทน (CH4)"""
        # สร้างสเปกตรัมจำลองที่มีหลุมดูดกลืน CH4 ที่ 3.32 um เทียบกับ Continuum ที่ 3.7 um
        fluxes = np.ones_like(WAVELENGTHS_102) * 10.0
        ch4_dip = (WAVELENGTHS_102 >= 3.20) & (WAVELENGTHS_102 <= 3.45)
        fluxes[ch4_dip] = 3.0  # ตกฮวบเหลือ 30%

        spec_list = [
            {"wavelength_um": float(w), "flux_ujy": float(f), "flux_err_ujy": 0.1, "snr": 30.0}
            for w, f in zip(WAVELENGTHS_102, fluxes)
        ]
        molecules = detect_molecular_absorption_bands(spec_list)
        assert any("CH4" in m or "Methane" in m for m in molecules)


# =====================================================================
# 3. ทดสอบไฟล์สัญญาข้อมูลและเกณฑ์ NASA (Contracts & Physics Invariants)
# =====================================================================
class TestNasaBenchmarkContracts:
    """ทดสอบความสมบูรณ์ทางฟิสิกส์ของไฟล์ Benchmark JSON ทั้ง 4 เป้าหมายตามเกณฑ์ NASA"""

    @pytest.mark.parametrize("target_id, spec", BENCHMARK_SPECS.items())
    def test_benchmark_json_schema_completeness(self, target_id, spec):
        json_path = Path(CONTRACTS_DIR) / spec["filename"]
        assert json_path.exists(), f"Missing benchmark file: {json_path}"

        raw_json = json.loads(json_path.read_text(encoding="utf-8"))
        bundle = SpherexTargetBundle(**raw_json)

        # 1. โครงสร้างมิติข้อมูล
        assert len(bundle.spectrum_102_bands) == 102
        assert len(bundle.image_layers_64x64.epoch1_asinh) == 64
        assert len(bundle.image_layers_64x64.epoch1_asinh[0]) == 64
        assert len(bundle.image_layers_64x64.epoch2_asinh) == 64
        assert len(bundle.image_layers_64x64.difference_snr) == 64

        # 2. ช่วงคลื่น SPHEREx ต้องครอบคลุม 0.75 ถึง 5.00 ไมครอน
        first_wave = bundle.spectrum_102_bands[0].wavelength_um
        last_wave = bundle.spectrum_102_bands[-1].wavelength_um
        assert abs(first_wave - 0.75) < 0.05
        assert abs(last_wave - 5.00) < 0.05

        # 3. Telemetry และสถานะการตรวจสอบ
        assert bundle.target_id == target_id
        assert len(bundle.title) > 0

    def test_wise0855_invariants(self):
        """WISE 0855: ดาวแคระน้ำตาลคลาส Y เคลื่อนที่เร็ว อุณหภูมิเยือกแข็ง ตาบอดใน Gaia DR3"""
        raw = json.loads((Path(CONTRACTS_DIR) / "sample_wise0855.json").read_text())
        b = SpherexTargetBundle(**raw)
        assert b.target_category == "moving_object"
        assert b.ai_analysis.is_real_dipole is True
        assert b.ai_analysis.dipole_confidence >= 0.85
        assert b.catalog_crossmatch.gaia_dr3_match is False
        assert b.ai_analysis.estimated_temp_k < 400.0
        assert b.kinematics.proper_motion_arcsec_yr > 8.0

    def test_barnards_star_invariants(self):
        """Barnard's Star: ดาวแคระแดง M-Dwarf ดาวฤกษ์เคลื่อนที่เร็วที่สุดในท้องฟ้า มีใน Gaia DR3"""
        raw = json.loads((Path(CONTRACTS_DIR) / "barnards_star.json").read_text())
        b = SpherexTargetBundle(**raw)
        assert b.target_category == "moving_object"
        assert b.ai_analysis.is_real_dipole is True
        assert b.catalog_crossmatch.gaia_dr3_match is True
        assert b.ai_analysis.estimated_temp_k > 2500.0
        assert b.kinematics.proper_motion_arcsec_yr > 20.0

    def test_rw_aurigae_invariants(self):
        """RW Aurigae: ดาวแปรแสงก่อนแถบลำดับหลัก (T Tauri) สว่างวูบวาบ อยู่นิ่งกับที่"""
        raw = json.loads((Path(CONTRACTS_DIR) / "rw_aurigae.json").read_text())
        b = SpherexTargetBundle(**raw)
        assert b.target_category == "variable_star"
        assert b.ai_analysis.is_real_dipole is False  # ไม่ใช่วัตถุเคลื่อนที่ (Monopole)
        assert b.kinematics.proper_motion_arcsec_yr < 1.0
        assert b.kinematics.flux_change_pct > 50.0  # การแปรแสงรุนแรง

    def test_planet_x_candidate_invariants(self):
        """Planet X Candidate: วัตถุลึกลับเยือกแข็งขอบระบบสุริยะ Anomaly Score สูงสุด"""
        raw = json.loads((Path(CONTRACTS_DIR) / "planet_x_candidate.json").read_text())
        b = SpherexTargetBundle(**raw)
        assert b.target_category == "anomaly_candidate"
        assert b.ai_analysis.anomaly_score >= 0.85
        assert b.catalog_crossmatch.gaia_dr3_match is False
        assert b.ai_analysis.estimated_temp_k < 200.0


# =====================================================================
# 4. ทดสอบความเสถียรและประสิทธิภาพของ FastAPI Endpoints
# =====================================================================
@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestFastApiWebServices:
    """ทดสอบ REST API endpoints, validation, และ benchmark latency"""

    def test_health_check(self, client):
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert "timestamp" in data

    def test_get_all_targets(self, client):
        res = client.get("/api/targets")
        assert res.status_code == 200
        targets = res.json()
        assert len(targets) == 4
        ids = [t["target_id"] for t in targets]
        assert "WISE_0855_0714" in ids
        assert "PLANET_X_CANDIDATE" in ids

    @pytest.mark.parametrize("slug, expected_id", [
        ("wise0855", "WISE_0855_0714"),
        ("barnards_star", "BARNARDS_STAR"),
        ("rw_aurigae", "RW_AURIGAE"),
        ("planet_x", "PLANET_X_CANDIDATE"),
    ])
    def test_get_individual_target(self, client, slug, expected_id):
        res = client.get(f"/api/targets/{slug}")
        assert res.status_code == 200
        assert res.json()["target_id"] == expected_id

    def test_get_nonexistent_target_returns_404(self, client):
        res = client.get("/api/targets/non_existent_galaxy")
        assert res.status_code == 404

    def test_live_analyze_coordinate_endpoint(self, client):
        """ทดสอบการส่งพิกัดจำลองการคลิกบนท้องฟ้า 3D เข้ามาประมวลผลสด"""
        payload = {
            "ra": 133.7783,
            "dec": -7.2400,
            "base_target_id": "WISE_0855_0714",
            "use_live_vizier": False,
        }
        res = client.post("/api/analyze", json=payload)
        assert res.status_code == 200
        bundle = res.json()
        assert bundle["target_id"].startswith("CUSTOM_")
        assert len(bundle["spectrum_102_bands"]) == 102
        assert "ai_analysis" in bundle

    def test_input_validation_errors(self, client):
        """ทดสอบการปฏิเสธพิกัดที่อยู่นอกช่วงพิกัดดาราศาสตร์สากล (RA 0-360, Dec -90 to 90)"""
        # พิกัด Dec เกิน 90 องศา
        res_invalid_dec = client.post("/api/analyze", json={"ra": 100.0, "dec": 120.0})
        assert res_invalid_dec.status_code == 422

        # พิกัด RA ติดลบ
        res_invalid_ra = client.post("/api/analyze", json={"ra": -15.0, "dec": 0.0})
        assert res_invalid_ra.status_code == 422

    def test_api_latency_benchmark(self, client):
        """ทดสอบความเร็วในการประมวลผล (Latency Benchmark) ต้องตอบสนองภายใน 300 ms"""
        times = []
        payload = {"ra": 269.452, "dec": 4.693, "base_target_id": "BARNARDS_STAR", "use_live_vizier": False}

        for _ in range(5):
            t0 = time.perf_counter()
            res = client.post("/api/analyze", json=payload)
            dt = time.perf_counter() - t0
            assert res.status_code == 200
            times.append(dt)

        avg_latency_ms = (sum(times) / len(times)) * 1000.0
        # ยืนยันว่าการประมวลผลเฉลี่ยไม่เกิน 300 ms สำหรับ Interactive 3D Web
        assert avg_latency_ms < 300.0, f"Average latency too high: {avg_latency_ms:.1f} ms"


# =====================================================================
# 5. ทดสอบการเชื่อมต่อ Frontend 3D Viewer & Build Assets
# =====================================================================
class TestFrontendIntegration:
    """ตรวจสอบไฟล์ Adapter แปลงพิกัด 3D และโครงสร้าง Build Artifacts"""

    def test_frontend_adapter_exists(self):
        adapter_file = WORKSPACE_DIR / "src" / "utils" / "spherexAdapter.ts"
        assert adapter_file.exists()
        content = adapter_file.read_text(encoding="utf-8")
        assert "raToCartesian" in content or "sphericalToCartesian" in content
        assert "getSpherexTargetObjects" in content

    def test_production_build_artifacts(self):
        """ตรวจสอบว่าไฟล์ HTML และ Bundled Chunks ถูกสร้างอย่างสมบูรณ์"""
        dist_dir = WORKSPACE_DIR / "dist-demo"
        assert dist_dir.exists()
        index_html = dist_dir / "index.html"
        assert index_html.exists()

        html_content = index_html.read_text(encoding="utf-8")
        assert "assets/index-" in html_content

        assets_dir = dist_dir / "assets"
        assert assets_dir.exists()
        js_files = list(assets_dir.glob("*.js"))
        css_files = list(assets_dir.glob("*.css"))
        assert len(js_files) >= 1
        assert len(css_files) >= 1
