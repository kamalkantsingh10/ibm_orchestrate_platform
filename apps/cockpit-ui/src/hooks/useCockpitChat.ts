// useCockpitChat — Story 6.8 / AC #3.
//
// Local per-case chat state machine. POSTs user messages to the cockpit-
// chat endpoint and listens on its own EventSource for the streaming
// reply. Transcript lives entirely in component state — no Zustand,
// no DB persistence (per Story 6.8 demo simplification).

import { useCallback, useEffect, useRef, useState } from 'react';
import { useCurrentUser } from '@/stores/currentUser';

export type ChatMessage =
  | { id: string; role: 'user'; text: string; sentAt: string }
  | {
      id: string;
      role: 'agent';
      text: string;
      status: 'streaming' | 'complete' | 'error';
      agentActionIds: string[];
      updatedAt: string;
    };

interface _TokenData {
  message_id: string;
  token: string;
  position: number;
}
interface _CompleteData {
  message_id: string;
  full_text: string;
  agent_action_ids: string[];
}
interface _ErrorData {
  message_id: string;
  error_type: string;
  error_message: string;
}

export interface UseCockpitChatResult {
  messages: ChatMessage[];
  send: (text: string) => Promise<void>;
  isAwaitingReply: boolean;
  clearTranscript: () => void;
}

export function useCockpitChat(caseId: string): UseCockpitChatResult {
  const userId = useCurrentUser((s) => s.user.id);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const esRef = useRef<EventSource | null>(null);

  // Open a dedicated EventSource for chat events. The shared
  // subscribeToCase channel only invalidates query keys — we need
  // per-event hooks here.
  useEffect(() => {
    if (typeof EventSource === 'undefined') return;
    const url = `/v1/cases/${encodeURIComponent(caseId)}/stream?as=${encodeURIComponent(userId)}`;
    const es = new EventSource(url);
    esRef.current = es;

    const handleToken = (ev: MessageEvent) => {
      const d = JSON.parse(ev.data) as _TokenData;
      setMessages((prev) =>
        prev.map((m) =>
          m.id === d.message_id && m.role === 'agent' && m.status === 'streaming'
            ? { ...m, text: m.text + d.token, updatedAt: new Date().toISOString() }
            : m,
        ),
      );
    };
    const handleComplete = (ev: MessageEvent) => {
      const d = JSON.parse(ev.data) as _CompleteData;
      setMessages((prev) =>
        prev.map((m) =>
          m.id === d.message_id && m.role === 'agent'
            ? {
                ...m,
                text: d.full_text,
                status: 'complete' as const,
                agentActionIds: d.agent_action_ids,
                updatedAt: new Date().toISOString(),
              }
            : m,
        ),
      );
    };
    const handleError = (ev: MessageEvent) => {
      const d = JSON.parse(ev.data) as _ErrorData;
      setMessages((prev) =>
        prev.map((m) =>
          m.id === d.message_id && m.role === 'agent'
            ? {
                ...m,
                text: `Error: ${d.error_message}`,
                status: 'error' as const,
                updatedAt: new Date().toISOString(),
              }
            : m,
        ),
      );
    };

    es.addEventListener('cockpit_chat.token', handleToken as EventListener);
    es.addEventListener('cockpit_chat.message_complete', handleComplete as EventListener);
    es.addEventListener('cockpit_chat.error', handleError as EventListener);

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [caseId, userId]);

  const send = useCallback(
    async (text: string) => {
      const messageId =
        typeof crypto !== 'undefined' && 'randomUUID' in crypto
          ? crypto.randomUUID()
          : `msg_${Date.now()}_${Math.random().toString(36).slice(2)}`;
      const now = new Date().toISOString();
      setMessages((prev) => [
        ...prev,
        { id: messageId, role: 'user', text, sentAt: now },
        {
          id: messageId,
          role: 'agent',
          text: '',
          status: 'streaming',
          agentActionIds: [],
          updatedAt: now,
        },
      ]);

      const resp = await fetch(`/v1/cases/${encodeURIComponent(caseId)}/cockpit-chat/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Cockpit-Demo-User': userId,
        },
        body: JSON.stringify({ message: text, message_id: messageId }),
      });
      if (!resp.ok) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === messageId && m.role === 'agent'
              ? {
                  ...m,
                  text: `Failed to send: HTTP ${resp.status}`,
                  status: 'error' as const,
                  updatedAt: new Date().toISOString(),
                }
              : m,
          ),
        );
      }
    },
    [caseId, userId],
  );

  const clearTranscript = useCallback(() => setMessages([]), []);
  const isAwaitingReply = messages.some((m) => m.role === 'agent' && m.status === 'streaming');

  return { messages, send, isAwaitingReply, clearTranscript };
}
