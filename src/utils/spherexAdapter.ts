import type { SpaceObject } from '../types';
import type { SpherexTargetBundle } from '../../contracts/spherex';

import wise0855Data from '../../contracts/sample_wise0855.json';
import barnardsStarData from '../../contracts/barnards_star.json';
import rwAurigaeData from '../../contracts/rw_aurigae.json';
import planetXData from '../../contracts/planet_x_candidate.json';

/**
 * แปลงพิกัดเส้นศูนย์สูตรท้องฟ้า ICRS (RA, Dec ในหน่วยองศา)
 * ให้อยู่บนทรงกลมท้องฟ้า 3 มิติ (Scene Units) สำหรับ Three.js
 */
export function skyToScene(raDeg: number, decDeg: number, radius: number = 45): [number, number, number] {
  const ra = (raDeg * Math.PI) / 180;
  const dec = (decDeg * Math.PI) / 180;
  return [
    radius * Math.cos(dec) * Math.cos(ra),
    radius * Math.sin(dec),
    -radius * Math.cos(dec) * Math.sin(ra),
  ];
}

/**
 * แปลง SpherexTargetBundle (Data Contract กลางจาก Backend)
 * ให้กลายเป็น SpaceObject 3D ที่พร้อมเรนเดอร์บน Canvas
 */
export function spherexBundleToSpaceObject(bundle: SpherexTargetBundle): SpaceObject {
  const ep1 = bundle.epochs.epoch1;
  const ep2 = bundle.epochs.epoch2;

  // เลือกสี Glow ตามประเภทของวัตถุดาราศาสตร์
  let color = '#38bdf8'; // Sky blue default
  if (bundle.target_category === 'anomaly_candidate') {
    color = '#00ffcc'; // Cyan / Teal neon สำหรับ Planet X Anomaly
  } else if (bundle.target_category === 'variable_star') {
    color = '#f59e0b'; // Amber / Orange สำหรับดาวแปรแสง
  } else if (bundle.target_id.includes('WISE')) {
    color = '#c084fc'; // Purple / Infrared สำหรับ Cold Brown Dwarf
  } else {
    color = '#f87171'; // Red-orange สำหรับ M-Dwarf
  }

  // ปรับสเกล Display brightness ให้อยู่ในช่วง 0.1 .. 1.25
  const maxRefFlux = 120.0;
  const b1 = Math.min(1.25, Math.max(0.12, ep1.flux_ujy / maxRefFlux));
  const b2 = Math.min(1.25, Math.max(0.12, ep2.flux_ujy / maxRefFlux));

  const pos = skyToScene(ep2.ra, ep2.dec, 48);

  return {
    id: bundle.target_id,
    name: bundle.title,
    position: pos,
    category: bundle.target_category,
    description: `${bundle.ai_analysis.predicted_class} | Teff: ${bundle.ai_analysis.estimated_temp_k} K | Anomaly: ${bundle.ai_analysis.anomaly_score}`,
    color,
    size: bundle.target_category === 'anomaly_candidate' ? 10 : 8,
    synthetic: false,
    epochs: {
      1: {
        brightness: round(b1, 3),
        flux: ep1.flux_ujy,
        fluxUnit: 'uJy',
        observedAt: `MJD ${ep1.mjd}`,
      },
      2: {
        brightness: round(b2, 3),
        flux: ep2.flux_ujy,
        fluxUnit: 'uJy',
        observedAt: `MJD ${ep2.mjd}`,
      },
    },
    meta: {
      kinematics: bundle.kinematics,
      ai_analysis: bundle.ai_analysis,
      catalog_crossmatch: bundle.catalog_crossmatch,
      spectral_absorption_markers: bundle.spectral_absorption_markers,
      spectrum_102_bands: bundle.spectrum_102_bands,
    },
  };
}

function round(val: number, decimals: number): number {
  const p = Math.pow(10, decimals);
  return Math.round(val * p) / p;
}

/**
 * ดึงข้อมูล Benchmark Targets ทั้ง 4 ตัวที่ผ่านการประมวลผลจาก Backend แล้ว
 */
export function getBenchmarkSpaceObjects(): SpaceObject[] {
  const rawList: SpherexTargetBundle[] = [
    wise0855Data as unknown as SpherexTargetBundle,
    barnardsStarData as unknown as SpherexTargetBundle,
    rwAurigaeData as unknown as SpherexTargetBundle,
    planetXData as unknown as SpherexTargetBundle,
  ];

  return rawList.map(spherexBundleToSpaceObject);
}
