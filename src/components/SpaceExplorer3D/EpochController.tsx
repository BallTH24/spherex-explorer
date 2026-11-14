import { useCallback, useRef, type MutableRefObject } from 'react';
import type { EpochId, ViewMode } from '../../types';

export interface EpochAnimState {
  /** 0 = epoch 1 brightness, 1 = epoch 2 brightness. */
  mix: number;
  /** 0..1, strength of the difference-mode overlay. */
  diff: number;
}

interface AnimatorArgs {
  mode: ViewMode;
  epoch: EpochId;
  blinkPeriodMs: number;
  blinkPlaying: boolean;
  reducedMotion: boolean;
}

const smooth = (a: number, b: number, x: number) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};

/**
 * Turns (mode, epoch) into two animated scalars the shaders read each frame.
 * Kept in a ref so epoch switching never triggers React re-renders.
 */
export function useEpochAnimator(args: AnimatorArgs): {
  state: MutableRefObject<EpochAnimState>;
  tick: (dt: number, timeSec: number) => void;
} {
  const cfg = useRef(args);
  cfg.current = args;
  const blinkPhase = useRef(0);
  const state = useRef<EpochAnimState>({
    mix: args.epoch === 2 ? 1 : 0,
    diff: args.mode === 'difference' ? 1 : 0,
  });

  const tick = useCallback((dt: number, _timeSec: number) => {
    const { mode, epoch, blinkPeriodMs, blinkPlaying, reducedMotion } = cfg.current;
    const s = state.current;
    const ease = reducedMotion ? 1 : 1 - Math.exp(-dt * 6);

    if (mode === 'blink') {
      const period = Math.max(600, reducedMotion ? Math.max(blinkPeriodMs, 2400) : blinkPeriodMs) / 1000;
      // Own phase accumulator (not the clock) so Pause really freezes the sky and speed changes never jump.
      if (blinkPlaying) blinkPhase.current = (blinkPhase.current + dt / period) % 1;
      const phase = blinkPhase.current;
      // Hold epoch 1, ease to epoch 2, hold, ease back.
      s.mix = reducedMotion
        ? phase < 0.5 ? 0 : 1
        : smooth(0.42, 0.52, phase) - smooth(0.92, 1.0, phase);
    } else {
      blinkPhase.current = 0; // blink always starts on epoch 1
      const target = mode === 'difference' ? 1 : mode === 'compare' ? 0 : epoch === 2 ? 1 : 0;
      s.mix += (target - s.mix) * ease;
    }
    const diffTarget = mode === 'difference' ? 1 : 0;
    s.diff += (diffTarget - s.diff) * ease;
  }, []);

  return { state, tick };
}

export type ModeTab = 'epoch1' | 'epoch2' | 'compare' | 'blink' | 'difference';

const TABS: Array<{ id: ModeTab; label: string; key: string }> = [
  { id: 'epoch1', label: 'EPOCH 1', key: '1' },
  { id: 'epoch2', label: 'EPOCH 2', key: '2' },
  { id: 'compare', label: 'COMPARE', key: '3' },
  { id: 'blink', label: 'BLINK', key: '4' },
  { id: 'difference', label: 'DIFFERENCE', key: '5' },
];

export function tabFor(mode: ViewMode, epoch: EpochId): ModeTab {
  return mode === 'epoch' ? (epoch === 2 ? 'epoch2' : 'epoch1') : mode;
}

export function EpochControls({ active, onSelect }: { active: ModeTab; onSelect: (t: ModeTab) => void }) {
  return (
    <div className="sx3d-modebar" role="group" aria-label="Observation comparison mode">
      {TABS.map((t) => (
        <button
          key={t.id}
          type="button"
          className="sx3d-modebtn"
          aria-pressed={active === t.id}
          onClick={() => onSelect(t.id)}
        >
          {t.label}
          <kbd aria-hidden="true">{t.key}</kbd>
        </button>
      ))}
    </div>
  );
}
