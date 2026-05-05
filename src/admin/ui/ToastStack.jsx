// Bottom-right stack of transient feedback messages. Driven entirely
// by the `toasts` prop from UIProvider — this component owns no state.
const KIND_STYLES = {
  success: {
    border: '1px solid var(--accent)',
    color: 'var(--fg)',
    background: 'color-mix(in oklab, var(--accent) 14%, var(--bg-2))',
  },
  error: {
    border: '1px solid var(--danger, #c44)',
    color: 'var(--fg)',
    background: 'color-mix(in oklab, var(--danger, #c44) 14%, var(--bg-2))',
  },
  info: {
    border: '1px solid var(--line-2)',
    color: 'var(--fg-2)',
    background: 'var(--bg-2)',
  },
};

const KIND_LABEL = { success: '✓', error: '!', info: 'i' };

export default function ToastStack({ toasts, onDismiss }) {
  if (!toasts.length) return null;
  return (
    <div style={stackStyle} data-testid="toast-stack">
      {toasts.map((t) => (
        <div
          key={t.id}
          role="status"
          data-testid={`toast-${t.kind}`}
          style={{ ...itemStyle, ...KIND_STYLES[t.kind] }}
          onClick={() => onDismiss(t.id)}
        >
          <span style={iconStyle}>{KIND_LABEL[t.kind]}</span>
          <span>{t.message}</span>
        </div>
      ))}
    </div>
  );
}

const stackStyle = {
  position: 'fixed',
  right: 18,
  bottom: 18,
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
  zIndex: 200,
  fontFamily: "'JetBrains Mono', monospace",
  pointerEvents: 'none',
};
const itemStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  padding: '8px 12px',
  borderRadius: 6,
  fontSize: 12,
  minWidth: 220,
  maxWidth: 360,
  boxShadow: '0 8px 28px rgba(0,0,0,0.35)',
  pointerEvents: 'auto',
  cursor: 'pointer',
  animation: 'fadein 0.2s ease-out',
};
const iconStyle = {
  display: 'inline-flex',
  width: 18,
  height: 18,
  alignItems: 'center',
  justifyContent: 'center',
  borderRadius: 999,
  border: '1px solid currentColor',
  fontSize: 11,
  flexShrink: 0,
};
