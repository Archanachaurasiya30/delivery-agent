import type { ReactNode } from 'react';
import { Sidebar, type Page } from './Sidebar';
import { ToastHost } from '../notifications/ToastHost';

interface AppShellProps {
  page: Page;
  setPage: (p: Page) => void;
  selectedTeam: string | null;
  onSelectTeam: (team: string) => void;
  selectedStreamId: string | null;
  onSelectStream: (id: string) => void;
  sprintId: string | null;
  onSelectSprint: (id: string | null) => void;
  children: ReactNode;
}

export function AppShell({
  page,
  setPage,
  selectedTeam,
  onSelectTeam,
  selectedStreamId,
  onSelectStream,
  sprintId,
  onSelectSprint,
  children,
}: AppShellProps) {
  return (
    <div className="app">
      <Sidebar
        page={page}
        setPage={setPage}
        selectedTeam={selectedTeam}
        onSelectTeam={onSelectTeam}
        selectedStreamId={selectedStreamId}
        onSelectStream={onSelectStream}
        sprintId={sprintId}
        onSelectSprint={onSelectSprint}
      />
      <main className="main">{children}</main>
      <ToastHost />
    </div>
  );
}
