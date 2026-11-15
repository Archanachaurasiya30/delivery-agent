import type { CSSProperties } from 'react';
import { ExternalLink } from 'lucide-react';

// Small status pill for a task's coding-agent run (shown on board/backlog cards).
const AGENT_STATUS: Record<string, { label: string; bg: string; fg: string }> = {
  dispatched: { label: 'queued', bg: 'var(--tint-orange)', fg: '#c2410c' },
  groomed: { label: 'grooming', bg: 'var(--tint-orange)', fg: '#c2410c' },
  running: { label: 'coding', bg: 'var(--tint-orange)', fg: '#c2410c' },
  ci_pending: { label: 'CI…', bg: 'var(--tint-orange)', fg: '#c2410c' },
  ci_failed: { label: 'CI failed', bg: 'var(--tint-danger)', fg: '#b91c1c' },
  pr_open: { label: 'PR open', bg: 'var(--tint-blue)', fg: 'var(--accent-2)' },
  merged: { label: 'merged', bg: 'var(--tint-success)', fg: '#047857' },
  failed: { label: 'failed', bg: 'var(--tint-danger)', fg: '#b91c1c' },
  skipped_human_only: { label: 'human-only', bg: 'var(--tint-neutral)', fg: 'var(--ink-soft)' },
};

interface AgentBadgeProps {
  status: string;
  /** When set, the pill renders as a button (e.g. opens the run drawer). */
  onClick?: () => void;
  /** On pr_open/merged, adds a small external-link glyph to the PR. */
  prUrl?: string | null;
}

export function AgentBadge({ status, onClick, prUrl }: AgentBadgeProps) {
  const s = AGENT_STATUS[status] || { label: status, bg: 'var(--tint-neutral)', fg: 'var(--ink-soft)' };
  const style: CSSProperties = {
    display: 'inline-flex', alignItems: 'center', gap: 4,
    fontSize: 10, fontWeight: 600, padding: '1px 7px',
    borderRadius: 'var(--radius-pill)', background: s.bg, color: s.fg, whiteSpace: 'nowrap',
  };
  const showPr = !!prUrl && (status === 'pr_open' || status === 'merged');
  const content = (
    <>
      🤖 {s.label}
      {showPr && (
        <a
          href={prUrl!}
          target="_blank"
          rel="noreferrer"
          onClick={(e) => e.stopPropagation()}
          title="Open pull request"
          aria-label="Open pull request"
          style={{ display: 'inline-flex', color: 'inherit' }}
        >
          <ExternalLink size={10} strokeWidth={2.5} />
        </a>
      )}
    </>
  );

  if (onClick) {
    return (
      <button
        type="button"
        title={`AI agent: ${status} — view run`}
        // Cards have their own click action (task detail) — the badge is the
        // direct shortcut to the run, so it must not bubble.
        onClick={(e) => { e.stopPropagation(); onClick(); }}
        style={{ ...style, border: 'none', fontFamily: 'inherit', cursor: 'pointer' }}
      >
        {content}
      </button>
    );
  }
  return (
    <span title={`AI agent: ${status}`} style={style}>
      {content}
    </span>
  );
}
