import { useEffect, useRef } from 'react';
import { resolveJump, shouldIgnoreEvent } from './keyboardShortcuts.js';

// 1.5s window for the second key in a `g <x>` sequence. Long enough for
// the user to think; short enough that a stray `g` doesn't lock global
// keys for the next minute.
const G_WINDOW_MS = 1500;

// React hook: binds `?` (open help) and `g <x>` (jump-to) to the window.
// All other shortcuts (⌘K, palette internals, page-specific j/k) live
// elsewhere and are coordinated via `shouldIgnoreEvent`.
export default function useGlobalShortcuts({ navigate, onShowHelp }) {
  const gPendingRef = useRef(null);

  useEffect(() => {
    function onKey(e) {
      if (shouldIgnoreEvent(e)) return;

      // Resolving the `g <x>` second key takes priority over a fresh `g`.
      if (gPendingRef.current) {
        clearTimeout(gPendingRef.current);
        gPendingRef.current = null;
        const dest = resolveJump(e.key);
        if (dest) {
          e.preventDefault();
          navigate(dest.to);
        }
        return;
      }

      if (e.key === '?') {
        e.preventDefault();
        onShowHelp();
        return;
      }

      if (e.key === 'g' || e.key === 'G') {
        e.preventDefault();
        gPendingRef.current = setTimeout(() => {
          gPendingRef.current = null;
        }, G_WINDOW_MS);
      }
    }

    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
      if (gPendingRef.current) clearTimeout(gPendingRef.current);
    };
  }, [navigate, onShowHelp]);
}
