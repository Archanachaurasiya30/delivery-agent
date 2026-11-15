import type { ReactNode } from 'react';

interface EmptyStateProps {
  icon?: ReactNode;
  children: ReactNode;
}

/** Centered empty / placeholder state. */
export function EmptyState({ icon, children }: EmptyStateProps) {
  return (
    <div className="empty">
      {icon && <div className="empty-icon">{icon}</div>}
      <div>{children}</div>
    </div>
  );
}
