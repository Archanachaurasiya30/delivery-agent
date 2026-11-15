import type { Task } from '../types';

/**
 * Sub-areas: the real grouping synced work carries.
 *
 * Azure DevOps files each work item under an area path
 * ("Northwind\Retail Platform\Storefront"); the leaf below the
 * stream root is the sub-area, and the import stores it as `project_name`.
 *
 * This replaces the old mock `TEAMS` / `teamForTask()`, which derived a
 * ".NET / Android / iOS" badge from a hash of the task id and rendered it on
 * real work items as though the server had said so.
 *
 * Items filed directly on the stream root have no sub-area, and get no badge —
 * an absent label beats an invented one.
 */

/** Palette for sub-area chips. Presentation only — the label is the data. */
const PALETTE = ['#3B82F6', '#10B981', '#F97316', '#8B5CF6', '#EC4899', '#0EA5E9'];

/** Stable colour for a sub-area, so a name keeps its colour across views. */
export function subAreaColor(name: string | null | undefined): string {
  if (!name) return '#9CA3AF';
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) | 0;
  return PALETTE[Math.abs(h) % PALETTE.length];
}

/** Distinct sub-areas present in the given tasks, busiest first. */
export function subAreasOf(tasks: Task[]): { id: string; name: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const t of tasks) {
    if (!t.project_name) continue;
    counts.set(t.project_name, (counts.get(t.project_name) || 0) + 1);
  }
  return [...counts.entries()]
    .map(([name, count]) => ({ id: name, name, count }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
}

/** Azure DevOps types that represent something broken rather than planned work. */
const DEFECT_TYPES = new Set(['bug', 'issue', 'impediment']);

export function isDefect(type: string | null | undefined): boolean {
  return DEFECT_TYPES.has((type || '').toLowerCase());
}

/**
 * The type chip to show on a card, or null to show none.
 *
 * "Task" is the default and by far the most common type, so labelling it adds
 * noise without information; everything else earns a chip.
 */
export function typeChip(type: string | null | undefined): string | null {
  if (!type || type.toLowerCase() === 'task') return null;
  return type === 'Product Backlog Item' ? 'PBI' : type;
}
