// Global keyboard shortcuts — Stories 4.7 (Cmd+1..6 mode switch), 4.8
// (⌘K command palette), and 7.2 (⌘+Shift+D focus DecisionZone).
// Mounted once in __root.tsx so they fire on every route, including the
// case canvas.
//
// Queue-specific bindings (j/k/Enter/x/d) live in useKeyboardShortcuts and
// are mounted only in /queue, where the focusable list exists.

import { useEffect } from 'react';
import { toast } from 'sonner';
import { useAnnouncer } from '@/stores/announcerStore';
import { useMode } from '@/stores/modeStore';
import { usePalette } from '@/stores/paletteStore';

function _isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
  if (target.isContentEditable) return true;
  return false;
}

export function useGlobalShortcuts(): void {
  const setMode = useMode((s) => s.setMode);
  const togglePalette = usePalette((s) => s.toggle);
  const announce = useAnnouncer((s) => s.announce);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const cmdOrCtrl = e.metaKey || e.ctrlKey;

      // ⌘K — bypass input-focus guard so users can toggle from inside the
      // palette's own input.
      if (cmdOrCtrl && e.key === 'k') {
        e.preventDefault();
        togglePalette();
        return;
      }

      // ⌘+Shift+D — Story 7.2 focus the Decision Zone. We allow this
      // even when typing target is active so the analyst can jump
      // straight from the queue's `j/k` traversal into the editor.
      // `e.code === 'KeyD'` so caps-lock and lowercase both work.
      if (cmdOrCtrl && e.shiftKey && (e.key === 'd' || e.key === 'D' || e.code === 'KeyD')) {
        const target = document.querySelector<HTMLElement>('[data-decision-zone-focus-target]');
        if (target) {
          e.preventDefault();
          // The focus target is a content wrapper; look inside for the
          // contenteditable Tiptap surface so the cursor lands ready
          // for the analyst to type. Fall back to the wrapper itself
          // if the editor hasn't mounted yet.
          const editable = target.querySelector<HTMLElement>('[contenteditable="true"]');
          (editable ?? target).focus();
          announce('Focused Decision Zone');
          return;
        }
      }

      if (_isTypingTarget(e.target)) return;

      if (cmdOrCtrl && /^[1-6]$/.test(e.key)) {
        e.preventDefault();
        if (e.key === '1') {
          setMode('investigation');
          announce('Switched to Investigation mode');
        } else {
          toast('Mode not yet available', {
            description: 'Investigation is the only mode in this build.',
            duration: 2500,
          });
        }
      }
    };

    window.addEventListener('keydown', handler, { capture: true });
    return () => window.removeEventListener('keydown', handler, { capture: true });
  }, [setMode, togglePalette, announce]);
}
