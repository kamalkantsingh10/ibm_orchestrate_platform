// citationValidator — Story 7.1 / AC #7.
//
// Pure helpers that scan Tiptap-rendered HTML for `data-ledger-id`
// attributes and return broken IDs (those not present in the case
// ledger). Pure / non-React so the helpers double as the test fodder
// for AC #14 and the wiring point for the Commit-button gate in
// DecisionZone.tsx.
//
// LedgerEntryId pattern matches the contract used everywhere else in
// the demo: `led_<26 char Crockford-Base32>` (excluding I, L, O, U).

const _CITATION_RE = /data-ledger-id="(led_[0-9A-HJKMNP-TV-Z]{26})"/g;

export function findCitations(html: string): string[] {
  return Array.from(html.matchAll(_CITATION_RE), (m) => m[1] as string);
}

export function findBrokenCitations(html: string, ledgerIds: Set<string>): string[] {
  return findCitations(html).filter((id) => !ledgerIds.has(id));
}
