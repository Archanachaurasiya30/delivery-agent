import { useRoadmap, useStreams } from '../../hooks/useApi';
import { Legend, Timeline, shortDate } from '../../ui/charts';
import { Badge } from '../../ui/Badge';
import { EmptyState } from '../../ui/EmptyState';
import { STATUS_TONE } from '../portfolio/PortfolioView';
import type { StreamStatus } from '../../types';

interface Props {
  streamId: string | null;
  onSelectStream: (id: string | null) => void;
}

/**
 * Feature timeline.
 *
 * Spans are derived from the sprint dates of the tasks inside each feature —
 * `features` has no date column. That means the bars cannot drift away from
 * delivery, but also that a feature nobody has scheduled into a sprint has no
 * bar. That is reported, not papered over with an invented window.
 */
export function RoadmapView({ streamId, onSelectStream }: Props) {
  const { data: streams = [] } = useStreams();
  const { data, isPending } = useRoadmap(streamId);

  const items = data?.items ?? [];
  const scheduled = items.filter((i) => i.start_date && i.end_date);
  const unscheduled = items.filter((i) => !i.start_date || !i.end_date);

  // Pad the window by a fortnight either side so end-caps are not flush with
  // the frame, and always include today so the marker has somewhere to land.
  const pad = (iso: string, days: number) => {
    const d = new Date(`${iso}T00:00:00`);
    d.setDate(d.getDate() + days);
    return d.toISOString().slice(0, 10);
  };
  const today = data?.today ?? new Date().toISOString().slice(0, 10);
  const start = data?.window_start
    ? pad([data.window_start, today].sort()[0], -14)
    : today;
  const end = data?.window_end ? pad([data.window_end, today].sort().reverse()[0], 14) : today;

  return (
    <>
      <header className="header">
        <h1 className="header-title">Roadmap</h1>
      </header>

      <div className="content">
        <p className="dash-intro">
          Each feature’s span is derived from the sprint dates of the tasks inside it — earliest
          start to latest end. Nothing here is a hand-entered date, so the bars move when the work
          moves.
        </p>

        <div className="sprint-picker">
          <button
            className={`chip-btn${streamId ? '' : ' is-active'}`}
            onClick={() => onSelectStream(null)}
          >
            All streams
          </button>
          {streams.map((s) => (
            <button
              key={s.id}
              className={`chip-btn${streamId === s.id ? ' is-active' : ''}`}
              onClick={() => onSelectStream(s.id)}
            >
              {s.name}
            </button>
          ))}
        </div>

        <div className="command-card">
          <div className="command-card-title">Features in flight</div>
          <p className="card-sub">
            The bar is the feature’s window; the fill is completion by story points. Colour carries
            the owning stream’s health band, so this never disagrees with the portfolio.
          </p>
          <Legend
            entries={[
              { name: 'On track', color: 'var(--chart-good)' },
              { name: 'At risk', color: 'var(--chart-warn)' },
              { name: 'Behind', color: 'var(--chart-bad)' },
              { name: 'No data', color: 'var(--chart-nodata)' },
            ]}
          />
          {isPending ? (
            <EmptyState>Loading roadmap…</EmptyState>
          ) : scheduled.length ? (
            <Timeline
              items={scheduled.map((i) => ({
                name: i.name,
                stream: i.stream_name,
                start: i.start_date as string,
                end: i.end_date as string,
                status: i.status,
                progress: i.progress,
              }))}
              start={start}
              end={end}
              today={today}
            />
          ) : (
            <EmptyState>
              No feature has tasks in a sprint yet, so there is nothing to place on a timeline.
            </EmptyState>
          )}
        </div>

        {items.length > 0 && (
          <div className="command-card" style={{ marginTop: 16 }}>
            <table className="dash-table">
              <thead>
                <tr>
                  <th>Feature</th>
                  <th>Stream</th>
                  <th>Window</th>
                  <th>Health</th>
                  <th className="num">Points</th>
                  <th className="num">Complete</th>
                </tr>
              </thead>
              <tbody>
                {items.map((i) => (
                  <tr key={i.id}>
                    <td style={{ fontWeight: 600 }}>{i.name}</td>
                    <td className="muted">{i.stream_name ?? '—'}</td>
                    <td className="muted">
                      {i.start_date && i.end_date
                        ? `${shortDate(i.start_date)} → ${shortDate(i.end_date)}`
                        : 'not scheduled'}
                    </td>
                    <td>
                      <Badge tone={STATUS_TONE[i.status as StreamStatus] ?? 'neutral'}>
                        {i.status}
                      </Badge>
                    </td>
                    <td className="num">{i.completed_points}/{i.total_points}</td>
                    <td className="num">{Math.round(i.progress * 100)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {unscheduled.length > 0 && (
          <div className="command-card" style={{ marginTop: 16 }}>
            <div className="command-card-title">Not on the timeline</div>
            <p className="card-sub" style={{ marginBottom: 0 }}>
              {unscheduled.length} feature{unscheduled.length === 1 ? ' has' : 's have'} no task in a
              sprint, so there is no window to draw. Adding a <code>features.target_date</code>{' '}
              column would let the roadmap show a commitment before the work is planned — a
              deliberate follow-up, not an oversight.
            </p>
          </div>
        )}
      </div>
    </>
  );
}
