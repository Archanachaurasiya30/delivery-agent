/**
 * In-house chart kit.
 *
 * No charting library: every mark is inline SVG bound to the CSS tokens in
 * styles/tokens.css. Two rules hold across all of it —
 *
 *   1. A null value breaks the mark. "No data" never renders as zero.
 *   2. Colour comes from --chart-* tokens only. The categorical order is fixed
 *      and validated (--chart-1 and --chart-4 must never be adjacent series;
 *      they fail the normal-vision separation floor).
 */
export { BarChart, type BarSeries } from './BarChart';
export {
  ChartBox, ChartEmpty, ChartNote, ChartTooltip, Grid, useChartSize, useTooltip,
} from './ChartFrame';
export { DotPlot, type DotPoint, type RefLine } from './DotPlot';
export { HBars, Meter, type HBarRow } from './HBars';
export { BAND_FILL, HeatStrip, type HeatRow } from './HeatStrip';
export { Legend, type LegendEntry } from './Legend';
export { LineChart, type Series, type SeriesPoint } from './LineChart';
export { CFD_RAMP, StackedAreaChart, type StackBand } from './StackedAreaChart';
export { Timeline, type TimelineItem } from './Timeline';
export {
  barPath, colPath, compact, linearScale, money, niceTicks, PAD,
  pathFromPoints, shortDate,
} from './scale';
