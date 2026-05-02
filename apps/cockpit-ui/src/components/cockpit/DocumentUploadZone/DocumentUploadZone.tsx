// DocumentUploadZone — Story 3.8 AC #5.
//
// Drag-and-drop + file-picker upload zone. Posts to
// /v1/cases/{id}/documents (multipart). Shows per-file progress via XHR.
// On success, calls onUploadComplete so the parent can invalidate the
// document_intelligence query.

import clsx from 'clsx';
import { Upload, X, FileText } from 'lucide-react';
import { useCallback, useRef, useState } from 'react';
import { useCurrentUser } from '@/stores/currentUser';

export interface DocumentUploadZoneProps {
  caseId: string;
  /** Called after every successful upload batch. */
  onUploadComplete?: () => void;
}

interface UploadState {
  filename: string;
  progress: number; // 0..100
  status: 'pending' | 'uploading' | 'done' | 'error';
  error?: string;
}

const ENDPOINT_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '';

export function DocumentUploadZone({
  caseId,
  onUploadComplete,
}: DocumentUploadZoneProps): JSX.Element {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [items, setItems] = useState<UploadState[]>([]);
  const userId = useCurrentUser((s) => s.user.id);

  const upload = useCallback(
    async (files: File[]) => {
      if (files.length === 0) return;
      const initial: UploadState[] = files.map((f) => ({
        filename: f.name,
        progress: 0,
        status: 'uploading',
      }));
      setItems((prev) => [...prev, ...initial]);

      // Use a single multipart request for all files (matches the backend's
      // batch behavior).
      const fd = new FormData();
      for (const f of files) fd.append('files', f);

      const xhr = new XMLHttpRequest();
      const url = `${ENDPOINT_BASE}/v1/cases/${caseId}/documents`;
      xhr.open('POST', url);
      xhr.setRequestHeader('X-Cockpit-Demo-User', userId);

      xhr.upload.onprogress = (e) => {
        if (!e.lengthComputable) return;
        const pct = Math.round((e.loaded / e.total) * 100);
        setItems((prev) =>
          prev.map((it) =>
            files.some((f) => f.name === it.filename) && it.status === 'uploading'
              ? { ...it, progress: pct }
              : it,
          ),
        );
      };

      xhr.onload = () => {
        const ok = xhr.status >= 200 && xhr.status < 300;
        let detail: string | undefined;
        if (!ok) {
          try {
            const body = JSON.parse(xhr.responseText) as { detail?: string };
            detail = body.detail ?? `HTTP ${xhr.status}`;
          } catch {
            detail = `HTTP ${xhr.status}`;
          }
        }
        setItems((prev) =>
          prev.map((it) => {
            if (!files.some((f) => f.name === it.filename)) return it;
            return ok
              ? { ...it, progress: 100, status: 'done' }
              : { ...it, status: 'error', error: detail };
          }),
        );
        if (ok) onUploadComplete?.();
      };

      xhr.onerror = () => {
        setItems((prev) =>
          prev.map((it) =>
            files.some((f) => f.name === it.filename)
              ? { ...it, status: 'error', error: 'Network error' }
              : it,
          ),
        );
      };

      xhr.send(fd);
    },
    [caseId, userId, onUploadComplete],
  );

  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragActive(false);
    const files = Array.from(e.dataTransfer.files).filter((f) =>
      f.name.toLowerCase().endsWith('.pdf'),
    );
    void upload(files);
  };

  const onFilePicked = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    void upload(files);
    if (inputRef.current) inputRef.current.value = '';
  };

  const dismissItem = (filename: string) => {
    setItems((prev) => prev.filter((it) => it.filename !== filename));
  };

  return (
    <div
      className={clsx(
        'rounded-md border-2 border-dashed px-4 py-5 transition-colors duration-150 motion-reduce:transition-none',
        dragActive ? 'border-emerald-500 bg-emerald-50' : 'border-zinc-300 bg-zinc-50',
      )}
      onDragEnter={(e) => {
        e.preventDefault();
        setDragActive(true);
      }}
      onDragOver={(e) => {
        e.preventDefault();
        setDragActive(true);
      }}
      onDragLeave={() => setDragActive(false)}
      onDrop={onDrop}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm text-zinc-700">
          <Upload className="w-4 h-4 text-zinc-500" aria-hidden="true" />
          <span>Drop PDFs here or click to browse</span>
        </div>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="text-xs px-2 py-1 rounded border border-zinc-300 bg-white hover:bg-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-400"
        >
          Browse
        </button>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf"
          multiple
          className="hidden"
          onChange={onFilePicked}
        />
      </div>

      {items.length > 0 ? (
        <ul className="mt-3 space-y-1.5" data-testid="upload-zone-items">
          {items.map((it) => (
            <li
              key={it.filename}
              className="flex items-center gap-2 text-xs"
              data-testid={`upload-item-${it.filename}`}
            >
              <FileText className="w-3.5 h-3.5 flex-shrink-0 text-zinc-500" aria-hidden="true" />
              <span className="font-mono text-zinc-700 flex-1 truncate">{it.filename}</span>
              {it.status === 'uploading' ? (
                <span className="tabular-nums text-zinc-600">{it.progress}%</span>
              ) : null}
              {it.status === 'done' ? <span className="text-emerald-600">✓ uploaded</span> : null}
              {it.status === 'error' ? (
                <span role="alert" className="text-rose-600">
                  {it.error ?? 'Failed'}
                </span>
              ) : null}
              <button
                type="button"
                onClick={() => dismissItem(it.filename)}
                className="p-0.5 rounded hover:bg-zinc-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-400"
                aria-label={`Dismiss ${it.filename} from list`}
              >
                <X className="w-3 h-3 text-zinc-500" aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
