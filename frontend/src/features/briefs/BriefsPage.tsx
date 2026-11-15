import { useState } from 'react';
import {
  AlertTriangle, Bot, ClipboardCheck, Clock, FileText, Newspaper, Rocket, Sparkles,
} from 'lucide-react';
import { useBriefs, useGenerateBrief } from '../../hooks/useApi';
import type { Brief } from '../../types';
import { Button } from '../../ui/Button';
import { EmptyState } from '../../ui/EmptyState';
import { Markdown } from '../../ui/Markdown';
import { relTime } from '../coding/runStatus';

function briefDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
}

const list = (v?: string[]): string[] => (Array.isArray(v) ? v : []);

function ListSection({
  Icon, title, items, listClass = 'recommendation-list',
}: { Icon: typeof Rocket; title: string; items: string[]; listClass?: string }) {
  if (items.length === 0) return null;
  return (
    <div className="report-section">
      <h4><Icon size={17} strokeWidth={2.5} /> {title} ({items.length})</h4>
      <ul className={listClass}>{items.map((item, i) => <li key={i}><Markdown text={String(item)} /></li>)}</ul>
    </div>
  );
}

function BriefReader({ brief }: { brief: Brief }) {
  const content = brief.content ?? {};
  const numbers = Object.entries(content.numbers ?? {}).slice(0, 4);
  return (
    <div className="agent-report">
      <div className="report-header">
        <div className="report-title">
          <span className="report-icon"><Newspaper size={28} strokeWidth={2} /></span>
          <div>
            <h3>{brief.headline}</h3>
            <span className="report-id">{briefDate(brief.brief_date)}</span>
          </div>
        </div>
        <span className="report-time"><Clock size={14} strokeWidth={2.5} /> {relTime(brief.created_at)}</span>
      </div>

      {numbers.length > 0 && (
        <div className="report-stats" style={{ gridTemplateColumns: `repeat(${numbers.length}, 1fr)` }}>
          {numbers.map(([key, value]) => (
            <div key={key} className="report-stat">
              <div className="report-stat-value">{String(value)}</div>
              <div className="report-stat-label" style={{ textTransform: 'capitalize' }}>
                {key.replace(/_/g, ' ')}
              </div>
            </div>
          ))}
        </div>
      )}

      <ListSection Icon={Rocket} title="Shipped" items={list(content.shipped)} />
      <ListSection Icon={Bot} title="AI delivered" items={list(content.ai_delivered)} />
      <ListSection Icon={AlertTriangle} title="Risks" items={list(content.risks)} listClass="risk-list" />
      <ListSection Icon={ClipboardCheck} title="Needs decision" items={list(content.needs_decision)} />

      {content.narrative && (
        <div className="report-section">
          <h4><FileText size={17} strokeWidth={2.5} /> Narrative</h4>
          <div style={{ color: 'var(--ink)', lineHeight: 1.7, fontSize: 14 }}>
            <Markdown text={String(content.narrative)} />
          </div>
        </div>
      )}
    </div>
  );
}

/** Daily morning briefs: a date rail on the left, the selected brief rendered
 *  as a report on the right, and an on-demand "Generate now". */
export function BriefsPage() {
  const { data: briefs = [], isPending } = useBriefs();
  const generate = useGenerateBrief();

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selected = briefs.find((b) => b.id === selectedId) ?? briefs[0];

  const generateNow = () => {
    setError(null);
    generate.mutateAsync()
      .then((b) => setSelectedId(b.id))
      .catch((e: any) => setError(e.message || 'Failed to generate brief'));
  };

  return (
    <>
      <header className="header">
        <h1 className="header-title">Briefs</h1>
        <div className="header-actions">
          <Button
            variant="primary"
            disabled={generate.isPending}
            onClick={generateNow}
            icon={generate.isPending
              ? <span className="spinner" />
              : <Sparkles size={15} strokeWidth={2.5} />}
          >
            {generate.isPending ? 'Generating…' : 'Generate now'}
          </Button>
        </div>
      </header>

      <div className="content">
        {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

        {isPending ? (
          <EmptyState>Loading briefs…</EmptyState>
        ) : briefs.length === 0 ? (
          <EmptyState icon={<Newspaper size={28} strokeWidth={1.75} />}>
            No briefs yet — the agent writes one every morning, or generate the first one now.
          </EmptyState>
        ) : (
          <div className="briefs-layout">
            <div className="briefs-rail">
              {briefs.map((b) => (
                <button
                  key={b.id}
                  className={`brief-rail-item ${selected?.id === b.id ? 'active' : ''}`}
                  onClick={() => setSelectedId(b.id)}
                >
                  <div className="brief-rail-date">{briefDate(b.brief_date)}</div>
                  <div className="brief-rail-headline">{b.headline}</div>
                </button>
              ))}
            </div>
            {selected && <BriefReader brief={selected} />}
          </div>
        )}
      </div>
    </>
  );
}
