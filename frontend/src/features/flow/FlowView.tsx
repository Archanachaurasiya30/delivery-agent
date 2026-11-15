import { useState } from 'react';
import { useFlowMetrics, useStreams } from '../../hooks/useApi';
import {
  BarChart, CFD_RAMP, DotPlot, Legend, StackedAreaChart, shortDate,
} from '../../ui/charts';
import { Badge } from '../../ui/Badge';
import { EmptyState } from '../../ui/EmptyState';
import { Kpi } from '../../ui/Kpi';

const WINDOWS = [14, 30, 90] as const;

// Bottom-to-top in workflow order — the stack order IS the encoding.
const CFD_BANDS = [
  { key: 'todo', label: 'To do' },
  { key: 'in_progress', label: 'In progress' },
  { key: 'review', label: 'Review' },
  { key: 'done', label: 'Done' },
];

/**
 * Flow metrics — cycle time, lead time, throughput, aging WIP.
 *
 * These come from `task_status_events` and nowhere else. The confidence
 * snapshots record a daily position, not a transition, so they can produce a
 * burndown but never a cycle time.
 */
export function FlowView({
  streamId,
  onSelectStream,
}: {
  streamId: string | null;
  onSelectStream: (id: string | null) => void;
}) {
  const [days, setDays] = useState<number>(30);
  const { data: streams = [] } = useStreams();
  const { data, isPending } = useFlowMetrics(days, streamId);

  const fmtDays = (v: number) => (v < 1 ? `${Math.round(v * 24)}h` : `${v}d`);

  return (
    <>
      <header className="header">
        <h1 className="header-title">Flow</h1>
      </header>

      <div className="content">
        <p className="dash-intro">
          How long work actually takes, and how much of it finishes. Measured from the task status
          event log — the burndown can be rebuilt from daily snapshots, but cycle time cannot: a
          snapshot records where work sat that day, not when it moved.
        </p>

        <div className="sprint-picker">
          {WINDOWS.map((w) => (
            <button
              key={w}
              className={`chip-btn${days === w ? ' is-active' : ''}`}
              onClick={() => setDays(w)}
            >
              {w} days
            </button>
          ))}
          <span style={{ width: 12 }} />
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

        {isPending ? (
          <EmptyState>Loading flow metrics…</EmptyState>
        ) : !data ? (
          <EmptyState>No flow data</EmptyState>
        ) : (
          <>
            {/* The event log starts when the migration ran, not when the project
                did. Say so rather than implying these cover all history. */}
            {data.backfilled_only ? (
              <div className="caveat" style={{ marginBottom: 16 }}>
                <b>No measured transitions yet.</b> The event log was seeded with one synthetic row
                per task when it was created, and those are deliberately excluded from every number
                here. Cycle time and throughput start populating as soon as work moves between
                statuses.
              </div>
            ) : data.history_starts ? (
              <div className="chart-note" style={{ marginBottom: 16 }}>
                Measured history starts {shortDate(data.history_starts)}. Anything completed before
                then has no recorded start, so it is excluded rather than counted as instant.
              </div>
            ) : null}

            <div className="kpis">
              <Kpi
                label="Cycle time (p50)"
                value={data.cycle_time_p50 == null ? null : fmtDays(data.cycle_time_p50)}
                foot="in progress → done"
              />
              <Kpi
                label="Cycle time (p85)"
                value={data.cycle_time_p85 == null ? null : fmtDays(data.cycle_time_p85)}
                foot="the number to plan against"
              />
              <Kpi
                label="Lead time (p50)"
                value={data.lead_time_p50 == null ? null : fmtDays(data.lead_time_p50)}
                foot="created → done"
              />
              <Kpi
                label="Completed"
                value={data.throughput.reduce((a, b) => a + b.count, 0)}
                foot={`in the last ${days} days`}
              />
              <Kpi
                label="Aging WIP"
                value={data.aging_wip.length}
                tone={data.aging_wip.length ? 'var(--orange)' : undefined}
                foot="in progress or review"
              />
            </div>

            <div className="command-card">
              <div className="command-card-title">Throughput</div>
              <p className="card-sub">
                Items reaching done per day. Unlike the delivery summary elsewhere, this counts
                recorded transitions rather than inferring from a last-modified timestamp.
              </p>
              <BarChart
                groups={data.throughput.map((t) => shortDate(t.date))}
                series={[{
                  name: 'Completed',
                  values: data.throughput.map((t) => t.count),
                  color: 'var(--chart-good)',
                }]}
                valueFmt={(v) => String(v)}
                emptyMessage={`Nothing completed in the last ${days} days`}
              />
            </div>

            <div className="command-card" style={{ marginTop: 16 }}>
              <div className="command-card-title">Cycle time spread</div>
              <p className="card-sub">
                Each dot is one completed item. Plan against p85, not the average — the average
                hides the tail, and the tail is what misses dates.
              </p>
              <DotPlot
                points={data.items.map((i) => ({
                  date: i.completed_on,
                  value: i.days,
                  label: i.title,
                }))}
                refs={[
                  ...(data.cycle_time_p50 != null
                    ? [{ value: data.cycle_time_p50, label: 'p50' }]
                    : []),
                  ...(data.cycle_time_p85 != null
                    ? [{ value: data.cycle_time_p85, label: 'p85' }]
                    : []),
                ]}
                valueFmt={fmtDays}
                emptyMessage={`No items completed with a recorded start in the last ${days} days`}
              />
            </div>


            <div className="command-card" style={{ marginTop: 16 }}>
              <div className="command-card-title">Cumulative flow</div>
              <p className="card-sub">
                How many items sat in each stage, per day. Bands are one hue in workflow order
                rather than four colours — the position in the pipeline is the meaning, and an
                ordered ramp says that where unrelated hues would not. Widening bands mean work is
                arriving faster than it is leaving.
              </p>
              <Legend
                entries={CFD_BANDS.map((b, i) => ({ name: b.label, color: CFD_RAMP[i] }))}
              />
              <StackedAreaChart
                rows={data.cfd as unknown as Array<Record<string, string | number>>}
                bands={CFD_BANDS}
                emptyMessage="Not enough recorded history for a flow diagram yet"
              />
            </div>

            <div className="command-card" style={{ marginTop: 16 }}>
              <div className="command-card-title">Aging work in progress</div>
              <p className="card-sub">
                Open items by how long they have been in their current status. This is a recorded
                transition, not a last-modified guess — it survives the autopilot nudge and provider
                sync, both of which rewrite <code>updated_at</code>.
              </p>
              {data.aging_wip.length ? (
                <table className="dash-table">
                  <thead>
                    <tr>
                      <th>Item</th>
                      <th>Assignee</th>
                      <th>Status</th>
                      <th className="num">Days</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.aging_wip.map((a) => {
                      const over85 =
                        data.cycle_time_p85 != null && a.days_in_status > data.cycle_time_p85;
                      return (
                        <tr key={a.task_id}>
                          <td>{a.title}</td>
                          <td className="muted">{a.assignee_name ?? 'Unassigned'}</td>
                          <td className="muted">{a.status.replace('_', ' ')}</td>
                          <td className="num">
                            <Badge tone={over85 ? 'danger' : 'neutral'}>
                              {a.days_in_status.toFixed(1)}
                            </Badge>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              ) : (
                <EmptyState>Nothing is in progress right now.</EmptyState>
              )}
            </div>
          </>
        )}
      </div>
    </>
  );
}
