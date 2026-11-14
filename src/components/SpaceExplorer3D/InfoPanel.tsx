import type { InfoPanelContext } from '../../types';
import { CHANGE_COLOR, CHANGE_LABEL } from '../../utils/epoch';

const pct = (b: number) => `${Math.round(Math.min(1, Math.max(0, b / 1.25)) * 100)}%`;

export function InfoPanel({ object, change, close }: InfoPanelContext) {
  const b1 = object.epochs[1]?.brightness ?? 0;
  const b2 = object.epochs[2]?.brightness ?? 0;
  const swatch = change === 'none' ? 'transparent' : CHANGE_COLOR[change];
  return (
    <aside className="sx3d-panel" aria-label={`Details for ${object.name}`}>
      <div className="sx3d-panel-head">
        <div>
          <h2 className="sx3d-panel-title">{object.name}</h2>
          {object.category && <p className="sx3d-panel-sub">{object.category}</p>}
        </div>
        <button type="button" className="sx3d-iconbtn" onClick={close} aria-label="Close details">
          ×
        </button>
      </div>

      {object.synthetic && <p className="sx3d-tag">Synthetic demonstration data</p>}
      {object.description && <p className="sx3d-panel-desc">{object.description}</p>}

      <dl className="sx3d-bars">
        {([['Epoch 1', b1, object.epochs[1]], ['Epoch 2', b2, object.epochs[2]]] as const).map(([label, b, m]) => (
          <div key={label} className="sx3d-bar-row">
            <dt>{label}</dt>
            <dd>
              <span className="sx3d-bar"><span style={{ width: pct(b) }} /></span>
              <span className="sx3d-num">
                {b.toFixed(2)}
                {m?.flux !== undefined ? ` · ${m.flux}${m.fluxUnit ? ' ' + m.fluxUnit : ''}` : ''}
              </span>
              {m?.observedAt && <span className="sx3d-date">{m.observedAt}</span>}
            </dd>
          </div>
        ))}
      </dl>

      <p className="sx3d-change">
        <span className="sx3d-swatch" style={{ background: swatch, borderColor: swatch === 'transparent' ? 'var(--sx-muted)' : swatch }} />
        {CHANGE_LABEL[change]}
      </p>
      <p className="sx3d-coords">
        x {object.position[0].toFixed(1)} · y {object.position[1].toFixed(1)} · z {object.position[2].toFixed(1)}
        {object.synthetic ? ' (scene units, not sky coordinates)' : ''}
      </p>
    </aside>
  );
}
