import { useEffect, useMemo, useRef, useState } from 'react';
import { useSprints, useTasks } from '../hooks/useApi';
import type { Sprint } from '../types';

interface SprintSwitcherProps {
  /** null = no sprint filter ("All sprints"). */
  sprintId: string | null;
  onSelectSprint: (id: string | null) => void;
}

/** A sprint plus the numbers we show beside it. */
interface Row {
  id: string | null;          // null = the "All sprints" row
  name: string;
  dates: string;
  items: number;
  hours: number;
  group: 'active' | 'upcoming' | 'completed';
  dayTotal?: number;          // only for an in-flight sprint
  dayLeft?: number;
  elapsed?: number;
  overdue?: boolean;
}

const DAY_MS = 86_400_000;

const asDate = (iso: string) => new Date(`${iso.slice(0, 10)}T00:00:00`);

/** "16–27 Aug", or "21 Jun–5 Jul" when the sprint straddles a month. */
function formatRange(start: string, end: string): string {
  const s = asDate(start);
  const e = asDate(end);
  const month = (d: Date) => d.toLocaleString('en', { month: 'short' });
  return s.getMonth() === e.getMonth()
    ? `${s.getDate()}–${e.getDate()} ${month(e)}`
    : `${s.getDate()} ${month(s)}–${e.getDate()} ${month(e)}`;
}

/**
 * Sprint length in days, and how many remain.
 *
 * "Days left" is counted to the end date, matching what the Sprint Dashboard
 * already reports — the two must not disagree by a day. `overdue` covers a
 * sprint still flagged active after its end date has passed, where showing
 * "0d left" against a full rail reads as a bug rather than as late.
 */
function dayProgress(start: string, end: string) {
  const s = asDate(start).getTime();
  const e = asDate(end).getTime();
  const today = new Date();
  const now = new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime();
  const dayTotal = Math.max(1, Math.round((e - s) / DAY_MS) + 1);
  const dayLeft = Math.max(0, Math.round((e - now) / DAY_MS));
  return {
    dayTotal,
    dayLeft,
    elapsed: Math.min(dayTotal, Math.max(0, dayTotal - dayLeft)),
    overdue: now > e,
  };
}

/** Case-insensitive match, returning the name split around the hit. */
function splitMatch(name: string, q: string): [string, string, string] | null {
  if (!q) return null;
  const i = name.toLowerCase().indexOf(q.toLowerCase());
  return i < 0 ? null : [name.slice(0, i), name.slice(i, i + q.length), name.slice(i + q.length)];
}

const GROUP_LABEL: Record<Row['group'], string> = {
  active: 'Active',
  upcoming: 'Upcoming',
  completed: 'Completed',
};

/**
 * Global sprint selector, shown under the wordmark in the sidebar.
 *
 * Drives the board, the backlog and the sprint dashboard from one place, so
 * "which sprint am I looking at" is answered once rather than per view.
 *
 * Deliberately not a native <select>: the option list there is OS chrome and
 * cannot carry the dates, item counts and hours that make one sprint
 * distinguishable from another. Design: Open Design project
 * "delivery-agent-sprint-switcher".
 */
export function SprintSwitcher({ sprintId, onSelectSprint }: SprintSwitcherProps) {
  const { data: sprints = [] } = useSprints();
  const { data: tasks = [] } = useTasks();

  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [focusId, setFocusId] = useState<string | null>(null);

  const rootRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  // Per-sprint item counts and hours, derived from the tasks already loaded
  // for the board — no extra request.
  const stats = useMemo(() => {
    const m = new Map<string, { items: number; hours: number }>();
    for (const t of tasks) {
      if (!t.sprint_id) continue;
      const e = m.get(t.sprint_id) ?? { items: 0, hours: 0 };
      e.items += 1;
      e.hours += t.estimated_hours ?? 0;
      m.set(t.sprint_id, e);
    }
    return m;
  }, [tasks]);

  const rows: Row[] = useMemo(() => {
    const toRow = (s: Sprint): Row => {
      const st = stats.get(s.id) ?? { items: 0, hours: 0 };
      const group: Row['group'] =
        s.status === 'active' ? 'active' : s.status === 'planning' ? 'upcoming' : 'completed';
      const row: Row = {
        id: s.id,
        name: s.name,
        dates: formatRange(s.start_date, s.end_date),
        items: st.items,
        hours: st.hours,
        group,
      };
      if (group === 'active') {
        const { dayTotal, dayLeft, elapsed, overdue } = dayProgress(s.start_date, s.end_date);
        row.dayTotal = dayTotal;
        row.dayLeft = dayLeft;
        row.elapsed = elapsed;
        row.overdue = overdue;
      }
      return row;
    };
    // Newest first — a real instance accumulates a long tail of finished ones.
    return [...sprints]
      .sort((a, b) => b.start_date.localeCompare(a.start_date))
      .map(toRow);
  }, [sprints, stats]);

  const allRow: Row = {
    id: null,
    name: 'All sprints',
    dates: '',
    items: tasks.length,
    hours: 0,
    group: 'active',
  };

  const q = query.trim();
  const matches = (r: Row) => !q || r.name.toLowerCase().includes(q.toLowerCase());
  const showAll = !q || matches(allRow);

  const grouped = (['active', 'upcoming', 'completed'] as const).map((g) => ({
    group: g,
    rows: rows.filter((r) => r.group === g && matches(r)),
  })).filter((s) => s.rows.length > 0);

  // Flat visible order — what arrow keys walk.
  const visible: Row[] = [...(showAll ? [allRow] : []), ...grouped.flatMap((s) => s.rows)];
  const shown = visible.length - (showAll ? 1 : 0);

  // Magnitude bars are relative to the biggest sprint in view, so 200 vs 8
  // reads without parsing digits.
  const magMax = Math.max(1, ...rows.map((r) => r.items));

  const selected = sprintId === null ? allRow : rows.find((r) => r.id === sprintId) ?? allRow;

  const keyOf = (r: Row) => r.id ?? '__all__';
  const focusKey =
    focusId !== null && visible.some((r) => keyOf(r) === focusId) ? focusId : keyOf(visible[0] ?? allRow);

  // Close on outside click.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [open]);

  // Keep the keyboard-focused row inside the scroll port. offsetTop maths
  // rather than scrollIntoView, which would also scroll the whole sidebar.
  useEffect(() => {
    if (!open || !listRef.current) return;
    const el = listRef.current.querySelector<HTMLElement>('.swx-row.is-focus');
    if (!el) return;
    const list = listRef.current;
    const top = el.offsetTop;
    const bottom = top + el.offsetHeight;
    const pad = 26; // clears the sticky group header
    if (top - pad < list.scrollTop) list.scrollTop = Math.max(0, top - pad);
    else if (bottom > list.scrollTop + list.clientHeight) {
      list.scrollTop = bottom - list.clientHeight + 6;
    }
  }, [focusKey, open, query]);

  const openList = () => {
    setQuery('');
    setFocusId(keyOf(selected));
    setOpen(true);
    requestAnimationFrame(() => inputRef.current?.focus());
  };

  const choose = (r: Row) => {
    onSelectSprint(r.id);
    setOpen(false);
    triggerRef.current?.focus();
  };

  const move = (step: number) => {
    if (visible.length === 0) return;
    const i = Math.max(0, visible.findIndex((r) => keyOf(r) === focusKey));
    const next = Math.min(visible.length - 1, Math.max(0, i + step));
    setFocusId(keyOf(visible[next]));
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    switch (e.key) {
      case 'ArrowDown': e.preventDefault(); move(1); break;
      case 'ArrowUp': e.preventDefault(); move(-1); break;
      case 'Home': e.preventDefault(); move(-9999); break;
      case 'End': e.preventDefault(); move(9999); break;
      case 'Enter': {
        e.preventDefault();
        const r = visible.find((x) => keyOf(x) === focusKey);
        if (r) choose(r);
        break;
      }
      case 'Escape': e.preventDefault(); setOpen(false); triggerRef.current?.focus(); break;
      case 'Tab': setOpen(false); break;
    }
  };

  if (sprints.length === 0) return null;

  const rail = (total: number, elapsed: number) => (
    <span className="swx-rail" aria-hidden="true">
      {Array.from({ length: total }, (_, i) => (
        <span key={i} className={i < elapsed ? 'on' : undefined} />
      ))}
    </span>
  );

  const renderRow = (r: Row) => {
    const isAll = r.id === null;
    const key = keyOf(r);
    const isSelected = (selected.id ?? null) === r.id;
    const parts = splitMatch(r.name, q);
    return (
      <div
        key={key}
        id={`swx-opt-${key}`}
        role="option"
        aria-selected={isSelected}
        className={`swx-row${isAll ? ' swx-row-all' : ''}${key === focusKey ? ' is-focus' : ''}`}
        onClick={() => choose(r)}
        onMouseEnter={() => setFocusId(key)}
      >
        <span className="swx-check">
          {isSelected && (
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
              <path d="M2.4 6.3 4.7 8.6 9.6 3.6" stroke="currentColor" strokeWidth="1.7"
                strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          )}
        </span>
        <span className="swx-main">
          <span className="swx-name">
            {parts ? (<>{parts[0]}<mark>{parts[1]}</mark>{parts[2]}</>) : r.name}
          </span>
          {isAll ? (
            <span className="swx-meta">Every sprint <i>·</i> {rows.length} total</span>
          ) : (
            <>
              <span className="swx-meta">{r.dates} <i>·</i> {r.hours}h</span>
              {r.dayTotal !== undefined && !r.overdue && (
                <span className="swx-prog">
                  {rail(r.dayTotal, r.elapsed ?? 0)}
                  <span className="swx-left">{r.dayLeft}d left</span>
                </span>
              )}
              {r.overdue && (
                <span className="swx-prog"><span className="swx-pill swx-late">Overdue</span></span>
              )}
            </>
          )}
        </span>
        <span className="swx-num">
          <b>{r.items}</b>
          {isAll ? (
            <small>items</small>
          ) : (
            <span className="swx-mag">
              <u style={{ width: `${Math.max(3, Math.round((r.items / magMax) * 100))}%` }} />
            </span>
          )}
        </span>
      </div>
    );
  };

  return (
    <div className="swx" data-open={open} ref={rootRef}>
      <button
        type="button"
        ref={triggerRef}
        className="swx-trigger"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => (open ? setOpen(false) : openList())}
        onKeyDown={(e) => {
          if (!open && (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ')) {
            e.preventDefault();
            openList();
          }
        }}
      >
        <span className="swx-top">
          <span
            className="swx-dot"
            data-state={selected.id === null ? 'all' : selected.group === 'active' ? 'active' : 'done'}
          />
          <span className="swx-tname">{selected.name}</span>
          <svg className="swx-chev" width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
            <path d="M3.1 4.7 6 7.6l2.9-2.9" stroke="currentColor" strokeWidth="1.45"
              strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
        <span className="swx-tmeta">
          {selected.id === null
            ? <>{rows.length} sprints <i>·</i> {selected.items} items</>
            : <>{selected.dates} <i>·</i> {selected.items} items <i>·</i> {selected.hours}h</>}
        </span>
        <span className="swx-tfoot">
          {selected.id !== null && selected.dayTotal !== undefined && !selected.overdue ? (
            <>
              {rail(selected.dayTotal, selected.elapsed ?? 0)}
              <span className="swx-tleft">{selected.dayLeft}d left</span>
            </>
          ) : (
            <span className={`swx-pill${selected.overdue ? ' swx-late' : ''}`}>
              {selected.id === null ? 'No sprint filter'
                : selected.overdue ? 'Overdue'
                : selected.group === 'completed' ? 'Completed' : 'Active'}
            </span>
          )}
        </span>
      </button>

      {open && (
        <div className="swx-pop" onKeyDown={onKeyDown}>
          <div className="swx-search">
            <svg width="13" height="13" viewBox="0 0 14 14" fill="none" aria-hidden="true">
              <circle cx="6.2" cy="6.2" r="3.9" stroke="currentColor" strokeWidth="1.35" />
              <path d="M9.2 9.2 12 12" stroke="currentColor" strokeWidth="1.35" strokeLinecap="round" />
            </svg>
            <input
              ref={inputRef}
              type="text"
              autoComplete="off"
              spellCheck={false}
              role="combobox"
              aria-expanded
              aria-autocomplete="list"
              aria-label="Filter sprints"
              aria-activedescendant={`swx-opt-${focusKey}`}
              placeholder={`Filter ${rows.length} sprints…`}
              value={query}
              onChange={(e) => { setQuery(e.target.value); setFocusId(null); }}
            />
            {q && (
              <button type="button" className="swx-clear" aria-label="Clear filter" tabIndex={-1}
                onClick={() => { setQuery(''); setFocusId(null); inputRef.current?.focus(); }}>
                <svg width="8" height="8" viewBox="0 0 8 8" fill="none" aria-hidden="true">
                  <path d="M1.6 1.6 6.4 6.4M6.4 1.6 1.6 6.4" stroke="currentColor"
                    strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              </button>
            )}
          </div>

          <div className="swx-list" ref={listRef} role="listbox" aria-label="Sprints">
            {visible.length === 0 ? (
              <div className="swx-empty">
                <b>No sprints match “{q}”</b>
                Try a sprint number, or part of its name.
              </div>
            ) : (
              <>
                {showAll && (<>{renderRow(allRow)}<div className="swx-sep" /></>)}
                {grouped.map(({ group, rows: gr }) => (
                  <div key={group} role="group" aria-label={`${GROUP_LABEL[group]} sprints`}>
                    <div className="swx-ghead">{GROUP_LABEL[group]} <b>{gr.length}</b></div>
                    {gr.map(renderRow)}
                  </div>
                ))}
              </>
            )}
          </div>

          <div className="swx-foot">
            <span>
              {q
                ? `${shown} of ${rows.length} sprints match “${q}”`
                : `${rows.length} sprints · ${tasks.length} items`}
            </span>
            <span className="swx-hint">
              <kbd>↑</kbd><kbd>↓</kbd> move <kbd>↵</kbd> select <kbd>esc</kbd> close
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
