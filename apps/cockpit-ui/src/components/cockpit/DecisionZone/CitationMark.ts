// CitationMark — Story 7.1 / AC #6.
//
// Tiptap inline mark that wraps text in a `<span data-ledger-id="led_…">`
// so the rendered citation token resolves to the case ledger. The mark is
// intentionally minimal: it carries one attribute (ledgerId) and a single
// CSS class. Validation (AC #7) and click-to-open-trace (AC #10) are
// owned by the DecisionZone component, not the mark itself.

import { Mark, mergeAttributes } from '@tiptap/core';

export interface CitationMarkOptions {
  HTMLAttributes: Record<string, unknown>;
}

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    citation: {
      setCitation: (attrs: { ledgerId: string }) => ReturnType;
      unsetCitation: () => ReturnType;
    };
  }
}

export const CitationMark = Mark.create<CitationMarkOptions>({
  name: 'citation',

  addOptions() {
    return {
      HTMLAttributes: {},
    };
  },

  addAttributes() {
    return {
      ledgerId: {
        default: null,
        parseHTML: (el) => el.getAttribute('data-ledger-id'),
        renderHTML: (attrs) =>
          attrs.ledgerId ? { 'data-ledger-id': attrs.ledgerId as string } : {},
      },
    };
  },

  parseHTML() {
    return [{ tag: 'span[data-ledger-id]' }];
  },

  renderHTML({ HTMLAttributes }) {
    return [
      'span',
      mergeAttributes(this.options.HTMLAttributes, HTMLAttributes, {
        class: 'citation-token',
      }),
      0,
    ];
  },

  addCommands() {
    return {
      setCitation:
        (attrs) =>
        ({ commands }) =>
          commands.setMark(this.name, attrs),
      unsetCitation:
        () =>
        ({ commands }) =>
          commands.unsetMark(this.name),
    };
  },
});
