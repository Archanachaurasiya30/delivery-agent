import { DEFAULT_CAPACITY_HOURS, currentSprintId } from '../../lib/capacity';
import { useSprints, useTasks, useTeamMembers } from '../../hooks/useApi';

type CapacityPanelProps = {
  /** Sprint selected on the board, or null for its "all sprints" view. */
  sprintId: string | null;
};

/** Right-hand capacity rail: assigned hours vs capacity, per member. */
export function CapacityPanel({ sprintId }: CapacityPanelProps) {
  const { data: members = [] } = useTeamMembers();
  const { data: tasks = [] } = useTasks();
  const { data: sprints = [] } = useSprints();

  // Capacity is per sprint, so this rail is always scoped to exactly one — the
  // board's "all sprints" view falls back to the current sprint rather than
  // summing every sprint, which compared a year of work against one sprint's
  // hours and produced things like "357h / 60h".
  const scopedTo = sprintId ?? currentSprintId(sprints);
  const scopedSprint = sprints.find((s) => s.id === scopedTo);
  const inSprint = scopedTo ? tasks.filter((t) => t.sprint_id === scopedTo) : [];

  const assignedByMember = new Map<string, number>();
  for (const t of inSprint) {
    if (!t.assignee_id) continue;
    // Same measure the board columns use. Synced work items estimate in hours
    // (OriginalEstimate) and carry no story points, so points alone read zero.
    const hours = t.estimated_hours ?? t.story_points ?? 0;
    assignedByMember.set(t.assignee_id, (assignedByMember.get(t.assignee_id) || 0) + hours);
  }

  // Only people carrying work in this sprint, busiest first. The full roster is
  // 50 people; listing everyone put a wall of empty bars above the ones that
  // matter, and someone with no work in the sprint has nothing to report here.
  const ordered = members
    .filter((m) => (assignedByMember.get(m.id) || 0) > 0)
    .sort((a, b) => (assignedByMember.get(b.id) || 0) - (assignedByMember.get(a.id) || 0));

  return (
    <div className="capacity-panel">
      <div className="capacity-panel-header">
        <h3>Assigned To</h3>
        {/* Name the sprint: the rail can be scoped to the current sprint while
            the board itself shows all of them, and silent disagreement there is
            how the numbers stopped making sense in the first place. */}
        {scopedSprint && <span className="capacity-panel-scope">{scopedSprint.name}</span>}
      </div>
      <div className="capacity-panel-list">
        {ordered.map((member) => {
          const assigned = assignedByMember.get(member.id) || 0;
          const capacity = member.capacity_hours_per_sprint || DEFAULT_CAPACITY_HOURS;
          const percent = Math.min((assigned / capacity) * 100, 100);
          const overCapacity = assigned > capacity;
          return (
            <div key={member.id} className="capacity-member">
              <div className="capacity-member-name">{member.name}</div>
              <div className="capacity-member-bar">
                <div
                  className="capacity-member-fill"
                  style={{ width: `${percent}%`, background: overCapacity ? 'var(--danger)' : 'var(--success)' }}
                />
                {overCapacity && (
                  <div
                    className="capacity-member-over"
                    style={{ width: `${((assigned - capacity) / capacity) * 100}%`, left: '100%' }}
                  />
                )}
              </div>
              <div className="capacity-member-text">
                {assigned}h / {capacity}h
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
