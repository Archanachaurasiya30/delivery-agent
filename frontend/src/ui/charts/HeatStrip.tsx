import { type MouseEvent } from 'react';
import { ChartBox, ChartTooltip, useTooltip } from './ChartFrame';
import { shortDate } from './scale';

/** Status band → fill. The only place bands become colour. */
export const BAND_FILL: Record<string, string> = {
  Ahead: 'var(--chart-good)',
  'On track': 'var(--chart-good)',
  'At risk': 'var(--chart-warn)',
  Behind: 'var(--chart-bad)',
  'No data': 'var(--chart-nodata)',
};

export interface HeatRow {
  name: string;
  bands: string[];
}

const ROW_H = 32;
const CELL_H = 20;

/**
 * Ordered status per entity per day.
 *
 * Qualitative on purpose: colour and label, never a number. This is how the
 * executive altitude shows stream health over time without exposing the
 * per-stream confidence score — a score the four-factor blend cannot support
 * being compared across streams.
 */
export function HeatStrip({
  rows,
  dates,
  label = 'Stream health',
}: {
  rows: HeatRow[];
  dates: string[];
  label?: string;
}) {
  const { tip, show, hide } = useTooltip();
  const height = rows.length * ROW_H + 22;

  if (!rows.length || !dates.length) {
    return <div className="chart-note">No history yet</div>;
  }

  return (
    <ChartBox height={height}>
      {(width) => {
        const labelW = Math.min(190, Math.max(84, width * 0.24));
        const cellW = (width - labelW - 4) / dates.length;

        const onMove =
          (row: HeatRow, band: string, i: number) => (ev: MouseEvent<SVGRectElement>) => {
            const box = ev.currentTarget.ownerSVGElement!.getBoundingClientRect();
            show(
              ev.clientX - box.left,
              ev.clientY - box.top,
              <>
                <div className="tt-head">{row.name}</div>
                <div className="tt-row">
                  <span className="tt-key" style={{ background: BAND_FILL[band] }} />
                  <span>{shortDate(dates[i])}</span>
                  <b>{band}</b>
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
              {rows.map((r, ri) => {
                const y = ri * ROW_H + 6;
                return (
                  <g key={r.name}>
                    <text
                      x={labelW - 12}
                      y={y + 14}
                      textAnchor="end"
                      fontSize={12}
                      fill="var(--ink-soft)"
                    >
                      {r.name}
                    </text>
                    {r.bands.map((b, ci) => (
                      // 2px surface gap does the separating — no stroke on cells.
                      <rect
                        key={ci}
                        x={labelW + ci * cellW}
                        y={y}
                        width={Math.max(1, cellW - 2)}
                        height={CELL_H}
                        rx={3}
                        fill={BAND_FILL[b] ?? 'var(--chart-nodata)'}
                        opacity={b === 'No data' ? 1 : 0.92}
                        style={{ cursor: 'pointer' }}
                        onMouseMove={onMove(r, b, ci)}
                        onMouseLeave={hide}
                      />
                    ))}
                  </g>
                );
              })}
              <text x={labelW} y={height - 4} fontSize={10} fill="var(--ink-mute)">
                {shortDate(dates[0])}
              </text>
              <text
                x={width - 4}
                y={height - 4}
                textAnchor="end"
                fontSize={10}
                fill="var(--ink-mute)"
              >
                {shortDate(dates[dates.length - 1])}
              </text>
            </svg>
            <ChartTooltip tip={tip} width={width} />
          </>
        );
      }}
    </ChartBox>
  );
}
