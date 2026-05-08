// EvidenceShelfDock — Story 8.5.
//
// Right-edge dock that hosts case evidence in Zen mode. Three ingest
// paths land here: drag-drop (file), clipboard paste, and email-body
// paste. Each is a thin wrapper over `useUploadEvidence`. The dock
// shows a list of uploaded evidence newest-first; each row carries a
// drag handle (Story 8.5 / AC #4 — drag into the editor inserts an
// `evidenceRef` chip; the Tiptap node and route registration are
// downstream wiring beyond this story's deliverables).

import { useRef, useState, type DragEvent, type FormEvent } from 'react';
import {
  useEvidenceItems,
  useUploadEvidence,
  useDeleteEvidence,
  type EvidenceItem,
} from '@/hooks/useEvidenceItems';

export interface EvidenceShelfDockProps {
  caseId: string;
}

type IngestTab = 'drop' | 'clipboard' | 'email';

function _formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString();
  } catch {
    return iso;
  }
}

function _safeFilename(prefix: string, ext: string): string {
  // Tight character set so `sanitize_evidence_filename` accepts it.
  const stamp = new Date()
    .toISOString()
    .replace(/[^0-9A-Za-z]/g, '-')
    .slice(0, 20);
  return `${prefix}-${stamp}.${ext}`;
}

export function EvidenceShelfDock({ caseId }: EvidenceShelfDockProps): JSX.Element {
  const { data: items = [] } = useEvidenceItems(caseId);
  const upload = useUploadEvidence(caseId);
  const remove = useDeleteEvidence(caseId);
  const [showIngest, setShowIngest] = useState(false);
  const [tab, setTab] = useState<IngestTab>('drop');
  const [emailBody, setEmailBody] = useState('');
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleDrop = async (ev: DragEvent<HTMLDivElement>) => {
    ev.preventDefault();
    setError(null);
    const file = ev.dataTransfer.files?.[0];
    if (!file) return;
    try {
      await upload.mutateAsync({ file, filename: file.name });
      setShowIngest(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    }
  };

  const handleFileSelect = async (ev: FormEvent<HTMLInputElement>) => {
    const file = (ev.currentTarget.files ?? [])[0];
    if (!file) return;
    setError(null);
    try {
      await upload.mutateAsync({ file, filename: file.name });
      setShowIngest(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    }
  };

  const handlePasteClipboard = async () => {
    setError(null);
    try {
      const items = await navigator.clipboard.read();
      for (const item of items) {
        for (const type of item.types) {
          // Try image first; fall back to text.
          if (type.startsWith('image/')) {
            const blob = await item.getType(type);
            const ext = type.split('/')[1] ?? 'png';
            const filename = _safeFilename('pasted', ext === 'jpeg' ? 'jpg' : ext);
            await upload.mutateAsync({ file: blob, filename });
            setShowIngest(false);
            return;
          }
          if (type === 'text/plain') {
            const blob = await item.getType(type);
            const filename = _safeFilename('pasted', 'txt');
            await upload.mutateAsync({ file: blob, filename });
            setShowIngest(false);
            return;
          }
        }
      }
      setError('Clipboard had no image or text to attach.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Clipboard read failed');
    }
  };

  const handleSaveEmailBody = async () => {
    setError(null);
    if (!emailBody.trim()) {
      setError('Paste an email body first.');
      return;
    }
    try {
      const blob = new Blob([emailBody], { type: 'text/plain' });
      const filename = _safeFilename('email', 'txt');
      await upload.mutateAsync({ file: blob, filename });
      setEmailBody('');
      setShowIngest(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed');
    }
  };

  const handleDelete = async (filename: string) => {
    try {
      await remove.mutateAsync(filename);
    } catch {
      // Surface via list query refetch; non-blocking for the demo.
    }
  };

  return (
    <aside
      data-testid="evidence-shelf-dock"
      className="flex h-full w-[320px] flex-col border-l border-[#2A2622] bg-[#1f1c19] text-[#F1ECE3]"
    >
      <header className="flex items-center justify-between border-b border-[#2A2622] px-4 py-3">
        <h2 className="text-sm font-semibold tracking-tight">Evidence</h2>
        <button
          type="button"
          data-testid="evidence-add-button"
          onClick={() => setShowIngest((v) => !v)}
          className="rounded border border-[#2A2622] px-2 py-0.5 text-[11px] font-medium text-[#F1ECE3]/80 hover:text-[#F1ECE3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#F1ECE3]/40"
        >
          {showIngest ? 'Close' : '+ Add'}
        </button>
      </header>

      {showIngest ? (
        <div
          data-testid="evidence-ingest-popover"
          className="border-b border-[#2A2622] p-4 text-xs"
        >
          <div role="tablist" className="mb-3 flex gap-2 text-[11px]">
            {(['drop', 'clipboard', 'email'] as IngestTab[]).map((t) => (
              <button
                key={t}
                type="button"
                role="tab"
                aria-selected={tab === t}
                data-testid={`evidence-tab-${t}`}
                onClick={() => setTab(t)}
                className={
                  tab === t
                    ? 'rounded border border-[#F1ECE3]/60 bg-[#1A1815] px-2 py-1'
                    : 'rounded border border-[#2A2622] px-2 py-1 opacity-60'
                }
              >
                {t === 'drop' ? 'Drop file' : t === 'clipboard' ? 'Clipboard' : 'Email body'}
              </button>
            ))}
          </div>

          {tab === 'drop' ? (
            <button
              type="button"
              data-testid="evidence-drop-zone"
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className="flex min-h-[80px] w-full cursor-pointer flex-col items-center justify-center rounded border border-dashed border-[#F1ECE3]/30 px-3 py-4 text-center text-[11px] opacity-80 hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#F1ECE3]/40"
            >
              <span>Drop a file here or click to choose.</span>
              <span className="mt-1 opacity-60">PDF · PNG · JPG · TXT · EML</span>
              <input
                ref={fileInputRef}
                type="file"
                data-testid="evidence-file-input"
                accept=".pdf,.png,.jpg,.jpeg,.txt,.eml"
                onChange={handleFileSelect}
                className="hidden"
              />
            </button>
          ) : null}

          {tab === 'clipboard' ? (
            <button
              type="button"
              data-testid="evidence-paste-clipboard"
              onClick={handlePasteClipboard}
              className="w-full rounded border border-[#F1ECE3]/40 px-3 py-2 text-[11px] hover:bg-[#1A1815]"
            >
              Paste image / file from clipboard
            </button>
          ) : null}

          {tab === 'email' ? (
            <div className="flex flex-col gap-2">
              <textarea
                data-testid="evidence-email-body"
                value={emailBody}
                onChange={(e) => setEmailBody(e.target.value)}
                placeholder="Paste email body here…"
                rows={5}
                className="w-full rounded border border-[#2A2622] bg-[#1A1815] px-2 py-2 text-[11px] text-[#F1ECE3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#F1ECE3]/40"
              />
              <button
                type="button"
                data-testid="evidence-save-email"
                onClick={handleSaveEmailBody}
                className="self-end rounded border border-[#F1ECE3]/40 px-3 py-1 text-[11px] hover:bg-[#1A1815]"
              >
                Save as evidence
              </button>
            </div>
          ) : null}

          {error ? (
            <p role="alert" data-testid="evidence-error" className="mt-2 text-[11px] text-rose-300">
              {error}
            </p>
          ) : null}
        </div>
      ) : null}

      <ul className="flex flex-1 flex-col overflow-y-auto py-1">
        {items.length === 0 ? (
          <li
            data-testid="evidence-empty-state"
            className="px-4 py-8 text-center text-[11px] opacity-60"
          >
            Drop files, paste from clipboard, or paste email body to attach evidence to this case.
          </li>
        ) : (
          items.map((item) => (
            <EvidenceRow key={item.filename} item={item} onDelete={handleDelete} caseId={caseId} />
          ))
        )}
      </ul>
    </aside>
  );
}

interface EvidenceRowProps {
  item: EvidenceItem;
  onDelete: (filename: string) => void;
  caseId: string;
}

function EvidenceRow({ item, onDelete, caseId }: EvidenceRowProps): JSX.Element {
  const [confirming, setConfirming] = useState(false);
  return (
    <li
      data-testid="evidence-row"
      data-filename={item.filename}
      className="flex items-center gap-2 border-b border-[#2A2622]/60 px-4 py-2 text-[11px]"
    >
      <span
        data-testid="evidence-drag-handle"
        draggable
        onDragStart={(e) => {
          // Story 8.5 / AC #4 — minimal payload; the editor's Tiptap
          // extension can read this on drop. Full Tiptap inline-node
          // wiring lands later (noted in the story doc).
          e.dataTransfer.setData(
            'application/x-cockpit-evidence-ref',
            JSON.stringify({ filename: item.filename, caseId }),
          );
          e.dataTransfer.effectAllowed = 'copy';
        }}
        className="cursor-grab select-none text-[#F1ECE3]/40 hover:text-[#F1ECE3]/70"
        aria-label={`Drag ${item.filename} into editor`}
      >
        ⋮⋮
      </span>
      <a
        href={`/v1/cases/${encodeURIComponent(caseId)}/evidence/${encodeURIComponent(item.filename)}/download`}
        target="_blank"
        rel="noreferrer"
        className="flex-1 truncate hover:underline"
      >
        {item.filename}
      </a>
      <span className="opacity-50">{_formatTimestamp(item.uploaded_at)}</span>
      {confirming ? (
        <button
          type="button"
          data-testid="evidence-confirm-delete"
          onClick={() => onDelete(item.filename)}
          className="rounded border border-rose-400/60 px-1.5 py-0.5 text-[10px] text-rose-300"
        >
          Delete?
        </button>
      ) : (
        <button
          type="button"
          data-testid="evidence-delete-button"
          onClick={() => setConfirming(true)}
          aria-label={`Remove ${item.filename}`}
          className="opacity-30 hover:opacity-80"
        >
          ×
        </button>
      )}
    </li>
  );
}
