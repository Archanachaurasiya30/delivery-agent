import { DEFAULT_CAPACITY_HOURS, currentSprintId } from '../../lib/capacity';
import { subAreaColor, subAreasOf } from '../../lib/subAreas';
import { useSprints, useTasks, useTeamMembers } from '../../hooks/useApi';
import { Spinner } from '../../ui/Spinner';

export function CapacityView() {
  const { data: members = [], isLoading } = useTeamMembers();
  const { data: tasks = [] } = useTasks();
  const { data: sprints = [] } = useSprints();

  // Capacity is per sprint. This page used to sum every sprint and compare the
  // total against one sprint's hours.
  const scopedTo = currentSprintId(sprints);
  const scopedSprint = sprints.find((s) => s.id === scopedTo);
  const inSprint = scopedTo ? tasks.filter((t) => t.sprint_id === scopedTo) : [];

  // Hours, not story points: synced work items estimate in OriginalEstimate and
  // carry no points, so a points sum reads zero for the whole real team.
  const hoursOf = (t: (typeof tasks)[number]) => t.estimated_hours ?? t.story_points ?? 0;

  const assignedByMember = new Map<string, number>();
  for (const t of inSprint) {
    if (!t.assignee_id) continue;
    assignedByMember.set(t.assignee_id, (assignedByMember.get(t.assignee_id) || 0) + hoursOf(t));
  }

  // Grouped by the real Azure DevOps sub-area. The old grid grouped by a
  // hardcoded name -> team map that matched none of the synced people, so every
  // card silently rendered empty.
  const areas = subAreasOf(inSprint).map((area) => ({
    ...area,
    hours: inSprint
      .filter((t) => t.project_name === area.id)
      .reduce((sum, t) => sum + hoursOf(t), 0),
  }));

  const loaded = members
    .filter((m) => (assignedByMember.get(m.id) || 0) > 0)
    .sort((a, b) => (assignedByMember.get(b.id) || 0) - (assignedByMember.get(a.id) || 0));

  return (
    <>
      <header className="header">
        <h1 className="header-title">Team Capacity</h1>
        {scopedSprint && (
          <span className="mono" style={{ fontSize: 12, color: 'var(--ink-soft)', fontWeight: 600 }}>
            {scopedSprint.name}
          </span>
        )}
      </header>
      <div className="content">
        {isLoading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}><Spinner /></div>
        ) : (
          <>
            <div className="stats-grid">
              {areas.map((area, i) => (
                <div key={area.id} className="stat-card reveal" style={{ ['--i' as any]: i }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                    <span className="sidebar-dot" style={{ background: subAreaColor(area.id), width: 12, height: 12, marginLeft: 0 }} />
                    <span style={{ fontWeight: 600 }}>{area.name}</span>
                  </div>
                  <div className="mono" style={{ fontSize: 12, color: 'var(--ink-soft)', fontWeight: 600 }}>
                    {area.hours}h across {area.count} item{area.count === 1 ? '' : 's'}
                  </div>
                </div>
              ))}
            </div>

            <h2 style={{ fontSize: 18, fontWeight: 650, margin: '28px 0 16px', letterSpacing: '-0.02em' }}>
              Team Members
            </h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 14 }}>
              {loaded.map((member) => {
                const assigned = assignedByMember.get(member.id) || 0;
                const capacity = member.capacity_hours_per_sprint || DEFAULT_CAPACITY_HOURS;
                const percent = (assigned / capacity) * 100;
                const overCapacity = assigned > capacity;
                return (
                  <div key={member.id} className="card" style={{ padding: 16 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
                      <span style={{ fontWeight: 600 }}>{member.name}</span>
                      <span className="mono" style={{ fontSize: 12, fontWeight: 600, color: overCapacity ? 'var(--danger)' : 'var(--ink-soft)' }}>
                        {assigned}h / {capacity}h
                      </span>
                    </div>
                    <div className="team-capacity-bar">
                      <div className="team-capacity-fill" style={{ width: `${Math.min(percent, 100)}%`, background: overCapacity ? 'var(--danger)' : 'var(--success)' }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </>
  );
}
