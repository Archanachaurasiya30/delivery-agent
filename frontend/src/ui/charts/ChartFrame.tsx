import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { compact, PAD } from './scale';

/**
 * Measures the container so charts draw at their true pixel width.
 *
 * Without this a chart has to pick a fixed viewBox width, and on a wider card
 * the browser scales the whole drawing up — including the type, which then
 * renders at the wrong size. Returns 0 until the first measurement so callers
 * can skip drawing rather than flash a wrong-sized chart.
 */
export function useChartSize(): [React.RefObject<HTMLDivElement | null>, number] {
  const ref = useRef<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const measure = () => setWidth(Math.round(node.getBoundingClientRect().width));
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(node);
    return () => ro.disconnect();
  }, []);

  return [ref, width];
}

/* ---------- tooltip ---------- */

export interface TipState {
  x: number;
  y: number;
  content: ReactNode;
}

export function useTooltip() {
  const [tip, setTip] = useState<TipState | null>(null);
  const show = useCallback((x: number, y: number, content: ReactNode) => {
    setTip({ x, y, content });
  }, []);
  const hide = useCallback(() => setTip(null), []);
  return { tip, show, hide };
}

export function ChartTooltip({ tip, width }: { tip: TipState | null; width: number }) {
  if (!tip) return null;
  // Flip to the left of the cursor near the right edge so the tooltip never
  // escapes the card.
  const flip = tip.x > width - 150;
  return (
    <div
      className="chart-tooltip"
      style={{
        left: flip ? undefined : tip.x + 14,
        right: flip ? width - tip.x + 14 : undefined,
        top: Math.max(0, tip.y - 12),
      }}
    >
      {tip.content}
    </div>
  );
}

/* ---------- shared states ---------- */

/**
 * The one canonical "not enough data" state.
 *
 * Centralised so that every chart in the app fails the same way — a dashed
 * rule and a sentence, never an axis full of zeros.
 */
export function ChartEmpty({ height, message }: { height: number; message: string }) {
  return (
    <svg
      width="100%"
      height={height}
      viewBox={`0 0 300 ${height}`}
      preserveAspectRatio="none"
      role="img"
      aria-label={message}
      style={{ display: 'block' }}
    >
      <line
        x1={8}
        y1={height / 2}
        x2={292}
        y2={height / 2}
        stroke="var(--line-strong)"
        strokeWidth={2}
        strokeDasharray="4 4"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

export function ChartNote({ children }: { children: ReactNode }) {
  return <div className="chart-note">{children}</div>;
}

/* ---------- axes ---------- */

export interface XLabel {
  x: number;
  text: string;
  anchor?: 'start' | 'middle' | 'end';
}

/** Gridlines with value labels, plus x-axis labels. Recessive by design. */
export function Grid({
  width,
  height,
  y,
  ticks,
  xLabels,
  fmt = compact,
}: {
  width: number;
  height: number;
  y: (v: number) => number;
  ticks: number[];
  xLabels?: XLabel[];
  fmt?: (n: number) => string;
}) {
  return (
    <g>
      {/* Keyed by index, not value: two ticks can round to the same label on a
          narrow domain, and duplicate keys drop gridlines silently. */}
      {ticks.map((t, i) => (
        <g key={i}>
          <line
            x1={PAD.l}
            y1={y(t)}
            x2={width - PAD.r}
            y2={y(t)}
            stroke="var(--chart-grid)"
            strokeWidth={1}
          />
          <text
            x={PAD.l - 8}
            y={y(t) + 3.5}
            textAnchor="end"
            fontSize={10}
            fill="var(--ink-mute)"
            style={{ fontVariantNumeric: 'tabular-nums' }}
          >
            {fmt(t)}
          </text>
        </g>
      ))}
      {(xLabels ?? []).map((l, i) => (
        <text
          key={i}
          x={l.x}
          y={height - 8}
          textAnchor={l.anchor ?? 'middle'}
          fontSize={10}
          fill="var(--ink-mute)"
        >
          {l.text}
        </text>
      ))}
    </g>
  );
}

/** Wrapper that owns measurement + tooltip positioning for a chart. */
export function ChartBox({
  height,
  children,
}: {
  height: number;
  children: (width: number) => ReactNode;
}) {
  const [ref, width] = useChartSize();
  return (
    <div ref={ref} className="chart-box" style={{ minHeight: height }}>
      {width > 0 ? children(width) : null}
    </div>
  );
}
