// OutcomeSelector — Story 7.9 / AC #3.
//
// Replaces Story 7.1's stub. Native <select> for the outcome (Radix
// Select would be the ideal — left as a follow-up if accessibility
// review flags); a chip-style conditions editor when outcome is
// `approve_with_conditions`; an italicized hint when `escalate_to_edd`.
// The component clears conditions on outcome change to keep
// Story 7.7's tightened validator happy (conditions + non-AwC →
// 422 on commit).

import { X } from 'lucide-react';
import { useState, type ChangeEvent, type KeyboardEvent } from 'react';
import type { DecisionOutcome } from '@/hooks/useDecisionDraft';

const _OUTCOMES: { value: DecisionOutcome; label: string }[] = [
  { value: 'approve', label: 'Approve' },
  { value: 'decline', label: 'Decline' },
  { value: 'approve_with_conditions', label: 'Approve with conditions' },
  { value: 'escalate_to_edd', label: 'Escalate to EDD' },
];

const _MAX_CONDITIONS = 10;
const _MAX_CONDITION_CHARS = 200;

export interface OutcomeSelectorProps {
  outcome: DecisionOutcome | null;
  conditions: string[];
  onOutcomeChange: (outcome: DecisionOutcome | null) => void;
  onConditionsChange: (conds: string[]) => void;
  disabled?: boolean;
}

export function OutcomeSelector({
  outcome,
  conditions,
  onOutcomeChange,
  onConditionsChange,
  disabled = false,
}: OutcomeSelectorProps) {
  const [draft, setDraft] = useState('');

  const showConditions = outcome === 'approve_with_conditions';
  const showEscalationHint = outcome === 'escalate_to_edd';
  const atMax = conditions.length >= _MAX_CONDITIONS;

  const handleOutcomeChange = (e: ChangeEvent<HTMLSelectElement>) => {
    const next = (e.target.value || null) as DecisionOutcome | null;
    onOutcomeChange(next);
    // Story 7.9 / AC #4 — switching away from approve_with_conditions
    // clears conditions so Story 7.7's validator doesn't reject the
    // committed body.
    if (next !== 'approve_with_conditions' && conditions.length > 0) {
      onConditionsChange([]);
    }
  };

  const addConditions = (raw: string) => {
    if (atMax) return;
    const splits = raw
      .split(/[\n,]/)
      .map((s) => s.trim())
      .filter((s) => s.length > 0 && s.length <= _MAX_CONDITION_CHARS);
    if (splits.length === 0) return;
    const remaining = _MAX_CONDITIONS - conditions.length;
    onConditionsChange([...conditions, ...splits.slice(0, remaining)]);
    setDraft('');
  };

  const removeAt = (idx: number) => {
    onConditionsChange(conditions.filter((_, i) => i !== idx));
  };

  const onConditionKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addConditions(draft);
      return;
    }
    if (e.key === 'Backspace' && draft === '' && conditions.length > 0 && !disabled) {
      e.preventDefault();
      removeAt(conditions.length - 1);
    }
  };

  const onConditionPaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    const text = e.clipboardData.getData('text');
    if (text.includes('\n') || text.includes(',')) {
      e.preventDefault();
      addConditions(text);
    }
  };

  return (
    <div className="flex flex-col gap-1.5" data-testid="outcome-selector">
      <div className="flex items-center gap-2">
        <label className="text-xs font-medium text-zinc-700" htmlFor="decision-outcome">
          Outcome
        </label>
        <select
          id="decision-outcome"
          aria-label="Decision outcome"
          value={outcome ?? ''}
          onChange={handleOutcomeChange}
          disabled={disabled}
          className="rounded border border-zinc-300 bg-white px-2 py-1 text-xs text-zinc-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-400 disabled:opacity-50"
        >
          <option value="">Select outcome…</option>
          {_OUTCOMES.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      {showConditions ? (
        <div className="flex flex-col gap-1" data-testid="outcome-selector-conditions">
          <div className="flex flex-wrap items-center gap-1">
            {conditions.map((c, idx) => (
              <span
                key={`${idx}-${c}`}
                title={c}
                data-testid="outcome-condition-chip"
                className="inline-flex max-w-[200px] items-center gap-1 truncate rounded bg-zinc-100 px-2 py-0.5 text-xs text-zinc-800"
              >
                <span className="truncate">{c}</span>
                {!disabled ? (
                  <button
                    type="button"
                    onClick={() => removeAt(idx)}
                    aria-label={`Remove condition ${c}`}
                    className="rounded text-zinc-500 hover:text-zinc-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-400"
                  >
                    <X className="h-3 w-3" aria-hidden />
                  </button>
                ) : null}
              </span>
            ))}
            {!disabled ? (
              <input
                aria-label="Add condition"
                data-testid="outcome-condition-input"
                type="text"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={onConditionKeyDown}
                onPaste={onConditionPaste}
                onBlur={() => draft.trim() && addConditions(draft)}
                maxLength={_MAX_CONDITION_CHARS}
                disabled={atMax}
                placeholder={atMax ? 'Max 10 conditions' : 'Add condition (Enter)'}
                className="min-w-[140px] flex-1 rounded border border-zinc-300 px-2 py-1 text-xs text-zinc-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-400 disabled:cursor-not-allowed disabled:opacity-50"
              />
            ) : null}
          </div>
          <span className="text-[10px] text-zinc-500">
            {conditions.length} / {_MAX_CONDITIONS}
          </span>
        </div>
      ) : null}

      {showEscalationHint ? (
        <p className="text-xs italic text-zinc-500">
          This case will appear in the Team Lead&apos;s approval queue after sealing.
        </p>
      ) : null}
    </div>
  );
}
