import type { CSSProperties, ReactNode } from 'react';

export type Vec3 = [number, number, number];
export type EpochId = 1 | 2;
/**
 * 'epoch'      shows the single epoch given by the `epoch` prop.
 * 'compare'    epoch 1 left of a draggable divider, epoch 2 right, one shared camera.
 * 'blink'      alternates epoch 1 / epoch 2.
 * 'difference' highlights changed objects.
 */
export type ViewMode = 'epoch' | 'compare' | 'blink' | 'difference';

/** Observation window. Epoch 1 = `start`, epoch 2 = `end`. ISO calendar dates, `YYYY-MM-DD`. */
export interface ObservationRange {
  start: string;
  end: string;
}
export interface BlinkSettings {
  playing: boolean;
  /** Full cycle (epoch 1 -> epoch 2 -> epoch 1) in ms. */
  periodMs: number;
}
export type QualityLevel = 'auto' | 'high' | 'low';
export type ChangeKind = 'none' | 'brightened' | 'dimmed' | 'appeared' | 'disappeared';

/** One observation of one object at one epoch. */
export interface EpochMeasurement {
  /**
   * Normalised display brightness, roughly 0..1.25 (0 = not detected).
   * Your data adapter converts real flux to this scale (see README).
   */
  brightness: number;
  /** Optional raw values, shown in the info panel when present. */
  flux?: number;
  fluxUnit?: string;
  /** ISO date or MJD string of the observation. */
  observedAt?: string;
}

export interface SpaceObject {
  id: string;
  name: string;
  /** Scene units. The demo scene spans about +/-60 units around the origin. */
  position: Vec3;
  category?: string;
  description?: string;
  /** CSS colour for the glow. */
  color?: string;
  /** Relative glow size, default 7. */
  size?: number;
  /** MUST be true for generated or placeholder objects. Drives the on-screen "demonstration data" label. */
  synthetic?: boolean;
  epochs: { 1: EpochMeasurement; 2: EpochMeasurement };
  meta?: Record<string, unknown>;
}

export interface SpaceExplorer3DHandle {
  /** Deselect and fly back to the home view. */
  reset(): void;
  /** Select an object and fly to it. */
  focusObject(id: string): void;
}

export interface InfoPanelContext {
  object: SpaceObject;
  change: ChangeKind;
  mode: ViewMode;
  epoch: EpochId;
  close(): void;
}

export interface SpaceExplorer3DProps {
  /** Objects to display. `undefined` loads labelled synthetic demo objects; `[]` shows an empty sky. */
  objects?: SpaceObject[];

  /** Controlled epoch. Omit for uncontrolled (see defaultEpoch). */
  epoch?: EpochId;
  defaultEpoch?: EpochId;
  /** Controlled mode. Omit for uncontrolled (see defaultMode). */
  mode?: ViewMode;
  defaultMode?: ViewMode;
  /** Controlled observation window. Omit for uncontrolled (see defaultDateRange). */
  dateRange?: ObservationRange;
  defaultDateRange?: ObservationRange;
  /**
   * Data adapter for real observations. Called whenever the APPLIED range changes.
   * Return objects whose epochs[1] / epochs[2] correspond to range.start / range.end.
   * Ignored when `objects` is given. If omitted, labelled SIMULATED demo objects are generated for the range.
   */
  loadObjects?: (range: ObservationRange, signal: AbortSignal) => Promise<SpaceObject[]>;
  /** Blink playback; controlled via `blinkPlaying`, otherwise uncontrolled. */
  blinkPlaying?: boolean;
  /** Show the Observation Time Range bar above the viewer. Default true (needs showControls). */
  showTimeRange?: boolean;

  /** Controlled selection: an object, an id, or null for none. */
  selectedObject?: SpaceObject | string | null;
  defaultSelectedObject?: string | null;

  onObjectSelect?: (object: SpaceObject | null) => void;
  onObjectHover?: (object: SpaceObject | null) => void;
  onEpochChange?: (epoch: EpochId) => void;
  /** Fired when the user presses Apply (or the host changes it). */
  onDateRangeChange?: (range: ObservationRange) => void;
  onBlinkChange?: (settings: BlinkSettings) => void;
  onModeChange?: (mode: ViewMode) => void;
  /** Fired once the WebGL scene has been created. */
  onReady?: () => void;
  onError?: (error: Error) => void;

  quality?: QualityLevel;
  /** Override the number of background stars. */
  backgroundStarCount?: number;
  /** Cinematic loading and camera intro. Default true (always off under prefers-reduced-motion). */
  intro?: boolean;
  /** Full blink cycle in ms. Default 1800. The built-in speed slider changes it; a changed prop value resets it. */
  blinkPeriodMs?: number;
  /** Relative brightness change that counts as "changed" in DIFFERENCE mode. Default 0.15. */
  differenceThreshold?: number;

  /** Built-in time bar, mode bar, reset button, object list, legend, data label. Default true. */
  showControls?: boolean;
  showInfoPanel?: boolean;
  renderInfoPanel?: (ctx: InfoPanelContext) => ReactNode;

  className?: string;
  style?: CSSProperties;
}
