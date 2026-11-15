interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  stroke?: string;
  /** Fix the value domain (defaults to data min/max). Confidence is 0-100. */
  min?: number;
  max?: number;
}

/**
 * Minimal inline-SVG trend line. No chart dependency — the project ships none.
 * Renders a dashed flat line when there aren't yet two points to connect.
 */
export function Sparkline({
  data,
  width = 168,
  height = 44,
  stroke = 'var(--accent)',
  min,
  max,
}: SparklineProps) {
  const pad = 3;

  if (!data || data.length < 2) {
    return (
      <svg width={width} height={height} role="img" aria-label="Not enough trend data yet">
        <line
          x1={pad}
          y1={height / 2}
          x2={width - pad}
          y2={height / 2}
          stroke="var(--line-strong)"
          strokeWidth={2}
          strokeDasharray="4 4"
        />
      </svg>
    );
  }

  const lo = min ?? Math.min(...data);
  const hi = max ?? Math.max(...data);
  const range = hi - lo || 1;
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;

  const coords = data.map((v, i) => {
    const x = pad + (i / (data.length - 1)) * innerW;
    const y = pad + innerH - ((v - lo) / range) * innerH;
    return [x, y] as const;
  });
  const points = coords.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
  const [lastX, lastY] = coords[coords.length - 1];

  return (
    <svg width={width} height={height} role="img" aria-label="Confidence trend">
      <polyline
        points={points}
        fill="none"
        stroke={stroke}
        strokeWidth={2}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <circle cx={lastX.toFixed(1)} cy={lastY.toFixed(1)} r={2.75} fill={stroke} />
    </svg>
  );
}
