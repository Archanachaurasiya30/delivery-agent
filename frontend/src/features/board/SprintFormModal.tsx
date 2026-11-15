import { useEffect, useState } from 'react';
import { CalendarRange } from 'lucide-react';
import { Modal } from '../../ui/Modal';
import { Button } from '../../ui/Button';
import { useCreateSprint, useSprints } from '../../hooks/useApi';

// Sprints are always two weeks: the window spans 14 calendar days, so the end
// date is start + 13 (inclusive). Matches the backend default in SprintCreate.
const SPRINT_LENGTH_DAYS = 13;

/** Today as a local-timezone YYYY-MM-DD (toISOString would shift near midnight). */
function todayISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function addDays(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

function fmtDate(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, {
    weekday: 'short', month: 'short', day: 'numeric',
  });
}

/** "Sprint 24" when the highest numbered existing sprint is "Sprint 23". */
function suggestName(names: string[]): string {
  let max = 0;
  for (const n of names) {
    const m = n.match(/(\d+)\s*$/);
    if (m) max = Math.max(max, parseInt(m[1], 10));
  }
  return `Sprint ${max + 1}`;
}

interface SprintFormModalProps {
  onClose: () => void;
}

/** Authoring form for a sprint. Only the start date is chosen — every sprint
 *  is a fixed two-week iteration, so the end date is derived, not edited. */
export function SprintFormModal({ onClose }: SprintFormModalProps) {
  const { data: sprints = [] } = useSprints();
  const createSprint = useCreateSprint();

  const suggestion = suggestName(sprints.map((s) => s.name));
  const [name, setName] = useState('');
  const [touched, setTouched] = useState(false);
  const [goal, setGoal] = useState('');
  const [startDate, setStartDate] = useState(todayISO);
  const [error, setError] = useState<string | null>(null);

  // Keep the suggested name in sync while sprints load, until the user types.
  useEffect(() => {
    if (!touched) setName(suggestion);
  }, [suggestion, touched]);

  const endDate = startDate ? addDays(startDate, SPRINT_LENGTH_DAYS) : '';
  const busy = createSprint.isPending;

  const submit = async () => {
    if (!name.trim()) { setError('Name is required'); return; }
    if (!startDate) { setError('Start date is required'); return; }
    setError(null);
    try {
      await createSprint.mutateAsync({
        name: name.trim(),
        goal: goal.trim() || null,
        start_date: startDate,
        end_date: endDate,
      });
      onClose();
    } catch (e: any) {
      setError(e.message || 'Failed to create sprint');
    }
  };

  return (
    <Modal
      title="New Sprint"
      onClose={onClose}
      width={480}
      footer={
        <>
          <span className="modal-foot-hint">Starts in planning — activate it when the team kicks off</span>
          <Button variant="secondary" onClick={onClose} disabled={busy}>Cancel</Button>
          <Button variant="primary" onClick={submit} disabled={busy || !name.trim()}>
            {busy ? 'Creating…' : 'Create Sprint'}
          </Button>
        </>
      }
    >
      <p className="form-modal-sub">Plan the next two-week iteration.</p>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>
      )}

      <div className="form-group">
        <label className="form-label">Name</label>
        <input
          className="form-input lead"
          value={name}
          onChange={(e) => { setTouched(true); setName(e.target.value); }}
          placeholder={suggestion}
          autoFocus
        />
      </div>

      <div className="form-group">
        <label className="form-label">Goal <span className="form-label-opt">optional</span></label>
        <textarea
          className="form-textarea"
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          placeholder="What should this sprint achieve?"
        />
      </div>

      <div className="form-group">
        <label className="form-label">Start date</label>
        <input
          className="form-input"
          type="date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
        />
      </div>

      {startDate && (
        <p style={{
          display: 'flex', alignItems: 'center', gap: 8,
          fontSize: 12.5, color: 'var(--ink-soft)', margin: '2px 0 0',
        }}>
          <CalendarRange size={15} strokeWidth={2.25} />
          <span>Two-week sprint · {fmtDate(startDate)} → <strong>{fmtDate(endDate)}</strong></span>
        </p>
      )}
    </Modal>
  );
}
