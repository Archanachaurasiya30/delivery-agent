import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { ChevronDown, Search, Check, Plus } from 'lucide-react';

export interface ComboOption {
  value: string;
  label: string;
  hint?: string;
}

export interface ComboGroup {
  label: string;
  options: ComboOption[];
}

interface ComboboxProps {
  value: string;
  onChange: (value: string) => void;
  /** Flat options (use this OR groups). */
  options?: ComboOption[];
  /** Grouped options, rendered with section headers. */
  groups?: ComboGroup[];
  /** First selectable row mapping to value="" (e.g. "— No feature —"). */
  noneLabel?: string;
  placeholder?: string;
  searchPlaceholder?: string;
  emptyLabel?: string;
  allowCreate?: boolean;
  createLabel?: (q: string) => string;
  /** Returns the value to select for the freshly-created entry. */
  onCreate?: (name: string) => Promise<string>;
  placement?: 'bottom' | 'top';
  leading?: ReactNode;
  disabled?: boolean;
}

interface Section {
  label?: string;
  options: ComboOption[];
}

/**
 * Searchable single-select with optional inline "create". Used for Feature
 * (grouped by stream) and Repository (flat + add-new) in the authoring form.
 * Self-contained: click-outside + Escape close, arrow-key navigation, no deps
 * beyond lucide icons.
 */
export function Combobox({
  value, onChange, options, groups, noneLabel, placeholder = 'Select…',
  searchPlaceholder = 'Search…', emptyLabel = 'No matches', allowCreate = false,
  createLabel = (q) => `Create “${q}”`, onCreate, placement = 'bottom', leading, disabled,
}: ComboboxProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const [creating, setCreating] = useState(false);
  // Labels for values created during this session (until the source refetches).
  const [created, setCreated] = useState<Record<string, string>>({});

  // Normalize input into sections, with an optional leading "none" row.
  const sections: Section[] = useMemo(() => {
    const base: Section[] = groups
      ? groups.map((g) => ({ label: g.label, options: g.options }))
      : [{ options: options ?? [] }];
    if (noneLabel) return [{ options: [{ value: '', label: noneLabel }] }, ...base];
    return base;
  }, [groups, options, noneLabel]);

  const allOptions = useMemo(() => sections.flatMap((s) => s.options), [sections]);

  const labelFor = (v: string): string | null => {
    if (!v) return noneLabel ?? null;
    const found = allOptions.find((o) => o.value === v);
    return found?.label ?? created[v] ?? null;
  };

  const q = query.trim().toLowerCase();
  const filtered: Section[] = useMemo(() => {
    if (!q) return sections;
    return sections
      .map((s) => ({ ...s, options: s.options.filter((o) => o.label.toLowerCase().includes(q)) }))
      .filter((s) => s.options.length > 0);
  }, [sections, q]);

  const flat = useMemo(() => filtered.flatMap((s) => s.options), [filtered]);
  const exactMatch = allOptions.some((o) => o.label.toLowerCase() === q);
  const showCreate = allowCreate && q.length > 0 && !exactMatch;
  const rowCount = flat.length + (showCreate ? 1 : 0);

  useEffect(() => {
    if (open) {
      setQuery('');
      setActive(0);
      const t = setTimeout(() => searchRef.current?.focus(), 0);
      return () => clearTimeout(t);
    }
  }, [open]);

  useEffect(() => { setActive(0); }, [query]);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [open]);

  const pick = (v: string) => { onChange(v); setOpen(false); };

  const doCreate = async () => {
    if (!onCreate || creating) return;
    const name = query.trim();
    if (!name) return;
    setCreating(true);
    try {
      const v = await onCreate(name);
      setCreated((prev) => ({ ...prev, [v]: name }));
      onChange(v);
      setOpen(false);
    } catch {
      // Creation failed — keep the panel open so the user can retry; error
      // surfacing is the caller's job (e.g. the form's error banner).
    } finally {
      setCreating(false);
    }
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') { setOpen(false); return; }
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, rowCount - 1)); return; }
    if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); return; }
    if (e.key === 'Enter') {
      e.preventDefault();
      if (active < flat.length) pick(flat[active].value);
      else if (showCreate) doCreate();
    }
  };

  const selectedLabel = labelFor(value);
  let idx = -1; // running index across rendered options for keyboard highlight

  return (
    <div className={`combo ${disabled ? 'is-disabled' : ''}`} ref={rootRef}>
      <button
        type="button"
        className={`combo-trigger ${open ? 'open' : ''}`}
        onClick={() => !disabled && setOpen((o) => !o)}
        disabled={disabled}
      >
        {leading && <span className="combo-leading">{leading}</span>}
        <span className={`combo-value ${value ? '' : 'placeholder'}`}>
          {selectedLabel ?? placeholder}
        </span>
        <ChevronDown size={15} strokeWidth={2.25} className="combo-chevron" />
      </button>

      {open && (
        <div className={`combo-panel ${placement}`} role="listbox">
          <div className="combo-search">
            <Search size={14} strokeWidth={2.25} />
            <input
              ref={searchRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder={searchPlaceholder}
            />
          </div>

          <div className="combo-list">
            {flat.length === 0 && !showCreate && (
              <div className="combo-empty">{emptyLabel}</div>
            )}

            {filtered.map((section, si) => (
              <div key={section.label ?? `s${si}`}>
                {section.label && <div className="combo-group-label">{section.label}</div>}
                {section.options.map((o) => {
                  idx += 1;
                  const myIdx = idx;
                  const selected = o.value === value;
                  return (
                    <div
                      key={o.value || '__none__'}
                      className={`combo-option ${myIdx === active ? 'active' : ''} ${selected ? 'selected' : ''}`}
                      onMouseEnter={() => setActive(myIdx)}
                      onClick={() => pick(o.value)}
                      role="option"
                      aria-selected={selected}
                    >
                      <span className="combo-option-label">{o.label}</span>
                      {o.hint && <span className="combo-option-hint">{o.hint}</span>}
                      {selected && <Check size={15} strokeWidth={2.5} className="check" />}
                    </div>
                  );
                })}
              </div>
            ))}

            {showCreate && (
              <div
                className={`combo-create ${active === flat.length ? 'active' : ''}`}
                onMouseEnter={() => setActive(flat.length)}
                onClick={doCreate}
              >
                <Plus size={15} strokeWidth={2.5} />
                <span>{creating ? 'Creating…' : createLabel(query.trim())}</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
