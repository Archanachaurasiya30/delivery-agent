import { useEffect, useRef, useState } from 'react';
import { Bell, GitMerge, GitPullRequest, Newspaper, Play, XCircle } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useAgentActivityOptional, type AgentEvent } from './AgentActivityContext';

const KIND_ICONS: Record<AgentEvent['kind'], LucideIcon> = {
  started: Play,
  pr_open: GitPullRequest,
  merged: GitMerge,
  failed: XCircle,
  brief: Newspaper,
};

function relTime(at: Date): string {
  const mins = Math.round((Date.now() - at.getTime()) / 60_000);
  if (mins < 1) return 'now';
  if (mins < 60) return `${mins}m`;
  return `${Math.round(mins / 60)}h`;
}

/** Bell in the sidebar header: unread badge + dropdown with the session's
 *  agent-activity history. Opening it marks everything read. */
export function NotificationBell() {
  const activity = useAgentActivityOptional();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  // Rendered outside the provider (e.g. the ADO bundle) → no bell.
  if (!activity) return null;
  const { events, unreadCount, markAllRead, openPrs, openBriefs } = activity;

  const toggle = () => {
    setOpen((o) => {
      if (!o) markAllRead();
      return !o;
    });
  };

  return (
    <div className="bell" ref={rootRef}>
      <button className="bell-btn" onClick={toggle} aria-label="Agent activity" aria-expanded={open}>
        <Bell size={15} strokeWidth={2.25} />
        {unreadCount > 0 && <span className="bell-unread">{unreadCount > 9 ? '9+' : unreadCount}</span>}
      </button>

      {open && (
        <div className="bell-panel" role="menu" aria-label="Agent activity history">
          <div className="bell-panel-head">Agent activity</div>
          {events.length === 0 ? (
            <div className="bell-empty">No agent activity yet this session.</div>
          ) : (
            events.map((e) => {
              const Icon = KIND_ICONS[e.kind];
              const open = e.kind === 'brief' ? openBriefs : openPrs;
              return (
                <button
                  key={e.id}
                  className="bell-item"
                  onClick={() => { setOpen(false); open(); }}
                >
                  <span className={`bell-ico ${e.tone}`}>
                    <Icon size={13} strokeWidth={2.5} />
                  </span>
                  <span className="bell-body">
                    <span className="bell-title">{e.title}</span>
                    <span className="bell-detail">{e.detail}</span>
                  </span>
                  <span className="bell-time">{relTime(e.at)}</span>
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
