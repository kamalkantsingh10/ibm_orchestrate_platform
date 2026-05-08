// DecisionZone tests — Story 7.1 / AC #12.
//
// We mock the data hooks at the module boundary so we can drive each
// case state path without running a real Tanstack Query loop. Tiptap
// itself runs natively (jsdom is sufficient) — its rendered output is
// what the tests assert against.

import type { ReactNode } from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const { useCaseMock, useWritingAgentDraftMock, useDocIntelMock } = vi.hoisted(() => ({
  useCaseMock: vi.fn(),
  useWritingAgentDraftMock: vi.fn(),
  useDocIntelMock: vi.fn(),
}));

vi.mock('@/hooks/useCase', () => ({ useCase: useCaseMock }));
vi.mock('@/hooks/useWritingAgentDraft', () => ({ useWritingAgentDraft: useWritingAgentDraftMock }));
vi.mock('@/hooks/useDocumentIntelligence', () => ({
  useDocumentIntelligence: useDocIntelMock,
}));

import { DecisionZone } from './DecisionZone';
import { useCurrentUser } from '@/stores/currentUser';
import { useDecisionZoneFocusStore } from '@/stores/decisionZoneStore';
import { DEMO_USERS } from '@/lib/demoUsers';

const CASE_ID = 'case_01HZ7ZK4G7EXAMPLE0000000DD';
const LED_A = 'led_01ABCDEFGHJKMNPQRSTVWXYZ12';
const LED_B = 'led_01HXY3GHJKMNPQRSTVWXYZ7HX2';
const BROKEN = 'led_01ZZZZZZZZZZZZZZZZZZZZZ7HX';

function makeWrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function _ledgerResponse(ids: string[]): Response {
  return jsonResponse(
    ids.map((id) => ({
      id,
      action: 'agent.completed',
      actor_id: 'screening',
      actor_type: 'AGENT',
      case_id: CASE_ID,
      recorded_at: '2026-05-08T00:00:00Z',
      payload: {},
    })),
  );
}

function _setupCase(state: string) {
  useCaseMock.mockReturnValue({
    data: {
      id: CASE_ID,
      state,
      customer_metadata: { customer_name: 'Acme', extra: {} },
      assigned_to_user_id: null,
      risk_band: null,
      created_at: '2026-05-08T00:00:00Z',
      updated_at: '2026-05-08T00:00:00Z',
      closure_date: null,
      _links: { documents: null, reasoning_traces: null },
    },
    isError: false,
    isPending: false,
    isSuccess: true,
  });
}

beforeEach(() => {
  localStorage.clear();
  const analyst = DEMO_USERS.find((u) => u.role === 'analyst')!;
  useCurrentUser.setState({ user: analyst });
  useDecisionZoneFocusStore.setState({ isFocused: false });
  useCaseMock.mockReset();
  useWritingAgentDraftMock.mockReset();
  useDocIntelMock.mockReset();
  useWritingAgentDraftMock.mockReturnValue({
    data: null,
    isPending: false,
    isError: false,
    isSuccess: true,
  });
  useDocIntelMock.mockReturnValue({
    data: null,
    isPending: false,
    isError: false,
    isSuccess: true,
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe('DecisionZone', () => {
  it('renders nothing when case state is intake_scheduled', () => {
    _setupCase('intake_scheduled');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(_ledgerResponse([])));
    const { container } = render(<DecisionZone caseId={CASE_ID} />, { wrapper: makeWrapper() });
    expect(container.firstChild).toBeNull();
  });

  it('renders nothing when case state is closed', () => {
    _setupCase('closed');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(_ledgerResponse([])));
    const { container } = render(<DecisionZone caseId={CASE_ID} />, { wrapper: makeWrapper() });
    expect(container.firstChild).toBeNull();
  });

  it('renders an editable Tiptap when case is decision_ready', async () => {
    _setupCase('decision_ready');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(_ledgerResponse([])));
    render(<DecisionZone caseId={CASE_ID} />, { wrapper: makeWrapper() });
    expect(screen.getByText('Decision Zone')).toBeInTheDocument();
    expect(screen.getByText('Ready to commit')).toBeInTheDocument();
    expect(screen.getByTestId('decision-commit-button')).toBeInTheDocument();
  });

  it('seeds the editor with the writing-agent draft when localStorage is empty', async () => {
    _setupCase('decision_ready');
    useWritingAgentDraftMock.mockReturnValue({
      data: { rationaleHtml: '<p>Auto-drafted by Writing agent.</p>', agentActionId: LED_A },
      isPending: false,
      isError: false,
      isSuccess: true,
    });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(_ledgerResponse([LED_A])));
    render(<DecisionZone caseId={CASE_ID} />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByText(/Auto-drafted by Writing agent/)).toBeInTheDocument();
    });
  });

  it('does NOT clobber a localStorage draft when the writing-agent draft arrives later', async () => {
    _setupCase('decision_ready');
    localStorage.setItem(
      `cockpit:decision-draft:${CASE_ID}`,
      JSON.stringify({
        rationaleHtml: '<p>Officer was already typing.</p>',
        outcome: null,
        conditions: [],
        updatedAt: '2026-05-08T00:00:00Z',
      }),
    );
    useWritingAgentDraftMock.mockReturnValue({
      data: { rationaleHtml: '<p>SHOULD NOT APPEAR.</p>', agentActionId: LED_A },
      isPending: false,
      isError: false,
      isSuccess: true,
    });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(_ledgerResponse([LED_A])));
    render(<DecisionZone caseId={CASE_ID} />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByText(/Officer was already typing/)).toBeInTheDocument();
    });
    expect(screen.queryByText(/SHOULD NOT APPEAR/)).toBeNull();
  });

  it('renders the OutcomeSelector stub with all four outcomes', () => {
    _setupCase('decision_ready');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(_ledgerResponse([])));
    render(<DecisionZone caseId={CASE_ID} />, { wrapper: makeWrapper() });
    const select = screen.getByLabelText('Decision outcome') as HTMLSelectElement;
    const optionValues = Array.from(select.querySelectorAll('option')).map((o) => o.value);
    expect(optionValues).toEqual([
      '',
      'approve',
      'decline',
      'approve_with_conditions',
      'escalate_to_edd',
    ]);
  });

  it('renders the conditions input only when approve_with_conditions is selected', () => {
    _setupCase('decision_ready');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(_ledgerResponse([])));
    render(<DecisionZone caseId={CASE_ID} />, { wrapper: makeWrapper() });
    expect(screen.queryByLabelText('Add condition')).toBeNull();
    fireEvent.change(screen.getByLabelText('Decision outcome'), {
      target: { value: 'approve_with_conditions' },
    });
    expect(screen.getByLabelText('Add condition')).toBeInTheDocument();
  });

  it('disables the commit button when outcome is null', () => {
    _setupCase('decision_ready');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(_ledgerResponse([])));
    render(<DecisionZone caseId={CASE_ID} />, { wrapper: makeWrapper() });
    const btn = screen.getByTestId('decision-commit-button') as HTMLButtonElement;
    expect(btn).toBeDisabled();
  });

  it('disables the commit button when a citation is broken and shows an error strip', async () => {
    _setupCase('decision_ready');
    localStorage.setItem(
      `cockpit:decision-draft:${CASE_ID}`,
      JSON.stringify({
        rationaleHtml: `<p>Approve based on <span data-ledger-id="${BROKEN}" class="citation-token">screening</span>.</p>`,
        outcome: 'approve',
        conditions: [],
        updatedAt: '2026-05-08T00:00:00Z',
      }),
    );
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(_ledgerResponse([LED_A])));
    render(<DecisionZone caseId={CASE_ID} />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByRole('alert').textContent).toContain(BROKEN);
    });
    const btn = screen.getByTestId('decision-commit-button') as HTMLButtonElement;
    expect(btn).toBeDisabled();
  });

  it('cmd+Enter triggers POST /v1/cases/{id}/decisions with the right body', async () => {
    _setupCase('decision_ready');
    localStorage.setItem(
      `cockpit:decision-draft:${CASE_ID}`,
      JSON.stringify({
        rationaleHtml: `<p>OK <span data-ledger-id="${LED_A}" class="citation-token">screening</span>.</p>`,
        outcome: 'approve',
        conditions: [],
        updatedAt: '2026-05-08T00:00:00Z',
      }),
    );
    const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url =
        typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
      if (url.includes('/decisions') && init?.method === 'POST') {
        return Promise.resolve(jsonResponse({ ok: true }));
      }
      return Promise.resolve(_ledgerResponse([LED_A]));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<DecisionZone caseId={CASE_ID} />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId('decision-commit-button')).not.toBeDisabled();
    });

    const zone = screen.getByTestId('decision-zone');
    await act(async () => {
      fireEvent.keyDown(zone, { key: 'Enter', metaKey: true });
    });

    await waitFor(() => {
      const postCall = fetchMock.mock.calls.find(
        ([, init]) => (init as RequestInit | undefined)?.method === 'POST',
      );
      expect(postCall).toBeDefined();
    });
    const postCall = fetchMock.mock.calls.find(
      ([, init]) => (init as RequestInit | undefined)?.method === 'POST',
    )!;
    const body = JSON.parse((postCall[1] as RequestInit).body as string);
    expect(body.outcome).toBe('approve');
    expect(body.rationale_html).toContain(LED_A);
  });

  it('clicking the commit button POSTs to /decisions', async () => {
    _setupCase('decision_ready');
    localStorage.setItem(
      `cockpit:decision-draft:${CASE_ID}`,
      JSON.stringify({
        rationaleHtml: `<p>OK <span data-ledger-id="${LED_A}" class="citation-token">screening</span>.</p>`,
        outcome: 'approve',
        conditions: [],
        updatedAt: '2026-05-08T00:00:00Z',
      }),
    );
    const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url =
        typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
      if (url.includes('/decisions') && init?.method === 'POST') {
        return Promise.resolve(jsonResponse({ ok: true }));
      }
      return Promise.resolve(_ledgerResponse([LED_A]));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<DecisionZone caseId={CASE_ID} />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId('decision-commit-button')).not.toBeDisabled();
    });

    await act(async () => {
      fireEvent.click(screen.getByTestId('decision-commit-button'));
    });

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(
          ([, init]) => (init as RequestInit | undefined)?.method === 'POST',
        ),
      ).toBe(true);
    });
  });

  it('renders read-only with no commit button when state is pending_seal', async () => {
    _setupCase('pending_seal');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(_ledgerResponse([])));
    render(<DecisionZone caseId={CASE_ID} />, { wrapper: makeWrapper() });
    expect(screen.queryByTestId('decision-commit-button')).toBeNull();
    expect(screen.getByText(/Awaiting seal/i)).toBeInTheDocument();
  });

  it('renders read-only with sealed indicator when state is committed', () => {
    _setupCase('committed');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(_ledgerResponse([])));
    render(<DecisionZone caseId={CASE_ID} />, { wrapper: makeWrapper() });
    expect(screen.getByText(/Sealed \(read-only\)/i)).toBeInTheDocument();
    expect(screen.queryByTestId('decision-commit-button')).toBeNull();
  });

  it('default state — sans + zinc palette + bg-white (Story 7.2 AC #3)', () => {
    _setupCase('decision_ready');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(_ledgerResponse([])));
    render(<DecisionZone caseId={CASE_ID} />, { wrapper: makeWrapper() });
    const zone = screen.getByTestId('decision-zone');
    expect(zone.dataset.focused).toBe('false');
    expect(zone.className).toMatch(/bg-white/);
    expect(zone.className).toMatch(/text-zinc-900/);
    const body = zone.querySelector('.editor-body') as HTMLElement;
    expect(body.className).toMatch(/font-sans/);
    expect(body.className).toMatch(/text-sm/);
  });

  it('focusin inside the Decision Zone flips to stone palette + serif body', async () => {
    _setupCase('decision_ready');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(_ledgerResponse([])));
    render(<DecisionZone caseId={CASE_ID} />, { wrapper: makeWrapper() });
    const zone = screen.getByTestId('decision-zone');
    const editor = zone.querySelector('[contenteditable="true"]') as HTMLElement;
    expect(editor).not.toBeNull();
    await act(async () => {
      editor.focus();
      // jsdom doesn't auto-fire focusin from .focus() in all configs;
      // dispatch explicitly.
      editor.dispatchEvent(new FocusEvent('focusin', { bubbles: true }));
    });
    expect(zone.dataset.focused).toBe('true');
    expect(zone.className).toMatch(/bg-stone-50/);
    expect(zone.className).toMatch(/text-stone-900/);
    const body = zone.querySelector('.editor-body') as HTMLElement;
    expect(body.className).toMatch(/font-serif/);
    expect(body.className).toMatch(/text-base/);
  });

  it('focusout reverts to default tonal state', async () => {
    _setupCase('decision_ready');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(_ledgerResponse([])));
    render(<DecisionZone caseId={CASE_ID} />, { wrapper: makeWrapper() });
    const zone = screen.getByTestId('decision-zone');
    const editor = zone.querySelector('[contenteditable="true"]') as HTMLElement;
    await act(async () => {
      editor.dispatchEvent(new FocusEvent('focusin', { bubbles: true }));
    });
    expect(zone.dataset.focused).toBe('true');
    await act(async () => {
      const evt = new FocusEvent('focusout', { bubbles: true });
      // focusout dispatched on the section; relatedTarget undefined → outside.
      zone.dispatchEvent(evt);
    });
    expect(zone.dataset.focused).toBe('false');
  });

  it('focus shift between sibling controls inside the zone keeps isFocused true', async () => {
    _setupCase('decision_ready');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(_ledgerResponse([])));
    render(<DecisionZone caseId={CASE_ID} />, { wrapper: makeWrapper() });
    const zone = screen.getByTestId('decision-zone');
    const editor = zone.querySelector('[contenteditable="true"]') as HTMLElement;
    const select = screen.getByLabelText('Decision outcome') as HTMLElement;
    await act(async () => {
      editor.dispatchEvent(new FocusEvent('focusin', { bubbles: true }));
    });
    // focusout from editor with relatedTarget pointing at the in-zone select.
    await act(async () => {
      const evt = new FocusEvent('focusout', { bubbles: true, relatedTarget: select });
      editor.dispatchEvent(evt);
    });
    // Should NOT flip false because relatedTarget is still inside zone.
    expect(zone.dataset.focused).toBe('true');
  });

  it('h2 header stays font-sans regardless of focus state (AC #8)', async () => {
    _setupCase('decision_ready');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(_ledgerResponse([])));
    render(<DecisionZone caseId={CASE_ID} />, { wrapper: makeWrapper() });
    const heading = screen.getByText('Decision Zone');
    expect(heading.className).toMatch(/font-sans/);
    const zone = screen.getByTestId('decision-zone');
    const editor = zone.querySelector('[contenteditable="true"]') as HTMLElement;
    await act(async () => {
      editor.dispatchEvent(new FocusEvent('focusin', { bubbles: true }));
    });
    expect(heading.className).toMatch(/font-sans/);
    expect(heading.className).not.toMatch(/font-serif/);
  });

  it('Esc on a focused control inside the zone blurs it (AC #6)', async () => {
    _setupCase('decision_ready');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(_ledgerResponse([])));
    render(<DecisionZone caseId={CASE_ID} />, { wrapper: makeWrapper() });
    const editor = screen
      .getByTestId('decision-zone')
      .querySelector('[contenteditable="true"]') as HTMLElement;
    editor.focus();
    expect(document.activeElement).toBe(editor);
    await act(async () => {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    });
    expect(document.activeElement).not.toBe(editor);
  });

  it('Esc does NOT blur when an open Radix dialog is present', async () => {
    _setupCase('decision_ready');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(_ledgerResponse([])));
    const { container } = render(<DecisionZone caseId={CASE_ID} />, { wrapper: makeWrapper() });
    const editor = screen
      .getByTestId('decision-zone')
      .querySelector('[contenteditable="true"]') as HTMLElement;
    editor.focus();
    // Inject a fake open Radix dialog into the document.
    const dialog = document.createElement('div');
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('data-state', 'open');
    container.appendChild(dialog);
    await act(async () => {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    });
    expect(document.activeElement).toBe(editor);
    dialog.remove();
  });

  it('writes isFocused into the global store so the route can consume it', async () => {
    _setupCase('decision_ready');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(_ledgerResponse([])));
    render(<DecisionZone caseId={CASE_ID} />, { wrapper: makeWrapper() });
    expect(useDecisionZoneFocusStore.getState().isFocused).toBe(false);
    const editor = screen
      .getByTestId('decision-zone')
      .querySelector('[contenteditable="true"]') as HTMLElement;
    await act(async () => {
      editor.dispatchEvent(new FocusEvent('focusin', { bubbles: true }));
    });
    expect(useDecisionZoneFocusStore.getState().isFocused).toBe(true);
  });

  it('container has motion-reduce:transition-none for prefers-reduced-motion (AC #7)', () => {
    _setupCase('decision_ready');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(_ledgerResponse([])));
    render(<DecisionZone caseId={CASE_ID} />, { wrapper: makeWrapper() });
    const zone = screen.getByTestId('decision-zone');
    expect(zone.className).toMatch(/motion-reduce:transition-none/);
  });

  it('clicking a citation token dispatches cockpit:open-trace', async () => {
    _setupCase('decision_ready');
    localStorage.setItem(
      `cockpit:decision-draft:${CASE_ID}`,
      JSON.stringify({
        rationaleHtml: `<p>OK <span data-ledger-id="${LED_B}" class="citation-token">screening</span>.</p>`,
        outcome: null,
        conditions: [],
        updatedAt: '2026-05-08T00:00:00Z',
      }),
    );
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(_ledgerResponse([LED_B])));
    const listener = vi.fn();
    window.addEventListener('cockpit:open-trace', listener as EventListener);
    render(<DecisionZone caseId={CASE_ID} />, { wrapper: makeWrapper() });
    await waitFor(() => {
      const span = document.querySelector(`span[data-ledger-id="${LED_B}"]`);
      expect(span).not.toBeNull();
    });
    const span = document.querySelector(`span[data-ledger-id="${LED_B}"]`)!;
    fireEvent.click(span);
    expect(listener).toHaveBeenCalled();
    const firstCall = listener.mock.calls[0];
    expect(firstCall).toBeDefined();
    const event = firstCall![0] as CustomEvent<{ ledgerId: string }>;
    expect(event.detail.ledgerId).toBe(LED_B);
    window.removeEventListener('cockpit:open-trace', listener as EventListener);
  });

  // ───────────── Story 7.8 — Evidence toggle ─────────────

  it('Evidence toggle button does not render when onToggleEvidence is omitted', () => {
    _setupCase('decision_ready');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(_ledgerResponse([])));
    render(<DecisionZone caseId={CASE_ID} />, { wrapper: makeWrapper() });
    expect(screen.queryByTestId('decision-zone-evidence-toggle')).toBeNull();
  });

  it('Evidence toggle button renders when onToggleEvidence is supplied', () => {
    _setupCase('decision_ready');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(_ledgerResponse([])));
    render(<DecisionZone caseId={CASE_ID} onToggleEvidence={() => {}} />, {
      wrapper: makeWrapper(),
    });
    const button = screen.getByTestId('decision-zone-evidence-toggle');
    expect(button).toBeInTheDocument();
    expect(button.textContent?.trim()).toBe('Evidence');
  });

  it('Evidence toggle shows the document count when intake is populated', () => {
    _setupCase('decision_ready');
    useDocIntelMock.mockReturnValue({
      data: {
        case_id: CASE_ID,
        extracted_fields: [
          {
            field_name: 'cin',
            document_ref: 'doc1.pdf',
            value: {
              value: 'x',
              provenance: {
                source_agent: 'document_intelligence',
                source_system: 'fixture_doc_ai',
                confidence: 0.9,
                confidence_band: 'high',
                evidence_ids: [],
                captured_at: '2026-05-08T00:00:00Z',
              },
            },
          },
          {
            field_name: 'pan',
            document_ref: 'doc2.pdf',
            value: {
              value: 'y',
              provenance: {
                source_agent: 'document_intelligence',
                source_system: 'fixture_doc_ai',
                confidence: 0.9,
                confidence_band: 'high',
                evidence_ids: [],
                captured_at: '2026-05-08T00:00:00Z',
              },
            },
          },
          {
            field_name: 'address',
            document_ref: 'doc1.pdf',
            value: {
              value: 'z',
              provenance: {
                source_agent: 'document_intelligence',
                source_system: 'fixture_doc_ai',
                confidence: 0.9,
                confidence_band: 'high',
                evidence_ids: [],
                captured_at: '2026-05-08T00:00:00Z',
              },
            },
          },
        ],
      },
      isPending: false,
      isError: false,
      isSuccess: true,
    });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(_ledgerResponse([])));
    render(<DecisionZone caseId={CASE_ID} onToggleEvidence={() => {}} />, {
      wrapper: makeWrapper(),
    });
    expect(screen.getByTestId('decision-zone-evidence-toggle').textContent?.trim()).toBe(
      'Evidence (2)',
    );
  });

  it('clicking the Evidence toggle invokes onToggleEvidence', () => {
    _setupCase('decision_ready');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(_ledgerResponse([])));
    const onToggle = vi.fn();
    render(<DecisionZone caseId={CASE_ID} onToggleEvidence={onToggle} />, {
      wrapper: makeWrapper(),
    });
    fireEvent.click(screen.getByTestId('decision-zone-evidence-toggle'));
    expect(onToggle).toHaveBeenCalled();
  });

  it('Evidence toggle reflects evidenceOpen via aria-pressed', () => {
    _setupCase('decision_ready');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(_ledgerResponse([])));
    const { rerender } = render(
      <DecisionZone caseId={CASE_ID} onToggleEvidence={() => {}} evidenceOpen={false} />,
      { wrapper: makeWrapper() },
    );
    expect(screen.getByTestId('decision-zone-evidence-toggle').getAttribute('aria-pressed')).toBe(
      'false',
    );
    rerender(<DecisionZone caseId={CASE_ID} onToggleEvidence={() => {}} evidenceOpen={true} />);
    expect(screen.getByTestId('decision-zone-evidence-toggle').getAttribute('aria-pressed')).toBe(
      'true',
    );
  });
});
