import { type MouseEvent } from 'react';
import { ChartBox, ChartEmpty, ChartTooltip, Grid, useTooltip } from './ChartFrame';
import { bandScale, colPath, compact, linearScale, niceTicks, PAD } from './scale';

export interface BarSeries {
  name: string;
  values: (number | null)[];
  color?: string;
  /** Renders at low opacity — the "plan" half of a plan-vs-actual pair. */
  muted?: boolean;
}

interface Props {
  groups: string[];
  series: BarSeries[];
  height?: number;
  label?: string;
  valueFmt?: (v: number) => string;
  /** Label only the final group, so the chart stays readable. */
  labelLast?: boolean;
  emptyMessage?: string;
}

/** Bars are capped at this thickness — a full-width bar reads as a block. */
const MAX_BAR = 24;
/** Gap in the surface colour between touching bars. */
const GAP = 2;

/**
 * Grouped columns for velocity (committed vs completed) and throughput.
 *
 * Plan-vs-actual pairs should pass ONE colour with `muted` on the plan series
 * rather than two categorical hues — two hues implies two unrelated things.
 */
export function BarChart({
  groups,
  series,
  height = 200,
  label = 'Comparison',
  valueFmt = compact,
  labelLast = true,
  emptyMessage = 'No data yet',
}: Props) {
  const { tip, show, hide } = useTooltip();

  // All-zero is not the same as no data, but a chart of nothing but zeros reads
  // as broken — say it in words and skip the empty axis.
  const anyValue = series.some((s) => s.values.some((v) => v != null && v > 0));
  if (!groups.length || !anyValue) {
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
        const all = series
          .flatMap((s) => s.values)
          .filter((v): v is number => v != null);
        const hi = Math.max(...all, 1) * 1.15;
        const y = linearScale(0, hi, height - PAD.b, PAD.t);
        const band = bandScale(groups.length, PAD.l, width - PAD.r, 0.32);
        const ticks = niceTicks(0, hi, 4);
        const baseline = height - PAD.b;

        const n = series.length;
        const slot = (band.band - (n - 1) * GAP) / n;
        const bw = Math.max(2, Math.min(MAX_BAR, slot));
        const groupW = n * bw + (n - 1) * GAP;

        const onMove =
          (group: string, s: BarSeries, v: number, fill: string) =>
          (ev: MouseEvent<SVGPathElement>) => {
            const box = ev.currentTarget.ownerSVGElement!.getBoundingClientRect();
            show(
              ev.clientX - box.left,
              ev.clientY - box.top,
              <>
                <div className="tt-head">{group}</div>
                <div className="tt-row">
                  <span className="tt-key" style={{ background: fill, opacity: s.muted ? 0.32 : 1 }} />
                  <span>{s.name}</span>
                  <b>{valueFmt(v)}</b>
                </div>
              </>,
            );
          };

        return (
          <>
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
                xLabels={groups.map((g, i) => ({ x: band(i) + band.band / 2, text: g }))}
              />

              {groups.map((g, gi) =>
                series.map((s, si) => {
                  const v = s.values[gi];
                  if (v == null) return null;
                  const bx = band(gi) + (band.band - groupW) / 2 + si * (bw + GAP);
                  const by = y(v);
                  const fill = s.color ?? `var(--chart-${si + 1})`;
                  return (
                    <g key={`${g}-${s.name}`}>
                      <path
                        d={colPath(bx, by, bw, baseline - by, 4)}
                        fill={fill}
                        opacity={s.muted ? 0.32 : 1}
                        style={{ cursor: 'pointer' }}
                        onMouseMove={onMove(g, s, v, fill)}
                        onMouseLeave={hide}
                      />
                      {labelLast && gi === groups.length - 1 && (
                        <text
                          x={bx + bw / 2}
                          y={by - 6}
                          textAnchor="middle"
                          fontSize={10.5}
                          fontWeight={600}
                          fill="var(--ink-soft)"
                          style={{ fontVariantNumeric: 'tabular-nums' }}
                        >
                          {valueFmt(v)}
                        </text>
                      )}
                    </g>
                  );
                }),
              )}
            </svg>
            <ChartTooltip tip={tip} width={width} />
          </>
        );
      }}
    </ChartBox>
  );
}
