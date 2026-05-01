import { useState } from 'react';

async function copyToClipboard(text) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch { /* fall through */ }
  try {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    return true;
  } catch {
    return false;
  }
}

/**
 * Inline button that copies `value` and briefly replaces its label with a
 * "copied" confirmation. Use it where a click should yield clipboard text
 * rather than open a system handler (mailto silently no-ops without a
 * configured mail client).
 */
export default function CopyText({ label, value, copiedLabel, className, style }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      className={className}
      style={style}
      title={copied ? '' : `点击复制 ${value}`}
      onClick={async () => {
        const ok = await copyToClipboard(value);
        if (!ok) return;
        setCopied(true);
        setTimeout(() => setCopied(false), 1400);
      }}
    >
      {copied ? (copiedLabel || `✓ ${label} copied`) : label}
    </button>
  );
}

export { copyToClipboard };
