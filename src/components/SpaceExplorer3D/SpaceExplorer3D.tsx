'use client';
import {
  Component, forwardRef, useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState,
  type ErrorInfo, type KeyboardEvent, type MutableRefObject, type ReactNode,
} from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import type { EpochId, ObservationRange, SpaceExplorer3DHandle, SpaceExplorer3DProps, SpaceObject, ViewMode } from '../../types';
import { generateDemoObjectsForRange } from '../../utils/catalog';
import { DEFAULT_RANGE, formatDate, validateRange } from '../../utils/dates';
import { CHANGE_COLOR, CHANGE_LABEL, classifyChange, countChanges } from '../../utils/epoch';
import type { InteractionState } from '../../utils/interaction';
import { useControllable } from '../../hooks/useControllable';
import { useQualityPreset } from '../../hooks/useQualityPreset';
import { useReducedMotion } from '../../hooks/useReducedMotion';
import { CameraController } from './CameraController';
import { CompareDivider, SplitDriver, type SplitState } from './CompareSlider';
import { ObjectLayer } from './CelestialObject';
import { EpochControls, tabFor, type ModeTab } from './EpochController';
import { InfoPanel } from './InfoPanel';
import { SpectrumHudOverlay } from './SpectrumHudOverlay';
import { OverlayTracker } from './OverlayTracker';
import { StarField } from './StarField';
import { TimeRangeBar } from './TimeRangeBar';
import './styles.css';

const INTRO_SECONDS = 3.2;

function hasWebGL(): boolean {
  try {
    const c = document.createElement('canvas');
    return !!(c.getContext('webgl2') || c.getContext('webgl'));
  } catch {
    return false;
  }
}

class SceneBoundary extends Component<{ onError: (e: Error) => void; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(error: Error, _info: ErrorInfo) {
    this.props.onError(error);
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}

function RevealDriver({ revealRef, enabled }: { revealRef: MutableRefObject<number>; enabled: boolean }) {
  useFrame((_, dt) => {
    if (revealRef.current >= 1) return;
    revealRef.current = enabled ? Math.min(1, revealRef.current + Math.min(dt, 0.05) / INTRO_SECONDS) : 1;
  });
  return null;
}

export const SpaceExplorer3D = forwardRef<SpaceExplorer3DHandle, SpaceExplorer3DProps>(function SpaceExplorer3D(props, ref) {
  const {
    objects: objectsProp,
    defaultEpoch = 1,
    defaultMode = 'epoch',
    defaultSelectedObject = null,
    onObjectSelect, onObjectHover, onEpochChange, onModeChange, onDateRangeChange, onBlinkChange, onReady, onError,
    loadObjects,
    showTimeRange = true,
    quality = 'auto',
    backgroundStarCount,
    intro = true,
    blinkPeriodMs = 1800,
    differenceThreshold = 0.15,
    showControls = true,
    showInfoPanel = true,
    renderInfoPanel,
    className,
    style,
  } = props;

  const reducedMotion = useReducedMotion();
  const preset = useQualityPreset(quality, backgroundStarCount);

  // ---- observation window (applied range). Epoch 1 = start, epoch 2 = end. ----
  const [range, setRange] = useControllable<ObservationRange>(props.dateRange, props.defaultDateRange ?? DEFAULT_RANGE, onDateRangeChange);
  const rangeOk = validateRange(range) === null;
  const rangeStart = range.start;
  const rangeEnd = range.end;
  const stableRange = useMemo(() => ({ start: rangeStart, end: rangeEnd }), [rangeStart, rangeEnd]);

  // Data source: `objects` prop, else the `loadObjects` adapter, else labelled SIMULATED demo data for the range.
  const [loaded, setLoaded] = useState<{ range: ObservationRange; objects: SpaceObject[] } | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const loadRef = useRef(loadObjects);
  loadRef.current = loadObjects;
  const useAdapter = objectsProp === undefined && !!loadObjects;
  useEffect(() => {
    if (!useAdapter || !rangeOk || !loadRef.current) return;
    const ctl = new AbortController();
    setLoading(true);
    setLoadError(null);
    loadRef.current(stableRange, ctl.signal)
      .then((o) => { if (!ctl.signal.aborted) { setLoaded({ range: stableRange, objects: o }); setLoading(false); } })
      .catch((e: unknown) => {
        if (ctl.signal.aborted) return;
        setLoading(false);
        setLoadError(e instanceof Error ? e.message : 'Observations could not be loaded.');
      });
    return () => ctl.abort();
  }, [useAdapter, rangeOk, stableRange]);

  const demo = useMemo(
    () => (objectsProp === undefined && !loadObjects && rangeOk ? generateDemoObjectsForRange(stableRange) : null),
    [objectsProp, loadObjects, rangeOk, stableRange],
  );
  // Adapter data is only shown for the range it was loaded for, so old data never sits under new dates.
  const adapterObjects = loaded && loaded.range.start === rangeStart && loaded.range.end === rangeEnd ? loaded.objects : null;
  const objects: SpaceObject[] = objectsProp ?? (loadObjects ? adapterObjects : demo) ?? [];
  const byId = useMemo(() => new Map(objects.map((o) => [o.id, o] as const)), [objects]);
  const anySynthetic = objects.some((o) => o.synthetic);

  // ---- controlled / uncontrolled state ----
  const selProp = props.selectedObject;
  const selIdProp = selProp === undefined ? undefined : selProp === null ? null : typeof selProp === 'string' ? selProp : selProp.id;
  const [rawSelectedId, setSelectedId] = useControllable<string | null>(selIdProp, defaultSelectedObject, (id) =>
    onObjectSelect?.(id ? byId.get(id) ?? null : null),
  );
  const selectedId = rawSelectedId && byId.has(rawSelectedId) ? rawSelectedId : null;
  const selected = selectedId ? byId.get(selectedId) ?? null : null;
  const [epoch, setEpoch] = useControllable<EpochId>(props.epoch, defaultEpoch, onEpochChange);
  const [mode, setMode] = useControllable<ViewMode>(props.mode, defaultMode, onModeChange);

  // ---- blink playback / speed ----
  const [periodMs, setPeriodMs] = useState(blinkPeriodMs);
  useEffect(() => setPeriodMs(blinkPeriodMs), [blinkPeriodMs]);
  const periodRef = useRef(periodMs);
  periodRef.current = periodMs;
  const [playing, setPlaying] = useControllable<boolean>(props.blinkPlaying, true, (v) => onBlinkChange?.({ playing: v, periodMs: periodRef.current }));
  const changePeriod = (v: number) => {
    setPeriodMs(v);
    onBlinkChange?.({ playing, periodMs: v });
  };
  const [blinkEpoch, setBlinkEpoch] = useState<EpochId>(1);

  // ---- compare divider (refs only: dragging never re-renders React) ----
  const stageRef = useRef<HTMLDivElement>(null);
  const split = useRef<SplitState>({ value: 1, goal: 0.5, user: 0.5, dragging: false });
  useEffect(() => {
    const sp = split.current;
    if (mode === 'compare') {
      sp.goal = sp.user;
      sp.value = reducedMotion ? sp.goal : 1; // wipe in from the edge
    } else {
      sp.value = 1;
    }
  }, [mode, reducedMotion]);
  useEffect(() => { if (mode === 'blink') setBlinkEpoch(1); }, [mode]);

  // ---- camera triggers ----
  const [resetKey, setResetKey] = useState(0);
  const [focusKey, setFocusKey] = useState(0);
  const selectedIdRef = useRef(selectedId);
  selectedIdRef.current = selectedId;

  const handleSelect = useCallback(
    (id: string) => {
      if (id === selectedIdRef.current) setFocusKey((k) => k + 1);
      else setSelectedId(id);
    },
    [setSelectedId],
  );
  const reset = useCallback(() => {
    setSelectedId(null);
    setResetKey((k) => k + 1);
  }, [setSelectedId]);

  useImperativeHandle(
    ref,
    () => ({
      reset,
      focusObject: (id: string) => {
        if (byId.has(id)) handleSelect(id);
      },
    }),
    [reset, handleSelect, byId],
  );

  // ---- hover (tooltip) ----
  const hoverIdRef = useRef<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const byIdRef = useRef(byId);
  byIdRef.current = byId;
  const hoverCbRef = useRef(onObjectHover);
  hoverCbRef.current = onObjectHover;
  const handleHover = useCallback((id: string | null) => {
    hoverIdRef.current = id;
    setHoveredId(id);
    hoverCbRef.current?.(id ? byIdRef.current.get(id) ?? null : null);
  }, []);

  // ---- mode tabs ----
  const handleTab = useCallback(
    (t: ModeTab) => {
      if (t === 'epoch1' || t === 'epoch2') {
        setMode('epoch');
        setEpoch(t === 'epoch1' ? 1 : 2);
      } else setMode(t);
    },
    [setMode, setEpoch],
  );
  const activeTab = tabFor(mode, epoch);

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const tag = (e.target as HTMLElement).tagName;
    if (tag === 'SELECT' || tag === 'INPUT' || e.metaKey || e.ctrlKey || e.altKey) return;
    const map: Record<string, ModeTab> = { '1': 'epoch1', '2': 'epoch2', '3': 'compare', '4': 'blink', '5': 'difference' };
    if (map[e.key]) handleTab(map[e.key]);
    else if (e.key === 'r' || e.key === 'R') reset();
    else if (e.key === 'Escape') setSelectedId(null);
  };

  // ---- WebGL lifecycle ----
  const [mounted, setMounted] = useState(false);
  const [supported, setSupported] = useState(true);
  const [failure, setFailure] = useState<string | null>(null);
  const [sceneKey, setSceneKey] = useState(0);
  const [ready, setReady] = useState(false);
  const lostRef = useRef<{ el: HTMLElement; fn: (e: Event) => void } | null>(null);
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;
  const onReadyRef = useRef(onReady);
  onReadyRef.current = onReady;

  useEffect(() => {
    setSupported(hasWebGL());
    setMounted(true);
  }, []);
  useEffect(
    () => () => {
      const l = lostRef.current;
      if (l) l.el.removeEventListener('webglcontextlost', l.fn);
      lostRef.current = null;
    },
    [],
  );

  const fail = useCallback((e: Error) => {
    setFailure(e.message || 'The 3D scene stopped unexpectedly.');
    onErrorRef.current?.(e);
  }, []);
  const retry = () => {
    setFailure(null);
    setReady(false);
    setSceneKey((k) => k + 1);
  };

  // ---- shared refs ----
  const interaction = useRef<InteractionState>({ hover: false, drag: false });
  const introOn = intro && !reducedMotion;
  const revealRef = useRef(introOn ? 0 : 1);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const reticleRef = useRef<HTMLDivElement>(null);

  const hovered = hoveredId ? byId.get(hoveredId) : null;
  const change = selected ? classifyChange(selected, differenceThreshold) : 'none';
  const counts = useMemo(() => countChanges(objects, differenceThreshold), [objects, differenceThreshold]);
  const dateOf = (e: EpochId) => formatDate(e === 1 ? range.start : range.end);
  const status =
    mode === 'blink' ? `Blink ${playing ? 'playing' : 'paused'}: showing epoch ${blinkEpoch}, ${dateOf(blinkEpoch)}`
    : mode === 'compare' ? `Compare: epoch 1 (${dateOf(1)}) left of the divider, epoch 2 (${dateOf(2)}) right`
    : mode === 'difference' ? 'Difference: changed objects are circled and coloured'
    : `Showing epoch ${epoch}, ${dateOf(epoch)}`;
  const intervalMs = Math.round(periodMs / 2);
  const SPEED_MIN = 300;
  const SPEED_MAX = 3000;

  const canRender = mounted && supported && !failure;
  const badge = (e: EpochId, live = false) => (
    <span className={`sx3d-badge sx3d-badge-e${e}`} data-live={live}>
      <i className={`sx3d-dot sx3d-dot-e${e}`} />
      <b>EPOCH {e}</b>
      <time dateTime={e === 1 ? range.start : range.end}>{dateOf(e)}</time>
    </span>
  );

  return (
    <div
      className={`sx3d-root${className ? ' ' + className : ''}`}
      style={style}
      tabIndex={0}
      onKeyDown={onKeyDown}
      role="application"
      aria-label="Interactive infrared sky explorer. Keys 1 to 5 change mode, R resets the view, Escape clears the selection."
    >
      {showControls && (
        <div className="sx3d-toolbar">
          {showTimeRange && <TimeRangeBar value={range} loading={loading} onApply={setRange} />}
          <EpochControls active={activeTab} onSelect={handleTab} />
        </div>
      )}

      <div className="sx3d-stage" ref={stageRef} data-mode={mode}>
        <div className="sx3d-canvas-wrap">
          {canRender && (
            <SceneBoundary key={sceneKey} onError={fail}>
              <Canvas
                camera={{ fov: 50, near: 0.1, far: 3000, position: [0, 20, 100] }}
                dpr={[1, preset.dprMax]}
                gl={{ antialias: false, alpha: true, powerPreference: 'high-performance' }}
                flat
                onCreated={(state) => {
                  const el = state.gl.domElement;
                  const fn = (e: Event) => {
                    e.preventDefault();
                    fail(new Error('The graphics context was lost.'));
                  };
                  el.addEventListener('webglcontextlost', fn);
                  lostRef.current = { el, fn };
                  setReady(true);
                  onReadyRef.current?.();
                }}
              >
                <RevealDriver revealRef={revealRef} enabled={introOn} />
                <SplitDriver split={split} stageRef={stageRef} active={mode === 'compare'} reducedMotion={reducedMotion} />
                <StarField count={preset.starCount} revealRef={revealRef} />
                <ObjectLayer
                  objects={objects}
                  mode={mode}
                  epoch={epoch}
                  blinkPeriodMs={periodMs}
                  blinkPlaying={playing}
                  onBlinkEpoch={setBlinkEpoch}
                  split={split}
                  threshold={differenceThreshold}
                  selectedId={selectedId}
                  revealRef={revealRef}
                  reducedMotion={reducedMotion}
                  interaction={interaction}
                  onHover={handleHover}
                  onSelect={handleSelect}
                />
                <CameraController
                  focus={selected ? selected.position : null}
                  focusKey={focusKey}
                  resetKey={resetKey}
                  intro={intro}
                  reducedMotion={reducedMotion}
                  interaction={interaction}
                />
                <OverlayTracker
                  objects={objects}
                  hoverIdRef={hoverIdRef}
                  selectedId={selectedId}
                  tooltipRef={tooltipRef}
                  reticleRef={reticleRef}
                />
              </Canvas>
            </SceneBoundary>
          )}
        </div>

        {mounted && (!supported || failure) && (
          <div className="sx3d-fallback" role="alert">
            <p className="sx3d-fallback-title">The 3D view isn’t available</p>
            <p>
              {!supported
                ? 'This browser or device can’t start WebGL. Try another browser, or turn on hardware acceleration.'
                : failure}
            </p>
            {supported && (
              <button type="button" className="sx3d-modebtn" onClick={retry}>
                Reload the scene
              </button>
            )}
          </div>
        )}
        {canRender && !ready && <div className="sx3d-loading">Loading star field…</div>}

        <div className="sx3d-overlay" aria-hidden="true">
          {mode === 'compare' && (
            <>
              <div className="sx3d-tint sx3d-tint-l" />
              <div className="sx3d-tint sx3d-tint-r" />
            </>
          )}
          <div ref={tooltipRef} className="sx3d-track">
            {hovered && <div className="sx3d-tooltip">{hovered.name}</div>}
          </div>
          <div ref={reticleRef} className="sx3d-track">
            <div className="sx3d-reticle"><i /><i /><i /><i /></div>
          </div>
        </div>

        {mode === 'compare' && canRender && <CompareDivider split={split} stageRef={stageRef} />}

        {showControls && (
          <>
            <div className="sx3d-topleft">
              {anySynthetic && (
                <p className="sx3d-note" role="note" title="Positions, brightness and changes are generated for demonstration. They are not SPHEREx observations.">
                  <b>SIMULATED DATA</b><span> · not SPHEREx observations</span>
                </p>
              )}
              {loadError && <p className="sx3d-note sx3d-note-error" role="alert">{loadError}</p>}
              {!rangeOk && <p className="sx3d-note sx3d-note-error" role="alert">{validateRange(range)}</p>}
              {objects.length === 0 && !loading && !loadError && rangeOk && (
                <p className="sx3d-note">No objects supplied. Pass an <code>objects</code> array or a <code>loadObjects</code> adapter.</p>
              )}
              {objects.length > 0 && (
                <label className="sx3d-select">
                  <span>Object</span>
                  <select value={selectedId ?? ''} onChange={(e) => (e.target.value ? handleSelect(e.target.value) : setSelectedId(null))}>
                    <option value="">None selected</option>
                    {objects.map((o) => (
                      <option key={o.id} value={o.id}>{o.name}</option>
                    ))}
                  </select>
                </label>
              )}
            </div>
            <div className="sx3d-topright">
              <button type="button" className="sx3d-modebtn" onClick={reset}>
                Reset view<kbd aria-hidden="true">R</kbd>
              </button>
            </div>

            <div className="sx3d-footer">
              {mode === 'epoch' && <div className="sx3d-foot-group">{badge(epoch)}</div>}

              {mode === 'compare' && (
                <>
                  <div className="sx3d-foot-group sx3d-foot-l">{badge(1)}</div>
                  <p className="sx3d-hint">Drag the divider ‹ › to compare</p>
                  <div className="sx3d-foot-group sx3d-foot-r">{badge(2)}</div>
                </>
              )}

              {mode === 'blink' && (
                <div className="sx3d-foot-group sx3d-blinkbar" role="group" aria-label="Blink controls">
                  {badge(blinkEpoch, true)}
                  <button type="button" className="sx3d-playbtn" onClick={() => setPlaying(!playing)} aria-pressed={playing}>
                    {playing ? '❚❚ Pause' : '▶ Play'}
                  </button>
                  <label className="sx3d-speed">
                    <span>Speed</span>
                    <input
                      type="range"
                      min={SPEED_MIN}
                      max={SPEED_MAX}
                      step={100}
                      value={SPEED_MIN + SPEED_MAX - intervalMs}
                      onChange={(e) => changePeriod((SPEED_MIN + SPEED_MAX - Number(e.target.value)) * 2)}
                      aria-valuetext={`Switches every ${(intervalMs / 1000).toFixed(1)} seconds`}
                    />
                    <output>{(intervalMs / 1000).toFixed(1)} s</output>
                  </label>
                </div>
              )}

              {mode === 'difference' && (
                <div className="sx3d-foot-group sx3d-diffbar">
                  <ul className="sx3d-legend" aria-label="Difference colours">
                    {(['brightened', 'dimmed', 'appeared', 'disappeared'] as const).map((k) => (
                      <li key={k}>
                        <span className="sx3d-swatch" style={{ borderColor: CHANGE_COLOR[k], background: CHANGE_COLOR[k] }} />
                        {CHANGE_LABEL[k].split(' (')[0].replace(' in epoch 2', '')}
                        <span className="sx3d-count">{counts[k]}</span>
                      </li>
                    ))}
                  </ul>
                  <span className="sx3d-diffdates">{dateOf(1)} → {dateOf(2)}</span>
                  <button type="button" className="sx3d-playbtn" onClick={() => setMode('epoch')}>
                    ← Normal sky
                  </button>
                </div>
              )}
            </div>

            {showInfoPanel && selected &&
              (renderInfoPanel
                ? renderInfoPanel({ object: selected, change, mode, epoch, close: () => setSelectedId(null) })
                : (selected.meta?.spectrum_102_bands
                    ? <SpectrumHudOverlay object={selected} close={() => setSelectedId(null)} />
                    : <InfoPanel object={selected} change={change} mode={mode} epoch={epoch} close={() => setSelectedId(null)} />))}
          </>
        )}
      </div>
      <div className="sx3d-sr" aria-live="polite">{status}</div>
    </div>
  );
});
