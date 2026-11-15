import { useState } from 'react';
import {
  Bot, ClipboardCheck, Layers, GitBranch, GitPullRequest,
  Cpu, Map, Activity, ChartNoAxesCombined,
} from 'lucide-react';
import { Logo } from '../ui/Logo';
import { useStreams } from '../hooks/useApi';
import { AgentPage } from '../features/agent/AgentPage';
import { ProposalsPage } from '../features/proposals/ProposalsPage';
import { PrsPage } from '../features/prs/PrsPage';
import { PortfolioView } from '../features/portfolio/PortfolioView';
import { StreamView } from '../features/stream/StreamView';
import { WorkforceView } from '../features/workforce/WorkforceView';
import { SprintDashboard } from '../features/delivery/SprintDashboard';
import { RoadmapView } from '../features/roadmap/RoadmapView';
import { FlowView } from '../features/flow/FlowView';

// Trimmed shell for the Azure DevOps hub. Azure DevOps already owns the
// "delivery core" (boards, backlog, sprints, repos), so this omits the Kanban
// board / backlog / capacity / team-filter nav and reuses the standalone app's
// feature components and CSS as-is.
//
// The analytics pages ARE mirrored here. Azure DevOps ships its own burndown
// and velocity reports, so Sprint Dashboard and Flow partly overlap with what
// the host already offers — but they read the agent-aware model (confidence
// factors, stale detection, agent-delivered work) that ADO cannot see, and the
// AI Workforce page has no ADO equivalent at all.
type AdoPage =
  | 'agent' | 'prs' | 'proposals' | 'portfolio' | 'stream'
  | 'workforce' | 'delivery' | 'roadmap' | 'flow';

export function AdoApp() {
  const [page, setPage] = useState<AdoPage>('agent');
  const [streamId, setStreamId] = useState<string | null>(null);
  const [sprintId, setSprintId] = useState<string | null>(null);
  const { data: streams = [] } = useStreams();

  const openStream = (id: string) => {
    setStreamId(id);
    setPage('stream');
  };

  const openSprint = (id: string | null) => {
    setSprintId(id);
    setPage('delivery');
  };

  const navItem = (id: AdoPage, label: string, Icon: typeof Bot) => (
    <button
      key={id}
      className={`sidebar-item ${page === id ? 'active' : ''}`}
      onClick={() => setPage(id)}
      aria-current={page === id ? 'page' : undefined}
    >
      <Icon size={20} strokeWidth={2.25} />
      <span>{label}</span>
    </button>
  );

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-header">
          <Logo sprint="Azure DevOps" />
        </div>

        <nav className="sidebar-nav" aria-label="Primary">
          <div className="sidebar-section">
            <button
              className={`sidebar-item ${page === 'agent' ? 'active' : ''}`}
              onClick={() => setPage('agent')}
              aria-current={page === 'agent' ? 'page' : undefined}
            >
              <Bot size={20} strokeWidth={2.25} />
              <span>AI Agent</span>
            </button>
            <button
              className={`sidebar-item ${page === 'prs' ? 'active' : ''}`}
              onClick={() => setPage('prs')}
              aria-current={page === 'prs' ? 'page' : undefined}
            >
              <GitPullRequest size={20} strokeWidth={2.25} />
              <span>PRs</span>
            </button>
            <button
              className={`sidebar-item ${page === 'proposals' ? 'active' : ''}`}
              onClick={() => setPage('proposals')}
              aria-current={page === 'proposals' ? 'page' : undefined}
            >
              <ClipboardCheck size={20} strokeWidth={2.25} />
              <span>Proposals</span>
            </button>
          </div>

          <div className="sidebar-section">
            <div className="sidebar-section-title">Delivery</div>
            {navItem('workforce', 'AI Workforce', Cpu)}
            {navItem('delivery', 'Sprint Dashboard', ChartNoAxesCombined)}
            {navItem('roadmap', 'Roadmap', Map)}
            {navItem('flow', 'Flow', Activity)}
          </div>

          <div className="sidebar-section">
            <div className="sidebar-section-title">Altitude</div>
            <button
              className={`sidebar-item ${page === 'portfolio' ? 'active' : ''}`}
              onClick={() => setPage('portfolio')}
              aria-current={page === 'portfolio' ? 'page' : undefined}
            >
              <Layers size={20} strokeWidth={2.25} />
              <span>Portfolio</span>
            </button>
            {streams.map((s) => {
              const active = page === 'stream' && streamId === s.id;
              return (
                <button
                  key={s.id}
                  className={`sidebar-item ${active ? 'active' : ''}`}
                  onClick={() => openStream(s.id)}
                  aria-current={active ? 'page' : undefined}
                >
                  <GitBranch size={18} strokeWidth={2.25} />
                  <span>{s.name}</span>
                </button>
              );
            })}
          </div>
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-status">
            <span className="status-dot online" />
            <span>API Connected</span>
          </div>
        </div>
      </aside>

      <main className="main">
        {page === 'agent' && <AgentPage />}
        {page === 'prs' && <PrsPage />}
        {page === 'proposals' && <ProposalsPage />}
        {page === 'portfolio' && <PortfolioView onOpenStream={openStream} />}
        {page === 'stream' && streamId && <StreamView streamId={streamId} />}
        {page === 'workforce' && <WorkforceView />}
        {page === 'delivery' && <SprintDashboard sprintId={sprintId} onSelectSprint={openSprint} />}
        {page === 'roadmap' && <RoadmapView streamId={streamId} onSelectStream={setStreamId} />}
        {page === 'flow' && <FlowView streamId={streamId} onSelectStream={setStreamId} />}
      </main>
    </div>
  );
}
