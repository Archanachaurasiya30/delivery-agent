import { type MouseEvent } from 'react';
import { ChartBox, ChartTooltip, useTooltip } from './ChartFrame';
import { barPath, compact, linearScale } from './scale';

export interface HBarRow {
  name: string;
  value: number;
  color?: string;
  note?: string;
}

interface Props {
  rows: HBarRow[];
  max?: number;
  /** Draws a dashed reference line — e.g. a member's capacity. */
  refAt?: number;
  refLabel?: string;
  valueFmt?: (v: number) => string;
  label?: string;
}

const ROW_H = 30;
const BAR_H = 16;

/**
 * Horizontal bars for run funnels and team load.
 *
 * A funnel is magnitude down a pipeline, not identity — pass one colour for
 * the in-flight stages and reserve status colours for terminal outcomes.
 */
export function HBars({
  rows,
  max,
  refAt,
  refLabel,
  valueFmt = compact,
  label = 'Breakdown',
}: Props) {
  const { tip, show, hide } = useTooltip();
  const height = rows.length * ROW_H + (refAt != null ? 26 : 10);

  if (!rows.length) return <div className="chart-note">Nothing to show yet</div>;

  return (
    <ChartBox height={height}>
      {(width) => {
        const labelW = Math.min(190, Math.max(84, width * 0.24));
        const valueW = 54;
        const hi = max ?? Math.max(...rows.map((r) => r.value), 1);
        const x = linearScale(0, hi, labelW, width - valueW);

        const onMove =
          (r: HBarRow, fill: string) => (ev: MouseEvent<SVGPathElement>) => {
            const box = ev.currentTarget.ownerSVGElement!.getBoundingClientRect();
            show(
              ev.clientX - box.left,
              ev.clientY - box.top,
              <>
                <div className="tt-row">
                  <span className="tt-key" style={{ background: fill }} />
                  <span>{r.name}</span>
                  <b>{valueFmt(r.value)}</b>
                </div>
                {r.note && <div className="tt-note">{r.note}</div>}
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
              {refAt != null && (
                <g>
                  <line
                    x1={x(refAt)}
                    y1={2}
                    x2={x(refAt)}
                    y2={rows.length * ROW_H + 2}
                    stroke="var(--chart-ref)"
                    strokeWidth={1}
                    strokeDasharray="3 3"
                  />
                  <text
                    x={x(refAt)}
                    y={height - 6}
                    textAnchor="middle"
                    fontSize={10}
                    fill="var(--ink-mute)"
                  >
                    {refLabel ?? valueFmt(refAt)}
                  </text>
                </g>
              )}

              {rows.map((r, i) => {
                const y = i * ROW_H + 5;
                const fill = r.color ?? 'var(--chart-1)';
                return (
                  <g key={`${r.name}-${i}`}>
                    <text
                      x={labelW - 12}
                      y={y + 12}
                      textAnchor="end"
                      fontSize={12}
                      fill="var(--ink-soft)"
                    >
                      {r.name}
                    </text>
                    <rect
                      x={labelW}
                      y={y}
                      width={Math.max(0, width - valueW - labelW)}
                      height={BAR_H}
                      rx={4}
                      fill="var(--chart-track)"
                    />
                    <path
                      d={barPath(labelW, y, Math.max(0, x(r.value) - labelW), BAR_H, 4)}
                      fill={fill}
                      style={{ cursor: 'pointer' }}
                      onMouseMove={onMove(r, fill)}
                      onMouseLeave={hide}
                    />
                    <text
                      x={width - valueW + 8}
                      y={y + 12}
                      fontSize={12}
                      fontWeight={600}
                      fill="var(--ink)"
                      style={{ fontVariantNumeric: 'tabular-nums' }}
                    >
                      {valueFmt(r.value)}
                    </text>
                  </g>
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

/**
 * A single ratio against a limit. The unfilled track is a lighter step of the
 * same ramp so the state reads across the whole bar, not just the fill.
 */
export function Meter({
  value,
  tone = 'good',
  label = 'Progress',
}: {
  value: number | null;
  tone?: 'good' | 'warn' | 'bad';
  label?: string;
}) {
  const H = 14;
  return (
    <ChartBox height={H}>
      {(width) => (
        <svg
          width="100%"
          height={H}
          viewBox={`0 0 ${width} ${H}`}
          role="img"
          aria-label={`${label} ${value ?? 'no data'}`}
          style={{ display: 'block' }}
        >
          <rect x={0} y={0} width={width} height={H} rx={H / 2} fill="var(--chart-track)" />
          {value != null && value > 0 && (
            <path
              d={barPath(0, 0, Math.max(8, (value / 100) * width), H, H / 2)}
              fill={`var(--chart-${tone})`}
            />
          )}
        </svg>
      )}
    </ChartBox>
  );
}
