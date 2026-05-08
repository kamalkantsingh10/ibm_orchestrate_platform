// Drag-correct tag modal — Story 5.5 / AC #7.
//
// Tag the relationship as one of {real_ubo, nominee, director, removed},
// attach an evidence note, and opt-in for retraining (no current consumer
// — flag is captured for audit + future use).

import { useState, type FormEvent } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import type { components } from '@/api-types';
import type { UBOEdge } from './adapter';

export type CorrectionTag = components['schemas']['CorrectionTag'];

export interface CorrectionTagModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  edge: UBOEdge | null;
  newTargetId: string | null;
  onConfirm: (
    tag: CorrectionTag,
    evidenceNote: string,
    optInForRetraining: boolean,
  ) => Promise<void> | void;
}

const TAGS: { value: CorrectionTag; label: string; description: string; destructive?: boolean }[] =
  [
    {
      value: 'real_ubo',
      label: 'Real UBO',
      description: 'This holder is the genuine ultimate beneficial owner.',
    },
    {
      value: 'nominee',
      label: 'Nominee',
      description: 'This holder is acting as a nominee for someone else.',
    },
    { value: 'director', label: 'Director', description: 'Reclassify as a director relationship.' },
    {
      value: 'removed',
      label: 'Remove this edge',
      description: 'The relationship does not exist; strip the edge from the graph.',
      destructive: true,
    },
  ];

export function CorrectionTagModal({
  open,
  onOpenChange,
  edge,
  newTargetId,
  onConfirm,
}: CorrectionTagModalProps) {
  const [selectedTag, setSelectedTag] = useState<CorrectionTag | null>(null);
  const [evidenceNote, setEvidenceNote] = useState('');
  const [optIn, setOptIn] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedTag || evidenceNote.trim().length === 0) return;
    setSubmitting(true);
    try {
      await onConfirm(selectedTag, evidenceNote.trim(), optIn);
      onOpenChange(false);
      setSelectedTag(null);
      setEvidenceNote('');
      setOptIn(false);
    } finally {
      setSubmitting(false);
    }
  };

  const isConfirmDisabled = !selectedTag || evidenceNote.trim().length === 0 || submitting;

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/30" />
        <Dialog.Content
          className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[480px] max-w-[90vw] rounded-md bg-white shadow-lg p-5"
          data-testid="correction-tag-modal"
        >
          <Dialog.Title className="text-lg font-semibold text-zinc-900">
            Tag this correction
          </Dialog.Title>
          {edge ? (
            <Dialog.Description className="mt-1 text-xs text-zinc-500">
              {edge.from_id} → {edge.to_id} ({edge.kind}
              {edge.ownership_pct != null ? `, ${edge.ownership_pct}%` : ''})
              {newTargetId && newTargetId !== edge.to_id ? (
                <span className="block mt-1">
                  New target: <span className="font-mono">{newTargetId}</span>
                </span>
              ) : null}
            </Dialog.Description>
          ) : null}

          <form onSubmit={handleSubmit} className="mt-4 space-y-4">
            <fieldset className="space-y-2" aria-label="Correction tag">
              <legend className="text-xs font-medium text-zinc-700">Choose a tag</legend>
              {TAGS.map((opt) => {
                const disabled = opt.value === 'director' && edge?.kind !== 'director';
                return (
                  <label
                    key={opt.value}
                    className={`flex cursor-pointer items-start gap-3 rounded border p-2 transition-colors ${
                      selectedTag === opt.value
                        ? opt.destructive
                          ? 'border-rose-500 bg-rose-50'
                          : 'border-zinc-700 bg-zinc-50'
                        : 'border-zinc-200'
                    } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    <input
                      type="radio"
                      name="correction_tag"
                      value={opt.value}
                      checked={selectedTag === opt.value}
                      onChange={() => setSelectedTag(opt.value)}
                      disabled={disabled}
                      aria-label={opt.label}
                      data-testid={`tag-radio-${opt.value}`}
                      className="mt-1"
                    />
                    <div>
                      <div
                        className={`text-sm font-medium ${opt.destructive ? 'text-rose-700' : 'text-zinc-900'}`}
                      >
                        {opt.label}
                      </div>
                      <div className="text-xs text-zinc-600">{opt.description}</div>
                    </div>
                  </label>
                );
              })}
            </fieldset>

            <div>
              <label htmlFor="evidence-note" className="text-xs font-medium text-zinc-700">
                Evidence note
              </label>
              <textarea
                id="evidence-note"
                value={evidenceNote}
                onChange={(e) => setEvidenceNote(e.target.value)}
                placeholder='e.g., "RM email Nov 2024 — disclosed real UBO is offshore family trust"'
                required
                minLength={1}
                maxLength={500}
                rows={3}
                className="mt-1 w-full rounded border border-zinc-300 px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-500"
                data-testid="evidence-note-textarea"
              />
              <div className="text-[10px] text-zinc-500 text-right mt-0.5">
                {evidenceNote.length} / 500
              </div>
            </div>

            <label className="flex items-center gap-2 text-xs text-zinc-700">
              <input
                type="checkbox"
                checked={optIn}
                onChange={(e) => setOptIn(e.target.checked)}
                data-testid="opt-in-checkbox"
              />
              Use this correction as labeled training signal (opt-in)
            </label>

            <div className="flex justify-end gap-2 pt-2 border-t border-zinc-100">
              <button
                type="button"
                onClick={() => onOpenChange(false)}
                className="px-3 py-1.5 text-sm rounded border border-zinc-300 text-zinc-700 hover:bg-zinc-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-500"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isConfirmDisabled}
                data-testid="confirm-button"
                className={`px-3 py-1.5 text-sm rounded text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed ${
                  selectedTag === 'removed'
                    ? 'bg-rose-600 hover:bg-rose-700 focus-visible:ring-rose-500'
                    : 'bg-zinc-900 hover:bg-zinc-800 focus-visible:ring-zinc-500'
                }`}
              >
                Confirm correction
              </button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
