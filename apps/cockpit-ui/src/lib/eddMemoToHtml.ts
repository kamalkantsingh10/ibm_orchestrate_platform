// eddMemoToHtml — Story 8.3 / AC #7.
//
// Converts an `EddMemoOutput` into the Tiptap-seedable HTML expected by
// the Decision Zone editor. The five named sections render as
// `<h2>` + `<p>` blocks; inline `{{led_<ULID>}}` tokens become
// `<span data-ledger-id="led_…" class="citation-token">led_…</span>`
// chips so Story 7.1's commit-time citation validator picks them up
// without any extra wiring.
//
// Pure function, no DOM access — safe to call at SSR or in tests.

export interface EddMemoOutput {
  case_id: string;
  executive_summary: string;
  findings: string;
  risk_factors: string;
  mitigating_factors: string;
  recommendation: string;
  citations: string[];
  model_id: string;
  prompt_template_id: 'edd_memo_v1';
}

const _LEDGER_TOKEN_RE = /\{\{(led_[0-9A-HJKMNP-TV-Z]{26})\}\}/g;

function _escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function _renderSection(text: string): string {
  // Escape first, then re-introduce citation chips; the regex matches
  // the literal `{{led_…}}` markers which survive escape unchanged
  // because they contain no HTML special chars.
  const escaped = _escapeHtml(text);
  return escaped.replace(_LEDGER_TOKEN_RE, (_match, ledgerId: string) => {
    const safeId = _escapeHtml(ledgerId);
    return `<span data-ledger-id="${safeId}" class="citation-token">${safeId}</span>`;
  });
}

const _SECTION_TITLES: Array<[keyof EddMemoOutput, string]> = [
  ['executive_summary', 'Executive Summary'],
  ['findings', 'Findings'],
  ['risk_factors', 'Risk Factors'],
  ['mitigating_factors', 'Mitigating Factors'],
  ['recommendation', 'Recommendation'],
];

export function eddMemoToHtml(memo: EddMemoOutput): string {
  return _SECTION_TITLES
    .map(([key, title]) => {
      const body = _renderSection(memo[key] as string);
      return `<h2>${_escapeHtml(title)}</h2><p>${body}</p>`;
    })
    .join('');
}
