import { useCallback, useRef, type KeyboardEvent, type MutableRefObject, type PointerEvent, type RefObject } from 'react';
import { useFrame } from '@react-three/fiber';

/** Divider position as a fraction of the viewer width. `value` is what is drawn; `goal` is where it is easing to. */
export interface SplitState {
  value: number;
  goal: number;
  /** Last position the user chose; restored when COMPARE is re-entered. */
  user: number;
  dragging: boolean;
}
export const MIN_SPLIT = 0.03;
export const MAX_SPLIT = 0.97;
const clamp = (v: number) => Math.min(MAX_SPLIT, Math.max(MIN_SPLIT, v));

/** Inside the Canvas: eases the divider and publishes it as the CSS variable --sx-split on the stage. */
export function SplitDriver({ split, stageRef, active, reducedMotion }: {
  split: MutableRefObject<SplitState>; stageRef: RefObject<HTMLElement>; active: boolean; reducedMotion: boolean;
}) {
  useFrame((_, dt) => {
    const s = split.current;
    if (active && !s.dragging && Math.abs(s.goal - s.value) > 0.0005) {
      s.value += (s.goal - s.value) * (reducedMotion ? 1 : 1 - Math.exp(-Math.min(dt, 0.05) * 5));
    } else if (!active) s.value = 1;
    stageRef.current?.style.setProperty('--sx-split', String(s.value));
  });
  return null;
}

interface DividerProps {
  split: MutableRefObject<SplitState>;
  stageRef: RefObject<HTMLElement>;
}

/** The draggable vertical slider. Sits above the canvas, so dragging it never rotates the camera. */
export function CompareDivider({ split, stageRef }: DividerProps) {
  const sliderRef = useRef<HTMLDivElement>(null);
  const announce = (v: number) => sliderRef.current?.setAttribute('aria-valuenow', String(Math.round(v * 100)));
  const setFromX = useCallback((clientX: number) => {
    const el = stageRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const v = clamp((clientX - r.left) / Math.max(1, r.width));
    const s = split.current;
    s.value = s.goal = s.user = v;
    el.style.setProperty('--sx-split', String(v)); // instant, no frame delay while dragging
    announce(v);
  }, [split, stageRef]);

  const down = (e: PointerEvent<HTMLDivElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    split.current.dragging = true;
    setFromX(e.clientX);
  };
  const move = (e: PointerEvent<HTMLDivElement>) => {
    if (split.current.dragging) setFromX(e.clientX);
  };
  const up = (e: PointerEvent<HTMLDivElement>) => {
    split.current.dragging = false;
    try { e.currentTarget.releasePointerCapture(e.pointerId); } catch { /* already released */ }
  };
  const key = (e: KeyboardEvent<HTMLDivElement>) => {
    const step = e.shiftKey ? 0.1 : 0.03;
    const s = split.current;
    let v = s.goal;
    if (e.key === 'ArrowLeft') v -= step;
    else if (e.key === 'ArrowRight') v += step;
    else if (e.key === 'Home') v = MIN_SPLIT;
    else if (e.key === 'End') v = MAX_SPLIT;
    else return;
    e.preventDefault();
    e.stopPropagation();
    v = clamp(v);
    s.goal = s.user = v;
    announce(v);
  };

  return (
    <div
      ref={sliderRef}
      className="sx3d-divider"
      role="slider"
      tabIndex={0}
      aria-label="Comparison divider: left of it shows Epoch 1, right of it shows Epoch 2"
      aria-orientation="horizontal"
      aria-valuemin={Math.round(MIN_SPLIT * 100)}
      aria-valuemax={Math.round(MAX_SPLIT * 100)}
      aria-valuenow={Math.round(split.current.goal * 100)}
      onPointerDown={down}
      onPointerMove={move}
      onPointerUp={up}
      onPointerCancel={up}
      onKeyDown={key}
    >
      <span className="sx3d-divider-line" />
      <span className="sx3d-divider-knob" aria-hidden="true">‹ ›</span>
    </div>
  );
}
