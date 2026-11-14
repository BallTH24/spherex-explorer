import type { ChangeKind, SpaceObject } from '../types';

const DETECTION_FLOOR = 0.02;

export const CHANGE_CODE: Record<ChangeKind, number> = {
  none: 0,
  brightened: 1,
  dimmed: 2,
  appeared: 3,
  disappeared: 4,
};

export const CHANGE_LABEL: Record<ChangeKind, string> = {
  none: 'No significant change',
  brightened: 'Brighter',
  dimmed: 'Dimmer',
  appeared: 'Appeared in epoch 2',
  disappeared: 'Disappeared (not in epoch 2)',
};

/** Marker colours (CSS), mirrored in the shaders: cyan brighter, orange dimmer, green appeared, red disappeared. */
export const CHANGE_COLOR: Record<Exclude<ChangeKind, 'none'>, string> = {
  brightened: '#4de3ff',
  dimmed: '#ff8a3d',
  appeared: '#4ade80',
  disappeared: '#ff4d4d',
};

export function countChanges(objects: SpaceObject[], threshold = 0.15): Record<Exclude<ChangeKind, 'none'>, number> {
  const c = { brightened: 0, dimmed: 0, appeared: 0, disappeared: 0 };
  for (const o of objects) {
    const k = classifyChange(o, threshold);
    if (k !== 'none') c[k]++;
  }
  return c;
}

/**
 * Classifies the change between the two epochs from the data alone.
 * `threshold` is the relative change (|b2-b1| / max(b1,b2)) that counts as real.
 */
export function classifyChange(o: SpaceObject, threshold = 0.15): ChangeKind {
  const b1 = Math.max(0, o.epochs[1]?.brightness ?? 0);
  const b2 = Math.max(0, o.epochs[2]?.brightness ?? 0);
  const seen1 = b1 > DETECTION_FLOOR;
  const seen2 = b2 > DETECTION_FLOOR;
  if (!seen1 && seen2) return 'appeared';
  if (seen1 && !seen2) return 'disappeared';
  if (!seen1 && !seen2) return 'none';
  const rel = (b2 - b1) / Math.max(b1, b2);
  if (Math.abs(rel) < threshold) return 'none';
  return rel > 0 ? 'brightened' : 'dimmed';
}
