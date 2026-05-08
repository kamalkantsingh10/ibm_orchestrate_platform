// Citation parser — Story 6.8 / AC #5.
//
// Splits a chat reply into text + citation segments. The regex matches
// the `LedgerEntryId` contract pattern verbatim
// (`led_<26-char Crockford-Base32>`).

export type Segment = { kind: 'text'; text: string } | { kind: 'citation'; ledgerId: string };

const _LEDGER_RE = /led_[0-9A-HJKMNP-TV-Z]{26}/g;

export function parseCitations(text: string): Segment[] {
  const segments: Segment[] = [];
  let lastIndex = 0;
  for (const match of text.matchAll(_LEDGER_RE)) {
    const idx = match.index ?? 0;
    if (idx > lastIndex) {
      segments.push({ kind: 'text', text: text.slice(lastIndex, idx) });
    }
    segments.push({ kind: 'citation', ledgerId: match[0] });
    lastIndex = idx + match[0].length;
  }
  if (lastIndex < text.length) {
    segments.push({ kind: 'text', text: text.slice(lastIndex) });
  }
  return segments;
}
