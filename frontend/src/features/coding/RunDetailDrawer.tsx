import { useEffect, useRef } from 'react';
import {
  ArrowRight, Bot, Check, FilePen, Info, RotateCcw, Search, Terminal, X,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useRunEvents, useDispatchAgent } from '../../hooks/useApi';
import type { AgentRun } from '../../types';
import { AgentBadge } from '../../ui/AgentBadge';
import { Button } from '../../ui/Button';
import { TERMINAL_STATUSES } from './runStatus';

interface RunDetailDrawerProps {
  run: AgentRun;
  taskTitle?: string;
  onClose: () => void;
}

/** Right-side overlay drawer showing one coding-agent run: pipeline timeline,
 *  live event feed, and PR/retry actions. Stays live while the runs list polls. */
export function RunDetailDrawer({ run, taskTitle, onClose }: RunDetailDrawerProps) {
  const dispatchAgent = useDispatchAgent();
  const retryable = run.status === 'failed' || run.status === 'ci_failed';

  return (
    <div className="run-drawer-overlay" onClick={onClose}>
      <aside className="run-drawer" onClick={(e) => e.stopPropagation()} aria-label="Agent run detail">
        <div className="run-drawer-header">
          <span className="run-drawer-mark" aria-hidden="true">🤖</span>
          <span className="run-drawer-title" title={taskTitle}>{taskTitle || 'Agent run'}</span>
          <AgentBadge status={run.status} />
          <button className="modal-close" onClick={onClose} aria-label="Close run detail">
            <X size={16} strokeWidth={2.5} />
          </button>
        </div>

        <div className="run-drawer-body">
          <div className="run-drawer-meta">
            <div>
              <div className="run-drawer-meta-label">Repository</div>
              <div className="run-drawer-meta-value mono">{run.repository || '—'}</div>
            </div>
            <div>
              <div className="run-drawer-meta-label">Branch</div>
              <div className="run-drawer-meta-value mono">{run.branch_name || '—'}</div>
            </div>
            <div>
              <div className="run-drawer-meta-label">Iteration</div>
              <div className="run-drawer-meta-value">{run.iteration}</div>
            </div>
            {run.cost_estimate > 0 && (
              <div>
                <div className="run-drawer-meta-label">Cost</div>
                <div className="run-drawer-meta-value">${run.cost_estimate.toFixed(2)}</div>
              </div>
            )}
          </div>

          <RunTimeline status={run.status} />

          {run.error && <div className="alert alert-error">{run.error}</div>}

          <RunEventFeed run={run} />
        </div>

        {(run.pr_url || retryable) && (
          <div className="run-drawer-footer">
            {retryable && (
              <Button
                variant="secondary"
                icon={<RotateCcw size={15} strokeWidth={2.5} />}
                disabled={dispatchAgent.isPending}
                onClick={() => dispatchAgent.mutate({ taskId: run.task_id, repository: run.repository })}
              >
                {dispatchAgent.isPending ? 'Retrying…' : 'Retry'}
              </Button>
            )}
            {run.pr_url && (
              <a className="btn btn-primary" href={run.pr_url} target="_blank" rel="noreferrer">
                Open PR ↗
              </a>
            )}
          </div>
        )}
      </aside>
    </div>
  );
}

// ---- Pipeline timeline (Dispatched → … → Merged) ----

const STEP_LABELS = ['Dispatched', 'Groomed', 'Coding', 'CI', 'PR open', 'Merged'];

// Where each status sits on the pipeline; `failed` paints that step in danger,
// `done` marks the step itself as completed (end of the happy path).
const STATUS_STEP: Record<string, { idx: number; failed?: boolean; done?: boolean }> = {
  dispatched: { idx: 0 },
  groomed: { idx: 1 },
  running: { idx: 2 },
  ci_pending: { idx: 3 },
  ci_failed: { idx: 3, failed: true },
  pr_open: { idx: 4 },
  merged: { idx: 5, done: true },
  failed: { idx: 2, failed: true },
};

type StepState = 'done' | 'current' | 'failed' | 'todo';

function RunTimeline({ status }: { status: string }) {
  // Human-only tasks never enter the pipeline — a note instead of a dead timeline.
  if (status === 'skipped_human_only') {
    return (
      <div className="run-drawer-note">
        <Info size={15} strokeWidth={2.25} />
        <span>The agent groomed this task as <strong>human-only</strong> and skipped it — assign it to a team member.</span>
      </div>
    );
  }

  const pos = STATUS_STEP[status] ?? { idx: 0 };
  const states: StepState[] = STEP_LABELS.map((_, i) => {
    if (i < pos.idx) return 'done';
    if (i === pos.idx) return pos.failed ? 'failed' : pos.done ? 'done' : 'current';
    return 'todo';
  });

  return (
    <ol className="run-steps" aria-label="Run pipeline">
      {STEP_LABELS.map((label, i) => (
        <li key={label} className={`run-step ${states[i]}`}>
          <span className="run-step-node">
            {states[i] === 'done' && <Check size={12} strokeWidth={3} />}
            {states[i] === 'failed' && <X size={12} strokeWidth={3} />}
          </span>
          <span className="run-step-label">{label}</span>
        </li>
      ))}
    </ol>
  );
}

// ---- Live event feed ----

const KIND_ICONS: Record<string, LucideIcon> = {
  lifecycle: ArrowRight,
  assistant: Bot,
  inspect: Search,
  file_edit: FilePen,
  command: Terminal,
  result: Check,
  error: X,
};

const eventTime = (iso: string) =>
  new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

function RunEventFeed({ run }: { run: AgentRun }) {
  const { data } = useRunEvents(run.id);
  const events = data?.events ?? [];
  const isLive = !TERMINAL_STATUSES.has(run.status);
  const listRef = useRef<HTMLDivElement>(null);
  // Whether the user is pinned to the bottom — measured in onScroll (BEFORE
  // the DOM grows; measuring inside the effect would see the new, taller
  // scrollHeight and wrongly unpin a following user). Ref, not state: no
  // re-render needed.
  const pinnedRef = useRef(true);

  // Keep the newest event in view as the feed grows — unless the user
  // scrolled up to read history.
  useEffect(() => {
    const el = listRef.current;
    if (el && pinnedRef.current) el.scrollTop = el.scrollHeight;
  }, [events.length]);

  return (
    <div className="run-feed">
      <div className="run-feed-header">
        <span className="run-feed-title">
          Agent activity
          {isLive && (
            <span className="live-indicator">
              <span className="live-dot" />
              Live
            </span>
          )}
        </span>
        <span className="run-feed-count">{events.length} {events.length === 1 ? 'event' : 'events'}</span>
      </div>
      <div
        className="run-feed-list"
        ref={listRef}
        onScroll={(e) => {
          const el = e.currentTarget;
          pinnedRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
        }}
      >
        {events.length === 0 ? (
          <div className="run-feed-empty">Waiting for agent events…</div>
        ) : (
          events.map((e) => {
            const Icon = KIND_ICONS[e.kind] ?? ArrowRight;
            return (
              <div key={e.seq} className={`run-event ${e.kind}`}>
                <span className="run-event-icon"><Icon size={13} strokeWidth={2.5} /></span>
                <span className="run-event-msg">{e.message}</span>
                <span className="run-event-time">{eventTime(e.created_at)}</span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
