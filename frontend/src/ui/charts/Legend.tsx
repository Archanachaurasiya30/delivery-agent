export interface LegendEntry {
  name: string;
  color: string;
  /** Renders as a thin rule — matches a dashed reference line. */
  dashed?: boolean;
  /** Matches a muted series (a plan bar drawn at low opacity). */
  opacity?: number;
}

/**
 * Always present for two or more series — colour alone is never the only
 * identity channel. A single-series chart needs none: the title already names
 * what is plotted, so a one-swatch box just restates it.
 */
export function Legend({ entries }: { entries: LegendEntry[] }) {
  if (entries.length < 2) return null;
  return (
    <div className="chart-legend">
      {entries.map((e) => (
        <span className="chart-legend-item" key={e.name}>
          <span
            className="chart-legend-key"
            style={{
              background: e.color,
              opacity: e.opacity,
              ...(e.dashed ? { height: 2, borderRadius: 0 } : null),
            }}
          />
          {e.name}
        </span>
      ))}
    </div>
  );
}
