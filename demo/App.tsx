import { useEffect, useState } from 'react';
import { SpaceExplorer3D } from '../src';
import { IntegrationExample } from '../examples/IntegrationExample';

/** #integration shows the module embedded in a mock host page; anything else shows it standalone. */
export default function App() {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const on = () => setHash(window.location.hash);
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);

  if (hash === '#integration') return <IntegrationExample />;
  return (
    <div style={{ height: '100%', position: 'relative' }}>
      <SpaceExplorer3D />
      <a
        href="#integration"
        style={{ position: 'absolute', left: 16, bottom: 16, color: '#8aa0c8', font: '12px system-ui', zIndex: 5 }}
      >
        See the embedded example
      </a>
    </div>
  );
}
