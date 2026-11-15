import { useState } from 'react';
import { TrendingUp, TrendingDown, Minus, Check, X } from 'lucide-react';
import { Badge, type Tone } from '../../ui/Badge';
import { Button } from '../../ui/Button';
import { Modal } from '../../ui/Modal';
import { EmptyState } from '../../ui/EmptyState';
import { Sparkline } from '../../ui/Sparkline';
import { useStream, useApproveProposal, useRejectProposal } from '../../hooks/useApi';
import type {
  StreamStatus, StreamDirection, SprintConfidence, ConfidenceFactors, StreamProposal,
} from '../../types';

const STATUS_TONE: Record<StreamStatus, Tone> = {
  'On track': 'success',
  Ahead: 'blue',
  'At risk': 'orange',
  Behind: 'danger',
  'No data': 'neutral',
};

const DIRECTION = {
  improving: { Icon: TrendingUp, color: 'var(--success)' },
  declining: { Icon: TrendingDown, color: 'var(--danger)' },
  steady: { Icon: Minus, color: 'var(--ink-mute)' },
} as const;

const FACTOR_LABELS: { key: keyof ConfidenceFactors; label: string }[] = [
  { key: 'scope_remaining', label: 'Scope remaining' },
  { key: 'velocity_vs_plan', label: 'Velocity vs plan' },
  { key: 'open_blockers', label: 'Open blockers' },
  { key: 'untested_surface', label: 'Untested surface' },
];

// Score colour: confidence/factor health bands (higher = healthier).
const scoreColor = (v: number) => (v >= 75 ? 'var(--success)' : v >= 60 ? 'var(--orange)' : 'var(--danger)');

function DirectionChip({ direction }: { direction: StreamDirection }) {
  const { Icon, color } = DIRECTION[direction];
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 13, fontWeight: 600, color }}>
      <Icon size={16} strokeWidth={2.5} /> {direction}
    </span>
  );
}

function FactorBar({ label, value }: { label: string; value: number }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      <div style={{ width: 130, fontSize: 12, color: 'var(--ink-soft)' }}>{label}</div>
      <div style={{ flex: 1, height: 8, background: 'var(--surface-3)', borderRadius: 'var(--radius-pill)', overflow: 'hidden' }}>
        <div style={{ width: `${Math.max(0, Math.min(100, value))}%`, height: '100%', background: scoreColor(value) }} />
      </div>
      <div style={{ width: 34, textAlign: 'right', fontSize: 12, fontWeight: 600, color: 'var(--ink)' }}>{Math.round(value)}</div>
    </div>
  );
}

function ConfidenceCard({ sprint }: { sprint: SprintConfidence }) {
  const value = sprint.confidence_value;
  const trend = sprint.trend.map((t) => t.value);
  return (
    <div style={{ background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 'var(--radius-lg)', padding: 20, boxShadow: 'var(--shadow-xs)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink)' }}>{sprint.sprint_name}</div>
        <Badge tone={STATUS_TONE[sprint.status]}>{sprint.status}</Badge>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 24, marginBottom: 18 }}>
        <div style={{ minWidth: 96 }}>
          <div style={{ fontSize: 44, fontWeight: 800, lineHeight: 1, color: value == null ? 'var(--ink-mute)' : scoreColor(value) }}>
            {value == null ? '—' : value}
          </div>
          <div style={{ fontSize: 11, color: 'var(--ink-mute)', marginTop: 4, textTransform: 'uppercase', letterSpacing: 0.4 }}>
            Release confidence
          </div>
        </div>
        <div style={{ flex: 1, color: 'var(--accent)' }}>
          <Sparkline data={trend} min={0} max={100} width={220} height={56} />
          <div style={{ fontSize: 11, color: 'var(--ink-mute)', marginTop: 2 }}>
            {trend.length} day trend
          </div>
        </div>
      </div>

      {sprint.factors ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
          {FACTOR_LABELS.map(({ key, label }) => (
            <FactorBar key={key} label={label} value={sprint.factors![key]} />
          ))}
          <div style={{ fontSize: 11, color: 'var(--ink-mute)', marginTop: 2 }}>Each scored 0–100 — higher is healthier.</div>
        </div>
      ) : (
        <EmptyState>No confidence snapshot yet</EmptyState>
      )}
    </div>
  );
}

interface StreamViewProps {
  streamId: string;
}

export function StreamView({ streamId }: StreamViewProps) {
  const { data, isPending, error } = useStream(streamId);
  const approve = useApproveProposal();
  const reject = useRejectProposal();

  const [rejecting, setRejecting] = useState<string | null>(null);
  const [reason, setReason] = useState('');
  const busy = approve.isPending || reject.isPending;

  const closeReject = () => { setRejecting(null); setReason(''); };
  const confirmReject = () => {
    if (!rejecting) return;
    reject.mutate({ id: rejecting, reason });
    closeReject();
  };

  if (isPending) {
    return (
      <><header className="header"><h1 className="header-title">Stream</h1></header>
        <div className="content"><EmptyState>Loading stream…</EmptyState></div></>
    );
  }

  if (error || !data) {
    return (
      <><header className="header"><h1 className="header-title">Stream</h1></header>
        <div className="content"><EmptyState>{(error as Error)?.message || 'Stream not found'}</EmptyState></div></>
    );
  }

  return (
    <>
      <header className="header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <h1 className="header-title">{data.name}</h1>
          <Badge tone={STATUS_TONE[data.status]}>{data.status}</Badge>
          <DirectionChip direction={data.direction} />
        </div>
      </header>

      <div className="content">
        {data.description && (
          <p style={{ fontSize: 13, color: 'var(--ink-soft)', margin: '0 0 4px' }}>{data.description}</p>
        )}
        <div style={{ fontSize: 12, color: 'var(--ink-mute)', marginBottom: 24 }}>
          {data.owner_name ? `PM: ${data.owner_name}` : 'Unassigned'}
        </div>

        {/* Release confidence cards (precise numbers + factors + trend). */}
        <section style={{ marginBottom: 28 }}>
          <h2 style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink-mute)', textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 12 }}>
            Release confidence
          </h2>
          {data.sprints.length === 0 ? (
            <EmptyState>No active sprints in this stream</EmptyState>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: 14 }}>
              {data.sprints.map((s) => <ConfidenceCard key={s.sprint_id} sprint={s} />)}
            </div>
          )}
        </section>

        {/* Operational (project-scope) decision queue. */}
        <section>
          <h2 style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink-mute)', textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 12 }}>
            Decisions
          </h2>
          {data.proposals.length === 0 ? (
            <EmptyState>No operational proposals</EmptyState>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {data.proposals.map((p: StreamProposal) => (
                <div key={p.id} style={{ background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 'var(--radius-lg)', padding: 18, boxShadow: 'var(--shadow-xs)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink)', textTransform: 'capitalize' }}>
                      {p.type.replace(/_/g, ' ')}
                    </span>
                    {p.confidence && <Badge tone={p.confidence === 'high' ? 'success' : p.confidence === 'medium' ? 'orange' : 'danger'}>{p.confidence}</Badge>}
                  </div>
                  {p.reasoning && (
                    <p style={{ fontSize: 13, color: 'var(--ink-soft)', lineHeight: 1.6, margin: '0 0 14px' }}>{p.reasoning}</p>
                  )}
                  {p.state === 'pending_review' ? (
                    <div style={{ display: 'flex', gap: 10 }}>
                      <Button variant="success" disabled={busy} onClick={() => approve.mutate({ id: p.id })} icon={<Check size={15} strokeWidth={3} />}>Approve</Button>
                      <Button variant="danger" disabled={busy} onClick={() => setRejecting(p.id)} icon={<X size={15} strokeWidth={3} />}>Reject</Button>
                    </div>
                  ) : (
                    <Badge tone="neutral">{p.state.replace(/_/g, ' ')}</Badge>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>

        {rejecting && (
          <Modal
            title="Reject Proposal"
            onClose={closeReject}
            footer={
              <>
                <Button variant="secondary" onClick={closeReject}>Cancel</Button>
                <Button variant="danger" onClick={confirmReject} disabled={busy || !reason.trim()}>Reject</Button>
              </>
            }
          >
            <p style={{ fontSize: 13, color: 'var(--ink-soft)', marginBottom: 14 }}>Provide a reason for rejecting this proposal:</p>
            <textarea
              className="form-textarea"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Enter rejection reason…"
              style={{ minHeight: 110, resize: 'vertical' }}
            />
          </Modal>
        )}
      </div>
    </>
  );
}
