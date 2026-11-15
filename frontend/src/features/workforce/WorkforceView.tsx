import { AlertTriangle, Cpu } from 'lucide-react';
import { useCodingStats, useCostByStream, useWorkforceTrend } from '../../hooks/useApi';
import { BarChart, HBars, LineChart, money, shortDate } from '../../ui/charts';
import { EmptyState } from '../../ui/EmptyState';
import { Formula, Kpi } from '../../ui/Kpi';
import { AutopilotCard } from '../command/AutopilotCard';

/**
 * The AI-workforce ROI page — the executive answer to "is this paying off?".
 *
 * Every number here was already returned by GET /coding/stats and thrown away:
 * the Command Center fetched all eleven fields and rendered two. The page that
 * proves the product's central claim did not exist.
 */
export function WorkforceView() {
  const { data: stats, isPending } = useCodingStats();
  const { data: trend } = useWorkforceTrend(84, 7);
  const { data: cost } = useCostByStream();

  if (isPending) {
    return (
      <>
        <header className="header"><h1 className="header-title">AI Workforce</h1></header>
        <div className="content"><EmptyState>Loading workforce stats…</EmptyState></div>
      </>
    );
  }

  const merged = stats?.merged ?? 0;
  const hours = stats?.hours_saved ?? 0;
  const spend = stats?.total_cost ?? 0;
  // Guard every derived ratio: 0 merged runs must not produce Infinity.
  const perMerged = merged > 0 ? spend / merged : null;
  const perHour = hours > 0 ? spend / hours : null;
  const points = trend?.points ?? [];

  const funnel = stats
    ? [
        { name: 'Dispatched', value: stats.total_runs, color: 'var(--chart-1)' },
        { name: 'PR opened', value: stats.pr_open + stats.merged, color: 'var(--chart-1)' },
        { name: 'Merged', value: stats.merged, color: 'var(--chart-good)', note: 'human-approved' },
        { name: 'Failed', value: stats.failed, color: 'var(--chart-bad)', note: 'CI red or agent error' },
      ]
    : [];

  return (
    <>
      <header className="header">
        <h1 className="header-title">AI Workforce</h1>
        <div className="header-actions">
          {(stats?.active_now ?? 0) > 0 && (
            <span className="live-indicator">
              <span className="live-dot" />
              {stats!.active_now} in flight
            </span>
          )}
        </div>
      </header>

      <div className="content">
        <p className="dash-intro">
          What the coding agent shipped, how often it was right, what it cost and what it saved.
          Every merged run below passed CI and was approved by a human — the agent never merges
          its own work.
        </p>

        {/* Hero: the one number this page leads with. */}
        <div className="command-card">
          <div className="hero">
            <div>
              <div className="kpi-label">Engineering time returned</div>
              <div className={`hero-value${hours ? '' : ' is-empty'}`}>
                {hours ? Math.round(hours) : '—'}
              </div>
            </div>
            <div className="hero-unit">hours</div>
            <div className="hero-note">
              across {merged} merged run{merged === 1 ? '' : 's'}, for {money(spend)} of model spend
            </div>
          </div>
          <Formula>
            <b>hours returned</b> = Σ estimated_hours of merged runs, falling back to
            story_points at 1&nbsp;pt ≈ 1&nbsp;h
            <br />
            {money(spend)} spent
            {perMerged != null && <> · <b>{money(perMerged)}</b> per merged run</>}
            {perHour != null && <> · <b>{money(perHour)}</b> per hour returned</>}
          </Formula>
        </div>

        <div className="kpis" style={{ marginTop: 16 }}>
          <Kpi
            label="Runs shipped"
            value={stats ? stats.merged : null}
            foot={stats ? `of ${stats.total_runs} dispatched` : undefined}
          />
          <Kpi
            label="Success rate"
            // null while nothing has finished — not 0%.
            value={stats?.success_rate == null ? null : `${Math.round(stats.success_rate)}%`}
            foot={stats ? `${stats.pr_open} still undecided, excluded` : undefined}
          />
          <Kpi
            label="Time to PR"
            value={stats?.avg_minutes_to_pr == null ? null : `${stats.avg_minutes_to_pr} min`}
            foot="dispatch → review"
          />
          <Kpi label="Total spend" value={money(spend)} foot="all time" />
          <Kpi
            label="Per merged run"
            value={perMerged == null ? null : money(perMerged)}
            foot="spend ÷ merged"
          />
        </div>

        <div className="dash-grid-2">
          <div className="command-card">
            <div className="command-card-title"><Cpu size={16} strokeWidth={2.25} /> Merged runs per week</div>
            <p className="card-sub">Work the agent completed that a human accepted.</p>
            <BarChart
              groups={points.map((p) => shortDate(p.date))}
              series={[{ name: 'Merged', values: points.map((p) => p.merged), color: 'var(--chart-good)' }]}
              valueFmt={(v) => String(v)}
              emptyMessage="Nothing merged in the last 12 weeks"
            />
          </div>

          <div className="command-card">
            <div className="command-card-title">Spend per week</div>
            {/* Two measures of different scale never share an axis — that is the
                single most misleading thing a dashboard can do. */}
            <p className="card-sub">
              Model cost in US dollars. Plotted separately from output on purpose: two measures on
              one axis invites a causal reading the data does not support.
            </p>
            <LineChart
              series={[{
                name: 'Spend',
                points: points.map((p) => ({ date: p.date, value: p.cost })),
                color: 'var(--chart-1)',
              }]}
              area
              valueFmt={money}
              emptyMessage="No spend recorded yet"
            />
          </div>
        </div>

        <div className="command-card" style={{ marginTop: 16 }}>
          <div className="command-card-title">Where runs end up</div>
          <p className="card-sub">
            Every dispatch, followed to its outcome. The gap between “PR opened” and “Merged” is the
            human approval gate doing its job.
          </p>
          <HBars rows={funnel} max={stats?.total_runs || 1} valueFmt={(v) => String(v)} />
        </div>

        <div className="dash-grid-2">
          <div className="command-card">
            <div className="command-card-title">Spend by stream</div>
            <p className="card-sub">Attributed through the task’s sprint to its stream.</p>
            {cost && cost.streams.length > 0 ? (
              <>
                <HBars
                  rows={cost.streams.map((s) => ({
                    name: s.stream_name,
                    value: s.cost,
                    color: 'var(--chart-1)',
                    note: `${s.runs} run${s.runs === 1 ? '' : 's'}, ${s.merged} merged`,
                  }))}
                  valueFmt={money}
                />
                {cost.unattributed_cost > 0 && (
                  <div className="chart-note">
                    {money(cost.unattributed_cost)} could not be attributed — those runs’ tasks are
                    not in a sprint, so there is no stream to charge.
                  </div>
                )}
              </>
            ) : (
              <EmptyState>No attributable spend yet</EmptyState>
            )}
          </div>

          <div className="command-card">
            <div className="command-card-title">
              <AlertTriangle size={16} strokeWidth={2.25} /> Read these two carefully
            </div>
            <div className="caveat">
              <b>Hours returned</b> is an estimate, not a measurement. It sums the estimate that was
              already on each task before the agent touched it — if those estimates were generous,
              so is this number.
            </div>
            <div className="caveat">
              <b>Success rate</b> is merged ÷ (merged + failed). Runs sitting in open PRs are
              excluded rather than counted as failures, so the rate is not depressed by work that
              simply has not been reviewed yet.
            </div>
          </div>
        </div>

        <div style={{ marginTop: 16 }}>
          <AutopilotCard />
        </div>
      </div>
    </>
  );
}
