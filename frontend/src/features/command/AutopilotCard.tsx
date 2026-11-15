import { useEffect, useState } from 'react';
import { Bot, SkipForward } from 'lucide-react';
import { useAutopilot, useUpdateAutopilot } from '../../hooks/useApi';
import type { AutopilotMode, AutopilotUpdate } from '../../types';
import { EmptyState } from '../../ui/EmptyState';

const MODES: { value: AutopilotMode; label: string; desc: string }[] = [
  { value: 'off', label: 'Off', desc: 'The autopilot takes no action on its own.' },
  { value: 'propose', label: 'Propose', desc: 'Triages new tasks and queues dispatch proposals for your approval.' },
  { value: 'auto', label: 'Auto', desc: 'Triages and dispatches suitable tasks on its own, within the daily limit.' },
];

const COUNTERS: { key: 'triaged' | 'dispatched' | 'suggested' | 'skipped' | 'nudged' | 'escalated'; label: string }[] = [
  { key: 'triaged', label: 'Triaged' },
  { key: 'dispatched', label: 'Dispatched' },
  { key: 'suggested', label: 'Suggested' },
  { key: 'skipped', label: 'Skipped' },
  { key: 'nudged', label: 'Nudged' },
  { key: 'escalated', label: 'Escalated' },
];

/** The live autopilot dial: mode segmented control, dispatch budget,
 *  repository, plus today's activity counters and skip reasons. Every change
 *  PUTs immediately — the beat tick reads the new state on its next pass. */
export function AutopilotCard() {
  const { data, isPending, error: loadError } = useAutopilot();
  const update = useUpdateAutopilot();

  // Local drafts for the text/number inputs (committed on blur / Enter).
  // Re-seeded only when the server value actually changes, so the 15s poll
  // doesn't clobber in-progress typing.
  const [limit, setLimit] = useState('');
  const [repo, setRepo] = useState('');
  const [error, setError] = useState<string | null>(null);

  const serverLimit = data?.daily_limit;
  const serverRepo = data?.repository ?? '';
  useEffect(() => {
    if (serverLimit !== undefined) setLimit(String(serverLimit));
  }, [serverLimit]);
  useEffect(() => {
    setRepo(serverRepo);
  }, [serverRepo]);

  const save = (body: AutopilotUpdate) => {
    setError(null);
    update.mutateAsync(body).catch((e: any) => setError(e.message || 'Failed to update autopilot'));
  };

  const commitLimit = () => {
    if (!data) return;
    const n = Math.max(0, Math.min(50, Math.round(Number(limit))));
    if (limit.trim() === '' || !Number.isFinite(n)) { setLimit(String(data.daily_limit)); return; }
    setLimit(String(n));
    if (n !== data.daily_limit) save({ daily_limit: n });
  };

  const commitRepo = () => {
    if (!data) return;
    const value = repo.trim();
    if (value !== (data.repository ?? '')) save({ repository: value || null });
  };

  const mode = data?.mode;
  const modeDesc = MODES.find((m) => m.value === mode)?.desc;

  return (
    <div className="command-card">
      <div className="command-card-title">
        <Bot size={16} strokeWidth={2.25} /> Delivery Autopilot
        {update.isPending && <span style={{ marginLeft: 'auto', fontSize: 11, fontWeight: 500, color: 'var(--ink-mute)' }}>Saving…</span>}
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: 12 }}>{error}</div>}

      {isPending ? (
        <EmptyState>Loading autopilot…</EmptyState>
      ) : loadError || !data ? (
        <EmptyState>{(loadError as Error | null)?.message || 'Autopilot unavailable'}</EmptyState>
      ) : (
        <>
          <div className="ap-seg" role="radiogroup" aria-label="Autopilot mode">
            {MODES.map((m) => (
              <button
                key={m.value}
                type="button"
                role="radio"
                aria-checked={mode === m.value}
                className={`ap-chip ${mode === m.value ? 'selected' : ''}`}
                disabled={update.isPending}
                onClick={() => { if (m.value !== mode) save({ mode: m.value }); }}
              >
                {m.label}
              </button>
            ))}
          </div>
          {modeDesc && <p className="ap-mode-desc">{modeDesc}</p>}

          <div className="ap-inputs">
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">Daily limit</label>
              <input
                className="form-input"
                type="number"
                min={0}
                max={50}
                value={limit}
                onChange={(e) => setLimit(e.target.value)}
                onBlur={commitLimit}
                onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); }}
              />
            </div>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">Repository</label>
              <input
                className="form-input"
                value={repo}
                onChange={(e) => setRepo(e.target.value)}
                onBlur={commitRepo}
                onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); }}
                placeholder="Default (configured repo)"
              />
            </div>
          </div>

          <div className="ap-counters">
            {COUNTERS.map(({ key, label }) => (
              <div key={key} className="ap-counter">
                <div className="ap-counter-value">{data.today[key]}</div>
                <div className="ap-counter-label">{label}</div>
              </div>
            ))}
          </div>
          <div className="ap-budget">
            {data.budget_remaining} of {data.daily_limit} auto-dispatches left today
          </div>

          {data.today.skips.length > 0 && (
            <div className="ap-skips">
              <div className="ap-skips-title">
                <SkipForward size={13} strokeWidth={2.5} /> Skipped today
              </div>
              {data.today.skips.map((s) => (
                <div key={s.task_id} className="ap-skip">
                  <strong>{s.title}</strong> — {s.reason}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
