import { useMemo, useState } from 'react';
import {
  AlertTriangle, Bot, Check, ExternalLink, GitMerge, GitPullRequest,
  MessageSquare, RefreshCw, RotateCcw,
} from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import {
  codingKeys, proposalKeys, useApproveProposal, useCodingRuns, useDispatchAgent,
  useMergeCodingRun, useProposals, useReviseCodingRun, useTasks,
} from '../../hooks/useApi';
import type { AgentRun, Proposal } from '../../types';
import { AgentBadge } from '../../ui/AgentBadge';
import { Badge } from '../../ui/Badge';
import { Button } from '../../ui/Button';
import { EmptyState } from '../../ui/EmptyState';
import { Modal } from '../../ui/Modal';
import { RunDetailDrawer } from '../coding/RunDetailDrawer';
import { isActive, relTime } from '../coding/runStatus';
import { useAgentActivityOptional } from '../../notifications/AgentActivityContext';

type Tab = 'all' | 'inflight' | 'open' | 'merged' | 'failed';

const TAB_LABEL: Record<Tab, string> = {
  all: 'All', inflight: 'In flight', open: 'Open', merged: 'Merged', failed: 'Failed',
};

const IN_FLIGHT = new Set(['dispatched', 'groomed', 'running', 'ci_pending']);
const FAILED = new Set(['failed', 'ci_failed']);

function tabOf(run: AgentRun): Tab {
  if (IN_FLIGHT.has(run.status)) return 'inflight';
  if (run.status === 'pr_open') return 'open';
  if (run.status === 'merged') return 'merged';
  if (FAILED.has(run.status)) return 'failed';
  return 'all'; // skipped_human_only and friends only show under All
}

/** The agent hub: every coding run with its PR, live state, and the full
 *  review flow (approve → merge, request changes, retry) inline. */
export function PrsPage() {
  const qc = useQueryClient();
  const { data: runs = [], isLoading } = useCodingRuns();
  const { data: proposals = [] } = useProposals();
  const { data: tasks = [] } = useTasks();
  const activity = useAgentActivityOptional();

  const approve = useApproveProposal();
  const merge = useMergeCodingRun();
  const revise = useReviseCodingRun();
  const retry = useDispatchAgent();

  const [tab, setTab] = useState<Tab>('all');
  const [openRunId, setOpenRunId] = useState<string | null>(null);
  const [reviseRunId, setReviseRunId] = useState<string | null>(null);
  const [comment, setComment] = useState('');
  const [error, setError] = useState<string | null>(null);

  const proposalById = useMemo(
    () => new Map<string, Proposal>(proposals.map((p) => [p.id, p])),
    [proposals],
  );
  const titleOf = (taskId: string) => tasks.find((t) => t.id === taskId)?.title ?? taskId.slice(0, 8);

  const sorted = useMemo(
    () => [...runs].sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? '')),
    [runs],
  );
  const counts = useMemo(() => {
    const c: Record<Tab, number> = { all: sorted.length, inflight: 0, open: 0, merged: 0, failed: 0 };
    for (const r of sorted) {
      const t = tabOf(r);
      if (t !== 'all') c[t] += 1;
    }
    return c;
  }, [sorted]);
  const visible = tab === 'all' ? sorted : sorted.filter((r) => tabOf(r) === tab);

  const liveRun = openRunId ? runs.find((r) => r.id === openRunId) : undefined;
  const activeCount = activity?.activeRunCount ?? runs.filter((r) => isActive(r.status)).length;

  const act = (p: Promise<unknown>) => {
    setError(null);
    p.catch((e: any) => setError(e.message || 'Action failed'));
  };

  const submitRevise = () => {
    if (!reviseRunId || !comment.trim()) return;
    act(revise.mutateAsync({ runId: reviseRunId, comment: comment.trim() }));
    setReviseRunId(null);
    setComment('');
  };

  return (
    <>
      <header className="header">
        <h1 className="header-title">Pull Requests</h1>
        <div className="header-actions">
          {activeCount > 0 && (
            <span className="live-indicator">
              <span className="live-dot" />
              {activeCount} run{activeCount === 1 ? '' : 's'} in flight
            </span>
          )}
          <Button
            variant="ghost"
            onClick={() => {
              qc.invalidateQueries({ queryKey: codingKeys.all });
              qc.invalidateQueries({ queryKey: proposalKeys.all });
            }}
            icon={<RefreshCw size={15} strokeWidth={2.5} />}
          >
            Refresh
          </Button>
        </div>
      </header>

      <div className="content">
        <div className="header-tabs pr-tabs">
          {(Object.keys(TAB_LABEL) as Tab[]).map((t) => (
            <button
              key={t}
              className={`header-tab ${tab === t ? 'active' : ''}`}
              onClick={() => setTab(t)}
            >
              {TAB_LABEL[t]} <span className="pr-tab-count">{counts[t]}</span>
            </button>
          ))}
        </div>

        {error && <div className="alert alert-error" style={{ marginBottom: 14 }}>{error}</div>}

        {isLoading ? null : visible.length === 0 ? (
          <EmptyState>
            {tab === 'all'
              ? 'No agent runs yet — assign a task to the 🤖 AI Agent from the board.'
              : `No ${TAB_LABEL[tab].toLowerCase()} runs right now.`}
          </EmptyState>
        ) : (
          <div className="pr-rows">
            {visible.map((run) => {
              const proposal = run.proposal_id ? proposalById.get(run.proposal_id) : undefined;
              const canApprove = proposal?.state === 'pending_review';
              const canMerge = run.status === 'pr_open' && proposal?.state === 'approved';
              const canRevise = run.status === 'pr_open';
              const canRetry = FAILED.has(run.status);
              const merging = merge.isPending && merge.variables === run.id;
              const inFlight = IN_FLIGHT.has(run.status);
              return (
                <div key={run.id} className="pr-row" onClick={() => setOpenRunId(run.id)}>
                  <span className={`pr-row-ico ${run.status === 'merged' ? 'ok' : FAILED.has(run.status) ? 'err' : ''}`}>
                    {inFlight ? <Bot size={16} strokeWidth={2.25} />
                      : FAILED.has(run.status) ? <AlertTriangle size={16} strokeWidth={2.25} />
                      : run.status === 'merged' ? <GitMerge size={16} strokeWidth={2.25} />
                      : <GitPullRequest size={16} strokeWidth={2.25} />}
                  </span>
                  <div className="pr-row-main">
                    <div className="pr-row-title">{titleOf(run.task_id)}</div>
                    <div className="pr-row-meta">
                      {run.repository && <span className="pr-mono">{run.repository}</span>}
                      {run.branch_name && <span className="pr-mono">{run.branch_name}</span>}
                      {run.iteration > 0 && <span>iteration {run.iteration}</span>}
                      <span>{relTime(run.updated_at || run.created_at)}</span>
                      {run.pr_url && (
                        <a
                          className="pr-link"
                          href={run.pr_url}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}
                        >
                          PR {run.pr_id ? `#${run.pr_id}` : ''} <ExternalLink size={11} strokeWidth={2.5} />
                        </a>
                      )}
                    </div>
                  </div>
                  <AgentBadge status={run.status} />
                  {proposal && (run.status === 'pr_open' || run.status === 'merged') && (
                    <Badge tone={proposal.state === 'approved' ? 'success' : 'orange'}>
                      {proposal.state === 'approved' ? 'Approved' : 'Pending review'}
                    </Badge>
                  )}
                  <div className="pr-row-actions" onClick={(e) => e.stopPropagation()}>
                    {canRevise && (
                      <Button
                        variant="secondary"
                        onClick={() => { setReviseRunId(run.id); setComment(''); }}
                        icon={<MessageSquare size={14} strokeWidth={2.5} />}
                      >
                        Request changes
                      </Button>
                    )}
                    {canApprove && proposal && (
                      <Button
                        variant="primary"
                        disabled={approve.isPending}
                        onClick={() => act(approve.mutateAsync({ id: proposal.id }))}
                        icon={<Check size={14} strokeWidth={2.5} />}
                      >
                        Approve
                      </Button>
                    )}
                    {canMerge && (
                      <Button
                        variant="primary"
                        className="btn-merge"
                        disabled={merging}
                        onClick={() => act(merge.mutateAsync(run.id))}
                        icon={<GitMerge size={14} strokeWidth={2.5} />}
                      >
                        {merging ? 'Merging…' : 'Merge PR'}
                      </Button>
                    )}
                    {canRetry && (
                      <Button
                        variant="secondary"
                        disabled={retry.isPending}
                        onClick={() => act(retry.mutateAsync({ taskId: run.task_id, repository: run.repository }))}
                        icon={<RotateCcw size={14} strokeWidth={2.5} />}
                      >
                        Retry
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {liveRun && (
        <RunDetailDrawer
          run={liveRun}
          taskTitle={titleOf(liveRun.task_id)}
          onClose={() => setOpenRunId(null)}
        />
      )}

      {reviseRunId && (
        <Modal
          title="Request changes"
          onClose={() => setReviseRunId(null)}
          width={480}
          footer={
            <>
              <Button variant="secondary" onClick={() => setReviseRunId(null)}>Cancel</Button>
              <Button variant="primary" disabled={!comment.trim()} onClick={submitRevise}>
                Send to agent
              </Button>
            </>
          }
        >
          <p className="form-modal-sub">
            The agent revises on the same branch — the pull request updates in place.
          </p>
          <textarea
            className="form-textarea"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="e.g. also cover the empty-list case with a test…"
            autoFocus
          />
        </Modal>
      )}
    </>
  );
}
