import { ChartBox, ChartEmpty, Grid } from './ChartFrame';
import { linearScale, niceTicks, PAD, shortDate } from './scale';

export interface StackBand {
  key: string;
  label: string;
  /** Explicit fill; defaults to a step of the sequential ramp below. */
  color?: string;
}

interface Props {
  /** One row per day: `{ date, [bandKey]: count }`. */
  rows: Array<Record<string, string | number>>;
  bands: StackBand[];
  height?: number;
  label?: string;
  emptyMessage?: string;
}

/**
 * A cumulative flow diagram is an ORDERED scale — position in the workflow —
 * not a set of unrelated categories. So the bands take one hue in increasing
 * steps rather than a categorical palette.
 *
 * That is also what keeps it valid: a sequential ramp is allowed to have
 * low-contrast neighbours because the ordering carries the meaning, whereas
 * four categorical hues here would have to clear the adjacency floor and the
 * obvious board colours (grey todo, blue in-progress) fail it.
 */
const RAMP = [
  'rgba(91, 91, 214, 0.16)',
  'rgba(91, 91, 214, 0.34)',
  'rgba(91, 91, 214, 0.55)',
  'rgba(91, 91, 214, 0.78)',
  'rgba(91, 91, 214, 0.95)',
];

export function StackedAreaChart({
  rows,
  bands,
  height = 240,
  label = 'Cumulative flow',
  emptyMessage = 'Not enough history yet',
}: Props) {
  if (rows.length < 2) {
    return (
      <>
        <ChartEmpty height={height} message={emptyMessage} />
        <div className="chart-note">{emptyMessage}</div>
      </>
    );
  }

  return (
    <ChartBox height={height}>
      {(width) => {
        const totals = rows.map((r) =>
          bands.reduce((sum, b) => sum + Number(r[b.key] ?? 0), 0),
        );
        const hi = Math.max(...totals, 1) * 1.08;
        const y = linearScale(0, hi, height - PAD.b, PAD.t);
        const x = linearScale(0, rows.length - 1, PAD.l, width - PAD.r);
        const ticks = niceTicks(0, hi, 4);

        // Build each band's polygon from its running baseline upward, so the
        // stack reads bottom-to-top in workflow order.
        const baselines = rows.map(() => 0);
        const shapes = bands.map((b, bi) => {
          const lower = [...baselines];
          rows.forEach((r, i) => {
            baselines[i] += Number(r[b.key] ?? 0);
          });
          const upper = [...baselines];
          const d =
            upper.map((v, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ') +
            ' ' +
            // Walk the lower edge back the other way to close the band.
            lower
              .map((_, i) => {
                const j = lower.length - 1 - i;
                return `L${x(j).toFixed(1)},${y(lower[j]).toFixed(1)}`;
              })
              .join(' ') +
            ' Z';
          return { d, fill: b.color ?? RAMP[bi % RAMP.length], key: b.key };
        });

        return (
          <svg
            width="100%"
            height={height}
            viewBox={`0 0 ${width} ${height}`}
            role="img"
            aria-label={label}
            style={{ display: 'block' }}
          >
            <Grid
              width={width}
              height={height}
              y={y}
              ticks={ticks}
              xLabels={[
                { x: PAD.l, text: shortDate(String(rows[0].date)), anchor: 'start' },
                {
                  x: width - PAD.r,
                  text: shortDate(String(rows[rows.length - 1].date)),
                  anchor: 'end',
                },
              ]}
            />
            {shapes.map((s) => (
              // 1px surface stroke is the gap that separates touching bands.
              <path
                key={s.key}
                d={s.d}
                fill={s.fill}
                stroke="var(--chart-surface)"
                strokeWidth={1}
              />
            ))}
          </svg>
        );
      }}
    </ChartBox>
  );
}

export const CFD_RAMP = RAMP;
