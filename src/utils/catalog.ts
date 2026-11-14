import type { SpaceObject, ChangeKind, ObservationRange } from '../types';
import { gaussian, hash01, mulberry32 } from './prng';
import { daysBetween } from './dates';

export interface StarBuffers {
  position: Float32Array;
  color: Float32Array;
  size: Float32Array;
  phase: Float32Array;
  pulse: Float32Array;
  rand: Float32Array;
}

const PALETTE: Array<[number, number, number]> = [
  [0.62, 0.74, 1.0], // blue-white
  [0.8, 0.88, 1.0],
  [1.0, 1.0, 1.0],
  [1.0, 0.95, 0.82], // pale yellow
  [1.0, 0.78, 0.52], // orange
  [1.0, 0.55, 0.35], // infrared-red
];
const PALETTE_CUM = [0.18, 0.45, 0.7, 0.85, 0.95, 1];

/**
 * Decorative background stars on three depth shells, with a faint galactic-style band.
 * These are NOT catalogue stars; they exist only to give the scene depth.
 */
export function generateStarBuffers(count: number, seed = 1337): StarBuffers {
  const rnd = mulberry32(seed);
  const position = new Float32Array(count * 3);
  const color = new Float32Array(count * 3);
  const size = new Float32Array(count);
  const phase = new Float32Array(count);
  const pulse = new Float32Array(count);
  const rand = new Float32Array(count);

  for (let i = 0; i < count; i++) {
    const u = rnd();
    const radius = u < 0.55 ? 260 + rnd() * 500 : u < 0.85 ? 110 + rnd() * 150 : 25 + rnd() * 85;

    let x: number, y: number, z: number;
    if (rnd() < 0.35) {
      // band: concentrated near a tilted plane
      const a = rnd() * Math.PI * 2;
      const bx = Math.cos(a);
      const bz = Math.sin(a);
      const by = gaussian(rnd) * 0.14;
      // tilt the plane around the z axis
      const tilt = 0.5;
      x = bx * Math.cos(tilt) - by * Math.sin(tilt);
      y = bx * Math.sin(tilt) + by * Math.cos(tilt);
      z = bz;
    } else {
      z = rnd() * 2 - 1;
      const a = rnd() * Math.PI * 2;
      const r = Math.sqrt(1 - z * z);
      x = r * Math.cos(a);
      y = r * Math.sin(a);
    }
    const len = Math.hypot(x, y, z) || 1;
    position[i * 3] = (x / len) * radius;
    position[i * 3 + 1] = (y / len) * radius;
    position[i * 3 + 2] = (z / len) * radius;

    const c = rnd();
    let k = 0;
    while (k < PALETTE_CUM.length - 1 && c > PALETTE_CUM[k]) k++;
    const jitter = 0.92 + rnd() * 0.08;
    color[i * 3] = PALETTE[k][0] * jitter;
    color[i * 3 + 1] = PALETTE[k][1] * jitter;
    color[i * 3 + 2] = PALETTE[k][2] * jitter;

    size[i] = 0.6 + Math.pow(rnd(), 3) * 3.4;
    phase[i] = rnd();
    pulse[i] = rnd() < 0.06 ? 0.15 + rnd() * 0.25 : 0.03;
    rand[i] = rnd() * 0.9;
  }
  return { position, color, size, phase, pulse, rand };
}

const CATEGORIES: Array<{ name: string; color: string }> = [
  { name: 'Infrared source', color: '#ff9a55' },
  { name: 'Variable star', color: '#9fd0ff' },
  { name: 'Transient candidate', color: '#c4a3ff' },
  { name: 'Ice-feature source', color: '#7ff0ff' },
];

const KIND_PATTERN: ChangeKind[] = [
  'none', 'brightened', 'none', 'none', 'dimmed', 'none',
  'none', 'appeared', 'none', 'none', 'disappeared', 'none',
];

/**
 * SYNTHETIC demonstration objects. Positions, brightness values and
 * "changes" are generated from a fixed seed and are NOT SPHEREx observations.
 */
export function generateDemoObjects(count = 36, seed = 7): SpaceObject[] {
  const rnd = mulberry32(seed);
  const out: SpaceObject[] = [];
  for (let i = 0; i < count; i++) {
    const radius = 14 + rnd() * 42;
    const z = rnd() * 2 - 1;
    const a = rnd() * Math.PI * 2;
    const r = Math.sqrt(1 - z * z);
    const cat = CATEGORIES[i % CATEGORIES.length];
    const kind = KIND_PATTERN[i % KIND_PATTERN.length];

    let b1 = 0.35 + rnd() * 0.55;
    let b2 = b1 * (1 + (rnd() - 0.5) * 0.06);
    if (kind === 'brightened') b2 = Math.min(1.25, b1 * (1.5 + rnd() * 0.6));
    if (kind === 'dimmed') b2 = b1 * (0.35 + rnd() * 0.25);
    if (kind === 'appeared') {
      b1 = 0;
      b2 = 0.5 + rnd() * 0.4;
    }
    if (kind === 'disappeared') b2 = 0;

    out.push({
      id: `DEMO-${String(i + 1).padStart(3, '0')}`,
      name: `DEMO-${String(i + 1).padStart(3, '0')}`,
      position: [radius * r * Math.cos(a), radius * r * Math.sin(a) * 0.7, radius * z],
      category: cat.name,
      color: cat.color,
      size: 6 + rnd() * 3,
      synthetic: true,
      description:
        'Synthetic demonstration object. Its position and brightness are generated and are not a SPHEREx measurement.',
      epochs: { 1: { brightness: b1 }, 2: { brightness: b2 } },
    });
  }
  return out;
}

/**
 * SIMULATED objects for a chosen observation window. No SPHEREx data is read: the sky layout is fixed,
 * and which objects change (and how much) is generated from the dates, with more change over longer gaps.
 * Every object is flagged `synthetic`. Replace with real data through the `loadObjects` prop.
 */
export function generateDemoObjectsForRange(range: ObservationRange, count = 36): SpaceObject[] {
  const base = generateDemoObjects(count, 7); // same sky layout every time
  const days = Math.max(1, daysBetween(range.start, range.end) ?? 180);
  const rnd = mulberry32(Math.floor(hash01(`${range.start}|${range.end}`) * 1e9) + days);
  const pChange = Math.min(0.55, 0.12 + (days / 365) * 0.3);
  return base.map((o, i) => {
    const b1 = o.epochs[1].brightness || 0.35 + rnd() * 0.5; // keep a visible baseline for every object
    let kind: ChangeKind = 'none';
    if (rnd() < pChange) {
      const r = rnd();
      kind = r < 0.32 ? 'brightened' : r < 0.64 ? 'dimmed' : r < 0.82 ? 'appeared' : 'disappeared';
    }
    let e1 = b1;
    let e2 = b1 * (1 + (rnd() - 0.5) * 0.06);
    if (kind === 'brightened') e2 = Math.min(1.25, b1 * (1.5 + rnd() * 0.6));
    if (kind === 'dimmed') e2 = b1 * (0.35 + rnd() * 0.25);
    if (kind === 'appeared') { e1 = 0; e2 = 0.5 + rnd() * 0.4; }
    if (kind === 'disappeared') e2 = 0;
    return {
      ...o,
      description: 'SIMULATED object. Position and brightness are generated for demonstration, not measured by SPHEREx.',
      epochs: {
        1: { brightness: e1, observedAt: range.start },
        2: { brightness: e2, observedAt: range.end },
      },
    };
  });
}
