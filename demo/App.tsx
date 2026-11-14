import { useEffect, useMemo, useRef, useState } from 'react';
import { SpaceExplorer3D, getBenchmarkSpaceObjects } from '../src';
import type { SpaceExplorer3DHandle, SpaceObject } from '../src';
import { IntegrationExample } from '../examples/IntegrationExample';

/** #integration shows the module embedded in a mock host page; anything else shows it standalone. */
export default function App() {
  const [hash, setHash] = useState(window.location.hash);
  const [dataSource, setDataSource] = useState<'benchmarks' | 'synthetic'>('benchmarks');
  const [selectedTarget, setSelectedTarget] = useState<SpaceObject | null>(null);
  const explorerRef = useRef<SpaceExplorer3DHandle>(null);

  useEffect(() => {
    const on = () => setHash(window.location.hash);
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);

  const benchmarkObjects = useMemo(() => getBenchmarkSpaceObjects(), []);

  // Sync URL query params on initial mount
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const targetQuery = params.get('target');
    if (targetQuery && benchmarkObjects.length > 0) {
      const match = benchmarkObjects.find(
        (o) => o.id.toLowerCase() === targetQuery.toLowerCase() || o.name.toLowerCase().includes(targetQuery.toLowerCase())
      );
      if (match) {
        setSelectedTarget(match);
        setTimeout(() => explorerRef.current?.focusObject(match.id), 800);
      }
    }
  }, [benchmarkObjects]);

  const handleSelectObject = (obj: SpaceObject | null) => {
    setSelectedTarget(obj);
    const url = new URL(window.location.href);
    if (obj) {
      url.searchParams.set('target', obj.id);
      const meta = obj.meta || {};
      if (typeof meta.ra === 'number') url.searchParams.set('ra', meta.ra.toFixed(4));
      if (typeof meta.dec === 'number') url.searchParams.set('dec', meta.dec.toFixed(4));
    } else {
      url.searchParams.delete('target');
      url.searchParams.delete('ra');
      url.searchParams.delete('dec');
    }
    window.history.replaceState(null, '', url.toString());
  };

  const handleQuickJump = (obj: SpaceObject) => {
    handleSelectObject(obj);
    explorerRef.current?.focusObject(obj.id);
  };

  if (hash === '#integration') return <IntegrationExample />;

  return (
    <div style={{ height: '100%', position: 'relative' }}>
      <SpaceExplorer3D
        ref={explorerRef}
        objects={dataSource === 'benchmarks' ? benchmarkObjects : undefined}
        selectedObject={selectedTarget}
        onObjectSelect={handleSelectObject}
      />

      {/* Top Banner: Benchmark Target Quick Switcher */}
      {dataSource === 'benchmarks' && (
        <div
          style={{
            position: 'absolute',
            top: 52,
            left: '50%',
            transform: 'translateX(-50%)',
            display: 'flex',
            gap: 6,
            zIndex: 10,
            background: 'rgba(6, 12, 32, 0.88)',
            padding: '5px 10px',
            borderRadius: 20,
            border: '1px solid rgba(95, 212, 255, 0.3)',
            backdropFilter: 'blur(10px)',
            boxShadow: '0 4px 20px rgba(0, 0, 0, 0.5)',
          }}
        >
          <span style={{ fontSize: 11, color: '#8aa0c8', alignSelf: 'center', fontWeight: 600, paddingRight: 4 }}>
            NASA Targets:
          </span>
          {benchmarkObjects.map((target) => {
            const isSelected = selectedTarget?.id === target.id;
            const isAnomaly = target.category === 'anomaly_candidate';
            return (
              <button
                key={target.id}
                type="button"
                onClick={() => handleQuickJump(target)}
                style={{
                  background: isSelected
                    ? isAnomaly ? '#00ffcc' : '#38bdf8'
                    : 'rgba(255, 255, 255, 0.06)',
                  color: isSelected ? '#030712' : '#dbe7ff',
                  border: isAnomaly && !isSelected ? '1px solid rgba(0, 255, 204, 0.4)' : '1px solid transparent',
                  padding: '4px 10px',
                  borderRadius: 14,
                  fontSize: 11,
                  fontWeight: isSelected ? 700 : 500,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  whiteSpace: 'nowrap',
                }}
              >
                {isAnomaly ? '🛸 ' : target.category === 'variable_star' ? '🌟 ' : '🪐 '}
                {target.name.split(' ')[0]} {target.category === 'anomaly_candidate' ? '(Planet X)' : ''}
              </button>
            );
          })}
        </div>
      )}

      {/* Floating Mode Switcher & Host Link */}
      <div
        style={{
          position: 'absolute',
          top: 12,
          right: 16,
          display: 'flex',
          gap: 6,
          zIndex: 10,
          background: 'rgba(10, 15, 26, 0.88)',
          padding: '4px 10px',
          borderRadius: 8,
          border: '1px solid rgba(138, 160, 200, 0.25)',
          backdropFilter: 'blur(8px)',
          fontSize: 11,
          fontFamily: 'system-ui, sans-serif',
          color: '#cbd5e1',
        }}
      >
        <span style={{ alignSelf: 'center' }}>Sky Mode:</span>
        <button
          onClick={() => { setDataSource('benchmarks'); setSelectedTarget(null); }}
          style={{
            background: dataSource === 'benchmarks' ? '#0284c7' : 'transparent',
            color: dataSource === 'benchmarks' ? '#fff' : '#94a3b8',
            border: 'none',
            padding: '3px 8px',
            borderRadius: 4,
            cursor: 'pointer',
            fontWeight: dataSource === 'benchmarks' ? 600 : 400,
          }}
        >
          NASA SPHEREx 4 Benchmarks
        </button>
        <button
          onClick={() => { setDataSource('synthetic'); setSelectedTarget(null); }}
          style={{
            background: dataSource === 'synthetic' ? '#0284c7' : 'transparent',
            color: dataSource === 'synthetic' ? '#fff' : '#94a3b8',
            border: 'none',
            padding: '3px 8px',
            borderRadius: 4,
            cursor: 'pointer',
            fontWeight: dataSource === 'synthetic' ? 600 : 400,
          }}
        >
          Simulated Sky
        </button>
      </div>

      <a
        href="#integration"
        style={{ position: 'absolute', left: 16, bottom: 16, color: '#8aa0c8', font: '12px system-ui', zIndex: 5 }}
      >
        See the embedded host example
      </a>
    </div>
  );
}
