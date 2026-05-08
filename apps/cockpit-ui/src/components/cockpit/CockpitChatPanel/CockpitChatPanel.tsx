// CockpitChatPanel — Story 6.8 / AC #4.
//
// Mounted at the bottom of the Agent Copilot Pane. Transcript above,
// composer below. Agent messages are tinted with the chat-agent's hue
// (orange-50/60); user messages are zinc-100. Citations
// (`led_<ULID>`) render inline as ProvenancePill chips when they
// resolve in the case ledger; broken citations render as red error
// chips. Click on a resolved citation opens the reasoning trace
// slide-out (currently routed through the same callback shape used by
// other case-canvas surfaces).

import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { useCockpitChat, type ChatMessage } from '@/hooks/useCockpitChat';
import { parseCitations } from './parseCitations';

export interface CockpitChatPanelProps {
  caseId: string;
  onCitationClick?: (ledgerId: string) => void;
}

const _EMPTY_HINT = "Ask Cockpit Chat about this case — try 'explain why screening is amber'";

export function CockpitChatPanel({ caseId, onCitationClick }: CockpitChatPanelProps) {
  const { messages, send, isAwaitingReply } = useCockpitChat(caseId);
  const [draft, setDraft] = useState('');
  const transcriptRef = useRef<HTMLDivElement | null>(null);

  // Demo simplification (per Story 6.8 / AC #5 trade-off): always scroll
  // to bottom on new content. A "preserve scroll if user scrolled up"
  // tracker is polish without behavioural change for the demo.
  useEffect(() => {
    const el = transcriptRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const text = draft.trim();
    if (!text) return;
    setDraft('');
    await send(text);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void handleSubmit(e as unknown as FormEvent);
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col" data-testid="cockpit-chat-panel">
      <div
        ref={transcriptRef}
        role="log"
        aria-live="polite"
        className="flex-1 min-h-0 overflow-y-auto px-1 py-2 space-y-2"
      >
        {messages.length === 0 ? (
          <p className="text-xs italic text-zinc-500">{_EMPTY_HINT}</p>
        ) : (
          messages.map((m) => (
            <Message key={`${m.id}-${m.role}`} message={m} onCitationClick={onCitationClick} />
          ))
        )}
        {isAwaitingReply ? (
          <div className="text-xs italic text-orange-700" aria-live="polite">
            <span className="motion-safe:animate-pulse">…</span>
          </div>
        ) : null}
      </div>
      <form
        onSubmit={handleSubmit}
        className="border-t border-zinc-200 px-2 py-2 flex items-end gap-2"
      >
        <textarea
          rows={1}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask cockpit chat…"
          aria-label="Cockpit chat composer"
          className="flex-1 resize-none rounded border border-zinc-300 px-2 py-1 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-300"
        />
        <button
          type="submit"
          className="rounded bg-orange-200 px-3 py-1 text-xs font-medium text-zinc-900 hover:bg-orange-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-400 disabled:opacity-50"
          disabled={!draft.trim()}
        >
          Send
        </button>
      </form>
    </div>
  );
}

function Message({
  message,
  onCitationClick,
}: {
  message: ChatMessage;
  onCitationClick?: (ledgerId: string) => void;
}) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-md bg-zinc-100 px-3 py-1.5 text-xs text-zinc-900 whitespace-pre-line">
          {message.text}
        </div>
      </div>
    );
  }
  const isError = message.status === 'error';
  const tone = isError ? 'bg-rose-50 text-rose-800' : 'bg-orange-50/60 text-zinc-900';
  return (
    <div className="flex justify-start">
      <div
        className={`max-w-[85%] rounded-md ${tone} px-3 py-1.5 text-xs whitespace-pre-line`}
        role={isError ? 'alert' : undefined}
      >
        {message.status === 'streaming' && message.text === '' ? (
          <span className="text-orange-700 italic">…</span>
        ) : (
          <AgentMessageBody
            text={message.text}
            agentActionIds={message.agentActionIds}
            onCitationClick={onCitationClick}
          />
        )}
      </div>
    </div>
  );
}

function AgentMessageBody({
  text,
  agentActionIds,
  onCitationClick,
}: {
  text: string;
  agentActionIds: string[];
  onCitationClick?: (ledgerId: string) => void;
}) {
  const segments = parseCitations(text);
  const validSet = new Set(agentActionIds);
  return (
    <span>
      {segments.map((seg, i) =>
        seg.kind === 'text' ? (
          <span key={i}>{seg.text}</span>
        ) : (
          <CitationChip
            key={i}
            ledgerId={seg.ledgerId}
            // While streaming, the agent_action_ids list is still empty —
            // render the citation as "tentative" (no error chip until the
            // server's complete event tells us it's broken).
            // When agent_action_ids has been populated and ledgerId is
            // missing from it, render as error.
            isResolved={validSet.size === 0 || validSet.has(seg.ledgerId)}
            onClick={() => onCitationClick?.(seg.ledgerId)}
          />
        ),
      )}
    </span>
  );
}

function CitationChip({
  ledgerId,
  isResolved,
  onClick,
}: {
  ledgerId: string;
  isResolved: boolean;
  onClick: () => void;
}) {
  if (!isResolved) {
    return (
      <span
        role="alert"
        title="citation does not resolve in this case's ledger"
        className="mx-0.5 inline-flex items-center rounded bg-rose-100 px-1.5 py-0.5 font-mono text-[10px] text-rose-800"
      >
        ⚠ {ledgerId.slice(0, 12)}…
      </span>
    );
  }
  return (
    <button
      type="button"
      data-testid={`chat-citation-${ledgerId}`}
      onClick={onClick}
      aria-label={`ledger entry ${ledgerId}; click to inspect`}
      className="mx-0.5 inline-flex items-center rounded bg-orange-100 px-1.5 py-0.5 font-mono text-[10px] text-orange-900 hover:bg-orange-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-400"
    >
      {ledgerId.slice(0, 12)}…
    </button>
  );
}
