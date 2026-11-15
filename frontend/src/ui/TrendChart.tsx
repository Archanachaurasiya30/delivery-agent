import { useEffect, useId, useRef, useState } from 'react';

export interface TrendChartPoint {
  date: string;
  value: number;
}

interface TrendChartProps {
  points: TrendChartPoint[];
  width?: number;
  height?: number;
}

// Confidence is 0–100, so the domain is fixed (like Sparkline with min/max).
const LO = 0;
const HI = 100;
const GRIDLINES = [25, 50, 75];

// Padding leaves room for the gridline labels (left) and date labels (bottom).
const PAD_L = 30;
const PAD_R = 10;
const PAD_T = 8;
const PAD_B = 20;

function shortDate(iso: string): string {
  const d = iso.includes('T') ? new Date(iso) : new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

/**
 * Inline-SVG area chart — Sparkline's bigger sibling for panel-sized trends.
 * Same no-dependency approach: fixed 0–100 domain, gridlines at 25/50/75,
 * a translucent accent fill under the line, and first/last date labels.
 * Renders a dashed flat line when there aren't yet two points to connect.
 */
export function TrendChart({ points, width = 720, height = 180 }: TrendChartProps) {
  const gradientId = useId();
  // Fill the parent (the card) instead of a fixed pixel width.
  const hostRef = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(width);
  useEffect(() => {
    const host = hostRef.current;
    if (!host || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(([entry]) => {
      setW(Math.max(320, Math.round(entry.contentRect.width)));
    });
    ro.observe(host);
    return () => ro.disconnect();
  }, []);
  width = w;

  if (!points || points.length < 2) {
    return (
      <div ref={hostRef}>
        <svg width={width} height={height} role="img" aria-label="Not enough trend data yet">
        <line
          x1={PAD_L}
          y1={height / 2}
          x2={width - PAD_R}
          y2={height / 2}
          stroke="var(--line-strong)"
          strokeWidth={2}
          strokeDasharray="4 4"
        />
        <text
          x={(PAD_L + width - PAD_R) / 2}
          y={height / 2 - 10}
          textAnchor="middle"
          fontSize={11}
          fill="var(--ink-mute)"
        >
          Not enough trend data yet
        </text>
        </svg>
      </div>
    );
  }

  const innerW = width - PAD_L - PAD_R;
  const innerH = height - PAD_T - PAD_B;
  const range = HI - LO;

  const yOf = (v: number) => PAD_T + innerH - ((Math.max(LO, Math.min(HI, v)) - LO) / range) * innerH;
  const coords = points.map((p, i) => {
    const x = PAD_L + (i / (points.length - 1)) * innerW;
    return [x, yOf(p.value)] as const;
  });
  const line = coords.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
  const baseline = PAD_T + innerH;
  // Close the polygon along the baseline for the area fill.
  const area = `${PAD_L.toFixed(1)},${baseline.toFixed(1)} ${line} ${(width - PAD_R).toFixed(1)},${baseline.toFixed(1)}`;
  const [lastX, lastY] = coords[coords.length - 1];

  return (
    <div ref={hostRef}>
      <svg width={width} height={height} role="img" aria-label="Portfolio confidence trend">
      <defs>
        {/* rgba fallback for the accent tint — color-mix may be unavailable. */}
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="rgba(91, 91, 214, 0.22)" />
          <stop offset="100%" stopColor="rgba(91, 91, 214, 0.03)" />
        </linearGradient>
      </defs>

      {/* Gridlines with small value labels */}
      {GRIDLINES.map((g) => (
        <g key={g}>
          <line
            x1={PAD_L}
            y1={yOf(g)}
            x2={width - PAD_R}
            y2={yOf(g)}
            stroke="var(--line)"
            strokeWidth={1}
          />
          <text
            x={PAD_L - 6}
            y={yOf(g) + 3}
            textAnchor="end"
            fontSize={10}
            fill="var(--ink-mute)"
          >
            {g}
          </text>
        </g>
      ))}

      <polygon points={area} fill={`url(#${gradientId})`} stroke="none" />
      <polyline
        points={line}
        fill="none"
        stroke="var(--accent)"
        strokeWidth={2}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <circle cx={lastX.toFixed(1)} cy={lastY.toFixed(1)} r={3} fill="var(--accent)" />

      {/* First / last date labels */}
      <text x={PAD_L} y={height - 5} textAnchor="start" fontSize={10} fill="var(--ink-mute)">
        {shortDate(points[0].date)}
      </text>
      <text x={width - PAD_R} y={height - 5} textAnchor="end" fontSize={10} fill="var(--ink-mute)">
        {shortDate(points[points.length - 1].date)}
      </text>
      </svg>
    </div>
  );
}
