import { useEffect, useState } from 'react';
import type { ObservationRange } from '../../types';
import { PRESETS, addMonths, describeSpan, formatDate, matchPreset, sameRange, validateRange } from '../../utils/dates';

interface Props {
  /** The applied range (what the viewer is currently showing). */
  value: ObservationRange;
  loading?: boolean;
  onApply: (r: ObservationRange) => void;
}

/** Observation Time Range: edits a draft, and only Apply changes what every mode shows. */
export function TimeRangeBar({ value, loading, onApply }: Props) {
  const [draft, setDraft] = useState<ObservationRange>(value);
  useEffect(() => setDraft(value), [value.start, value.end]); // host changed it: follow

  const error = validateRange(draft);
  const dirty = !sameRange(draft, value);
  const preset = matchPreset(draft);

  const usePreset = (months: number) => {
    const end = addMonths(draft.start, months);
    if (end) setDraft({ ...draft, end });
    else setDraft({ start: value.start, end: addMonths(value.start, months) ?? value.end });
  };

  return (
    <div className="sx3d-timebar" role="group" aria-label="Observation time range">
      <label className="sx3d-field">
        <span><i className="sx3d-dot sx3d-dot-e1" />Start · Epoch 1</span>
        <input type="date" value={draft.start} onChange={(e) => setDraft({ ...draft, start: e.target.value })} aria-invalid={!!error && error.includes('start')} />
      </label>
      <span className="sx3d-arrow" aria-hidden="true">→</span>
      <label className="sx3d-field">
        <span><i className="sx3d-dot sx3d-dot-e2" />End · Epoch 2</span>
        <input type="date" value={draft.end} min={draft.start || undefined} onChange={(e) => setDraft({ ...draft, end: e.target.value })} aria-invalid={!!error && !error.includes('start')} />
      </label>
      <div className="sx3d-presets" role="group" aria-label="Quick ranges from the start date">
        {PRESETS.map((p) => (
          <button key={p.months} type="button" className="sx3d-chip" aria-pressed={preset === p.months} onClick={() => usePreset(p.months)}>
            {p.label}
          </button>
        ))}
      </div>
      <button type="button" className="sx3d-apply" data-dirty={dirty && !error} disabled={!!error || !dirty || loading} onClick={() => onApply(draft)}>
        {loading ? 'Loading…' : 'Apply'}
      </button>
      <p className="sx3d-rangeline" role={error ? 'alert' : undefined} data-error={!!error}>
        {error ? (
          error
        ) : dirty ? (
          <>Not applied yet: press <b>Apply</b> to compare {formatDate(draft.start)} with {formatDate(draft.end)}.</>
        ) : (
          <>
            Comparing <b>{formatDate(value.start)}</b> (Epoch 1) with <b>{formatDate(value.end)}</b> (Epoch 2) · {describeSpan(value)}
          </>
        )}
      </p>
    </div>
  );
}
