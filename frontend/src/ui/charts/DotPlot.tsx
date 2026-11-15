import { type MouseEvent } from 'react';
import { ChartBox, ChartEmpty, ChartTooltip, Grid, useTooltip } from './ChartFrame';
import { linearScale, niceTicks, PAD, shortDate } from './scale';

export interface DotPoint {
  /** ISO date the item completed — the x position. */
  date: string;
  /** Days taken — the y position. */
  value: number;
  label: string;
}

export interface RefLine {
  value: number;
  label: string;
}

interface Props {
  points: DotPoint[];
  /** Horizontal rules, e.g. p50 and p85. */
  refs?: RefLine[];
  height?: number;
  label?: string;
  valueFmt?: (v: number) => string;
  emptyMessage?: string;
}

/**
 * Scatter of completed items over time.
 *
 * A percentile pair says more about delivery predictability than an average
 * does, so the reference rules are the point of the chart — the dots exist to
 * show the spread the percentiles summarise.
 */
export function DotPlot({
  points,
  refs = [],
  height = 220,
  label = 'Cycle time',
  valueFmt = (v) => `${v}d`,
  emptyMessage = 'No completed items in this window',
}: Props) {
  const { tip, show, hide } = useTooltip();

  if (!points.length) {
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
        const times = points.map((p) => new Date(`${p.date}T00:00:00`).getTime());
        const t0 = Math.min(...times);
        const t1 = Math.max(...times);
        // A single day (or one point) would give a zero-width domain, so pad it
        // and the dots land mid-chart instead of on the axis.
        const padMs = t1 === t0 ? 86_400_000 : (t1 - t0) * 0.06;
        const x = linearScale(t0 - padMs, t1 + padMs, PAD.l, width - PAD.r);

        const hi = Math.max(...points.map((p) => p.value), ...refs.map((r) => r.value), 1) * 1.15;
        const y = linearScale(0, hi, height - PAD.b, PAD.t);
        const ticks = niceTicks(0, hi, 4);

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
                fmt={valueFmt}
                xLabels={[
                  { x: PAD.l, text: shortDate(points[0].date), anchor: 'start' },
                  {
                    x: width - PAD.r,
                    text: shortDate(points[points.length - 1].date),
                    anchor: 'end',
                  },
                ]}
              />

              {refs.map((r) => (
                <g key={r.label}>
                  <line
                    x1={PAD.l}
                    y1={y(r.value)}
                    x2={width - PAD.r}
                    y2={y(r.value)}
                    stroke="var(--chart-ref)"
                    strokeWidth={1.5}
                    strokeDasharray="5 4"
                  />
                  <text
                    x={width - PAD.r}
                    y={y(r.value) - 5}
                    textAnchor="end"
                    fontSize={10.5}
                    fontWeight={600}
                    fill="var(--ink-soft)"
                  >
                    {r.label} {valueFmt(r.value)}
                  </text>
                </g>
              ))}

              {points.map((p, i) => {
                const cx = x(new Date(`${p.date}T00:00:00`).getTime());
                const cy = y(p.value);
                const onMove = (ev: MouseEvent<SVGCircleElement>) => {
                  const box = ev.currentTarget.ownerSVGElement!.getBoundingClientRect();
                  show(
                    ev.clientX - box.left,
                    ev.clientY - box.top,
                    <>
                      <div className="tt-head">{p.label}</div>
                      <div className="tt-row">
                        <span className="tt-key" style={{ background: 'var(--chart-1)' }} />
                        <span>{shortDate(p.date)}</span>
                        <b>{valueFmt(p.value)}</b>
                      </div>
                    </>,
                  );
                };
                return (
                  <circle
                    key={`${p.label}-${i}`}
                    cx={cx}
                    cy={cy}
                    r={5}
                    fill="var(--chart-1)"
                    fillOpacity={0.75}
                    // 2px ring in the surface colour keeps overlapping dots readable.
                    stroke="var(--chart-surface)"
                    strokeWidth={2}
                    style={{ cursor: 'pointer' }}
                    onMouseMove={onMove}
                    onMouseLeave={hide}
                  />
                );
              })}
            </svg>
            <ChartTooltip tip={tip} width={width} />
          </>
        );
      }}
    </ChartBox>
  );
}
