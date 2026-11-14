import type { ObservationRange } from '../types';

export const DEFAULT_RANGE: ObservationRange = { start: '2026-01-01', end: '2026-07-01' };
export const PRESETS: Array<{ label: string; months: number }> = [
  { label: '1 Month', months: 1 },
  { label: '3 Months', months: 3 },
  { label: '6 Months', months: 6 },
  { label: '1 Year', months: 12 },
];

const ISO = /^(\d{4})-(\d{2})-(\d{2})$/;

/** Parses YYYY-MM-DD to a UTC timestamp, or null if it is not a real calendar date. */
export function parseISO(s: string): number | null {
  const m = ISO.exec(s);
  if (!m) return null;
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const t = Date.UTC(y, mo - 1, d);
  const dt = new Date(t);
  return dt.getUTCFullYear() === y && dt.getUTCMonth() === mo - 1 && dt.getUTCDate() === d ? t : null;
}

export function toISO(t: number): string {
  return new Date(t).toISOString().slice(0, 10);
}

/** start + n calendar months, clamping the day (31 Jan + 1 month = 28/29 Feb). Returns null for an invalid start. */
export function addMonths(startISO: string, months: number): string | null {
  const t = parseISO(startISO);
  if (t === null) return null;
  const d = new Date(t);
  const y = d.getUTCFullYear();
  const m = d.getUTCMonth() + months;
  const day = d.getUTCDate();
  const last = new Date(Date.UTC(y, m + 1, 0)).getUTCDate();
  return toISO(Date.UTC(y, m, Math.min(day, last)));
}

export function daysBetween(a: string, b: string): number | null {
  const ta = parseISO(a);
  const tb = parseISO(b);
  return ta === null || tb === null ? null : Math.round((tb - ta) / 86400000);
}

/** Returns an error message, or null when the range is usable. */
export function validateRange(r: ObservationRange): string | null {
  if (parseISO(r.start) === null) return 'Choose a valid start date (Epoch 1).';
  if (parseISO(r.end) === null) return 'Choose a valid end date (Epoch 2).';
  if ((daysBetween(r.start, r.end) ?? 0) <= 0) return 'Epoch 2 must be after Epoch 1.';
  return null;
}

/** Which preset (months) the range matches exactly, or null. */
export function matchPreset(r: ObservationRange): number | null {
  for (const p of PRESETS) if (addMonths(r.start, p.months) === r.end) return p.months;
  return null;
}

export function formatDate(iso: string): string {
  const t = parseISO(iso);
  if (t === null) return iso || '—';
  return new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(t);
}

export function describeSpan(r: ObservationRange): string {
  const d = daysBetween(r.start, r.end);
  if (d === null || d <= 0) return '';
  const months = d / 30.4375;
  const text = d < 45 ? `${d} days` : months < 23 ? `${Math.round(months)} months` : `${(months / 12).toFixed(1)} years`;
  return `${text} apart`;
}

export const sameRange = (a: ObservationRange, b: ObservationRange) => a.start === b.start && a.end === b.end;
