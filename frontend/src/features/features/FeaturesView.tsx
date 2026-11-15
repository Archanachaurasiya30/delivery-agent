import { useState } from 'react';
import { Plus } from 'lucide-react';
import { useFeatures, useTasks, useStreams, useTeamMembers, useCodingRuns } from '../../hooks/useApi';
import { Button } from '../../ui/Button';
import { Badge, type Tone } from '../../ui/Badge';
import { Spinner } from '../../ui/Spinner';
import { EmptyState } from '../../ui/EmptyState';
import { AgentBadge } from '../../ui/AgentBadge';
import { RunDetailDrawer } from '../coding/RunDetailDrawer';
import { TaskDetailDrawer } from '../tasks/TaskDetailDrawer';
import { TaskFormModal } from '../board/TaskFormModal';
import type { Feature, Task } from '../../types';

const STATUS_TONE: Record<string, Tone> = {
  done: 'success', in_progress: 'blue', review: 'purple', todo: 'neutral', backlog: 'neutral',
};
const STATUS_LABEL: Record<string, string> = {
  done: 'Done', in_progress: 'In progress', review: 'Review', todo: 'To do', backlog: 'Backlog',
};

const taskHours = (t: Task) => t.estimated_hours ?? t.story_points ?? 0;

export function FeaturesView() {
  const { data: features = [], isLoading } = useFeatures();
  const { data: tasks = [] } = useTasks();
  const { data: streams = [] } = useStreams();
  const { data: members = [] } = useTeamMembers();
  const { data: agentRuns = [] } = useCodingRuns();
  const [showForm, setShowForm] = useState(false);
  const [openRunId, setOpenRunId] = useState<string | null>(null);
  const [openTaskId, setOpenTaskId] = useState<string | null>(null);

  const membersById = new Map(members.map((m) => [m.id, m.name]));
  const runByTask = new Map(agentRuns.map((r) => [r.task_id, r]));
  const streamName = new Map(streams.map((s) => [s.id, s.name]));

  // Resolve the open run/task from the polled lists each render so drawers stay live.
  const openRun = openRunId ? agentRuns.find((r) => r.id === openRunId) : undefined;
  const openTask = openTaskId ? tasks.find((t) => t.id === openTaskId) : undefined;

  // Tasks grouped under each feature.
  const tasksByFeature = new Map<string, Task[]>();
  for (const t of tasks) {
    if (!t.feature_id) continue;
    const list = tasksByFeature.get(t.feature_id) ?? [];
    list.push(t);
    tasksByFeature.set(t.feature_id, list);
  }

  // Features grouped by stream; unknown/null streams fall under "Other".
  const groups: { key: string; label: string; features: Feature[] }[] = [];
  for (const s of streams) {
    const fs = features.filter((f) => f.stream_id === s.id);
    if (fs.length) groups.push({ key: s.id, label: s.name, features: fs });
  }
  const orphan = features.filter((f) => !f.stream_id || !streamName.has(f.stream_id));
  if (orphan.length) groups.push({ key: '__other__', label: 'Other', features: orphan });

  const renderFeature = (f: Feature) => {
    const ftasks = tasksByFeature.get(f.id) ?? [];
    const total = ftasks.length;
    const done = ftasks.filter((t) => t.status === 'done').length;
    const pts = ftasks.reduce((sum, t) => sum + (t.story_points ?? 0), 0);
    const pct = total ? Math.round((done / total) * 100) : 0;

    return (
      <div key={f.id} className="feature-card">
        <div className="feature-card-head">
          <span className="feature-card-name">{f.name}</span>
          <Badge tone="accent">{total} {total === 1 ? 'task' : 'tasks'}</Badge>
        </div>
        {f.description && <p className="feature-card-desc">{f.description}</p>}

        {total > 0 ? (
          <>
            <div className="feature-progress">
              <div className="feature-progress-bar">
                <div className="feature-progress-fill" style={{ width: `${pct}%` }} />
              </div>
              <span className="feature-progress-label">{done} / {total} done · {pts} pts</span>
            </div>
            <div className="backlog-list">
              {ftasks.map((t) => {
                const assignee = (t.assignee_id && membersById.get(t.assignee_id)) || '';
                const run = runByTask.get(t.id);
                return (
                  <div
                    key={t.id}
                    className="backlog-row"
                    onClick={() => setOpenTaskId(t.id)}
                    style={{ cursor: 'pointer' }}
                  >
                    <span className="backlog-id">#{t.external_id || t.id.slice(0, 8)}</span>
                    <span className="backlog-title">{t.title}</span>
                    <Badge tone={STATUS_TONE[t.status] ?? 'neutral'}>{STATUS_LABEL[t.status] ?? t.status}</Badge>
                    {assignee && <span className="backlog-assignee">{assignee}</span>}
                    <span className="backlog-hours">{taskHours(t)}h</span>
                    {run && <AgentBadge status={run.status} prUrl={run.pr_url} onClick={() => setOpenRunId(run.id)} />}
                  </div>
                );
              })}
            </div>
          </>
        ) : (
          <div className="feature-empty-tasks">No tasks yet — assign one to this feature from the work item form.</div>
        )}
      </div>
    );
  };

  return (
    <>
      <header className="header">
        <h1 className="header-title">Features</h1>
        <div className="header-actions">
          <span className="mono" style={{ color: 'var(--ink-soft)', marginRight: 8, fontSize: 12, fontWeight: 600 }}>
            {features.length} {features.length === 1 ? 'feature' : 'features'}
          </span>
          <Button variant="primary" onClick={() => setShowForm(true)} icon={<Plus size={15} strokeWidth={2.5} />}>
            New Feature
          </Button>
        </div>
      </header>

      {showForm && (
        <TaskFormModal defaultStatus="todo" defaultKind="feature" onClose={() => setShowForm(false)} />
      )}

      <div className="content">
        {isLoading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}><Spinner /></div>
        ) : features.length === 0 ? (
          <EmptyState>No features yet — create one.</EmptyState>
        ) : (
          groups.map((g) => (
            <div key={g.key}>
              <h2 className="features-stream-title">{g.label}</h2>
              {g.features.map(renderFeature)}
            </div>
          ))
        )}
      </div>

      {openRun && (
        <RunDetailDrawer
          run={openRun}
          taskTitle={tasks.find((t) => t.id === openRun.task_id)?.title}
          onClose={() => setOpenRunId(null)}
        />
      )}
      {openTask && !openRun && (
        <TaskDetailDrawer
          task={openTask}
          run={runByTask.get(openTask.id)}
          onViewRun={(runId) => { setOpenTaskId(null); setOpenRunId(runId); }}
          onClose={() => setOpenTaskId(null)}
        />
      )}
    </>
  );
}
