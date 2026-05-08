// EvidenceShelfDock tests — Story 8.5 / AC #7.

import type { ReactNode } from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { EvidenceShelfDock } from './EvidenceShelfDock';
import { useCurrentUser } from '@/stores/currentUser';
import { DEMO_USERS } from '@/lib/demoUsers';

const CASE_ID = 'case_01HZ7ZK4G7EXAMPLE0000000DD';

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

function emptyResponse(status = 204): Response {
  return new Response(null, { status });
}

describe('EvidenceShelfDock', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    useCurrentUser.setState({ user: DEMO_USERS[0] });
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('renders_attached_evidence_items_newest_first', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        case_id: CASE_ID,
        items: [
          { filename: 'second.txt', size_bytes: 6, uploaded_at: '2026-05-08T12:00:00Z' },
          { filename: 'first.txt', size_bytes: 5, uploaded_at: '2026-05-08T11:00:00Z' },
        ],
      }),
    );
    const Wrapper = makeWrapper();
    render(
      <Wrapper>
        <EvidenceShelfDock caseId={CASE_ID} />
      </Wrapper>,
    );
    await waitFor(() => {
      const rows = screen.getAllByTestId('evidence-row');
      expect(rows).toHaveLength(2);
      // Server already sorts newest first; the UI preserves order.
      expect(rows[0].getAttribute('data-filename')).toBe('second.txt');
      expect(rows[1].getAttribute('data-filename')).toBe('first.txt');
    });
  });

  it('renders the empty-state caption when no evidence is attached', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ case_id: CASE_ID, items: [] }));
    const Wrapper = makeWrapper();
    render(
      <Wrapper>
        <EvidenceShelfDock caseId={CASE_ID} />
      </Wrapper>,
    );
    await waitFor(() => {
      expect(screen.getByTestId('evidence-empty-state').textContent).toMatch(
        /Drop files, paste from clipboard/,
      );
    });
  });

  it('drop_file_uploads_via_documents_endpoint_with_kind_evidence', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ case_id: CASE_ID, items: [] }));
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        case_id: CASE_ID,
        uploaded: [{ filename: 'note.txt', size_bytes: 5, uploaded_at: '2026-05-08T13:00:00Z' }],
        document_refs: [],
      }),
    );
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        case_id: CASE_ID,
        items: [{ filename: 'note.txt', size_bytes: 5, uploaded_at: '2026-05-08T13:00:00Z' }],
      }),
    );

    const Wrapper = makeWrapper();
    render(
      <Wrapper>
        <EvidenceShelfDock caseId={CASE_ID} />
      </Wrapper>,
    );
    await waitFor(() => expect(screen.getByTestId('evidence-empty-state')).toBeInTheDocument());

    fireEvent.click(screen.getByTestId('evidence-add-button'));
    fireEvent.click(screen.getByTestId('evidence-tab-drop'));

    const dropZone = screen.getByTestId('evidence-drop-zone');
    const file = new File(['plain text body'], 'note.txt', { type: 'text/plain' });
    await act(async () => {
      fireEvent.drop(dropZone, {
        dataTransfer: { files: [file] },
      });
    });

    await waitFor(() => {
      const uploadCall = fetchMock.mock.calls.find(
        ([url]) => typeof url === 'string' && url.includes('/documents?kind=evidence'),
      );
      expect(uploadCall).toBeDefined();
      const [, init] = uploadCall ?? [];
      expect((init as RequestInit).method).toBe('POST');
    });
  });

  it('paste_email_body_saves_as_text_file', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ case_id: CASE_ID, items: [] }));
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        case_id: CASE_ID,
        uploaded: [
          {
            filename: 'email-2026-05-08T13.txt',
            size_bytes: 12,
            uploaded_at: '2026-05-08T13:00:00Z',
          },
        ],
        document_refs: [],
      }),
    );
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        case_id: CASE_ID,
        items: [
          {
            filename: 'email-2026-05-08T13.txt',
            size_bytes: 12,
            uploaded_at: '2026-05-08T13:00:00Z',
          },
        ],
      }),
    );

    const Wrapper = makeWrapper();
    render(
      <Wrapper>
        <EvidenceShelfDock caseId={CASE_ID} />
      </Wrapper>,
    );
    await waitFor(() => expect(screen.getByTestId('evidence-empty-state')).toBeInTheDocument());

    fireEvent.click(screen.getByTestId('evidence-add-button'));
    fireEvent.click(screen.getByTestId('evidence-tab-email'));

    fireEvent.change(screen.getByTestId('evidence-email-body'), {
      target: { value: 'From: bank.com — confirm transfer' },
    });
    await act(async () => {
      fireEvent.click(screen.getByTestId('evidence-save-email'));
    });

    await waitFor(() => {
      const uploadCall = fetchMock.mock.calls.find(
        ([url]) => typeof url === 'string' && url.includes('/documents?kind=evidence'),
      );
      expect(uploadCall).toBeDefined();
      const init = (uploadCall ?? [])[1] as RequestInit;
      const fd = init.body as FormData;
      const file = fd.get('files') as Blob;
      expect(file).toBeTruthy();
      // Filename pattern `email-<stamp>.txt`.
      const stored = fd.get('files') as File | Blob;
      if (stored instanceof File) {
        expect(stored.name).toMatch(/^email-.*\.txt$/);
      }
    });
  });

  it('drag_handle_sets_evidence_ref_payload', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        case_id: CASE_ID,
        items: [{ filename: 'memo.txt', size_bytes: 5, uploaded_at: '2026-05-08T13:00:00Z' }],
      }),
    );
    const Wrapper = makeWrapper();
    render(
      <Wrapper>
        <EvidenceShelfDock caseId={CASE_ID} />
      </Wrapper>,
    );
    const handle = await screen.findByTestId('evidence-drag-handle');
    const setData = vi.fn();
    fireEvent.dragStart(handle, {
      dataTransfer: { setData, effectAllowed: '' },
    });
    expect(setData).toHaveBeenCalledWith(
      'application/x-cockpit-evidence-ref',
      expect.stringContaining('"filename":"memo.txt"'),
    );
  });

  it('delete_button_confirms_then_removes_evidence', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        case_id: CASE_ID,
        items: [{ filename: 'gone.txt', size_bytes: 3, uploaded_at: '2026-05-08T13:00:00Z' }],
      }),
    );
    fetchMock.mockResolvedValueOnce(emptyResponse(204));
    fetchMock.mockResolvedValueOnce(jsonResponse({ case_id: CASE_ID, items: [] }));

    const Wrapper = makeWrapper();
    render(
      <Wrapper>
        <EvidenceShelfDock caseId={CASE_ID} />
      </Wrapper>,
    );
    fireEvent.click(await screen.findByTestId('evidence-delete-button'));
    await act(async () => {
      fireEvent.click(screen.getByTestId('evidence-confirm-delete'));
    });
    await waitFor(() => {
      const deleteCall = fetchMock.mock.calls.find(
        ([url, init]) =>
          typeof url === 'string' &&
          url.includes('/evidence/gone.txt') &&
          (init as RequestInit | undefined)?.method === 'DELETE',
      );
      expect(deleteCall).toBeDefined();
    });
  });
});
