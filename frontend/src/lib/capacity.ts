/**
 * Hours one person is assumed to have in a sprint when the server has no
 * per-person figure.
 *
 * The on-prem instance leaves the sprint Capacity tab empty, so every synced
 * member falls back to this. Kept in one place because the board rail and the
 * capacity page both compare assigned hours against it and must not disagree.
 */
export const DEFAULT_CAPACITY_HOURS = 60;

/**
 * The sprint containing today, latest first when several overlap.
 *
 * Not `status === 'active'`: more than one sprint can carry that flag, so the
 * flag alone picks the wrong one. Dates are unambiguous.
 *
 * Capacity is a per-sprint quantity, so every view that compares assigned
 * hours against it has to pin itself to exactly one sprint — summing several
 * and dividing by one sprint's hours is what produced "357h / 60h".
 */
export function currentSprintId(
  sprints: { id: string; start_date: string; end_date: string }[],
): string | null {
  const today = new Date().toISOString().slice(0, 10);
  return (
    sprints
      .filter((s) => s.start_date <= today && today <= s.end_date)
      .sort((a, b) => b.start_date.localeCompare(a.start_date))[0]?.id ?? null
  );
}
