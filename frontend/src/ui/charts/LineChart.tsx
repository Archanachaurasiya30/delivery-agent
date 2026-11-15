import { useId, useMemo, type MouseEvent } from 'react';
import {
  ChartBox, ChartEmpty, ChartTooltip, Grid, useTooltip, type XLabel,
} from './ChartFrame';
import {
  compact, linearScale, niceTicks, PAD, pathFromPoints, runsOf, shortDate, type Pt,
} from './scale';

export interface SeriesPoint {
  date: string;
  value: number | null;
}

export interface Series {
  name: string;
  points: SeriesPoint[];
  /** CSS colour, normally a var(--chart-N) token. */
  color?: string;
  /** Dashed = a reference line (ideal, target). Gets no end marker. */
  dashed?: boolean;
  /** Area wash colour; only used when `area` is set. */
  wash?: string;
}

interface Props {
  series: Series[];
  height?: number;
  yDomain?: [number, number];
  area?: boolean;
  label?: string;
  valueFmt?: (v: number) => string;
  /** Axis tick labels; defaults to valueFmt. Use a bare number when the unit
   *  ("items") would not fit the narrow axis gutter. */
  axisFmt?: (v: number) => string;
  emptyMessage?: string;
}

/**
 * Multi-series line/area chart with a crosshair tooltip.
 *
 * Nullable points break the path rather than dropping to the baseline — that
 * distinction is the whole reason this exists instead of a chart library
 * default, because a missing confidence snapshot is not a confidence of zero.
 */
export function LineChart({
  series,
  height = 200,
  yDomain,
  area = false,
  label = 'Trend',
  valueFmt = compact,
  axisFmt,
  emptyMessage = 'Not enough history yet',
}: Props) {
  const gradientId = useId();
  const { tip, show, hide } = useTooltip();

  // The longest series drives the x axis, so a short reference line does not
  // truncate the actual data.
  const spine = useMemo(
    () => series.reduce((a, b) => (b.points.length > a.points.length ? b : a), series[0]),
    [series],
  );
  const plottable = spine?.points.filter((p) => p.value != null).length ?? 0;

  if (!spine || plottable < 2) {
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
          .flatMap((s) => s.points.map((p) => p.value))
          .filter((v): v is number => v != null);
        const lo = yDomain ? yDomain[0] : Math.min(0, ...all);
        const hi = yDomain ? yDomain[1] : Math.max(...all, 1) * 1.08;
        const y = linearScale(lo, hi, height - PAD.b, PAD.t);
        const x = linearScale(0, spine.points.length - 1, PAD.l, width - PAD.r);
        // niceTicks, not evenly-split-then-rounded: on a small range (weekly
        // spend tops out under $1) rounding collapses every tick to the same
        // value, which both duplicates React keys and draws stacked gridlines.
        const ticks = niceTicks(lo, hi, 4);
        const baseline = height - PAD.b;

        const xLabels: XLabel[] = [
          { x: PAD.l, text: shortDate(spine.points[0].date), anchor: 'start' },
          {
            x: width - PAD.r,
            text: shortDate(spine.points[spine.points.length - 1].date),
            anchor: 'end',
          },
        ];

        const onMove = (ev: MouseEvent<SVGRectElement>) => {
          const box = ev.currentTarget.ownerSVGElement!.getBoundingClientRect();
          const px = ev.clientX - box.left;
          const i = Math.max(
            0,
            Math.min(spine.points.length - 1, Math.round(x.invert(px))),
          );
          show(
            x(i),
            ev.clientY - box.top,
            <>
              <div className="tt-head">{shortDate(spine.points[i].date)}</div>
              {series.map((s, si) => {
                const v = s.points[i]?.value;
                return (
                  <div className="tt-row" key={s.name}>
                    <span
                      className="tt-key"
                      style={{ background: s.color ?? `var(--chart-${si + 1})` }}
                    />
                    <span>{s.name}</span>
                    <b>{v == null ? 'no data' : valueFmt(v)}</b>
                  </div>
                );
              })}
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
              <defs>
                <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="rgba(91, 91, 214, 0.20)" />
                  <stop offset="100%" stopColor="rgba(91, 91, 214, 0.02)" />
                </linearGradient>
              </defs>

              {/* Axis labels use the same formatter as the tooltip so a money
                  chart reads "$2" on both, not "2" on one and "$2.00" on the other. */}
              <Grid
                width={width}
                height={height}
                y={y}
                ticks={ticks}
                xLabels={xLabels}
                fmt={axisFmt ?? valueFmt}
              />

              {series.map((s, si) => {
                const stroke = s.color ?? `var(--chart-${si + 1})`;
                const coords: Pt[] = s.points.map((p, i) => ({
                  x: x(i),
                  y: p.value == null ? null : y(p.value),
                }));
                const last = [...coords].reverse().find((c) => c.y != null);

                return (
                  <g key={s.name}>
                    {area &&
                      !s.dashed &&
                      runsOf(coords).map((run, ri) => (
                        <path
                          key={ri}
                          d={
                            `M${run[0].x},${baseline} ` +
                            run.map((c) => `L${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(' ') +
                            ` L${run[run.length - 1].x},${baseline} Z`
                          }
                          fill={s.wash ?? `url(#${gradientId})`}
                          stroke="none"
                        />
                      ))}
                    <path
                      d={pathFromPoints(coords)}
                      fill="none"
                      stroke={stroke}
                      strokeWidth={2}
                      strokeLinejoin="round"
                      strokeLinecap="round"
                      strokeDasharray={s.dashed ? '5 4' : undefined}
                    />
                    {last && !s.dashed && (
                      <circle
                        cx={last.x}
                        cy={last.y!}
                        r={4}
                        fill={stroke}
                        stroke="var(--chart-surface)"
                        strokeWidth={2}
                      />
                    )}
                  </g>
                );
              })}

              {tip && (
                <line
                  x1={tip.x}
                  y1={PAD.t}
                  x2={tip.x}
                  y2={baseline}
                  stroke="var(--line-strong)"
                  strokeWidth={1}
                />
              )}

              <rect
                x={PAD.l}
                y={PAD.t}
                width={Math.max(0, width - PAD.l - PAD.r)}
                height={Math.max(0, height - PAD.t - PAD.b)}
                fill="transparent"
                style={{ cursor: 'crosshair' }}
                onMouseMove={onMove}
                onMouseLeave={hide}
              />
            </svg>
            <ChartTooltip tip={tip} width={width} />
          </>
        );
      }}
    </ChartBox>
  );
}
