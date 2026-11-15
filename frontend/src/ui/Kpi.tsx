import type { ReactNode } from 'react';

interface KpiProps {
  label: string;
  /** Pass null for "no data" — renders an em dash, never a zero. */
  value: ReactNode | null;
  foot?: ReactNode;
  /** Colour applied to the value only; labels always use text tokens. */
  tone?: string;
}

/**
 * A stat tile: label, value, optional footnote.
 *
 * The null contract matters more than it looks. `velocity` is null until a
 * sprint completes and `success_rate` is null until a run finishes — showing
 * either as 0 would report a real (bad) result where there is simply no
 * measurement yet.
 */
export function Kpi({ label, value, foot, tone }: KpiProps) {
  const empty = value == null || value === '';
  return (
    <div className="kpi">
      <div className="kpi-label">{label}</div>
      <div className={`kpi-value${empty ? ' is-empty' : ''}`} style={empty ? undefined : { color: tone }}>
        {empty ? '—' : value}
      </div>
      {foot ? <div className="kpi-foot">{foot}</div> : null}
    </div>
  );
}

/** Signed change against a named period. Green/red by direction, not by sign. */
export function Delta({
  value,
  suffix = '',
  goodWhen = 'up',
}: {
  value: number | null;
  suffix?: string;
  goodWhen?: 'up' | 'down';
}) {
  if (value == null || !Number.isFinite(value)) return null;
  const rounded = Math.round(value * 10) / 10;
  if (rounded === 0) return <span className="delta flat">no change</span>;
  const good = goodWhen === 'up' ? rounded > 0 : rounded < 0;
  return (
    <span className={`delta ${good ? 'up' : 'down'}`}>
      {rounded > 0 ? '+' : ''}
      {rounded}
      {suffix}
    </span>
  );
}

/** The receipt shown next to any derived or estimated number. */
export function Formula({ children }: { children: ReactNode }) {
  return <div className="formula">{children}</div>;
}
