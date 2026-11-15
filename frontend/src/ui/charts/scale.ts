/**
 * Scale and path helpers shared by every chart.
 *
 * Kept deliberately small and dependency-free — this is the whole reason the
 * app can draw real charts without pulling in a charting library.
 */

export interface Scale {
  (v: number): number;
  invert(p: number): number;
}

export function linearScale(d0: number, d1: number, r0: number, r1: number): Scale {
  const span = d1 - d0 || 1;
  const fn = ((v: number) => r0 + ((v - d0) / span) * (r1 - r0)) as Scale;
  fn.invert = (p: number) => d0 + ((p - r0) / (r1 - r0)) * span;
  return fn;
}

export interface BandScale {
  (i: number): number;
  band: number;
  step: number;
}

export function bandScale(n: number, r0: number, r1: number, pad = 0.25): BandScale {
  const step = (r1 - r0) / Math.max(n, 1);
  const band = step * (1 - pad);
  const fn = ((i: number) => r0 + i * step + (step - band) / 2) as BandScale;
  fn.band = band;
  fn.step = step;
  return fn;
}

/** Clean axis ticks at 1/2/5 x 10^n. */
export function niceTicks(lo: number, hi: number, count = 4): number[] {
  if (!Number.isFinite(lo) || !Number.isFinite(hi) || hi === lo) return [lo];
  const raw = (hi - lo) / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  const step = (norm >= 5 ? 10 : norm >= 2 ? 5 : norm >= 1 ? 2 : 1) * mag;
  const out: number[] = [];
  for (let t = Math.ceil(lo / step) * step; t <= hi + 1e-9; t += step) {
    out.push(Math.round(t * 1e6) / 1e6);
  }
  return out;
}

export interface Pt {
  x: number;
  y: number | null;
}

/**
 * Build an SVG path, breaking it wherever y is null.
 *
 * This is the mechanism that keeps "no data" from rendering as zero. Every
 * series that can have gaps must go through here rather than filtering nulls
 * out first — filtering would silently join across the gap.
 */
export function pathFromPoints(pts: Pt[]): string {
  let d = '';
  let pen = false;
  for (const p of pts) {
    if (p.y == null) {
      pen = false;
      continue;
    }
    d += `${pen ? 'L' : 'M'}${p.x.toFixed(1)},${p.y.toFixed(1)} `;
    pen = true;
  }
  return d.trim();
}

/** Contiguous runs of non-null points — used for area washes so gaps stay empty. */
export function runsOf(pts: Pt[]): { x: number; y: number }[][] {
  const runs: { x: number; y: number }[][] = [];
  let cur: { x: number; y: number }[] = [];
  for (const p of pts) {
    if (p.y == null) {
      if (cur.length > 1) runs.push(cur);
      cur = [];
    } else {
      cur.push({ x: p.x, y: p.y });
    }
  }
  if (cur.length > 1) runs.push(cur);
  return runs;
}

/** Column path: rounded at the data end, square at the baseline. */
export function colPath(x: number, y: number, w: number, h: number, r = 4): string {
  if (h <= 0.5) return '';
  const rr = Math.min(r, w / 2, h);
  return (
    `M${x},${y + h} L${x},${y + rr} Q${x},${y} ${x + rr},${y} ` +
    `L${x + w - rr},${y} Q${x + w},${y} ${x + w},${y + rr} ` +
    `L${x + w},${y + h} Z`
  );
}

/** Horizontal bar path: rounded at the right (data) end. */
export function barPath(x: number, y: number, w: number, h: number, r = 4): string {
  if (w <= 0.5) return '';
  const rr = Math.min(r, h / 2, w);
  return (
    `M${x},${y} L${x + w - rr},${y} Q${x + w},${y} ${x + w},${y + rr} ` +
    `L${x + w},${y + h - rr} Q${x + w},${y + h} ${x + w - rr},${y + h} ` +
    `L${x},${y + h} Z`
  );
}

export function shortDate(iso: string): string {
  const d = iso.includes('T') ? new Date(iso) : new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-GB', { month: 'short', day: 'numeric' });
}

/** Compact number formatting for axis ticks and stat values. */
export function compact(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return '—';
  const a = Math.abs(n);
  if (a >= 1e6) return `${(n / 1e6).toFixed(1).replace(/\.0$/, '')}M`;
  if (a >= 1e4) return `${(n / 1e3).toFixed(1).replace(/\.0$/, '')}K`;
  if (!Number.isInteger(n)) return n.toFixed(1);
  return n.toLocaleString('en-GB');
}

export const money = (n: number | null | undefined): string =>
  n == null ? '—' : `$${n.toFixed(2)}`;

/** Shared chart padding — leaves room for tick labels left and dates below. */
export const PAD = { t: 12, r: 14, b: 26, l: 40 } as const;
