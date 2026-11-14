import { useMemo, useRef, useState } from 'react';
import { SpaceExplorer3D, generateDemoObjectsForRange } from '../src';
import type { EpochId, ObservationRange, SpaceExplorer3DHandle, SpaceObject, ViewMode } from '../src';
import './integration.css';

/**
 * A mock host website. The host owns epoch, mode and selection (controlled props),
 * drives the scene from its own sidebar, and receives every callback.
 * In a real site, replace generateDemoObjects() with your adapter output (see README).
 */
export function IntegrationExample() {
  const [range, setRange] = useState<ObservationRange>({ start: '2026-01-01', end: '2026-07-01' });
  const objects = useMemo(() => generateDemoObjectsForRange(range), [range]);
  const [epoch, setEpoch] = useState<EpochId>(1);
  const [mode, setMode] = useState<ViewMode>('epoch');
  const [selected, setSelected] = useState<SpaceObject | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const explorer = useRef<SpaceExplorer3DHandle>(null);
  const note = (s: string) => setLog((l) => [s, ...l].slice(0, 12));

  return (
    <div className="host-app">
      <header className="host-nav">
        <h1>SPHEREx Explorer (host site)</h1>
        <a href="#">Back to standalone demo</a>
      </header>
      <div className="host-main">
        <aside className="host-side">
          <p>The host page owns the state. These buttons drive the 3D scene from outside.</p>
          <button aria-pressed={mode === 'epoch' && epoch === 1} onClick={() => { setMode('epoch'); setEpoch(1); }}>Epoch 1</button>
          <button aria-pressed={mode === 'epoch' && epoch === 2} onClick={() => { setMode('epoch'); setEpoch(2); }}>Epoch 2</button>
          <button aria-pressed={mode === 'compare'} onClick={() => setMode('compare')}>Compare</button>
          <button aria-pressed={mode === 'blink'} onClick={() => setMode('blink')}>Blink</button>
          <button aria-pressed={mode === 'difference'} onClick={() => setMode('difference')}>Difference</button>
          <button onClick={() => explorer.current?.focusObject(objects[7].id)}>Fly to {objects[7].name}</button>
          <button onClick={() => explorer.current?.reset()}>Reset view</button>
          <p>Selected: {selected ? selected.name : 'none'}</p>
          <p>Range: {range.start} → {range.end}</p>
          <pre aria-label="Callback log">{log.join('\n') || 'Callbacks will appear here.'}</pre>
        </aside>
        <div className="host-stage">
          <div className="host-frame">
            <SpaceExplorer3D
              ref={explorer}
              objects={objects}
              dateRange={range}
              onDateRangeChange={(r) => { setRange(r); note(`range: ${r.start} → ${r.end}`); }}
              onBlinkChange={(b) => note(`blink: ${b.playing ? 'play' : 'pause'} ${b.periodMs}ms`)}
              epoch={epoch}
              mode={mode}
              selectedObject={selected}
              onObjectSelect={(o) => { setSelected(o); note(`select: ${o?.id ?? 'none'}`); }}
              onEpochChange={(e) => { setEpoch(e); note(`epoch: ${e}`); }}
              onModeChange={(m) => { setMode(m); note(`mode: ${m}`); }}
              onObjectHover={(o) => o && note(`hover: ${o.id}`)}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
