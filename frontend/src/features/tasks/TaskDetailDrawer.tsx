import type { ReactNode } from 'react';
import { Bot, ExternalLink, X } from 'lucide-react';
import { useFeatures, useSprints, useTeamMembers } from '../../hooks/useApi';
import type { AgentRun, Task } from '../../types';
import { AgentBadge } from '../../ui/AgentBadge';
import { Badge, type Tone } from '../../ui/Badge';
import { Button } from '../../ui/Button';
import { relTime } from '../coding/runStatus';

const STATUS_LABEL: Record<Task['status'], string> = {
  backlog: 'Backlog', todo: 'To Do', in_progress: 'In Progress', review: 'Review', done: 'Done',
};
const STATUS_TONE: Record<Task['status'], Tone> = {
  backlog: 'neutral', todo: 'neutral', in_progress: 'blue', review: 'orange', done: 'success',
};
const PRIORITY_TONE: Record<Task['priority'], Tone> = {
  low: 'neutral', medium: 'orange', high: 'orange', critical: 'danger',
};

interface TaskDetailDrawerProps {
  task: Task;
  run?: AgentRun;
  onViewRun?: (runId: string) => void;
  onClose: () => void;
}

/** Right-side drawer with the full detail of ANY task (not just agent ones).
 *  When the task has a coding-agent run, an Agent section links into the
 *  live run drawer. Reuses the run drawer's shell styling. */
export function TaskDetailDrawer({ task, run, onViewRun, onClose }: TaskDetailDrawerProps) {
  const { data: members = [] } = useTeamMembers();
  const { data: sprints = [] } = useSprints();
  const { data: features = [] } = useFeatures();

  const assignee = task.assignee_id ? members.find((m) => m.id === task.assignee_id)?.name : null;
  const sprint = task.sprint_id ? sprints.find((s) => s.id === task.sprint_id)?.name : null;
  const feature = task.feature_id ? features.find((f) => f.id === task.feature_id)?.name : null;

  const meta: { label: string; value: ReactNode }[] = [
    { label: 'Status', value: <Badge tone={STATUS_TONE[task.status]}>{STATUS_LABEL[task.status]}</Badge> },
    { label: 'Priority', value: <Badge tone={PRIORITY_TONE[task.priority]}>{task.priority}</Badge> },
    { label: 'Assignee', value: run ? '🤖 AI Agent' : assignee ?? '—' },
    { label: 'Sprint', value: sprint ?? '—' },
    { label: 'Feature', value: feature ?? '—' },
    { label: 'Technology', value: task.technology ?? '—' },
    { label: 'Story points', value: task.story_points ?? '—' },
    { label: 'Estimated', value: task.estimated_hours != null ? `${task.estimated_hours}h` : '—' },
    { label: 'Created', value: relTime(task.created_at) },
  ];
  if (task.external_id) {
    meta.push({ label: 'External ID', value: <span className="pr-mono">{task.external_id}</span> });
  }

  return (
    <div className="run-drawer-overlay" onClick={onClose}>
      <aside className="run-drawer" onClick={(e) => e.stopPropagation()} aria-label="Task detail">
        <div className="run-drawer-header">
          <span className="run-drawer-title" title={task.title}>{task.title}</span>
          <button className="modal-close" onClick={onClose} aria-label="Close task detail">
            <X size={16} strokeWidth={2.5} />
          </button>
        </div>

        <div className="run-drawer-body">
          <div className="task-meta-grid">
            {meta.map(({ label, value }) => (
              <div key={label} className="task-meta-item">
                <span className="task-meta-label">{label}</span>
                <span className="task-meta-value">{value}</span>
              </div>
            ))}
          </div>

          <div className="task-desc">
            <div className="task-desc-title">Description</div>
            {task.description?.trim() ? (
              <p className="task-desc-body">{task.description}</p>
            ) : (
              <p className="task-desc-body muted">No description.</p>
            )}
          </div>

          {task.acceptance_criteria?.trim() && (
            <div className="task-desc">
              <div className="task-desc-title">Acceptance criteria</div>
              <p className="task-desc-body" style={{ whiteSpace: 'pre-wrap' }}>{task.acceptance_criteria}</p>
            </div>
          )}

          {run && (
            <div className="task-agent-card">
              <div className="task-agent-head">
                <span className="task-agent-mark"><Bot size={15} strokeWidth={2.25} /></span>
                <span className="task-agent-title">Coding agent</span>
                <AgentBadge status={run.status} />
              </div>
              <div className="task-agent-meta">
                {run.repository && <span className="pr-mono">{run.repository}</span>}
                {run.branch_name && <span className="pr-mono">{run.branch_name}</span>}
                {run.pr_url && (
                  <a className="pr-link" href={run.pr_url} target="_blank" rel="noreferrer">
                    Pull request <ExternalLink size={11} strokeWidth={2.5} />
                  </a>
                )}
              </div>
              {onViewRun && (
                <Button variant="secondary" onClick={() => onViewRun(run.id)}>
                  View live run →
                </Button>
              )}
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}
