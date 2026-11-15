export type Column = { id: string; name: string; color: string };

/** Board columns, mapped to task status. Real app config, not sample data. */
export const COLUMNS: Column[] = [
  { id: 'todo', name: 'To Do', color: '#9CA3AF' },
  { id: 'in_progress', name: 'In Progress', color: '#3B82F6' },
  { id: 'review', name: 'Review', color: '#F59E0B' },
  { id: 'done', name: 'Done', color: '#10B981' },
];
