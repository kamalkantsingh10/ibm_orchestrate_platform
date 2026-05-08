// useDecisionEditor — Story 7.1 / AC #5.
//
// Tiptap editor instance for the DecisionZone. StarterKit is slimmed to
// paragraph + bold + italic + history; everything else is overkill for a
// KYC rationale. Placeholder copy nudges the analyst when the Writing
// agent's draft hasn't arrived yet.
//
// Pitfall #4 (story dev notes): some Tiptap versions don't pick up
// `editable` flips after init. We mitigate by passing `editable` via the
// options object and then keying the surrounding component on the
// read-only flag — see DecisionZone.tsx.

import { useEditor, type Editor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Placeholder from '@tiptap/extension-placeholder';
import { CitationMark } from './CitationMark';

export interface UseDecisionEditorOptions {
  initialHtml: string;
  editable: boolean;
  onUpdate: (html: string) => void;
  /** When this changes, the editor is rebuilt with the new initialHtml.
   *  We key on caseId so a per-case content swap recreates the editor
   *  cleanly without a runtime setContent dance. */
  rebuildKey: string;
}

export function useDecisionEditor(opts: UseDecisionEditorOptions): Editor | null {
  return useEditor(
    {
      immediatelyRender: true,
      extensions: [
        StarterKit.configure({
          heading: false,
          codeBlock: false,
          code: false,
          horizontalRule: false,
          blockquote: false,
          bulletList: false,
          orderedList: false,
          listItem: false,
          strike: false,
        }),
        Placeholder.configure({
          placeholder: 'Write your rationale here, or wait for the Writing agent to populate one…',
        }),
        CitationMark,
      ],
      content: opts.initialHtml,
      editable: opts.editable,
      onUpdate: ({ editor }) => opts.onUpdate(editor.getHTML()),
      editorProps: {
        attributes: {
          class:
            'prose prose-sm max-w-none focus-visible:outline-none min-h-[12rem] text-zinc-900 leading-relaxed',
        },
      },
    },
    [opts.rebuildKey],
  );
}
