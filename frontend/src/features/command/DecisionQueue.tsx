import { useState, type ReactNode } from 'react';
import {
  AlertTriangle, Bot, Check, ChevronDown, ClipboardCheck, ExternalLink,
  GitMerge, GitPullRequest, X, Zap,
} from 'lucide-react';
import {
  useApproveProposal, useDecisions, useMergeCodingRun, useRejectProposal,
} from '../../hooks/useApi';
import type { DecisionItem } from '../../types';
import { Badge, type Tone } from '../../ui/Badge';
import { Button } from '../../ui/Button';
import { EmptyState } from '../../ui/EmptyState';
import { Modal } from '../../ui/Modal';
import { relTime } from '../coding/runStatus';

const SCOPE_TONE: Record<string, Tone> = {
  portfolio: 'purple',
  stream: 'orange',
  project: 'neutral',
};

// Plain-language framing per proposal type: what the item IS and what
// approving actually does — the raw type slugs read as jargon to an exec.
const TYPE_META: Record<string, { label: string; approveHint: string; approveLabel?: string }> = {
  coding_pr: {
    label: 'Code review',
    approveHint: 'Approving signs off on the AI’s pull request — merging stays a separate click.',
    approveLabel: 'Approve PR',
  },
  autopilot_dispatch: {
    label: 'Agent work request',
    approveHint: 'Approving hands this task to the coding agent — it starts on the next autopilot tick (within ~5 minutes).',
    approveLabel: 'Approve & Dispatch',
  },
  stale_blocker: {
    label: 'Stuck work',
    approveHint: 'Approving acknowledges the blocker so it’s tracked for action; declining dismisses it.',
    approveLabel: 'Acknowledge',
  },
  cross_stream_dependency: {
    label: 'Cross-team dependency',
    approveHint: 'Approving endorses the proposed cross-team plan; the stream owners follow through.',
  },
  release_slip: {
    label: 'Release risk',
    approveHint: 'Approving accepts the agent’s recommendation on the release plan.',
  },
  task_rebalance: {
    label: 'Reassignment suggestion',
    approveHint: 'Approving endorses the reassignment; the team applies it.',
  },
  blocker_resolution: {
    label: 'Unblock suggestion',
    approveHint: 'Approving endorses the proposed way to unblock this work.',
  },
  scope_cut: {
    label: 'Scope change',
    approveHint: 'Approving accepts the proposed scope reduction.',
  },
  standup: {
    label: 'Standup summary',
    approveHint: 'Approving marks the standup analysis as reviewed.',
  },
  sprint_planning: {
    label: 'Sprint plan',
    approveHint: 'Approving accepts the proposed sprint composition.',
  },
};

const DEFAULT_HINT = 'Approving records your sign-off; the team follows through.';

const typeLabel = (t: string) =>
  TYPE_META[t]?.label ?? t.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());

function iconOf(d: DecisionItem) {
  if (d.type === 'coding_pr') return GitPullRequest;
  if (d.type === 'autopilot_dispatch') return Bot;
  if (d.escalated) return AlertTriangle;
  return ClipboardCheck;
}

type SectionKey = 'escalations' | 'merge' | 'agent' | 'recommendations';

const SECTIONS: { key: SectionKey; title: string; sub: string }[] = [
  { key: 'escalations', title: 'Escalations', sub: 'Raised above the team — these genuinely need an executive call.' },
  { key: 'merge', title: 'Ready to merge', sub: 'AI pull requests you already approved — one click lands them.' },
  { key: 'agent', title: 'Agent work requests', sub: 'Tasks the autopilot found suitable and wants to build.' },
  { key: 'recommendations', title: 'Team recommendations', sub: 'Operational suggestions from the delivery agents — approve to endorse.' },
];

function sectionOf(d: DecisionItem): SectionKey {
  if (d.type === 'coding_pr' && d.state === 'approved' && d.run_status === 'pr_open') return 'merge';
  if (d.escalated) return 'escalations';
  if (d.type === 'autopilot_dispatch') return 'agent';
  return 'recommendations';
}

const RECOMMENDATIONS_PREVIEW = 4;

/** The Command Center's unified decision queue, grouped by what kind of call
 *  each item is. Rows expand for full context; every action states its
 *  consequence. Decisions ARE proposals — the existing approve/reject
 *  workflow drives everything, nothing bypasses it. */
export function DecisionQueue() {
  const { data: decisions = [], isPending, error: loadError } = useDecisions();

  const approve = useApproveProposal();
  const reject = useRejectProposal();
  const merge = useMergeCodingRun();

  const [declining, setDeclining] = useState<DecisionItem | null>(null);
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showAllRecs, setShowAllRecs] = useState(false);

  const act = (p: Promise<unknown>) => {
    setError(null);
    p.catch((e: any) => setError(e.message || 'Action failed'));
  };

  const closeDecline = () => { setDeclining(null); setReason(''); };
  const confirmDecline = () => {
    if (!declining || !reason.trim()) return;
    act(reject.mutateAsync({ id: declining.id, reason: reason.trim() }));
    closeDecline();
  };

  const renderRow = (d: DecisionItem): ReactNode => {
    const Icon = iconOf(d);
    const meta = TYPE_META[d.type];
    const canApprove = d.state === 'pending_review';
    const canMerge =
      d.type === 'coding_pr' && d.state === 'approved'
      && d.run_status === 'pr_open' && !!d.run_id;
    const approving = approve.isPending && approve.variables?.id === d.id;
    const merging = merge.isPending && merge.variables === d.run_id;
    const expanded = expandedId === d.id;
    return (
      <div key={d.id} className={`pr-row dq-row ${expanded ? 'expanded' : ''}`} onClick={() => setExpandedId(expanded ? null : d.id)}>
        <div className="dq-row-top">
          <span className={`pr-row-ico ${d.escalated ? 'err' : ''}`}>
            <Icon size={16} strokeWidth={2.25} />
          </span>
          <div className="pr-row-main">
            <div className={`pr-row-title ${expanded ? 'dq-title-full' : ''}`}>
              {d.summary || typeLabel(d.type)}
            </div>
            <div className="pr-row-meta">
              <span>{typeLabel(d.type)}</span>
              {d.created_by_agent && <span>by {d.created_by_agent}</span>}
              {d.repository && <span className="pr-mono">{d.repository}</span>}
              <span>{relTime(d.created_at)}</span>
              {d.pr_url && (
                <a
                  className="pr-link"
                  href={d.pr_url}
                  target="_blank"
                  rel="noreferrer"
                  onClick={(e) => e.stopPropagation()}
                >
                  PR <ExternalLink size={11} strokeWidth={2.5} />
                </a>
              )}
            </div>
          </div>
          <Badge tone={SCOPE_TONE[d.scope] ?? 'neutral'}>{d.scope}</Badge>
          {d.confidence && (
            <Badge tone={d.confidence === 'high' ? 'success' : d.confidence === 'medium' ? 'orange' : 'danger'}>
              {d.confidence} confidence
            </Badge>
          )}
          <div className="pr-row-actions" onClick={(e) => e.stopPropagation()}>
            {canApprove && (
              <>
                <Button
                  variant="primary"
                  disabled={approve.isPending}
                  onClick={() => act(approve.mutateAsync({ id: d.id }))}
                  icon={d.type === 'autopilot_dispatch'
                    ? <Zap size={14} strokeWidth={2.5} />
                    : <Check size={14} strokeWidth={2.5} />}
                >
                  {approving ? 'Approving…' : meta?.approveLabel ?? 'Approve'}
                </Button>
                <Button
                  variant="secondary"
                  disabled={reject.isPending}
                  onClick={() => { setDeclining(d); setReason(''); }}
                  icon={<X size={14} strokeWidth={2.5} />}
                >
                  Decline
                </Button>
              </>
            )}
            {canMerge && (
              <Button
                variant="primary"
                className="btn-merge"
                disabled={merging}
                onClick={() => act(merge.mutateAsync(d.run_id as string))}
                icon={<GitMerge size={14} strokeWidth={2.5} />}
              >
                {merging ? 'Merging…' : 'Merge PR'}
              </Button>
            )}
          </div>
          <ChevronDown size={15} strokeWidth={2.5} className="dq-chevron" />
        </div>

        {expanded && (
          <div className="dq-detail" onClick={(e) => e.stopPropagation()}>
            {d.task_title && (
              <div className="dq-detail-line"><span className="dq-detail-label">Task</span>{d.task_title}</div>
            )}
            {d.reasoning && (
              <div className="dq-detail-line"><span className="dq-detail-label">Why</span>{d.reasoning}</div>
            )}
            <div className="dq-hint">
              {canMerge
                ? 'Merging completes the pull request in Azure DevOps (squash) and moves the task to Done.'
                : meta?.approveHint ?? DEFAULT_HINT}
            </div>
          </div>
        )}
      </div>
    );
  };

  const grouped = new Map<SectionKey, DecisionItem[]>();
  for (const d of decisions) {
    const key = sectionOf(d);
    grouped.set(key, [...(grouped.get(key) ?? []), d]);
  }

  return (
    <>
      {error && <div className="alert alert-error" style={{ marginBottom: 14 }}>{error}</div>}

      {isPending ? (
        <EmptyState>Loading decisions…</EmptyState>
      ) : loadError ? (
        <EmptyState>{(loadError as Error).message}</EmptyState>
      ) : decisions.length === 0 ? (
        <EmptyState>Nothing needs your decision right now.</EmptyState>
      ) : (
        SECTIONS.map(({ key, title, sub }) => {
          const items = grouped.get(key) ?? [];
          if (items.length === 0) return null;
          const collapsed = key === 'recommendations' && !showAllRecs && items.length > RECOMMENDATIONS_PREVIEW;
          const visible = collapsed ? items.slice(0, RECOMMENDATIONS_PREVIEW) : items;
          return (
            <div key={key} className={`dq-section ${key === 'escalations' ? 'urgent' : ''}`}>
              <div className="dq-section-head">
                <span className="dq-section-title">{title}</span>
                <span className="dq-section-count">{items.length}</span>
                <span className="dq-section-sub">{sub}</span>
              </div>
              <div className="pr-rows">{visible.map(renderRow)}</div>
              {collapsed && (
                <button className="dq-show-all" onClick={() => setShowAllRecs(true)}>
                  Show all {items.length} recommendations <ChevronDown size={13} strokeWidth={2.5} />
                </button>
              )}
            </div>
          );
        })
      )}

      {declining && (
        <Modal
          title="Decline Decision"
          onClose={closeDecline}
          width={480}
          footer={
            <>
              <Button variant="secondary" onClick={closeDecline}>Cancel</Button>
              <Button variant="danger" disabled={!reason.trim()} onClick={confirmDecline}>
                Decline
              </Button>
            </>
          }
        >
          <p className="form-modal-sub">
            Provide a reason for declining “{declining.summary || typeLabel(declining.type)}”.
          </p>
          <textarea
            className="form-textarea"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Enter reason…"
            autoFocus
            style={{ minHeight: 110, resize: 'vertical' }}
          />
        </Modal>
      )}
    </>
  );
}
