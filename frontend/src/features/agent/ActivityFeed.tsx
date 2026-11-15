import { ArrowRight, Loader, Check } from 'lucide-react';
import { getMemberInfo, type AgentStep } from '../../lib/helpers';

interface ActivityFeedProps {
  steps: AgentStep[];
  isRunning: boolean;
}

/** Live, append-only log of the agent's work — system lines + member replies. */
export function ActivityFeed({ steps, isRunning }: ActivityFeedProps) {
  if (steps.length === 0) return null;

  return (
    <div className="agent-activity">
      <div className="agent-activity-header">
        <div className="agent-activity-title">
          Agent Activity
          {isRunning && (
            <span className="live-indicator">
              <span className="live-dot" />
              Live
            </span>
          )}
        </div>
        <span className="agent-activity-count">{steps.length} events</span>
      </div>
      <div className="activity-feed">
        {steps.map((step, idx) => {
          const memberInfo = step.member ? getMemberInfo(step.member) : null;
          return (
            <div key={idx} className="activity-item">
              {step.type === 'sending' && (
                <div className="activity-sending">
                  <span className="activity-icon"><ArrowRight size={14} strokeWidth={2.5} /></span>
                  <span>{step.message || `Requesting update from ${step.member}...`}</span>
                </div>
              )}
              {step.type === 'response' && step.data && memberInfo && (
                <div className="activity-response">
                  <div className="activity-response-header">
                    <div className={`member-avatar ${memberInfo.teamClass}`}>{memberInfo.initials}</div>
                    <div className="member-info">
                      <div className="member-name">{step.member}</div>
                    </div>
                    <span className="activity-badge">Replied</span>
                  </div>
                  <div className="activity-response-body">
                    {step.data.yesterday && (
                      <>
                        <div className="response-line"><span>Yesterday</span> {step.data.yesterday}</div>
                        <div className="response-line"><span>Today</span> {step.data.today}</div>
                        {step.data.blockers && (
                          <div className="response-line blocker">
                            <span>Blocker</span>
                            {step.data.blockers}
                          </div>
                        )}
                      </>
                    )}
                    {step.data.itemCount !== undefined && (
                      <>
                        <div className="response-line"><span>Assigned</span> {step.data.itemCount} items ({step.data.inProgress} in progress)</div>
                        <div className="response-line"><span>Status</span> {step.data.blocker}</div>
                      </>
                    )}
                  </div>
                </div>
              )}
              {step.type === 'analyzing' && (
                <div className="activity-analyzing">
                  <span className="activity-icon"><Loader size={14} strokeWidth={2.5} /></span>
                  <span>{step.message}</span>
                </div>
              )}
              {step.type === 'complete' && (
                <div className="activity-complete">
                  <span className="activity-icon"><Check size={14} strokeWidth={3} /></span>
                  <span>{step.message}</span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
