import { useState, useEffect } from 'react';
import { RefreshCw, Brain, Gauge, ClipboardList, Hourglass, Wrench, CheckCircle2, Check, X, ClipboardCheck, GitPullRequest, GitMerge } from 'lucide-react';
import { Button } from '../../ui/Button';
import { Badge, type Tone } from '../../ui/Badge';
import { Modal } from '../../ui/Modal';
import { EmptyState } from '../../ui/EmptyState';
import { apiFetch, mergeCodingRun, reviseCodingRun } from '../../lib/api';

type Proposal = {
  id: string;
  type: string;
  state: string;
  content: any;
  reasoning: string | null;
  confidence: string | null;
  created_by_agent: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
  execution_result?: Record<string, any> | null;
};

const STATE_TONE: Record<string, Tone> = {
  approved: 'success',
  rejected: 'danger',
  pending_review: 'orange',
  draft: 'neutral',
  executed: 'blue',
  failed: 'danger',
};

const STATE_LABEL: Record<string, string> = {
  pending_review: 'Pending Review',
  approved: 'Approved',
  rejected: 'Rejected',
  draft: 'Draft',
  executed: 'Executed',
  failed: 'Failed',
};

const FILTERS = ['all', 'pending_review', 'approved', 'rejected', 'draft'];

const stateLabel = (s: string) => STATE_LABEL[s] || s;
const stateTone = (s: string) => STATE_TONE[s] || 'neutral';
const confidenceTone = (c: string): Tone => (c === 'high' ? 'success' : c === 'medium' ? 'orange' : 'danger');
const formatDate = (d: string) => new Date(d).toLocaleString();

export function ProposalsPage() {
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedProposal, setSelectedProposal] = useState<Proposal | null>(null);
  const [filter, setFilter] = useState<string>('all');
  const [actionLoading, setActionLoading] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [modalMode, setModalMode] = useState<'reject' | 'request_changes'>('reject');

  const fetchProposals = async (filterState: string) => {
    setLoading(true);
    setError(null);
    try {
      const url = filterState === 'all' ? '/api/v1/agent/proposals' : `/api/v1/agent/proposals?state=${filterState}`;
      const response = await apiFetch(url);
      if (!response.ok) throw new Error('Failed to fetch proposals');
      const data = await response.json();
      setProposals(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProposals(filter);
  }, [filter]);

  const handleFilterChange = (newFilter: string) => {
    setFilter(newFilter);
    setSelectedProposal(null);
  };

  const approveProposal = async (id: string) => {
    setActionLoading(true);
    try {
      const response = await apiFetch(`/api/v1/agent/proposals/${id}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Failed to approve');
      }
      await fetchProposals(filter);
      setSelectedProposal(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const rejectProposal = async (id: string) => {
    if (!rejectReason.trim()) {
      setError('Please provide a reason for rejection');
      return;
    }
    setActionLoading(true);
    try {
      const response = await apiFetch(`/api/v1/agent/proposals/${id}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: rejectReason }),
      });
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Failed to reject');
      }
      await fetchProposals(filter);
      setSelectedProposal(null);
      setShowRejectModal(false);
      setRejectReason('');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const isCodingPr = (p: Proposal) => p.type === 'coding_pr';

  // Merge the PR represented by an approved coding_pr proposal. This is the
  // explicit, deliberate act that lands the change — separate from approval.
  const mergePr = async (p: Proposal) => {
    const runId = (p.content as any)?.run_id;
    if (!runId) { setError('No coding run linked to this proposal'); return; }
    setActionLoading(true);
    try {
      await mergeCodingRun(runId);
      await fetchProposals(filter);
      setSelectedProposal(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  // "Request changes" drives the bounded revise loop instead of rejecting.
  const requestChanges = async (p: Proposal) => {
    const runId = (p.content as any)?.run_id;
    if (!runId) { setError('No coding run linked to this proposal'); return; }
    if (!rejectReason.trim()) { setError('Please describe the changes to make'); return; }
    setActionLoading(true);
    try {
      await reviseCodingRun(runId, rejectReason);
      await fetchProposals(filter);
      setSelectedProposal(null);
      setShowRejectModal(false);
      setRejectReason('');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <>
      <header className="header">
        <h1 className="header-title">Agent Proposals</h1>
        <div className="header-actions">
          <Button variant="ghost" onClick={() => fetchProposals(filter)} disabled={loading} icon={<RefreshCw size={15} strokeWidth={2.5} className={loading ? 'spin-inline' : ''} />}>
            Refresh
          </Button>
        </div>
      </header>

      <div className="content">
        {error && (
          <div className="alert alert-error" style={{ marginBottom: 16 }}>
            <X size={16} strokeWidth={2.5} />
            <span style={{ flex: 1 }}>{error}</span>
            <button onClick={() => setError(null)} aria-label="Dismiss error" style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit', display: 'flex' }}>
              <X size={16} strokeWidth={2.5} />
            </button>
          </div>
        )}

        <div className="proposal-filters">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => handleFilterChange(f)}
              className={`header-tab ${filter === f ? 'active' : ''}`}
            >
              {f === 'all' ? 'All' : stateLabel(f)}
            </button>
          ))}
        </div>

        <div className="proposal-layout">
          {/* List */}
          <div className="proposal-list">
            {loading ? (
              <EmptyState>Loading proposals…</EmptyState>
            ) : proposals.length === 0 ? (
              <EmptyState>No proposals found</EmptyState>
            ) : (
              proposals.map((p) => (
                <div
                  key={p.id}
                  onClick={() => setSelectedProposal(p)}
                  className={`proposal-row ${selectedProposal?.id === p.id ? 'selected' : ''}`}
                >
                  <div className="proposal-row-top">
                    <span className="proposal-type">{p.type.replace(/_/g, ' ')}</span>
                    <Badge tone={stateTone(p.state)}>{stateLabel(p.state)}</Badge>
                  </div>
                  <div className="proposal-meta">{formatDate(p.created_at)}</div>
                  {p.confidence && <div className="proposal-meta" style={{ marginTop: 4 }}>Confidence: {p.confidence}</div>}
                </div>
              ))
            )}
          </div>

          {/* Detail */}
          <div style={{ flex: 2 }}>
            {selectedProposal ? (
              <div className="proposal-detail">
                <div className="proposal-detail-section">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
                    <div>
                      <h2>{selectedProposal.type.replace(/_/g, ' ')}</h2>
                      <div className="proposal-meta" style={{ marginTop: 8 }}>Created: {formatDate(selectedProposal.created_at)}</div>
                      {selectedProposal.created_by_agent && (
                        <div className="proposal-meta">Agent: {selectedProposal.created_by_agent}</div>
                      )}
                    </div>
                    <Badge tone={stateTone(selectedProposal.state)}>{stateLabel(selectedProposal.state)}</Badge>
                  </div>
                </div>

                {selectedProposal.reasoning && (
                  <div className="proposal-detail-section">
                    <h3><Brain size={16} strokeWidth={2.5} /> Reasoning</h3>
                    <p style={{ fontSize: 13, color: 'var(--ink-soft)', lineHeight: 1.6 }}>{selectedProposal.reasoning}</p>
                  </div>
                )}

                {selectedProposal.confidence && (
                  <div className="proposal-detail-section">
                    <h3><Gauge size={16} strokeWidth={2.5} /> Confidence</h3>
                    <Badge tone={confidenceTone(selectedProposal.confidence)}>{selectedProposal.confidence}</Badge>
                  </div>
                )}

                {isCodingPr(selectedProposal) && selectedProposal.content && (() => {
                  const c: any = selectedProposal.content;
                  return (
                    <div className="proposal-detail-section">
                      <h3><GitPullRequest size={16} strokeWidth={2.5} /> Pull Request</h3>
                      <div style={{ fontSize: 13, color: 'var(--ink-soft)', display: 'flex', flexDirection: 'column', gap: 4 }}>
                        {c.branch && <div>Branch: <span className="mono">{c.branch}</span></div>}
                        {c.pr_url && <div>PR: <a href={c.pr_url} target="_blank" rel="noreferrer">{c.pr_url}</a></div>}
                        {c.diff_summary && <div>{c.diff_summary}</div>}
                      </div>
                      {c.diff && (
                        <pre className="proposal-pre" style={{ marginTop: 10, maxHeight: 240, overflow: 'auto' }}>{c.diff}</pre>
                      )}
                    </div>
                  );
                })()}

                {!isCodingPr(selectedProposal) && selectedProposal.content && (() => {
                  const c: any = selectedProposal.content;
                  const agentText: string | null = typeof c?.content === 'string' ? c.content : null;
                  const toolCalls: any[] = Array.isArray(c?.tool_calls) ? c.tool_calls : [];
                  // A proposal that hasn't been processed yet only carries the
                  // original request payload — there's no agent output to show.
                  const isUnprocessed = agentText === null && c?.request_payload !== undefined;

                  return (
                    <div className="proposal-detail-section">
                      <h3><ClipboardList size={16} strokeWidth={2.5} /> Proposal</h3>

                      {isUnprocessed ? (
                        <div className="proposal-pre" style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--ink-mute)' }}>
                          <Hourglass size={14} strokeWidth={2.5} />
                          <span>Waiting for the agent to process this request. Refresh in a few seconds.</span>
                        </div>
                      ) : agentText !== null ? (
                        <div className="proposal-pre">{agentText}</div>
                      ) : (
                        <pre className="proposal-pre">{JSON.stringify(c, null, 2)}</pre>
                      )}

                      {toolCalls.length > 0 && (
                        <div style={{ marginTop: 12 }}>
                          <div className="form-label" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <Wrench size={12} strokeWidth={2.5} /> Data the agent pulled
                          </div>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                            {toolCalls.map((tc: any, i: number) => (
                              <span key={i} className="toolcall-chip">{tc?.name || 'tool'}()</span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })()}

                {selectedProposal.reviewed_by && (
                  <div className="proposal-detail-section">
                    <h3><CheckCircle2 size={16} strokeWidth={2.5} /> Review</h3>
                    <div style={{ fontSize: 13, color: 'var(--ink-soft)' }}>Reviewed by: {selectedProposal.reviewed_by}</div>
                    {selectedProposal.reviewed_at && <div className="proposal-meta">{formatDate(selectedProposal.reviewed_at)}</div>}
                    <ExecutionResult result={selectedProposal.execution_result} />
                  </div>
                )}

                {selectedProposal.state === 'pending_review' && (
                  <div className="proposal-detail-section" style={{ display: 'flex', gap: 12 }}>
                    <Button variant="success" onClick={() => approveProposal(selectedProposal.id)} disabled={actionLoading} icon={<Check size={15} strokeWidth={3} />} style={{ flex: 1, justifyContent: 'center' }}>
                      Approve
                    </Button>
                    {isCodingPr(selectedProposal) ? (
                      <Button variant="secondary" onClick={() => { setModalMode('request_changes'); setShowRejectModal(true); }} disabled={actionLoading} icon={<Wrench size={15} strokeWidth={2.5} />} style={{ flex: 1, justifyContent: 'center' }}>
                        Request changes
                      </Button>
                    ) : (
                      <Button variant="danger" onClick={() => { setModalMode('reject'); setShowRejectModal(true); }} disabled={actionLoading} icon={<X size={15} strokeWidth={3} />} style={{ flex: 1, justifyContent: 'center' }}>
                        Reject
                      </Button>
                    )}
                  </div>
                )}

                {isCodingPr(selectedProposal) && selectedProposal.state === 'approved' && (
                  <div className="proposal-detail-section" style={{ display: 'flex', gap: 12 }}>
                    <Button variant="success" onClick={() => mergePr(selectedProposal)} disabled={actionLoading} icon={<GitMerge size={15} strokeWidth={2.5} />} style={{ flex: 1, justifyContent: 'center' }}>
                      Merge PR
                    </Button>
                  </div>
                )}
              </div>
            ) : (
              <div className="proposal-detail" style={{ padding: 60 }}>
                <EmptyState icon={<ClipboardCheck size={44} strokeWidth={1.75} />}>Select a proposal to view details</EmptyState>
              </div>
            )}
          </div>
        </div>

        {showRejectModal && selectedProposal && (() => {
          const changes = modalMode === 'request_changes';
          return (
            <Modal
              title={changes ? 'Request Changes' : 'Reject Proposal'}
              onClose={() => { setShowRejectModal(false); setRejectReason(''); }}
              footer={
                <>
                  <Button variant="secondary" onClick={() => { setShowRejectModal(false); setRejectReason(''); }}>Cancel</Button>
                  <Button
                    variant={changes ? 'primary' : 'danger'}
                    onClick={() => changes ? requestChanges(selectedProposal) : rejectProposal(selectedProposal.id)}
                    disabled={actionLoading || !rejectReason.trim()}
                  >
                    {changes ? 'Request changes' : 'Reject'}
                  </Button>
                </>
              }
            >
              <p style={{ fontSize: 13, color: 'var(--ink-soft)', marginBottom: 14 }}>
                {changes
                  ? 'Describe the changes the agent should make. It will revise the PR (bounded by the iteration cap) and re-run CI.'
                  : 'Please provide a reason for rejecting this proposal:'}
              </p>
              <textarea
                className="form-textarea"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder={changes ? 'e.g. Add a null check and a test for the empty case…' : 'Enter rejection reason…'}
                style={{ minHeight: 110, resize: 'vertical' }}
              />
            </Modal>
          );
        })()}
      </div>
    </>
  );
}

// What approving actually did (Webex notifications sent, ADO checklist, …).
function ExecutionResult({ result }: { result?: Record<string, any> | null }) {
  if (!result) return null;
  const list = (label: string, items?: string[]) =>
    items && items.length > 0 ? (
      <div style={{ marginTop: 6 }}>
        <strong>{label}:</strong>
        <ul style={{ margin: '4px 0 0 18px' }}>{items.map((x, i) => <li key={i}>{x}</li>)}</ul>
      </div>
    ) : null;
  return (
    <div style={{ fontSize: 13, color: 'var(--ink-soft)', marginTop: 10 }}>
      {result.rejection_reason && <div>Reason: {result.rejection_reason}</div>}
      {result.approval_reason && <div>Note: {result.approval_reason}</div>}
      {result.action === 'notify_owners' && (
        <>
          <div>Webex: notified {result.sent?.length || 0} owner(s).</div>
          {list('Notified', result.sent)}
          {list('Skipped', result.skipped)}
          {list('Failed', result.failed)}
        </>
      )}
      {result.action === 'apply_in_ado' && (
        <div style={{ marginTop: 6 }}>
          <strong>Apply in Azure DevOps{result.targetSprint ? ` → ${result.targetSprint}` : ''}:</strong>
          <ul style={{ margin: '4px 0 0 18px' }}>
            {(result.items || []).map((it: any, i: number) => (
              <li key={i}>{it.url ? <a href={it.url} target="_blank" rel="noreferrer">{it.item}</a> : it.item} {it.title}</li>
            ))}
          </ul>
        </div>
      )}
      {result.note && <div style={{ marginTop: 6 }}>{result.note}</div>}
      {result.error && <div style={{ color: 'var(--danger)' }}>Execution error: {result.error}</div>}
    </div>
  );
}
