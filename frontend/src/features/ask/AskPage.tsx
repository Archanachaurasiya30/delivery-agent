import { useEffect, useRef, useState } from 'react';
import { Bot, MessageCircleQuestion, Send } from 'lucide-react';
import { useAskDeliveryManager } from '../../hooks/useApi';
import type { AskMessage } from '../../types';
import { Markdown } from '../../ui/Markdown';

const STARTERS = [
  'Which stream is most at risk right now?',
  'What did the AI workforce deliver this week?',
  'What decisions are waiting on me?',
  'Are the active sprints on track?',
];

/** Ask the Delivery Manager: a Q&A thread over a server-assembled snapshot of
 *  live delivery data. The last six turns ride along as history so follow-up
 *  questions keep their context. */
export function AskPage() {
  const ask = useAskDeliveryManager();

  const [thread, setThread] = useState<AskMessage[]>([]);
  const [input, setInput] = useState('');
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [thread, ask.isPending]);

  const submit = (raw: string) => {
    const question = raw.trim();
    if (!question || ask.isPending) return;
    const history = thread.slice(-6);
    setThread((t) => [...t, { role: 'user', content: question }]);
    setInput('');
    setError(null);
    ask.mutateAsync({ question, history })
      .then((res) => setThread((t) => [...t, { role: 'assistant', content: res.answer }]))
      .catch((e: any) => setError(e.message || 'The delivery manager could not answer.'));
  };

  return (
    <>
      <header className="header">
        <h1 className="header-title">Ask AI</h1>
      </header>

      <div className="content">
        <div className="ask-page">
          <div className="agent-intro">
            <div className="agent-intro-mark"><MessageCircleQuestion size={24} strokeWidth={2.25} /></div>
            <div>
              <div className="agent-intro-title">Ask the Delivery Manager</div>
              <div className="agent-intro-sub">
                Answers come from live delivery data — streams, sprints, agent runs, briefs, and open decisions.
              </div>
            </div>
          </div>

          {thread.length === 0 && !ask.isPending && (
            <div className="ask-chips">
              {STARTERS.map((q) => (
                <button key={q} className="ask-chip" onClick={() => submit(q)}>{q}</button>
              ))}
            </div>
          )}

          <div className="ask-thread" aria-live="polite">
            {thread.map((m, i) => (
              m.role === 'user' ? (
                <div key={i} className="ask-msg-user">{m.content}</div>
              ) : (
                <div key={i} className="ask-answer">
                  <div className="ask-answer-head">
                    <Bot size={14} strokeWidth={2.5} /> Delivery Manager
                  </div>
                  <div className="ask-answer-body"><Markdown text={m.content} /></div>
                </div>
              )
            ))}
            {ask.isPending && (
              <div className="ask-thinking">
                <span className="spinner" /> Thinking…
              </div>
            )}
            <div ref={endRef} />
          </div>

          {error && <div className="alert alert-error">{error}</div>}

          <div className="ask-inputbar">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  submit(input);
                }
              }}
              placeholder="Ask about delivery status, risks, the AI workforce… (Enter to send)"
              rows={2}
              aria-label="Ask the delivery manager"
            />
            <button
              className="ask-send"
              onClick={() => submit(input)}
              disabled={ask.isPending || !input.trim()}
              aria-label="Send question"
            >
              <Send size={16} strokeWidth={2.25} />
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
