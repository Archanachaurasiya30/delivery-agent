import type { LucideIcon } from 'lucide-react';
import { ArrowRight } from 'lucide-react';

export interface AgentAction {
  type: string;
  Icon: LucideIcon;
  color: string;
  title: string;
  desc: string;
}

interface AgentCardProps {
  action: AgentAction;
  isRunning: boolean;
  activeAction: string | null;
  onRun: (type: string) => void;
}

export function AgentCard({ action, isRunning, activeAction, onRun }: AgentCardProps) {
  const { type, Icon, color, title, desc } = action;
  const isActive = activeAction === type;
  return (
    <button
      className={`agent-card ${isActive ? 'active' : ''}`}
      onClick={() => onRun(type)}
      disabled={isRunning}
      style={{ opacity: isRunning && !isActive ? 0.5 : 1 }}
    >
      <div className="agent-icon" style={{ background: color }}>
        <Icon size={26} strokeWidth={2.25} color="var(--surface)" />
      </div>
      <div className="agent-title">
        {title}
        {isActive && <span className="agent-status-dot" />}
      </div>
      <div className="agent-desc">{desc}</div>
      <div className="agent-card-footer">
        <span className="agent-card-action">
          {isRunning && isActive ? 'Processing…' : <>Run Agent <ArrowRight size={13} strokeWidth={2.5} /></>}
        </span>
      </div>
    </button>
  );
}
