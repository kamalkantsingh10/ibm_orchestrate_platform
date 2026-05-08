// eddMemoToHtml tests — Story 8.3 / AC #7.

import { describe, expect, it } from 'vitest';
import { eddMemoToHtml, type EddMemoOutput } from './eddMemoToHtml';

const LED_A = 'led_01ABCDEFGHJKMNPQRSTVWXYZ12';
const LED_B = 'led_01HXY3GHJKMNPQRSTVWXYZ7HX2';

function _memo(overrides: Partial<EddMemoOutput> = {}): EddMemoOutput {
  return {
    case_id: 'case_01ABCDEFGHJKMNPQRSTVWXYZ12',
    executive_summary: `Cites {{${LED_A}}} as the basis.`,
    findings: `Findings cite {{${LED_B}}}.`,
    risk_factors: 'Risk factors text.',
    mitigating_factors: 'Mitigants text.',
    recommendation: `Recommend per {{${LED_A}}}.`,
    citations: [LED_A, LED_B],
    model_id: 'fixture-edd-v1',
    prompt_template_id: 'edd_memo_v1',
    ...overrides,
  };
}

describe('eddMemoToHtml', () => {
  it('renders five sections as h2 + p in the canonical order', () => {
    const html = eddMemoToHtml(_memo());
    expect(html).toMatch(
      /<h2>Executive Summary<\/h2><p>.*<\/p><h2>Findings<\/h2><p>.*<\/p><h2>Risk Factors<\/h2><p>.*<\/p><h2>Mitigating Factors<\/h2><p>.*<\/p><h2>Recommendation<\/h2><p>.*<\/p>/,
    );
  });

  it('rewrites `{{led_<ULID>}}` tokens to citation-token spans', () => {
    const html = eddMemoToHtml(_memo());
    expect(html).toContain(
      `<span data-ledger-id="${LED_A}" class="citation-token">${LED_A}</span>`,
    );
    expect(html).toContain(
      `<span data-ledger-id="${LED_B}" class="citation-token">${LED_B}</span>`,
    );
  });

  it('escapes HTML special chars in section text before inserting citation chips', () => {
    const html = eddMemoToHtml(
      _memo({
        executive_summary: `<script>alert(1)</script> cites {{${LED_A}}}.`,
      }),
    );
    expect(html).not.toContain('<script>');
    expect(html).toContain('&lt;script&gt;');
    // Citation chip still present and well-formed.
    expect(html).toContain(`<span data-ledger-id="${LED_A}"`);
  });

  it('emits no citation chip for sections without inline tokens', () => {
    const html = eddMemoToHtml(
      _memo({
        risk_factors: 'No citation here.',
        mitigating_factors: 'Also no citation here.',
      }),
    );
    expect(html).toContain('<h2>Risk Factors</h2><p>No citation here.</p>');
    expect(html).toContain('<h2>Mitigating Factors</h2><p>Also no citation here.</p>');
  });

  it('handles repeated tokens in the same section', () => {
    const html = eddMemoToHtml(
      _memo({
        findings: `Cites {{${LED_A}}} and again {{${LED_A}}}.`,
      }),
    );
    const matches = html.match(new RegExp(`data-ledger-id="${LED_A}"`, 'g'));
    expect(matches).not.toBeNull();
    // Two inline tokens → two chips. Plus the executive_summary uses
    // LED_A too, so total occurrences ≥ 3 across the rendered memo.
    expect(matches!.length).toBeGreaterThanOrEqual(3);
  });
});
