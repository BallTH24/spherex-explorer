import { useEffect, useMemo, useState } from 'react';
import { SpaceExplorer3D, getBenchmarkSpaceObjects } from '../src';
import { IntegrationExample } from '../examples/IntegrationExample';

/** #integration shows the module embedded in a mock host page; anything else shows it standalone. */
export default function App() {
  const [hash, setHash] = useState(window.location.hash);
  const [dataSource, setDataSource] = useState<'benchmarks' | 'synthetic'>('benchmarks');

  useEffect(() => {
    const on = () => setHash(window.location.hash);
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);

  const benchmarkObjects = useMemo(() => getBenchmarkSpaceObjects(), []);

  if (hash === '#integration') return <IntegrationExample />;

  return (
    <div style={{ height: '100%', position: 'relative' }}>
      <SpaceExplorer3D objects={dataSource === 'benchmarks' ? benchmarkObjects : undefined} />
      
      {/* Floating Mode Switcher & Host Link */}
      <div
        style={{
          position: 'absolute',
          top: 16,
          right: 16,
          display: 'flex',
          gap: 8,
          zIndex: 10,
          background: 'rgba(10, 15, 26, 0.85)',
          padding: '6px 12px',
          borderRadius: 8,
          border: '1px solid rgba(138, 160, 200, 0.25)',
          backdropFilter: 'blur(8px)',
          fontSize: 12,
          fontFamily: 'system-ui, sans-serif',
          color: '#cbd5e1',
        }}
      >
        <span>Data Source:</span>
        <button
          onClick={() => setDataSource('benchmarks')}
          style={{
            background: dataSource === 'benchmarks' ? '#0284c7' : 'transparent',
            color: dataSource === 'benchmarks' ? '#fff' : '#94a3b8',
            border: 'none',
            padding: '2px 8px',
            borderRadius: 4,
            cursor: 'pointer',
            fontWeight: dataSource === 'benchmarks' ? 600 : 400,
          }}
        >
          NASA SPHEREx 4 Benchmarks
        </button>
        <button
          onClick={() => setDataSource('synthetic')}
          style={{
            background: dataSource === 'synthetic' ? '#0284c7' : 'transparent',
            color: dataSource === 'synthetic' ? '#fff' : '#94a3b8',
            border: 'none',
            padding: '2px 8px',
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
