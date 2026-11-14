import { useMemo } from 'react';
import type { QualityLevel } from '../types';

export interface QualityPreset {
  level: 'high' | 'low';
  starCount: number;
  dprMax: number;
}

function detectLow(): boolean {
  if (typeof navigator === 'undefined') return false;
  const nav = navigator as Navigator & { deviceMemory?: number };
  const cores = nav.hardwareConcurrency ?? 8;
  const mem = nav.deviceMemory ?? 8;
  const coarse = typeof window.matchMedia === 'function' && window.matchMedia('(pointer: coarse)').matches;
  return cores <= 4 || mem <= 4 || (coarse && window.innerWidth < 900);
}

export function useQualityPreset(quality: QualityLevel = 'auto', starCountOverride?: number): QualityPreset {
  return useMemo(() => {
    const level = quality === 'auto' ? (detectLow() ? 'low' : 'high') : quality;
    const preset: QualityPreset =
      level === 'low'
        ? { level, starCount: 4000, dprMax: 1 }
        : { level, starCount: 14000, dprMax: 2 };
    if (starCountOverride !== undefined && starCountOverride >= 0) preset.starCount = Math.floor(starCountOverride);
    return preset;
  }, [quality, starCountOverride]);
}
