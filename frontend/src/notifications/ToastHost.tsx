import { GitMerge, GitPullRequest, Newspaper, Play, X, XCircle } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useAgentActivity, type AgentEvent } from './AgentActivityContext';

const KIND_ICONS: Record<AgentEvent['kind'], LucideIcon> = {
  started: Play,
  pr_open: GitPullRequest,
  merged: GitMerge,
  failed: XCircle,
  brief: Newspaper,
};

/** Fixed bottom-right stack of agent-activity toasts. Clicking a toast jumps
 *  to the page it's about (brief → Briefs, everything else → PRs); the X
 *  dismisses without navigating. */
export function ToastHost() {
  const { toasts, dismissToast, openPrs, openBriefs } = useAgentActivity();
  if (!toasts.length) return null;

  return (
    <div className="toast-stack" role="status" aria-live="polite">
      {toasts.map((t) => {
        const Icon = KIND_ICONS[t.kind];
        const open = t.kind === 'brief' ? openBriefs : openPrs;
        return (
          <div
            key={t.id}
            className={`toast ${t.tone}`}
            onClick={() => { dismissToast(t.id); open(); }}
          >
            <span className={`toast-ico ${t.tone}`}>
              <Icon size={14} strokeWidth={2.5} />
            </span>
            <span className="toast-body">
              <span className="toast-title">{t.title}</span>
              <span className="toast-detail">{t.detail}</span>
            </span>
            <button
              className="toast-close"
              aria-label="Dismiss notification"
              onClick={(e) => { e.stopPropagation(); dismissToast(t.id); }}
            >
              <X size={14} strokeWidth={2.5} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
