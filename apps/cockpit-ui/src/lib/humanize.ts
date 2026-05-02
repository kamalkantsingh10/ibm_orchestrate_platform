// Field-name humanization for the Documents panel and downstream
// agent-driven UIs — Story 3.6 AC #7.

const SPECIAL_ACRONYMS: Record<string, string> = {
  cin: 'CIN',
  pan: 'PAN',
  gst: 'GST',
  gstin: 'GSTIN',
  din: 'DIN',
  ubo: 'UBO',
  inr: 'INR',
};

export function humanizeFieldName(name: string): string {
  if (!name) return '';
  const tokens = name.split('_').map((tok) => {
    const lower = tok.toLowerCase();
    if (SPECIAL_ACRONYMS[lower]) return SPECIAL_ACRONYMS[lower];
    return lower;
  });
  if (tokens.length === 0) return '';
  // Capitalize the first non-acronym token; leave acronyms as-is.
  const [first, ...rest] = tokens;
  const firstFmt =
    first === SPECIAL_ACRONYMS[first.toLowerCase()]
      ? first
      : first.charAt(0).toUpperCase() + first.slice(1);
  return [firstFmt, ...rest].join(' ');
}
