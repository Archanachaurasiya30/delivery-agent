import { useEffect, useRef, useState } from 'react';
import {
  Bot, Sparkles, GitBranch, GitPullRequest, Inbox, ShieldCheck, ChevronDown,
  ListTodo, Boxes,
} from 'lucide-react';
import { Modal } from '../../ui/Modal';
import { Button } from '../../ui/Button';
import { Combobox, type ComboGroup, type ComboOption } from '../../ui/Combobox';
import { subAreasOf } from '../../lib/subAreas';
import {
  useTeamMembers, useSprints, useCreateTask, useTasks,
  useFeatures, useCreateFeature, useStreams, useCodingRepositories, useCreateRepository,
} from '../../hooks/useApi';
import { dispatchCodingAgent } from '../../lib/api';
import type { TaskStatus, TaskPriority, TaskCreate } from '../../types';

// Sentinel assignee value meaning "hand this task to the coding agent".
const AI_AGENT = '__AI_AGENT__';

type WorkItemKind = 'task' | 'feature';

const PRIORITIES: { value: TaskPriority; label: string }[] = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'critical', label: 'Critical' },
];

interface TaskFormModalProps {
  defaultStatus: TaskStatus;
  onClose: () => void;
  onCreated?: () => void;
  /** Which work-item type the form authors — fixed for the lifetime of the modal. */
  defaultKind?: WorkItemKind;
}

/** Authoring form for a work item. Board/backlog open it as a focused Task form;
 *  the Features view opens it as a Feature form. */
export function TaskFormModal({ defaultStatus, onClose, onCreated, defaultKind = 'task' }: TaskFormModalProps) {
  const [kind, setKind] = useState<WorkItemKind>(defaultKind);

  const { data: tasks = [] } = useTasks();
  const { data: members = [] } = useTeamMembers();
  const { data: sprints = [] } = useSprints();
  const { data: features = [] } = useFeatures();
  const { data: streams = [] } = useStreams();
  const { data: repos = [] } = useCodingRepositories();
  const createTask = useCreateTask();
  const createFeature = useCreateFeature();
  const createRepo = useCreateRepository();

  // Shared between both kinds (title doubles as the feature name).
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [acceptance, setAcceptance] = useState(''); // task-only

  // Task-only fields.
  const [assignee, setAssignee] = useState(''); // '' | AI_AGENT | member id
  const [technology, setTechnology] = useState('');
  const [hours, setHours] = useState('');
  const [points, setPoints] = useState('');
  const [sprintId, setSprintId] = useState('');
  const [featureId, setFeatureId] = useState('');
  const [priority, setPriority] = useState<TaskPriority>('medium');
  const [repository, setRepository] = useState('');

  // Feature-only field.
  const [featureStreamId, setFeatureStreamId] = useState('');

  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Task persisted by a prior submit whose agent dispatch failed — a retry
  // must re-dispatch, not create a duplicate. Resets when the modal unmounts.
  const createdTaskIdRef = useRef<string | null>(null);

  // Default a new feature to the first stream once streams load.
  useEffect(() => {
    if (streams.length && !featureStreamId) setFeatureStreamId(streams[0].id);
  }, [streams, featureStreamId]);

  // Only in-flight sprints are assignable.
  const assignableSprints = sprints.filter((s) => s.status === 'active' || s.status === 'planning');
  const toAgent = assignee === AI_AGENT;
  const selectedSprint = sprints.find((s) => s.id === sprintId);

  // Features grouped by stream for the Combobox; orphan features fall under "Other".
  const streamName = new Map(streams.map((s) => [s.id, s.name]));
  const featureGroups: ComboGroup[] = [];
  for (const s of streams) {
    const fs = features.filter((f) => f.stream_id === s.id);
    if (fs.length) featureGroups.push({ label: s.name, options: fs.map((f) => ({ value: f.id, label: f.name })) });
  }
  const orphan = features.filter((f) => !f.stream_id || !streamName.has(f.stream_id));
  if (orphan.length) featureGroups.push({ label: 'Other', options: orphan.map((f) => ({ value: f.id, label: f.name })) });

  const repoOptions: ComboOption[] = repos.map((r) => ({ value: r, label: r }));

  const submitTask = async () => {
    const body: TaskCreate = {
      title: title.trim(),
      description: description.trim() || null,
      acceptance_criteria: acceptance.trim() || null,
      status: defaultStatus,
      priority,
      assignee_id: assignee && assignee !== AI_AGENT ? assignee : null,
      sprint_id: sprintId || null,
      feature_id: featureId || null,
      story_points: points ? Number(points) : null,
      estimated_hours: hours ? Number(hours) : null,
      technology: technology || null,
    };
    let id = createdTaskIdRef.current;
    if (!id) {
      const task = await createTask.mutateAsync(body);
      id = task.id;
      createdTaskIdRef.current = id;
    }
    // Handing to the AI agent dispatches the coding-agent loop; the resulting
    // PR lands in the Proposals queue for review (never auto-merged).
    if (toAgent) await dispatchCodingAgent(id, repository || null);
  };

  const submitFeature = async () => {
    await createFeature.mutateAsync({
      name: title.trim(),
      description: description.trim() || null,
      stream_id: featureStreamId || null,
    });
  };

  const submit = async () => {
    if (!title.trim()) { setError(kind === 'feature' ? 'Name is required' : 'Title is required'); return; }
    setBusy(true);
    setError(null);
    try {
      if (kind === 'feature') await submitFeature();
      else await submitTask();
      onCreated?.();
      onClose();
    } catch (e: any) {
      setError(
        kind === 'task' && createdTaskIdRef.current
          ? `Task created, but agent dispatch failed: ${e.message}. Retrying re-dispatches without duplicating the task.`
          : e.message || `Failed to create ${kind}`,
      );
    } finally {
      setBusy(false);
    }
  };

  const createLabel = busy
    ? 'Creating…'
    : kind === 'feature'
      ? 'Create Feature'
      : toAgent ? 'Dispatch to AI Agent' : 'Create Task';

  const footHint = kind === 'feature'
    ? 'Features group related tasks'
    : toAgent ? 'Runs on its own branch' : 'Lands on your board';

  return (
    <Modal
      title="New Work Item"
      onClose={onClose}
      width={560}
      footer={
        <>
          <span className="modal-foot-hint">{footHint}</span>
          <Button variant="secondary" onClick={onClose} disabled={busy}>Cancel</Button>
          <Button
            variant="primary"
            onClick={submit}
            disabled={busy || createRepo.isPending || !title.trim()}
            className={toAgent ? 'btn-ai' : ''}
            icon={toAgent ? <Bot size={16} strokeWidth={2.25} /> : undefined}
          >
            {createLabel}
          </Button>
        </>
      }
    >
      <div className="type-switch" role="tablist" aria-label="Work item type">
        <button
          type="button" role="tab" aria-selected={kind === 'task'}
          className={`type-switch-btn ${kind === 'task' ? 'active' : ''}`}
          onClick={() => setKind('task')}
        >
          <ListTodo size={15} strokeWidth={2.25} /> Task
        </button>
        <button
          type="button" role="tab" aria-selected={kind === 'feature'}
          className={`type-switch-btn ${kind === 'feature' ? 'active' : ''}`}
          onClick={() => setKind('feature')}
        >
          <Boxes size={15} strokeWidth={2.25} /> Feature
        </button>
      </div>

      <p className="form-modal-sub">
        {kind === 'feature' ? 'Group related tasks under one deliverable.' : 'Add a work item to your board.'}
      </p>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>
      )}

      {kind === 'feature' ? (
        /* FEATURE */
        <div className="form-grid-2">
          <div className="form-group span-2">
            <label className="form-label">Name</label>
            <input className="form-input lead" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Feature name" autoFocus />
          </div>
          <div className="form-group span-2">
            <label className="form-label">Description</label>
            <textarea className="form-textarea" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What this feature delivers…" />
          </div>
          <div className="form-group span-2">
            <label className="form-label">Stream</label>
            <select className="form-select" value={featureStreamId} onChange={(e) => setFeatureStreamId(e.target.value)}>
              <option value="">— No stream —</option>
              {streams.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
        </div>
      ) : (
        /* TASK */
        <>
          {/* Lead: the work statement */}
          <div className="form-group">
            <label className="form-label">Title</label>
            <input className="form-input lead" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="What needs doing?" autoFocus />
          </div>
          <div className="form-group">
            <label className="form-label">Description <span className="form-label-opt">optional</span></label>
            <textarea className="form-textarea" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Add context or links…" />
          </div>
          <div className="form-group">
            <label className="form-label">Acceptance criteria <span className="form-label-opt">optional</span></label>
            <textarea
              className="form-textarea"
              value={acceptance}
              onChange={(e) => setAcceptance(e.target.value)}
              placeholder={'When is this story done? One criterion per line…'}
            />
          </div>

          <div className="form-divider"><span>Planning</span></div>

          {/* Assignee — the pivot: choosing AI Agent reshapes the form */}
          <div className="form-group">
            <label className="form-label">Assignee</label>
            <select className="form-select" value={assignee} onChange={(e) => setAssignee(e.target.value)}>
              <option value="">Unassigned</option>
              <option value={AI_AGENT}>🤖 AI Agent — autonomous</option>
              {members.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
            </select>
          </div>

          {/* AI dispatch panel — the signature moment */}
          {toAgent && (
            <section className="ai-dispatch">
              <div className="ai-dispatch-head">
                <span className="ai-dispatch-badge"><Bot size={20} strokeWidth={2} /></span>
                <div>
                  <div className="ai-dispatch-title">
                    AI Agent will pick this up <span className="ai-dispatch-pill">Autonomous</span>
                  </div>
                  <div className="ai-dispatch-sub">It grooms the task, builds on a branch, and opens a pull request for review.</div>
                </div>
              </div>

              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Repository</label>
                <Combobox
                  value={repository}
                  onChange={setRepository}
                  options={repoOptions}
                  noneLabel="Default (configured repo)"
                  searchPlaceholder="Search or create a repository…"
                  emptyLabel="No repositories yet"
                  allowCreate
                  createLabel={(q) => `Create repository “${q}” in Azure DevOps`}
                  onCreate={async (name) => {
                    // Really creates the repo in ADO (seeded with a sample app),
                    // then selects it; failures land in the form's error banner.
                    setError(null);
                    try {
                      const repo = await createRepo.mutateAsync({ name, seed: true });
                      return repo.name;
                    } catch (e: any) {
                      setError(e.message || 'Failed to create repository');
                      return repository; // keep the previous selection
                    }
                  }}
                  placement="bottom"
                />
                <p style={{ fontSize: 11.5, color: 'var(--ink-mute)', margin: '6px 0 0', lineHeight: 1.5 }}>
                  New repositories are created in Azure DevOps and seeded with a sample app.
                </p>
              </div>

              <ol className="ai-flow" aria-label="What the agent does">
                <li className="ai-flow-step"><span className="ai-flow-node"><Sparkles size={15} strokeWidth={2} /></span><span className="ai-flow-label">Grooms</span></li>
                <li className="ai-flow-step"><span className="ai-flow-node"><GitBranch size={15} strokeWidth={2} /></span><span className="ai-flow-label">Branch</span></li>
                <li className="ai-flow-step"><span className="ai-flow-node"><GitPullRequest size={15} strokeWidth={2} /></span><span className="ai-flow-label">Pull request</span></li>
                <li className="ai-flow-step ai-flow-step-end"><span className="ai-flow-node"><Inbox size={15} strokeWidth={2} /></span><span className="ai-flow-label">Proposals</span></li>
              </ol>

              <p className="ai-dispatch-note">
                <ShieldCheck size={15} strokeWidth={2} className="ai-dispatch-lock" />
                <span><strong>Nothing auto-merges.</strong> Every proposal lands in your review queue and waits for a human.</span>
              </p>
            </section>
          )}

          {/* Priority — glanceable segmented chips */}
          <div className="form-group">
            <label className="form-label">Priority</label>
            <div className="prio-seg" role="radiogroup" aria-label="Priority">
              {PRIORITIES.map((p) => (
                <button
                  key={p.value}
                  type="button"
                  role="radio"
                  aria-checked={priority === p.value}
                  className={`prio-chip ${priority === p.value ? 'selected' : ''}`}
                  data-prio={p.value}
                  onClick={() => setPriority(p.value)}
                >
                  <span className="prio-dot" />{p.label}
                </button>
              ))}
            </div>
          </div>

          {/* Sprint + Feature */}
          <div className="form-grid-2">
            <div className="form-group">
              <label className="form-label">Sprint</label>
              <select className="form-select" value={sprintId} onChange={(e) => setSprintId(e.target.value)}>
                <option value="">Backlog (no sprint)</option>
                {assignableSprints.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}{s.status === 'planning' ? ' (planning)' : ''}</option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Feature <span className="form-label-opt">optional</span></label>
              <Combobox
                value={featureId}
                onChange={setFeatureId}
                groups={featureGroups}
                noneLabel="— No feature —"
                searchPlaceholder="Search or create a feature…"
                emptyLabel="No features yet"
                allowCreate
                createLabel={(q) => `Create feature “${q}”`}
                onCreate={async (name) => {
                  setError(null);
                  try {
                    const f = await createFeature.mutateAsync({ name, stream_id: selectedSprint?.stream_id ?? null });
                    return f.id;
                  } catch (e: any) {
                    setError(e.message || 'Failed to create feature');
                    return featureId; // keep the previous selection
                  }
                }}
                placement="bottom"
              />
            </div>
          </div>

          {/* Advanced — estimation & stack, collapsed by default */}
          <details className="form-advanced">
            <summary className="form-advanced-summary">
              <Sparkles size={15} strokeWidth={2} className="form-advanced-lead" />
              Estimation &amp; stack
              <span className="form-advanced-meta">optional</span>
              <ChevronDown size={16} strokeWidth={2.25} className="form-advanced-chev" />
            </summary>
            <div className="form-advanced-body">
              <div className="form-group span-2">
                <label className="form-label">Technology</label>
                <select className="form-select" value={technology} onChange={(e) => setTechnology(e.target.value)}>
                  <option value="">—</option>
                  {subAreasOf(tasks).map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Estimated hours</label>
                <input className="form-input" type="number" min={0} value={hours} onChange={(e) => setHours(e.target.value)} placeholder="e.g. 8" />
              </div>
              <div className="form-group">
                <label className="form-label">Story points</label>
                <input className="form-input" type="number" min={1} max={21} value={points} onChange={(e) => setPoints(e.target.value)} placeholder="1–21" />
              </div>
            </div>
          </details>
        </>
      )}
    </Modal>
  );
}
