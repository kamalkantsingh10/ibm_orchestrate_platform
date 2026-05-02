// DocumentUploadZone — Story 3.8 AC #10.

import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { DocumentUploadZone } from './DocumentUploadZone';

const VORA = 'case_01KQC7GQ70GYHP15CZ8JB5ZT6A';

// XHR mock — we only exercise the open/setRequestHeader/upload/onload paths.
class MockXHR {
  status = 200;
  responseText = '{"case_id":"vora","uploaded":[],"document_refs":[]}';
  upload = { onprogress: null as ((e: ProgressEvent) => void) | null };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  open = vi.fn();
  setRequestHeader = vi.fn();
  send = vi.fn();
  static last: MockXHR | null = null;
  constructor() {
    MockXHR.last = this;
  }
}

beforeEach(() => {
  // @ts-expect-error overriding global XHR for tests
  globalThis.XMLHttpRequest = MockXHR;
});

afterEach(() => {
  MockXHR.last = null;
});

function makeFile(name: string, body = 'pdfdata'): File {
  return new File([body], name, { type: 'application/pdf' });
}

describe('DocumentUploadZone', () => {
  it('renders the empty drop hint by default', () => {
    render(<DocumentUploadZone caseId={VORA} />);
    expect(screen.getByText(/Drop PDFs here/i)).toBeTruthy();
    expect(screen.queryByTestId('upload-zone-items')).toBeNull();
  });

  it('opens file picker when Browse is clicked', () => {
    render(<DocumentUploadZone caseId={VORA} />);
    const browse = screen.getByText('Browse');
    // Just confirm the button is interactive — JSDOM's hidden file-input
    // click is a no-op, so we don't assert a dialog opened.
    fireEvent.click(browse);
  });

  it('uploads files dropped on the zone and shows progress entry', async () => {
    const onUploadComplete = vi.fn();
    render(<DocumentUploadZone caseId={VORA} onUploadComplete={onUploadComplete} />);
    const zone = screen.getByText(/Drop PDFs here/i).parentElement!.parentElement!;

    const file = makeFile('incorporation.pdf');
    fireEvent.drop(zone, {
      dataTransfer: { files: [file] },
    });

    expect(MockXHR.last).toBeTruthy();
    expect(MockXHR.last!.open).toHaveBeenCalledWith('POST', `/v1/cases/${VORA}/documents`);
    // Trigger onload with success status (200 from default).
    MockXHR.last!.onload?.();
    await Promise.resolve();
    expect(onUploadComplete).toHaveBeenCalled();
    expect(screen.getByText(/incorporation\.pdf/)).toBeTruthy();
  });

  it('renders error state when XHR fails', async () => {
    render(<DocumentUploadZone caseId={VORA} />);
    const zone = screen.getByText(/Drop PDFs here/i).parentElement!.parentElement!;
    fireEvent.drop(zone, { dataTransfer: { files: [makeFile('big.pdf')] } });

    const last = MockXHR.last!;
    last.status = 413;
    last.responseText = '{"detail":"file too large"}';
    last.onload?.();

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('file too large');
  });

  it('filters drag-dropped non-PDF files', () => {
    render(<DocumentUploadZone caseId={VORA} />);
    const zone = screen.getByText(/Drop PDFs here/i).parentElement!.parentElement!;
    fireEvent.drop(zone, {
      dataTransfer: { files: [new File(['x'], 'x.png', { type: 'image/png' })] },
    });
    // No XHR sent because the only file was filtered out
    expect(MockXHR.last).toBeNull();
  });

  it('dismiss button removes the item from the list', async () => {
    render(<DocumentUploadZone caseId={VORA} />);
    const zone = screen.getByText(/Drop PDFs here/i).parentElement!.parentElement!;
    fireEvent.drop(zone, {
      dataTransfer: { files: [makeFile('alpha.pdf')] },
    });
    MockXHR.last!.onload?.();
    await Promise.resolve();
    const dismiss = screen.getByRole('button', { name: /dismiss alpha\.pdf/i });
    fireEvent.click(dismiss);
    expect(screen.queryByTestId('upload-item-alpha.pdf')).toBeNull();
  });
});
