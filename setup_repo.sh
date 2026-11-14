#!/usr/bin/env bash
set -e

PROJECT_NAME="spherex-explorer"
CURRENT_DIR=$(basename "$PWD")
if [ "$CURRENT_DIR" != "$PROJECT_NAME" ]; then
  mkdir -p "$PROJECT_NAME"/{.gemini,contracts,backend/astronomy,backend/ml,backend/models_weights,backend/data_fits}
  cd "$PROJECT_NAME"
else
  mkdir -p .gemini contracts backend/astronomy backend/ml backend/models_weights backend/data_fits
fi

# 1. .gitignore
cat << 'GITIGNORE' > .gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.pytest_cache/

# Node / Next.js
node_modules/
.next/
out/
.env*.local

# Astronomy Raw Data & Heavy Model Weights (ไม่เอาไฟล์ใหญ่ขึ้น Git)
*.fits
*.fits.gz
*.fit
backend/data_fits/*
!backend/data_fits/.gitkeep
backend/models_weights/*.pt
backend/models_weights/*.joblib
!backend/models_weights/.gitkeep

# OS
.DS_Store
Thumbs.db
GITIGNORE

touch backend/data_fits/.gitkeep backend/models_weights/.gitkeep

# 2. .gemini/instructions.md (สำหรับ Antigravity CLI)
cat << 'GEMINI' > .gemini/instructions.md
# Workspace Rules: Planet X and SPHEREx (NASA Space Apps 2026)

1. **Architecture Split**:
   - `./backend`: Python Astrophysics Engine (`astropy`, `reproject`, `photutils`, `astroquery`) + Physics-Informed ML (`torch`, `scikit-learn`) + `fastapi`.
   - `./frontend`: Next.js (App Router), TypeScript, Tailwind CSS, HTML5 Canvas (developed by teammate Mogi).
   - `./contracts`: Single source of truth for JSON Schema (`spherex.ts` and `sample_wise0855.json`).

2. **Strict Data Contract**:
   - Any changes to backend JSON output MUST update `backend/schemas.py` and `contracts/spherex.ts` simultaneously.
   - Always include ICRS coordinates (`ra`, `dec`), `CircularAnnulus` background subtraction for 102-band spectra (0.75 - 5.0 um), and AI confidence scores.

3. **NASA Benchmark Targets to Support**:
   - Moving Objects: Barnard's Star, WISE 0855, Epsilon Indi B
   - Variable Stars: RW Aurigae, R Draconis
GEMINI

# 3. backend/requirements.txt
cat << 'REQ' > backend/requirements.txt
numpy>=1.26.0
scipy>=1.12.0
astropy>=6.0.0
reproject>=0.13.0
photutils>=1.11.0
astroquery>=0.4.7
torch>=2.2.0
scikit-learn>=1.4.0
joblib>=1.3.0
fastapi>=0.110.0
uvicorn>=0.29.0
pydantic>=2.6.0
REQ

# 4. backend/schemas.py (Pydantic Data Contract)
cat << 'SCHEMAS' > backend/schemas.py
from typing import List, Literal, Tuple
from pydantic import BaseModel, Field


class EpochPoint(BaseModel):
    mjd: float
    ra: float
    dec: float
    flux_ujy: float


class EpochsInfo(BaseModel):
    epoch1: EpochPoint
    epoch2: EpochPoint


class KinematicsInfo(BaseModel):
    separation_arcsec: float
    proper_motion_arcsec_yr: float
    position_angle_deg: float
    flux_change_pct: float


class AiAnalysisInfo(BaseModel):
    is_real_dipole: bool
    dipole_confidence: float = Field(..., ge=0.0, le=1.0)
    predicted_class: str
    estimated_temp_k: float
    anomaly_score: float = Field(..., ge=0.0, le=1.0)
    detected_molecules: List[str]


class CatalogSource(BaseModel):
    source: Literal["Gaia DR3", "AllWISE"]
    x: float
    y: float
    ra: float
    dec: float


class CatalogCrossmatchInfo(BaseModel):
    gaia_dr3_match: bool
    allwise_match: bool
    nearby_sources: List[CatalogSource]


class SpectralAbsorptionMarker(BaseModel):
    molecule: str
    range_um: Tuple[float, float]


class SpectrumBandPoint(BaseModel):
    band: int
    wavelength_um: float
    flux_ujy: float
    flux_err: float


class ImageLayers64x64(BaseModel):
    epoch1_asinh: List[List[float]]
    epoch2_asinh: List[List[float]]
    difference_snr: List[List[float]]


class SpherexTargetBundle(BaseModel):
    target_id: str
    title: str
    target_category: Literal["moving_object", "variable_star", "anomaly_candidate"]
    epochs: EpochsInfo
    kinematics: KinematicsInfo
    ai_analysis: AiAnalysisInfo
    catalog_crossmatch: CatalogCrossmatchInfo
    spectral_absorption_markers: List[SpectralAbsorptionMarker]
    spectrum_102_bands: List[SpectrumBandPoint]
    image_layers_64x64: ImageLayers64x64
SCHEMAS

# สร้างไฟล์ว่างใน backend
touch backend/__init__.py
touch backend/astronomy/__init__.py backend/astronomy/alignment.py backend/astronomy/photometry.py backend/astronomy/catalogs.py backend/astronomy/kinematics.py
touch backend/ml/__init__.py backend/ml/synthetic_data.py backend/ml/dipole_cnn.py backend/ml/spectral_models.py
touch backend/pipeline.py backend/main.py

# 5. contracts/spherex.ts (TypeScript Contract สำหรับโมกิ)
cat << 'TS' > contracts/spherex.ts
export interface EpochPoint {
  mjd: number;
  ra: number;
  dec: number;
  flux_ujy: number;
}

export interface KinematicsInfo {
  separation_arcsec: number;
  proper_motion_arcsec_yr: number;
  position_angle_deg: number;
  flux_change_pct: number;
}

export interface AiAnalysisInfo {
  is_real_dipole: boolean;
  dipole_confidence: number;
  predicted_class: string;
  estimated_temp_k: number;
  anomaly_score: number;
  detected_molecules: string[];
}

export interface CatalogSource {
  source: "Gaia DR3" | "AllWISE";
  x: number;
  y: number;
  ra: number;
  dec: number;
}

export interface CatalogCrossmatchInfo {
  gaia_dr3_match: boolean;
  allwise_match: boolean;
  nearby_sources: CatalogSource[];
}

export interface SpectralAbsorptionMarker {
  molecule: string;
  range_um: [number, number];
}

export interface SpectrumBandPoint {
  band: number;
  wavelength_um: number;
  flux_ujy: number;
  flux_err: number;
}

export interface ImageLayers64x64 {
  epoch1_asinh: number[][];
  epoch2_asinh: number[][];
  difference_snr: number[][];
}

export interface SpherexTargetBundle {
  target_id: string;
  title: string;
  target_category: "moving_object" | "variable_star" | "anomaly_candidate";
  epochs: {
    epoch1: EpochPoint;
    epoch2: EpochPoint;
  };
  kinematics: KinematicsInfo;
  ai_analysis: AiAnalysisInfo;
  catalog_crossmatch: CatalogCrossmatchInfo;
  spectral_absorption_markers: SpectralAbsorptionMarker[];
  spectrum_102_bands: SpectrumBandPoint[];
  image_layers_64x64: ImageLayers64x64;
}
TS

# 6. สร้างไฟล์ Mock JSON (contracts/sample_wise0855.json) ด้วย Python มาตรฐาน
python3 - << 'PY'
import json, math, random

random.seed(42)
ny, nx = 64, 64

static_stars = [(15, 20, 0.85), (48, 14, 0.70), (22, 50, 0.92), (52, 45, 0.65)]
ep1_img, ep2_img, diff_snr = [], [], []

for y in range(ny):
    r1, r2, rd = [], [], []
    for x in range(nx):
        base = sum(amp * math.exp(-((x - sx)**2 + (y - sy)**2) / 3.5) for sx, sy, amp in static_stars)
        p1 = 0.80 * math.exp(-((x - 28)**2 + (y - 30)**2) / 3.8)
        p2 = 0.80 * math.exp(-((x - 33)**2 + (y - 32)**2) / 3.8)
        v1 = min(1.0, max(0.0, round(base + p1 + random.uniform(0.04, 0.08), 4)))
        v2 = min(1.0, max(0.0, round(base + p2 + random.uniform(0.04, 0.08), 4)))
        snr = round((p2 - p1) * 18.0 + random.uniform(-0.6, 0.6), 2)
        r1.append(v1)
        r2.append(v2)
        rd.append(snr)
    ep1_img.append(r1)
    ep2_img.append(r2)
    diff_snr.append(rd)

spectrum = []
for i in range(102):
    wl = round(0.75 + (4.25 * i / 101.0), 4)
    continuum = 42.0 * math.exp(-((wl - 4.5)**2) / 2.8) + 12.0
    ch4 = 1.0 - 0.65 * math.exp(-((wl - 3.32)**2) / 0.012)
    h2o = 1.0 - 0.45 * math.exp(-((wl - 3.05)**2) / 0.02)
    flux = round(continuum * ch4 * h2o + random.uniform(-0.8, 0.8), 2)
    spectrum.append({
        "band": i + 1,
        "wavelength_um": wl,
        "flux_ujy": max(0.5, flux),
        "flux_err": 1.45
    })

bundle = {
    "target_id": "WISE_0855_0714",
    "title": "WISE J085510.83-071442.5 (Y-Type Brown Dwarf)",
    "target_category": "moving_object",
    "epochs": {
        "epoch1": {"mjd": 60700.0, "ra": 133.7869, "dec": -7.2434, "flux_ujy": 38.4},
        "epoch2": {"mjd": 60882.5, "ra": 133.7783, "dec": -7.2400, "flux_ujy": 39.1}
    },
    "kinematics": {
        "separation_arcsec": 32.93,
        "proper_motion_arcsec_yr": 8.13,
        "position_angle_deg": 291.8,
        "flux_change_pct": 1.82
    },
    "ai_analysis": {
        "is_real_dipole": True,
        "dipole_confidence": 0.984,
        "predicted_class": "Cold Y-Dwarf / Sub-stellar Candidate",
        "estimated_temp_k": 260.0,
        "anomaly_score": 0.91,
        "detected_molecules": ["H2O Ice (3.05 um)", "CH4 Methane (3.32 um)"]
    },
    "catalog_crossmatch": {
        "gaia_dr3_match": False,
        "allwise_match": True,
        "nearby_sources": [
            {"source": "Gaia DR3", "x": 15.0, "y": 20.0, "ra": 133.812, "dec": -7.261},
            {"source": "Gaia DR3", "x": 48.0, "y": 14.0, "ra": 133.756, "dec": -7.271},
            {"source": "AllWISE", "x": 22.0, "y": 50.0, "ra": 133.801, "dec": -7.210}
        ]
    },
    "spectral_absorption_markers": [
        {"molecule": "H2O Ice / Vapor", "range_um": [2.95, 3.15]},
        {"molecule": "CH4 (Methane)", "range_um": [3.20, 3.45]},
        {"molecule": "CO / CO2", "range_um": [4.20, 4.70]}
    ],
    "spectrum_102_bands": spectrum,
    "image_layers_64x64": {
        "epoch1_asinh": ep1_img,
        "epoch2_asinh": ep2_img,
        "difference_snr": diff_snr
    }
}

with open("contracts/sample_wise0855.json", "w", encoding="utf-8") as f:
    json.dump(bundle, f, indent=2)
PY

# 7. README.md
cat << 'README' > README.md
# SPHEREx Explorer — Planet X & Time-Domain Discovery Engine
**NASA Space Apps Challenge 2026 | Team NOVA-LAB**

## โครงสร้างโปรเจกต์และการแบ่งงาน
- **`contracts/`**: สัญญาข้อมูลกลาง (`spherex.ts` และ `sample_wise0855.json`) เชื่อมหลังบ้านกับหน้าบ้าน
- **`backend/`**: ระบบประมวลผลข้อมูลดาราศาสตร์ (Astropy, photutils, astroquery) + โมเดล AI/ML (PyTorch 2D-CNN, Spectral Classifier, Anomaly Detection) + FastAPI
- **`frontend/`**: เว็บแอป Interactive Sky Viewer (Next.js, TypeScript, Tailwind CSS, HTML5 Canvas)

---

## เริ่มต้นใช้งานสำหรับทีม

### 1. ฝั่งหน้าบ้าน (สำหรับโมกิ)
สร้างโปรเจกต์ Next.js ในโฟลเดอร์ `frontend` และดึงข้อมูลจำลองจาก `contracts/` ไปปั้น UI ได้ทันทีโดยไม่ต้องรอ Backend:
```bash
npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir --use-npm
mkdir -p frontend/public/data
cp contracts/sample_wise0855.json frontend/public/data/
cd frontend
npm run dev
```

### 2. ฝั่งหลังบ้าน + AI (Python)
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

---

## ข้อตกลงการอัปโค้ดขึ้น GitHub
แตก Branch แยกกันชัดเจนเพื่อไม่ให้เกิด Conflict:
- **หลังบ้าน**: `git checkout -b feat/backend-pipeline`
- **หน้าบ้าน**: `git checkout -b feat/frontend-viewer`
- **Data Contract Rules**: หากมีการแก้ไขโครงสร้าง JSON ให้แก้ทั้ง `backend/schemas.py` และ `contracts/spherex.ts` ให้ตรงกันเสมอ
- ค่าพิกัดใช้ระบบ ICRS (`ra`, `dec`)
- Spectrum 102 bands (0.75 - 5.0 $\mu$m) ต้องผ่านการลบ Background ด้วย `CircularAnnulus`
README

if [ ! -d ".git" ]; then
  git init
fi
git branch -M main

echo "สร้างโครงสร้างโปรเจกต์ $PROJECT_NAME เรียบร้อยแล้ว!"
