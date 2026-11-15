// Shared coding-run status vocabulary (used by the drawer, the notifications
// provider, the sidebar pulse, and the PRs page).

/** Statuses where the loop has stopped (nothing left to stream). */
export const TERMINAL_STATUSES = new Set([
  'pr_open', 'merged', 'failed', 'ci_failed', 'skipped_human_only',
]);

/** A run the agent is still actively working (drives pulses / live badges). */
export const isActive = (status: string) => !TERMINAL_STATUSES.has(status);

/** Relative "3m ago" formatting for run timestamps. Backend timestamps are
 *  naive UTC, so zone-less ISO strings get a `Z` appended before parsing. */
export function relTime(iso: string | null | undefined): string {
  if (!iso) return '';
  const normalized = /Z|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`;
  const diff = Date.now() - new Date(normalized).getTime();
  const mins = Math.round(diff / 60_000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}
