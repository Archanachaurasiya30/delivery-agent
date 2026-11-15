import { useState, type ReactNode } from 'react';
import {
  Target, AlertTriangle, Rocket, Sun, Zap, History, X, Clock, Users, Lightbulb,
  ListChecks, CheckSquare, FileText, Check, Sparkles, TrendingUp, Bug, ClipboardList,
  MessageSquare, ChevronDown, Timer, Bot, ExternalLink, Link2,
} from 'lucide-react';
import { getMemberInfo, type AgentStep } from '../../lib/helpers';
import { apiFetch, runAnalysis } from '../../lib/api';
import { ActivityFeed } from './ActivityFeed';
import { AgentCard, type AgentAction } from './AgentCard';

const ACTIONS: AgentAction[] = [
  { type: 'sprint_planning', Icon: Target, color: 'var(--accent-2)', title: 'Sprint Planning', desc: 'Propose the next sprint from the real backlog, recent velocity and each person\'s remaining capacity.' },
  { type: 'blocker_detection', Icon: AlertTriangle, color: 'var(--orange)', title: 'Detect Blockers', desc: 'Find On Hold, tagged-blocked and stuck items in Azure DevOps and suggest who can unblock them.' },
  { type: 'release_management', Icon: Rocket, color: 'var(--success)', title: 'Release Assessment', desc: 'Go/no-go for the current sprint: completion, open bugs, holds, and a changelog from done items.' },
  { type: 'standup', Icon: Sun, color: 'var(--pink)', title: 'Daily Standup', desc: 'Open a standup, share the link (also sent on Webex), and get an AI summary of the answers.' },
];

const RELEASE_STATUS_COLORS: Record<string, string> = {
  READY: 'var(--success)',
  READY_WITH_CAVEATS: 'var(--orange)',
  NOT_READY: 'var(--danger)',
};

const ANALYSIS_STEPS: Record<string, string[]> = {
  sprint_planning: ['Reading the backlog from Azure DevOps sync…', 'Measuring recent velocity and remaining capacity…', 'Asking the AI to pick and rank items…'],
  blocker_detection: ['Scanning in-progress and waiting items…', 'Checking On Hold states, tags and time in state…', 'Asking the AI for next actions…'],
  release_management: ['Loading the current sprint…', 'Checking completion, open bugs and holds…', 'Writing the go/no-go recommendation…'],
};

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
const fmtDate = (iso?: string) => (iso ? new Date(iso).toLocaleString() : '');

function ItemLink({ label, url }: { label: string; url?: string | null }) {
  if (!url) return <span className="mono" style={{ color: 'var(--accent-2)', fontWeight: 600 }}>{label}</span>;
  return (
    <a href={url} target="_blank" rel="noreferrer" className="mono" style={{ color: 'var(--accent-2)', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 3 }}>
      {label} <ExternalLink size={11} strokeWidth={2.5} />
    </a>
  );
}

export function AgentPage() {
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [finalReport, setFinalReport] = useState<any>(null);
  const [activeAction, setActiveAction] = useState<string | null>(null);
  const [aiError, setAiError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'actions' | 'history'>('actions');
  const [collapsedSections, setCollapsedSections] = useState<Record<string, boolean>>({});
  const [savedMsg, setSavedMsg] = useState<string | null>(null);
  const [standupLink, setStandupLink] = useState<{ roundId: string; url: string } | null>(null);
  const [closeRequested, setCloseRequested] = useState(false);

  const toggleSection = (section: string) => {
    setCollapsedSections((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  const flashSaved = () => {
    setSavedMsg('Saved to Proposals ✓');
    setTimeout(() => setSavedMsg(null), 4000);
  };

  // Sprint planning / blockers / release: the backend computes the report from
  // the synced Azure DevOps data and saves it as a pending proposal.
  const runBackendAnalysis = async (kind: 'sprint_planning' | 'blocker_detection' | 'release_management') => {
    setIsRunning(true);
    setActiveAction(kind);
    setFinalReport(null);
    setAiError(null);
    setStandupLink(null);

    const allSteps: AgentStep[] = [{ type: 'sending', message: 'Starting analysis on live Azure DevOps data…' }];
    setSteps([...allSteps]);
    let done = false;
    const narrate = (async () => {
      for (const msg of ANALYSIS_STEPS[kind]) {
        await delay(900);
        if (done) return;
        allSteps.push({ type: 'analyzing', message: msg });
        setSteps([...allSteps]);
      }
    })();

    try {
      const { report } = await runAnalysis(kind);
      done = true;
      await narrate;
      if (report.aiNote) setAiError(report.aiNote);
      allSteps.push({ type: 'complete', message: `Done — data as of ${fmtDate(report.dataAsOf)}` });
      setSteps([...allSteps]);
      if (kind === 'blocker_detection') setFinalReport({ type: 'blocker', data: report });
      if (kind === 'sprint_planning') setFinalReport({ type: 'sprint', data: report });
      if (kind === 'release_management') {
        setFinalReport({ type: 'release', data: { ...report, statusColor: RELEASE_STATUS_COLORS[report.status] || 'var(--danger)' } });
      }
      flashSaved();
    } catch (err: any) {
      done = true;
      setAiError(err.message || 'Analysis failed');
      allSteps.push({ type: 'analyzing', message: `Failed: ${err.message || 'unknown error'}` });
      setSteps([...allSteps]);
    } finally {
      setIsRunning(false);
      setActiveAction(null);
    }
  };

  // Standup: open a round, share the form link (also DM'd on Webex when
  // configured), poll until it closes and the AI summary is ready. The backend
  // saves the summary as a proposal itself.
  const runStandup = async () => {
    setIsRunning(true);
    setActiveAction('standup');
    setSteps([]);
    setFinalReport(null);
    setAiError(null);
    setCloseRequested(false);

    const allSteps: AgentStep[] = [{ type: 'sending', message: 'Opening a standup round…' }];
    setSteps([...allSteps]);

    let roundId: string;
    let expected: number;
    try {
      const res = await apiFetch('/api/v1/standup/start', { method: 'POST' });
      if (!res.ok) throw new Error(`start failed: ${res.status}`);
      const data = await res.json();
      roundId = data.round_id;
      expected = data.expected_count;
    } catch (err: any) {
      setAiError(`Could not start the standup: ${err.message}`);
      setIsRunning(false);
      setActiveAction(null);
      return;
    }

    const url = `${window.location.origin}/?standup=${roundId}`;
    setStandupLink({ roundId, url });
    allSteps.push({ type: 'sending', message: `Standup open for ${expected} team member(s). Share the link above — people with a Webex email also get it as a DM.` });
    setSteps([...allSteps]);

    // Rounds auto-close after the server cutoff (30 min by default); poll a bit longer.
    let round: any = null;
    for (let i = 0; i < 1260; i++) {
      await delay(2000);
      const r = await apiFetch(`/api/v1/standup/rounds/${roundId}`);
      if (!r.ok) continue;
      round = await r.json();
      const answered = (round.entries || []).filter((e: any) => e.completed).length;
      const status = round.status === 'collecting' ? 'collecting' : round.status === 'analyzed' ? 'done' : round.status;
      setSteps([...allSteps, { type: 'analyzing', message: `${answered}/${expected} answered (${status})` }]);
      if (round.status === 'analyzed' || round.status === 'failed') break;
    }

    setStandupLink(null);
    if (!round || round.status !== 'analyzed') {
      setAiError(round?.status === 'failed' ? 'Standup analysis failed — check the backend logs.' : 'Standup did not finish in time.');
      setIsRunning(false);
      setActiveAction(null);
      return;
    }

    const s = round.summary || {};
    const members = s.members || [];
    const aiBlockers = Array.isArray(s.blockers) ? s.blockers : [];
    setFinalReport({
      id: 'STANDUP-' + roundId.slice(0, 8),
      timestamp: new Date().toLocaleString(),
      summary: {
        totalMembers: expected,
        responded: members.filter((m: any) => m.responded).length,
        blockersFound: aiBlockers.length,
        itemsInProgress: members.filter((m: any) => m.today).length,
      },
      blockers: aiBlockers.map((b: any) => ({ severity: 'Medium', suggestedAction: '', ...b })),
      teamUpdates: members.filter((m: any) => m.responded).map((m: any) => ({
        member: m.member, yesterday: m.yesterday, today: m.today, hasBlocker: !!m.blockers,
      })),
      risks: Array.isArray(s.risks) ? s.risks : [],
      recommendations: Array.isArray(s.recommendations) ? s.recommendations : [],
      aiSummary: s.summary || '',
    });
    setSteps([...allSteps, { type: 'complete', message: 'Standup complete!' }]);
    flashSaved();
    setIsRunning(false);
    setActiveAction(null);
  };

  const closeStandupNow = async () => {
    if (!standupLink) return;
    setCloseRequested(true);
    await apiFetch(`/api/v1/standup/rounds/${standupLink.roundId}/close`, { method: 'POST' }).catch(() => null);
  };

  const runAgent = (type: string) => {
    switch (type) {
      case 'standup': runStandup(); break;
      case 'blocker_detection':
      case 'sprint_planning':
      case 'release_management':
        runBackendAnalysis(type); break;
    }
  };

  const Toggle = ({ id, children }: { id: string; children: ReactNode }) => (
    <button className={`report-section-toggle ${collapsedSections[id] ? 'collapsed' : ''}`} onClick={() => toggleSection(id)}>
      <h4>{children}</h4>
      <span className="toggle-icon"><ChevronDown size={16} strokeWidth={2.5} /></span>
    </button>
  );

  return (
    <>
      <header className="header">
        <h1 className="header-title">AI Agent</h1>
        {isRunning && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, fontWeight: 600 }}>
            <span className="spinner" /> Agent is working…
          </div>
        )}
        {savedMsg && !isRunning && (
          <span className="agent-connected" style={{ color: 'var(--success)', borderColor: 'var(--success)' }}>{savedMsg}</span>
        )}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 16 }}>
          <div className="agent-tabs">
            <button className={`agent-tab ${activeTab === 'actions' ? 'active' : ''}`} onClick={() => setActiveTab('actions')}>
              <span className="agent-tab-icon"><Zap size={15} strokeWidth={2.5} /></span> Actions
            </button>
            <button className={`agent-tab ${activeTab === 'history' ? 'active' : ''}`} onClick={() => setActiveTab('history')}>
              <span className="agent-tab-icon"><History size={15} strokeWidth={2.5} /></span> History
            </button>
          </div>
          <span className="agent-connected">
            <span className="status-dot online" /> AI Connected
          </span>
        </div>
      </header>

      <div className="content">
        <div className="agent-page">
          {/* Intro */}
          <div className="agent-intro">
            <div className="agent-intro-mark"><Bot size={24} strokeWidth={2.25} /></div>
            <div>
              <div className="agent-intro-title">AI-Powered Delivery Assistant</div>
              <div className="agent-intro-sub">Every report is computed from your synced <strong>Azure DevOps</strong> data; the AI only ranks and suggests. Results land in Proposals for approval.</div>
            </div>
          </div>

          {aiError && (
            <div className="alert alert-error">
              <AlertTriangle size={18} strokeWidth={2.5} />
              <span style={{ flex: 1 }}>{aiError}</span>
              <button onClick={() => setAiError(null)} aria-label="Dismiss error" style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit', display: 'flex' }}>
                <X size={16} strokeWidth={2.5} />
              </button>
            </div>
          )}

          {standupLink && (
            <div className="alert alert-success" style={{ flexWrap: 'wrap' }}>
              <Link2 size={18} strokeWidth={2.5} />
              <span style={{ flex: 1, minWidth: 0, overflowWrap: 'anywhere' }}>
                Standup link: <a href={standupLink.url} target="_blank" rel="noreferrer">{standupLink.url}</a>
              </span>
              <button className="btn btn-secondary" onClick={() => navigator.clipboard?.writeText(standupLink.url)}>Copy</button>
              <button className="btn btn-primary" disabled={closeRequested} onClick={closeStandupNow}>
                {closeRequested ? 'Closing…' : 'Close & summarize now'}
              </button>
            </div>
          )}

          {/* Action cards */}
          <div className="agent-grid">
            {ACTIONS.map((a) => (
              <AgentCard key={a.type} action={a} isRunning={isRunning} activeAction={activeAction} onRun={runAgent} />
            ))}
          </div>

          <ActivityFeed steps={steps} isRunning={isRunning} />

          {/* Final Report - Standup */}
          {finalReport && !finalReport.type && (
            <div className="agent-report">
              <div className="report-header">
                <div className="report-title">
                  <span className="report-icon"><ClipboardList size={28} strokeWidth={2} /></span>
                  <div>
                    <h3>Daily Standup Report</h3>
                    <span className="report-id">{finalReport.id}</span>
                  </div>
                </div>
                <span className="report-time"><Clock size={14} strokeWidth={2.5} /> {finalReport.timestamp}</span>
              </div>

              <div className="report-stats">
                <div className="report-stat"><div className="report-stat-value">{finalReport.summary.totalMembers}</div><div className="report-stat-label">Team Members</div></div>
                <div className="report-stat"><div className="report-stat-value">{finalReport.summary.responded}</div><div className="report-stat-label">Responded</div></div>
                <div className="report-stat"><div className="report-stat-value" style={{ color: finalReport.summary.blockersFound > 0 ? 'var(--danger)' : 'var(--success)' }}>{finalReport.summary.blockersFound}</div><div className="report-stat-label">Blockers</div></div>
                <div className="report-stat"><div className="report-stat-value">{finalReport.summary.itemsInProgress}</div><div className="report-stat-label">Working Today</div></div>
              </div>

              {finalReport.blockers.length > 0 && (
                <div className="report-section">
                  <Toggle id="blockers"><AlertTriangle size={17} strokeWidth={2.5} /> Blockers Requiring Attention ({finalReport.blockers.length})</Toggle>
                  {!collapsedSections['blockers'] && (
                    <div className="report-section-content">
                      {finalReport.blockers.map((b: any, i: number) => {
                        const memberInfo = getMemberInfo(b.member);
                        return (
                          <div key={i} className="blocker-card">
                            <div className="blocker-header">
                              <span className="blocker-member">
                                <span className={`member-avatar ${memberInfo.teamClass}`} style={{ width: 28, height: 28, fontSize: 11 }}>{memberInfo.initials}</span>
                                {b.member}
                              </span>
                              <span className={`blocker-severity ${String(b.severity).toLowerCase()}`}>{b.severity}</span>
                            </div>
                            <div className="blocker-issue">{b.issue}</div>
                            <div className="blocker-action"><Lightbulb size={15} strokeWidth={2.5} /> {b.suggestedAction}</div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              <div className="report-section">
                <Toggle id="updates"><Users size={17} strokeWidth={2.5} /> Team Updates ({finalReport.teamUpdates.length})</Toggle>
                {!collapsedSections['updates'] && (
                  <div className="report-section-content">
                    <div className="team-updates">
                      {finalReport.teamUpdates.map((update: any, i: number) => {
                        const memberInfo = getMemberInfo(update.member);
                        return (
                          <div key={i} className={`team-update ${update.hasBlocker ? 'has-blocker' : ''}`}>
                            <div className="update-header">
                              <div className={`member-avatar ${memberInfo.teamClass}`}>{memberInfo.initials}</div>
                              <div>
                                <div className="update-member">{update.member}</div>
                              </div>
                            </div>
                            <div className="update-content">
                              <div><strong>Yesterday:</strong> {update.yesterday}</div>
                              <div><strong>Today:</strong> {update.today}</div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>

              {finalReport.risks.length > 0 && (
                <div className="report-section">
                  <Toggle id="risks"><AlertTriangle size={17} strokeWidth={2.5} /> Risks ({finalReport.risks.length})</Toggle>
                  {!collapsedSections['risks'] && (
                    <div className="report-section-content">
                      <ul className="risk-list">{finalReport.risks.map((risk: string, i: number) => <li key={i}>{risk}</li>)}</ul>
                    </div>
                  )}
                </div>
              )}

              <div className="report-section">
                <Toggle id="recommendations"><Lightbulb size={17} strokeWidth={2.5} /> Recommendations ({finalReport.recommendations.length})</Toggle>
                {!collapsedSections['recommendations'] && (
                  <div className="report-section-content">
                    <ul className="recommendation-list">{finalReport.recommendations.map((rec: string, i: number) => <li key={i}>{rec}</li>)}</ul>
                  </div>
                )}
              </div>

              {finalReport.aiSummary && (
                <div className="report-section">
                  <h4><Bot size={17} strokeWidth={2.5} /> AI Summary</h4>
                  <p style={{ color: 'var(--ink)', lineHeight: 1.7, fontSize: 14 }}>{finalReport.aiSummary}</p>
                </div>
              )}
            </div>
          )}

          {/* Final Report - Blocker */}
          {finalReport?.type === 'blocker' && (
            <div className="agent-report">
              <div className="report-header">
                <div className="report-title">
                  <span className="report-icon" style={{ background: 'var(--danger)' }}><AlertTriangle size={28} strokeWidth={2} color="var(--surface)" /></span>
                  <div>
                    <h3>Blocker Analysis Report</h3>
                    <span className="report-id">{finalReport.data.id}</span>
                  </div>
                </div>
                <span className="report-time"><Clock size={14} strokeWidth={2.5} /> Data as of {fmtDate(finalReport.data.dataAsOf)}</span>
              </div>

              <div className="report-stats">
                <div className="report-stat"><div className="report-stat-value" style={{ color: 'var(--danger)' }}>{finalReport.data.summary.totalBlockers}</div><div className="report-stat-label">Total Blockers</div></div>
                <div className="report-stat"><div className="report-stat-value" style={{ color: 'var(--danger)' }}>{finalReport.data.summary.critical}</div><div className="report-stat-label">Critical</div></div>
                <div className="report-stat"><div className="report-stat-value" style={{ color: 'var(--orange)' }}>{finalReport.data.summary.medium}</div><div className="report-stat-label">Medium</div></div>
                <div className="report-stat"><div className="report-stat-value" style={{ color: 'var(--success)' }}>{finalReport.data.summary.low}</div><div className="report-stat-label">Low</div></div>
              </div>

              <div className="report-section">
                <Toggle id="activeBlockers"><AlertTriangle size={17} strokeWidth={2.5} /> Active Blockers ({finalReport.data.blockers.length})</Toggle>
                {!collapsedSections['activeBlockers'] && (
                  <div className="report-section-content">
                    {finalReport.data.blockers.map((b: any) => {
                      const memberInfo = getMemberInfo(b.member);
                      return (
                        <div key={b.id} className="blocker-card detailed">
                          <div className="blocker-header">
                            <span className="blocker-id">{b.id}</span>
                            <span className="blocker-type">{b.type}</span>
                            <span className={`blocker-severity ${String(b.severity).toLowerCase()}`}>{b.severity}</span>
                          </div>
                          <div className="blocker-details">
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <span className={`member-avatar ${memberInfo.teamClass}`} style={{ width: 24, height: 24, fontSize: 10 }}>{memberInfo.initials}</span>
                              <strong>{b.member}</strong>
                              <span style={{ color: 'var(--ink-mute)' }}>•</span>
                              <ItemLink label={b.item} url={b.url} />
                            </div>
                            {b.title && <div style={{ fontWeight: 600, marginTop: 4 }}>{b.title}</div>}
                            <div className="blocker-issue">{b.description}</div>
                            <div className="blocker-meta">
                              <Timer size={13} strokeWidth={2.5} /> {b.daysBlocked} day(s) in this state
                              {b.helper && <> · could help: <strong>{b.helper}</strong></>}
                            </div>
                          </div>
                          <div className="blocker-action"><Lightbulb size={15} strokeWidth={2.5} /> {b.suggestedAction}</div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {finalReport.data.aiSummary && (
                <p style={{ color: 'var(--ink)', lineHeight: 1.7, fontSize: 14 }}>{finalReport.data.aiSummary}</p>
              )}

              <div className="report-section">
                <Toggle id="blockerRecommendations"><Lightbulb size={17} strokeWidth={2.5} /> Recommended Actions ({finalReport.data.recommendations.length})</Toggle>
                {!collapsedSections['blockerRecommendations'] && (
                  <div className="report-section-content">
                    <ul className="recommendation-list">{finalReport.data.recommendations.map((rec: string, i: number) => <li key={i}>{rec}</li>)}</ul>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Final Report - Sprint */}
          {finalReport?.type === 'sprint' && (
            <div className="agent-report">
              <div className="report-header">
                <div className="report-title">
                  <span className="report-icon" style={{ background: 'var(--accent-2)' }}><Target size={28} strokeWidth={2} color="var(--surface)" /></span>
                  <div>
                    <h3>Sprint Planning Proposal</h3>
                    <span className="report-id">{finalReport.data.id}</span>
                  </div>
                </div>
                <span className="report-time"><Clock size={14} strokeWidth={2.5} /> Data as of {fmtDate(finalReport.data.dataAsOf)}</span>
              </div>

              <div className="sprint-goal">
                <strong>{finalReport.data.targetSprint || 'Next sprint'} goal:</strong> {finalReport.data.sprintGoal}
                {finalReport.data.velocity?.average != null && (
                  <span style={{ display: 'block', fontSize: 13, color: 'var(--ink-mute)', marginTop: 4 }}>
                    Recent velocity: {finalReport.data.velocity.recentSprints.join(', ')} items/sprint (avg {finalReport.data.velocity.average})
                  </span>
                )}
              </div>

              <div className="report-stats">
                <div className="report-stat"><div className="report-stat-value">{finalReport.data.capacity.total}h</div><div className="report-stat-label">Total Capacity</div></div>
                <div className="report-stat"><div className="report-stat-value" style={{ color: 'var(--success)' }}>{finalReport.data.capacity.available}h</div><div className="report-stat-label">Available</div></div>
                <div className="report-stat"><div className="report-stat-value">{finalReport.data.capacity.utilization}%</div><div className="report-stat-label">Utilization</div></div>
                <div className="report-stat"><div className="report-stat-value">{finalReport.data.proposedItems.length}</div><div className="report-stat-label">Proposed Items</div></div>
              </div>

              <div className="report-section">
                <Toggle id="sprintItems"><ListChecks size={17} strokeWidth={2.5} /> Proposed Sprint Items ({finalReport.data.proposedItems.length})</Toggle>
                {!collapsedSections['sprintItems'] && (
                  <div className="report-section-content">
                    <div className="proposed-items">
                      {finalReport.data.proposedItems.map((item: any) => (
                        <div key={item.id} className="proposed-item" title={item.reason || ''}>
                          <span className="item-id"><ItemLink label={item.id} url={item.url} /></span>
                          <span className="item-title">
                            {item.title}
                            {(item.assignee || item.reason) && (
                              <span style={{ display: 'block', fontSize: 12, color: 'var(--ink-mute)', fontWeight: 400 }}>
                                {[item.assignee, item.reason].filter(Boolean).join(' — ')}
                              </span>
                            )}
                          </span>
                          <span className={`item-priority ${String(item.priority).toLowerCase()}`}>{item.priority}</span>
                          <span className="item-hours">{item.hours ? `${item.hours}h` : item.points ? `${item.points}pt` : '—'}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {finalReport.data.warnings.length > 0 && (
                <div className="report-section">
                  <Toggle id="capacityWarnings"><AlertTriangle size={17} strokeWidth={2.5} /> Capacity Warnings ({finalReport.data.warnings.length})</Toggle>
                  {!collapsedSections['capacityWarnings'] && (
                    <div className="report-section-content">
                      {finalReport.data.warnings.map((w: any, i: number) => {
                        const memberInfo = getMemberInfo(w.member);
                        return (
                          <div key={i} className="warning-card" style={{ display: 'flex', alignItems: 'flex-start', gap: 12, padding: 16 }}>
                            <span className={`member-avatar ${memberInfo.teamClass}`} style={{ width: 36, height: 36, fontSize: 12, flexShrink: 0 }}>{memberInfo.initials}</span>
                            <div style={{ flex: 1 }}>
                              <div>
                                {w.type === 'Over Capacity'
                                  ? <><strong>{w.member}</strong> is over capacity ({w.current}h / {w.capacity}h)</>
                                  : <><strong>{w.type}:</strong> {w.member}</>}
                              </div>
                              <div className="warning-action" style={{ marginTop: 8 }}><Lightbulb size={14} strokeWidth={2.5} /> {w.action}</div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              <div className="report-section">
                <Toggle id="sprintRecommendations"><Lightbulb size={17} strokeWidth={2.5} /> Recommendations ({finalReport.data.recommendations.length})</Toggle>
                {!collapsedSections['sprintRecommendations'] && (
                  <div className="report-section-content">
                    <ul className="recommendation-list">{finalReport.data.recommendations.map((rec: string, i: number) => <li key={i}>{rec}</li>)}</ul>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Final Report - Release */}
          {finalReport?.type === 'release' && (
            <div className="agent-report">
              <div className="report-header">
                <div className="report-title">
                  <span className="report-icon" style={{ background: 'var(--success)' }}><Rocket size={28} strokeWidth={2} color="var(--surface)" /></span>
                  <div>
                    <h3>Release Assessment</h3>
                    <span className="report-id">{finalReport.data.id}</span>
                  </div>
                </div>
                <div className="release-status" style={{ background: finalReport.data.statusColor }}>
                  {finalReport.data.status.replace(/_/g, ' ')}
                </div>
              </div>

              <div className="report-stats">
                <div className="report-stat"><div className="report-stat-value" style={{ color: 'var(--success)' }}>{finalReport.data.summary.completed}</div><div className="report-stat-label">Completed</div></div>
                <div className="report-stat"><div className="report-stat-value" style={{ color: 'var(--orange)' }}>{finalReport.data.summary.inReview}</div><div className="report-stat-label">In Review</div></div>
                <div className="report-stat"><div className="report-stat-value" style={{ color: 'var(--danger)' }}>{finalReport.data.summary.blockers}</div><div className="report-stat-label">Blockers</div></div>
                <div className="report-stat"><div className="report-stat-value">{finalReport.data.summary.openBugs}</div><div className="report-stat-label">Open Bugs</div></div>
              </div>

              <div className="report-section">
                <Toggle id="releaseChecklist"><CheckSquare size={17} strokeWidth={2.5} /> Release Checklist ({finalReport.data.checklist.length})</Toggle>
                {!collapsedSections['releaseChecklist'] && (
                  <div className="report-section-content">
                    <div className="checklist">
                      {finalReport.data.checklist.map((item: any, i: number) => (
                        <div key={i} className={`checklist-item ${item.status ? 'passed' : 'failed'}`}>
                          <span className="checklist-icon">{item.status ? <Check size={15} strokeWidth={3} /> : <X size={15} strokeWidth={3} />}</span>
                          <span className="checklist-text">{item.item}</span>
                          <span className="checklist-note">{item.note}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div className="report-section">
                <Toggle id="changelog"><FileText size={17} strokeWidth={2.5} /> Changelog</Toggle>
                {!collapsedSections['changelog'] && (
                  <div className="report-section-content">
                    <div className="changelog">
                      <div className="changelog-section">
                        <h5><Sparkles size={14} strokeWidth={2.5} /> Features</h5>
                        <ul>{finalReport.data.changelog.features.map((f: string, i: number) => <li key={i}>{f}</li>)}</ul>
                      </div>
                      <div className="changelog-section">
                        <h5><TrendingUp size={14} strokeWidth={2.5} /> Improvements</h5>
                        <ul>{finalReport.data.changelog.improvements.map((f: string, i: number) => <li key={i}>{f}</li>)}</ul>
                      </div>
                      <div className="changelog-section">
                        <h5><Bug size={14} strokeWidth={2.5} /> Fixes</h5>
                        <ul>{finalReport.data.changelog.fixes.map((f: string, i: number) => <li key={i}>{f}</li>)}</ul>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {finalReport.data.blockers.length > 0 && (
                <div className="report-section">
                  <Toggle id="releaseBlockers"><AlertTriangle size={17} strokeWidth={2.5} /> Release Blockers ({finalReport.data.blockers.length})</Toggle>
                  {!collapsedSections['releaseBlockers'] && (
                    <div className="report-section-content">
                      <ul className="risk-list">
                        {finalReport.data.blockers.map((b: any, i: number) => (
                          <li key={i}>
                            {b.url ? <a href={b.url} target="_blank" rel="noreferrer">{b.issue}</a> : b.issue} — {b.impact} ({b.owner})
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              <div className="report-recommendation"><MessageSquare size={20} strokeWidth={2.5} /> {finalReport.data.recommendation}</div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
