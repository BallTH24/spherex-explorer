from contextlib import asynccontextmanager
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from astropy.io import fits
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord
import astropy.units as u

from backend.schemas import SpherexTargetBundle
from backend.ml import ensure_models_trained
from backend.pipeline import (
    BENCHMARK_SPECS,
    CONTRACTS_DIR,
    FITS_DIR,
    generate_all_benchmarks,
    generate_target_fits_files,
    run_target_pipeline,
)

# เก็บ Cache ข้อมูลเป้าหมายไว้ใน Memory เพื่อตอบสนองในระดับ < 5 ms
TARGET_CACHE: Dict[str, SpherexTargetBundle] = {}

# รองรับการเรียกด้วยชื่อไฟล์หรือรหัสเป้าหมาย
ALIAS_MAP: Dict[str, str] = {
    "sample_wise0855": "WISE_0855_0714",
    "wise0855": "WISE_0855_0714",
    "wise_0855_0714": "WISE_0855_0714",
    "barnards_star": "BARNARDS_STAR",
    "rw_aurigae": "RW_AURIGAE",
    "planet_x_candidate": "PLANET_X_CANDIDATE",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """เตรียมความพร้อมโมเดล AI และสร้าง JSON Benchmarks ทั้ง 4 เคสทันทีที่เปิดเซิร์ฟเวอร์"""
    ensure_models_trained()
    bundles = generate_all_benchmarks(use_real_nasa=False, use_live_vizier=False)
    TARGET_CACHE.update(bundles)
    yield


app = FastAPI(
    title="SPHEREx Explorer API — Planet X & Time-Domain Discovery Engine",
    version="1.0.0",
    lifespan=lifespan,
)

# เปิด CORS ให้ Next.js (localhost:3000) เรียก API ได้โดยไม่ติดบล็อก
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TargetSummaryItem(BaseModel):
    target_id: str
    title: str
    filename: str
    target_category: str
    ra: float
    dec: float
    anomaly_score: float


class LiveAnalyzeRequest(BaseModel):
    ra: float = Field(..., description="Right Ascension (ICRS Degrees)")
    dec: float = Field(..., description="Declination (ICRS Degrees)")
    base_target_id: Optional[str] = Field(
        default="WISE_0855_0714",
        description="รหัสชุดข้อมูล FITS ต้นทางที่ต้องการสกัดค่า ณ พิกัด (RA, Dec)",
    )
    use_live_vizier: bool = Field(
        default=False,
        description="ตั้งเป็น True หากต้องการยิง Query สดไปยัง VizieR Gaia DR3 / AllWISE",
    )


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "loaded_targets": list(TARGET_CACHE.keys()),
        "contracts_dir": str(CONTRACTS_DIR),
    }


@app.get("/api/targets", response_model=List[TargetSummaryItem])
def list_available_targets():
    """คืนค่ารายชื่อเป้าหมายทดสอบทั้งหมดสำหรับใส่ใน Dropdown บนหน้าเว็บ"""
    items: List[TargetSummaryItem] = []
    for tid, bundle in TARGET_CACHE.items():
        items.append(
            TargetSummaryItem(
                target_id=tid,
                title=bundle.title,
                filename=BENCHMARK_SPECS[tid]["filename"],
                target_category=bundle.target_category,
                ra=bundle.epochs.epoch2.ra,
                dec=bundle.epochs.epoch2.dec,
                anomaly_score=bundle.ai_analysis.anomaly_score,
            )
        )
    return items


@app.get("/api/targets/{target_key}", response_model=SpherexTargetBundle)
def get_target_bundle(target_key: str):
    """
    ดึงข้อมูล SpherexTargetBundle ตาม target_id (เช่น WISE_0855_0714)
    หรือตามชื่อไฟล์ (เช่น sample_wise0855, barnards_star, rw_aurigae, planet_x_candidate)
    """
    clean_key = target_key.replace(".json", "").strip()
    resolved_id = ALIAS_MAP.get(clean_key.lower(), clean_key.upper())

    if resolved_id not in TARGET_CACHE:
        raise HTTPException(
            status_code=404,
            detail=f"ไม่พบเป้าหมาย '{target_key}'. เป้าหมายที่รองรับ: {list(TARGET_CACHE.keys())}",
        )
    return TARGET_CACHE[resolved_id]


@app.post("/api/analyze", response_model=SpherexTargetBundle)
def analyze_custom_coordinates(req: LiveAnalyzeRequest):
    """
    รับพิกัด (RA, Dec) จากการคลิกบนหน้าเว็บหรือ URL Query
    แล้วสกัดสเปกตรัม 102 แบนด์ + รันโมเดล AI วิเคราะห์สด ณ พิกัดนั้นทันที
    """
    resolved_id = ALIAS_MAP.get((req.base_target_id or "").lower(), req.base_target_id or "WISE_0855_0714")
    if resolved_id not in BENCHMARK_SPECS:
        resolved_id = "WISE_0855_0714"

    spec = BENCHMARK_SPECS[resolved_id]
    ep1_path = FITS_DIR / f"{resolved_id.lower()}_ep1.fits"
    ep2_path = FITS_DIR / f"{resolved_id.lower()}_ep2.fits"
    cube_path = FITS_DIR / f"{resolved_id.lower()}_cube102.fits"

    if not (ep1_path.exists() and ep2_path.exists() and cube_path.exists()):
        generate_target_fits_files(resolved_id, spec)

    # แปลงพิกัด (RA, Dec) ที่ผู้ใช้ส่งมาให้เป็นพิกัดพิกเซล (x, y) บนเฟรม 64x64
    wcs_ref = WCS(fits.getheader(ep2_path), naxis=2)
    coord = SkyCoord(ra=req.ra * u.deg, dec=req.dec * u.deg, frame="icrs")
    px, py = wcs_ref.world_to_pixel(coord)
    px_clamped = float(max(6.0, min(57.0, float(px))))
    py_clamped = float(max(6.0, min(57.0, float(py))))

    bundle = run_target_pipeline(
        target_id=f"CUSTOM_{round(req.ra, 3)}_{round(req.dec, 3)}",
        title=f"Live SPHEREx Analysis @ RA {req.ra:.4f}°, Dec {req.dec:.4f}°",
        fits_ep1_path=str(ep1_path),
        fits_ep2_path=str(ep2_path),
        fits_cube_path=str(cube_path),
        ep1_xy=spec["ep1_xy"],
        ep2_xy=(px_clamped, py_clamped),
        use_live_vizier=req.use_live_vizier,
        fallback_optical_invisible=spec["optical_invisible"],
    )
    return bundle
