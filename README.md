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
