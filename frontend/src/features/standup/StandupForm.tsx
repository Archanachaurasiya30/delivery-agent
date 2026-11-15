import { useEffect, useState } from 'react';
import { CheckCircle2, Sun } from 'lucide-react';
import { Button } from '../../ui/Button';
import { getStandupRound, setUserName, submitStandup, type StandupRound } from '../../lib/api';

// Standalone page opened from the standup link (?standup=<round>[&member=<id>]).
// Webex can't call back into a LAN deployment, so this form is how answers
// come in. No app chrome: it should work on a phone in 30 seconds.
export function StandupForm({ roundId, memberId }: { roundId: string; memberId: string | null }) {
  const [round, setRound] = useState<StandupRound | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [member, setMember] = useState(memberId || '');
  const [yesterday, setYesterday] = useState('');
  const [today, setToday] = useState('');
  const [blockers, setBlockers] = useState('');
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    getStandupRound(roundId).then(setRound).catch((e) => setError(e.message));
  }, [roundId]);

  const people = (round?.entries || [])
    .filter((e) => e.member_name)
    .sort((a, b) => (a.member_name || '').localeCompare(b.member_name || ''));
  const closed = round && round.status !== 'collecting';

  const submit = async () => {
    if (!member || !yesterday.trim() || !today.trim()) {
      setError('Pick your name and fill in yesterday and today.');
      return;
    }
    setSending(true);
    setError(null);
    try {
      await submitStandup(roundId, { member_id: member, yesterday, today, blockers });
      const name = people.find((p) => p.member_id === member)?.member_name;
      if (name) setUserName(name);
      setDone(true);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSending(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', display: 'flex', justifyContent: 'center', padding: '32px 16px' }}>
      <div className="card" style={{ width: '100%', maxWidth: 520, padding: 24, alignSelf: 'flex-start' }}>
        <h1 style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 22, margin: '0 0 4px' }}>
          <Sun size={22} strokeWidth={2.5} /> Daily standup
        </h1>
        <p style={{ color: 'var(--ink-mute)', margin: '0 0 20px', fontSize: 14 }}>
          Three quick answers. Your delivery manager gets an AI summary of the team's updates.
        </p>

        {done ? (
          <div className="alert alert-success"><CheckCircle2 size={18} strokeWidth={2.5} /> Thanks — your update is recorded.</div>
        ) : closed ? (
          <div className="alert alert-error">This standup is already closed.</div>
        ) : !round && !error ? (
          <p>Loading…</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <label className="form-label">Who are you?</label>
              <select className="form-select" style={{ width: '100%' }} value={member} onChange={(e) => setMember(e.target.value)} disabled={!!memberId && people.some((p) => p.member_id === memberId)}>
                <option value="">Select your name…</option>
                {people.map((p) => (
                  <option key={p.member_id} value={p.member_id}>{p.member_name}{p.completed ? ' (answered)' : ''}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="form-label">What did you finish yesterday?</label>
              <textarea className="form-textarea" style={{ width: '100%' }} rows={3} value={yesterday} onChange={(e) => setYesterday(e.target.value)} />
            </div>
            <div>
              <label className="form-label">What are you working on today?</label>
              <textarea className="form-textarea" style={{ width: '100%' }} rows={3} value={today} onChange={(e) => setToday(e.target.value)} />
            </div>
            <div>
              <label className="form-label">Anything blocking you? <span style={{ fontWeight: 400 }}>(leave empty if not)</span></label>
              <textarea className="form-textarea" style={{ width: '100%' }} rows={2} value={blockers} onChange={(e) => setBlockers(e.target.value)} />
            </div>
            {error && <div className="alert alert-error">{error}</div>}
            <Button variant="primary" onClick={submit} disabled={sending} style={{ justifyContent: 'center' }}>
              {sending ? 'Sending…' : 'Submit update'}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
