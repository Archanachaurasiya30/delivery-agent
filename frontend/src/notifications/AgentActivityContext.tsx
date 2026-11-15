import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState,
  type ReactNode,
} from 'react';
import { useCodingRuns, useLatestBrief, useTasks } from '../hooks/useApi';
import { isActive } from '../features/coding/runStatus';
import type { AgentRun } from '../types';

export type EventTone = 'info' | 'success' | 'error';

export interface AgentEvent {
  id: number;
  // Run coordinates — absent for non-run events (e.g. a morning brief).
  runId?: string;
  taskId?: string;
  kind: 'started' | 'pr_open' | 'merged' | 'failed' | 'brief';
  tone: EventTone;
  title: string;
  detail: string;
  at: Date;
}

export interface Toast extends AgentEvent {}

interface AgentActivityValue {
  events: AgentEvent[];
  unreadCount: number;
  markAllRead: () => void;
  toasts: Toast[];
  dismissToast: (id: number) => void;
  activeRunCount: number;
  openPrCount: number;
  openPrs: () => void;
  openBriefs: () => void;
}

const AgentActivityContext = createContext<AgentActivityValue | null>(null);

const MAX_EVENTS = 50;
const MAX_TOASTS = 3;
const TOAST_MS = 6000;
const TOAST_ERROR_MS = 8000;

/** Maps a run's NEW status to a notification (classifying by the new status
 *  alone keeps this correct even when the 4s poll skips intermediate states). */
function classify(run: AgentRun, prev: string | undefined, taskTitle: string): Omit<AgentEvent, 'id' | 'at'> | null {
  const base = { runId: run.id, taskId: run.task_id, detail: taskTitle };
  switch (run.status) {
    case 'running':
      return { ...base, kind: 'started', tone: 'info', title: 'Agent started coding' };
    case 'pr_open':
      return { ...base, kind: 'pr_open', tone: 'success', title: 'PR opened' };
    case 'merged':
      return { ...base, kind: 'merged', tone: 'success', title: 'PR merged' };
    case 'failed':
      return { ...base, kind: 'failed', tone: 'error', title: 'Agent run failed' };
    case 'ci_failed':
      return { ...base, kind: 'failed', tone: 'error', title: 'CI failed' };
    case 'dispatched':
    case 'groomed':
      // Only announce brand-new runs, not e.g. a poll catching an old row.
      return prev === undefined
        ? { ...base, kind: 'started', tone: 'info', title: 'Agent dispatched' }
        : null;
    default:
      return null;
  }
}

/** Watches the shared coding-runs poll and turns status transitions into
 *  session events (bell history), toasts, and live counts. Costs no extra
 *  network — it rides the existing 4s ['coding-runs'] query. Also watches the
 *  60s latest-brief poll and announces freshly generated morning briefs. */
export function AgentActivityProvider({
  onOpenPrs,
  onOpenBriefs,
  children,
}: {
  onOpenPrs: () => void;
  onOpenBriefs?: () => void;
  children: ReactNode;
}) {
  const { data: runs } = useCodingRuns();
  const { data: tasks = [] } = useTasks();
  const { data: latestBrief } = useLatestBrief();

  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [lastSeenId, setLastSeenId] = useState(0);

  // runId -> last status seen. null = "no successful poll yet" (seed only).
  const prevRef = useRef<Map<string, string> | null>(null);
  // Last announced brief id. undefined = "no successful poll yet" (seed only);
  // null = polled successfully but no brief exists.
  const lastBriefIdRef = useRef<string | null | undefined>(undefined);
  const seqRef = useRef(0);
  const taskTitle = useCallback(
    (taskId: string) => tasks.find((t) => t.id === taskId)?.title ?? 'Task',
    [tasks],
  );

  const dismissToast = useCallback((id: number) => {
    setToasts((ts) => ts.filter((t) => t.id !== id));
  }, []);

  // Shared firing path: prepend to the bell history, stack the toasts, and
  // schedule their auto-dismissal.
  const emit = useCallback((fired: AgentEvent[]) => {
    if (!fired.length) return;
    setEvents((es) => [...fired].reverse().concat(es).slice(0, MAX_EVENTS));
    setToasts((ts) => ts.concat(fired).slice(-MAX_TOASTS));
    for (const evt of fired) {
      const ms = evt.tone === 'error' ? TOAST_ERROR_MS : TOAST_MS;
      setTimeout(() => dismissToast(evt.id), ms);
    }
  }, [dismissToast]);

  useEffect(() => {
    if (!runs) return;
    if (prevRef.current === null) {
      // First poll seeds the map without firing — runs that were already
      // in flight or terminal when the app loaded never toast.
      prevRef.current = new Map(runs.map((r) => [r.id, r.status]));
      return;
    }
    const fired: AgentEvent[] = [];
    for (const run of runs) {
      const prev = prevRef.current.get(run.id);
      if (prev === run.status) continue;
      // Update the map synchronously so a StrictMode double-effect can't
      // classify the same transition twice.
      prevRef.current.set(run.id, run.status);
      const evt = classify(run, prev, taskTitle(run.task_id));
      if (evt) fired.push({ ...evt, id: ++seqRef.current, at: new Date() });
    }
    emit(fired);
  }, [runs, taskTitle, emit]);

  useEffect(() => {
    if (latestBrief === undefined) return; // no successful poll yet
    if (lastBriefIdRef.current === undefined) {
      // First poll seeds without firing — the brief that already existed
      // when the app loaded never toasts.
      lastBriefIdRef.current = latestBrief?.id ?? null;
      return;
    }
    if (!latestBrief || latestBrief.id === lastBriefIdRef.current) return;
    // Updated synchronously (before emit) so a StrictMode double-effect
    // can't announce the same brief twice.
    lastBriefIdRef.current = latestBrief.id;
    emit([{
      id: ++seqRef.current,
      kind: 'brief',
      tone: 'info',
      title: 'Morning brief ready',
      detail: latestBrief.headline,
      at: new Date(),
    }]);
  }, [latestBrief, emit]);

  const value = useMemo<AgentActivityValue>(() => {
    const activeRunCount = (runs ?? []).filter((r) => isActive(r.status)).length;
    const openPrCount = (runs ?? []).filter((r) => r.status === 'pr_open').length;
    return {
      events,
      unreadCount: events.filter((e) => e.id > lastSeenId).length,
      markAllRead: () => setLastSeenId(seqRef.current),
      toasts,
      dismissToast,
      activeRunCount,
      openPrCount,
      openPrs: onOpenPrs,
      // Falls back to the PRs page when the host app has no Briefs page
      // (e.g. the ADO bundle).
      openBriefs: onOpenBriefs ?? onOpenPrs,
    };
  }, [runs, events, toasts, lastSeenId, dismissToast, onOpenPrs, onOpenBriefs]);

  return <AgentActivityContext.Provider value={value}>{children}</AgentActivityContext.Provider>;
}

export function useAgentActivity(): AgentActivityValue {
  const ctx = useContext(AgentActivityContext);
  if (!ctx) throw new Error('useAgentActivity must be used inside AgentActivityProvider');
  return ctx;
}

/** Safe variant for components that also render outside the provider
 *  (e.g. Sidebar is reused by the ADO bundle, which has no provider). */
export function useAgentActivityOptional(): AgentActivityValue | null {
  return useContext(AgentActivityContext);
}
