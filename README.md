# SPHEREx Explorer — Planet X & Time-Domain Discovery Engine
**NASA Space Apps Challenge 2026 | Team NOVA-LAB**

## โครงสร้างโปรเจกต์และการแบ่งงาน
- **`contracts/`**: สัญญาข้อมูลกลาง (`spherex.ts` และไฟล์ JSON ทั้ง 4 เคส) เชื่อมหลังบ้านกับหน้าบ้าน
- **`backend/`**: ระบบประมวลผลข้อมูลดาราศาสตร์ (Astropy, photutils, astroquery) + โมเดล AI/ML (PyTorch 2D-CNN, Spectral Classifier, Anomaly Detection) + FastAPI
- **`src/` / `frontend/`**: เว็บแอป Interactive 3D Sky Viewer & Animation Component (React Three Fiber, Canvas, TypeScript)

---

## เริ่มต้นใช้งานสำหรับทีม

### 1. ฝั่งหน้าบ้าน (Frontend & 3D Animation)
```bash
npm install
npm run dev          # เปิด Standalone 3D Sky Viewer ที่ http://localhost:5173
```
หรือเข้าดูตัวอย่างการ Embed ลง Mock Host App ได้ที่ `http://localhost:5173/#integration`

### 2. ฝั่งหลังบ้าน + AI (Python FastAPI)
```bash
source backend/.venv/bin/activate
uvicorn backend.main:app --reload --port 8000
```
เปิดดู Interactive API Docs ได้ที่ `http://localhost:8000/docs`

---

## ข้อตกลงการอัปโค้ดขึ้น GitHub
- แตก Branch แยกกันชัดเจนเพื่อไม่ให้เกิด Conflict
- **Data Contract Rules**: หากมีการแก้ไขโครงสร้าง JSON ให้แก้ทั้ง `backend/schemas.py` และ `contracts/spherex.ts` ให้ตรงกันเสมอ
- ค่าพิกัดใช้ระบบ ICRS (`ra`, `dec`)
- Spectrum 102 bands (0.75 - 5.0 $\mu$m) ต้องผ่านการลบ Background ด้วย `CircularAnnulus`

---

## SPHEREx Space Explorer 3D (React Three Fiber Module)

A self-contained 3D infrared sky module for the SPHEREx Explorer site. It is a React component, not a website: drop it into a page you already have, hand it data and callbacks, and it stays out of the way.

- Thousands of GPU-rendered stars on three depth layers, with twinkle, a faint band, and a staged reveal
- Hover highlight, tooltip, click-to-fly, target reticle, details panel
- **Observation Time Range** bar (start = Epoch 1, end = Epoch 2, 1M / 3M / 6M / 1Y presets, Apply)
- **EPOCH 1 / EPOCH 2 / COMPARE / BLINK / DIFFERENCE**, driven by per-object data (not decoration)
- Drag to orbit with inertia, wheel and pinch zoom, eased focus, reset, cinematic intro
- `prefers-reduced-motion`, keyboard control, low-quality mode, WebGL failure fallback
- Only three runtime dependencies: `react`, `three`, `@react-three/fiber`. No postprocessing, no drei.
