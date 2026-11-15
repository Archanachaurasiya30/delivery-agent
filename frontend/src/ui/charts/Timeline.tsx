import { type MouseEvent } from 'react';
import { ChartBox, ChartTooltip, useTooltip } from './ChartFrame';
import { BAND_FILL } from './HeatStrip';
import { barPath, linearScale, shortDate } from './scale';

export interface TimelineItem {
  name: string;
  stream?: string | null;
  start: string;
  end: string;
  status: string;
  /** 0–1 completion; drives the fill length inside the span. */
  progress: number;
}

const ROW_H = 34;
const BAR_H = 18;

const ms = (iso: string) => new Date(`${iso}T00:00:00`).getTime();

/**
 * Roadmap bars.
 *
 * The span is the feature's window (derived upstream from its tasks' sprint
 * dates); the fill inside it is completion. Colour carries the owning stream's
 * health band, so the roadmap and the portfolio never disagree.
 */
export function Timeline({
  items,
  start,
  end,
  today,
  label = 'Roadmap',
}: {
  items: TimelineItem[];
  start: string;
  end: string;
  today?: string;
  label?: string;
}) {
  const { tip, show, hide } = useTooltip();
  const height = items.length * ROW_H + 30;

  if (!items.length) return <div className="chart-note">No features with sprint dates yet</div>;

  return (
    <ChartBox height={height}>
      {(width) => {
        const labelW = Math.min(210, Math.max(100, width * 0.26));
        const x = linearScale(ms(start), ms(end), labelW, width - 12);

        // Month gridlines.
        const months: { x: number; text: string }[] = [];
        const cur = new Date(`${start}T00:00:00`);
        cur.setDate(1);
        while (cur.getTime() <= ms(end)) {
          if (cur.getTime() >= ms(start)) {
            months.push({
              x: x(cur.getTime()),
              text: cur.toLocaleDateString('en-GB', { month: 'short' }),
            });
          }
          cur.setMonth(cur.getMonth() + 1);
        }

        const onMove = (it: TimelineItem) => (ev: MouseEvent<SVGPathElement>) => {
          const box = ev.currentTarget.ownerSVGElement!.getBoundingClientRect();
          show(
            ev.clientX - box.left,
            ev.clientY - box.top,
            <>
              <div className="tt-head">{it.name}</div>
              <div className="tt-row">
                <span className="tt-key" style={{ background: BAND_FILL[it.status] }} />
                <span>{it.status}</span>
                <b>{Math.round(it.progress * 100)}%</b>
              </div>
              <div className="tt-note">
                {shortDate(it.start)} → {shortDate(it.end)}
                {it.stream ? ` · ${it.stream}` : ''}
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
              {months.map((m, i) => (
                <g key={i}>
                  <line
                    x1={m.x}
                    y1={4}
                    x2={m.x}
                    y2={height - 22}
                    stroke="var(--chart-grid)"
                    strokeWidth={1}
                  />
                  <text x={m.x + 4} y={height - 8} fontSize={10} fill="var(--ink-mute)">
                    {m.text}
                  </text>
                </g>
              ))}

              {items.map((it, i) => {
                const y = i * ROW_H + 8;
                const bx = x(ms(it.start));
                const bw = Math.max(6, x(ms(it.end)) - bx);
                return (
                  <g key={`${it.name}-${i}`}>
                    <text
                      x={labelW - 12}
                      y={y + 14}
                      textAnchor="end"
                      fontSize={12}
                      fill="var(--ink-soft)"
                    >
                      {it.name}
                    </text>
                    <rect x={bx} y={y + 2} width={bw} height={BAR_H} rx={5} fill="var(--chart-track)" />
                    <path
                      d={barPath(bx, y + 2, bw * Math.min(1, Math.max(0, it.progress)), BAR_H, 5)}
                      fill={BAND_FILL[it.status] ?? 'var(--chart-nodata)'}
                      style={{ cursor: 'pointer' }}
                      onMouseMove={onMove(it)}
                      onMouseLeave={hide}
                    />
                  </g>
                );
              })}

              {/* Labelled, because when every bar ends well before it the gap
                  is the point — "all of this was planned to finish a month
                  ago" is the signal, not a rendering artefact. */}
              {today && (
                <g>
                  <line
                    x1={x(ms(today))}
                    y1={4}
                    x2={x(ms(today))}
                    y2={height - 22}
                    stroke="var(--chart-1)"
                    strokeWidth={2}
                    opacity={0.55}
                  />
                  <text
                    x={x(ms(today)) - 5}
                    y={14}
                    textAnchor="end"
                    fontSize={10}
                    fontWeight={600}
                    fill="var(--chart-1)"
                  >
                    today
                  </text>
                </g>
              )}
            </svg>
            <ChartTooltip tip={tip} width={width} />
          </>
        );
      }}
    </ChartBox>
  );
}
