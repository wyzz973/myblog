import { useEffect } from 'react';

// Shared dialog used by `useConfirm()`. Visual language matches the
// existing palette / draft-banner surfaces (var(--bg-2), var(--line)).
// `state` is null when no confirm is pending — render nothing in that
// case so we never paint an empty backdrop.
export default function ConfirmModal({ state, onConfirm, onCancel }) {
  useEffect(() => {
    if (!state) return undefined;
    function onKey(e) {
      if (e.key === 'Escape') {
        e.preventDefault();
        onCancel();
      } else if (e.key === 'Enter') {
        e.preventDefault();
        onConfirm();
      }
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [state, onConfirm, onCancel]);

  if (!state) return null;

  const { title, message, confirmLabel, cancelLabel, destructive } = state;

  return (
    <div
      className="palette-bg"
      data-testid="confirm-modal"
      data-shortcut-suppress="true"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onCancel();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        style={panelStyle}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div style={headerStyle}>
          <span style={titleStyle}>{title}</span>
          <button type="button" onClick={onCancel} style={closeStyle} aria-label="关闭">
            ×
          </button>
        </div>
        {message && <div style={bodyStyle}>{message}</div>}
        <div style={footerStyle}>
          <button
            type="button"
            onClick={onCancel}
            style={cancelBtnStyle}
            data-testid="confirm-cancel"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            style={destructive ? destructiveBtnStyle : primaryBtnStyle}
            data-testid="confirm-ok"
            autoFocus
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

const panelStyle = {
  width: 'min(440px, 92vw)',
  background: 'var(--bg-2)',
  border: '1px solid var(--line-2)',
  borderRadius: 10,
  boxShadow: '0 20px 80px rgba(0,0,0,0.6), 0 0 0 1px var(--line)',
  overflow: 'hidden',
  fontFamily: "'JetBrains Mono', monospace",
};
const headerStyle = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: '14px 18px',
  borderBottom: '1px solid var(--line)',
};
const titleStyle = { fontSize: 13, fontWeight: 600, color: 'var(--fg)' };
const closeStyle = {
  background: 'transparent',
  border: 0,
  fontSize: 18,
  color: 'var(--fg-3)',
  cursor: 'pointer',
  padding: 0,
  width: 22,
  height: 22,
  lineHeight: 1,
};
const bodyStyle = {
  padding: '14px 18px',
  fontSize: 12,
  color: 'var(--fg-2)',
  lineHeight: 1.55,
};
const footerStyle = {
  display: 'flex',
  justifyContent: 'flex-end',
  gap: 8,
  padding: '12px 18px',
  borderTop: '1px solid var(--line)',
  background: 'var(--bg-3)',
};
const baseBtnStyle = {
  fontFamily: 'inherit',
  fontSize: 12,
  padding: '6px 14px',
  borderRadius: 4,
  cursor: 'pointer',
};
const cancelBtnStyle = {
  ...baseBtnStyle,
  background: 'transparent',
  color: 'var(--fg-2)',
  border: '1px solid var(--line-2)',
};
const primaryBtnStyle = {
  ...baseBtnStyle,
  background: 'var(--accent)',
  color: 'var(--bg)',
  border: '1px solid var(--accent)',
  fontWeight: 600,
};
const destructiveBtnStyle = {
  ...baseBtnStyle,
  background: 'var(--danger, #c44)',
  color: 'white',
  border: '1px solid var(--danger, #c44)',
  fontWeight: 600,
};
