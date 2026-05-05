import { useEffect } from 'react';
import { SHORTCUT_GROUPS } from './keyboardShortcuts.js';

// Modal listing every keyboard shortcut grouped by scope. Pure render —
// the parent owns open/close state and calls back via `onClose`.
export default function ShortcutsHelp({ open, onClose }) {
  useEffect(() => {
    if (!open) return undefined;
    function onKey(e) {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="palette-bg"
      data-testid="shortcuts-help"
      data-shortcut-suppress="true"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="palette" style={panelStyle} onMouseDown={(e) => e.stopPropagation()}>
        <header style={headerStyle}>
          <span style={titleStyle}>键盘快捷键</span>
          <span style={hintStyle}>
            按 <kbd style={kbdStyle}>Esc</kbd> 关闭
          </span>
        </header>
        <div style={bodyStyle}>
          {SHORTCUT_GROUPS.map((group) => (
            <section key={group.scope} style={groupStyle}>
              <div style={scopeStyle}>{group.scope}</div>
              <table style={tableStyle}>
                <tbody>
                  {group.items.map((item, i) => (
                    <tr key={i}>
                      <td style={keysCellStyle}>
                        {item.keys.map((k, j) => (
                          <span key={j}>
                            <kbd style={kbdStyle}>{k}</kbd>
                            {j < item.keys.length - 1 && <span style={plusStyle}>+</span>}
                          </span>
                        ))}
                      </td>
                      <td style={descCellStyle}>{item.desc}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}

const panelStyle = { width: 'min(560px, 92vw)', maxHeight: '78vh' };
const headerStyle = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: '14px 18px',
  borderBottom: '1px solid var(--line)',
};
const titleStyle = { fontSize: 13, fontWeight: 600, color: 'var(--fg)' };
const hintStyle = { color: 'var(--fg-4)', fontSize: 11 };
const bodyStyle = { padding: '12px 18px 18px', overflow: 'auto' };
const groupStyle = { marginBottom: 16 };
const scopeStyle = {
  fontSize: 9,
  letterSpacing: '0.12em',
  textTransform: 'uppercase',
  color: 'var(--fg-4)',
  marginBottom: 6,
};
const tableStyle = { width: '100%', fontSize: 12, borderCollapse: 'collapse' };
const keysCellStyle = { padding: '4px 8px 4px 0', whiteSpace: 'nowrap' };
const descCellStyle = { padding: '4px 0', color: 'var(--fg-2)' };
const kbdStyle = {
  padding: '1px 6px',
  border: '1px solid var(--line)',
  borderRadius: 3,
  background: 'var(--bg-3)',
  color: 'var(--fg)',
  fontSize: 11,
  fontFamily: "'JetBrains Mono', monospace",
};
const plusStyle = { color: 'var(--fg-4)', margin: '0 4px' };
