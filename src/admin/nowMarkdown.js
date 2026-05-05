// Minimal markdown → HTML renderer for the Now editor's preview pane.
// Now entries are short blurbs (≤ 5000 chars) — we don't need the full
// post pipeline. We support: paragraphs, **bold**, *italic*, `code`,
// `- item` lists, and bare links. Everything else is escaped.
//
// The output is meant to be injected via dangerouslySetInnerHTML, so we
// strictly escape HTML chars first. Unit-tested in nowMarkdown.test.js.

const HTML_ESCAPE = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => HTML_ESCAPE[c]);
}

function inline(s) {
  // Apply on already-escaped text — order matters: code first (literal),
  // then bold (** before *), then italic, then links.
  return s
    .replace(/`([^`]+)`/g, (_, x) => `<code>${x}</code>`)
    .replace(/\*\*([^*\n]+)\*\*/g, (_, x) => `<strong>${x}</strong>`)
    .replace(/\*([^*\n]+)\*/g, (_, x) => `<em>${x}</em>`)
    .replace(
      /\bhttps?:\/\/[^\s<]+/g,
      (m) => `<a href="${m}" target="_blank" rel="noopener noreferrer">${m}</a>`,
    );
}

export function renderNowMarkdown(md) {
  const text = String(md ?? '').trim();
  if (!text) return '';
  const lines = text.split(/\r?\n/);
  const out = [];
  let listBuf = [];

  function flushList() {
    if (!listBuf.length) return;
    out.push('<ul>' + listBuf.map((x) => `<li>${inline(escapeHtml(x))}</li>`).join('') + '</ul>');
    listBuf = [];
  }

  let paraBuf = [];
  function flushPara() {
    if (!paraBuf.length) return;
    const joined = paraBuf.join(' ');
    out.push('<p>' + inline(escapeHtml(joined)) + '</p>');
    paraBuf = [];
  }

  for (const raw of lines) {
    const line = raw.trim();
    if (line === '') {
      flushList();
      flushPara();
      continue;
    }
    const liMatch = line.match(/^[-*]\s+(.*)$/);
    if (liMatch) {
      flushPara();
      listBuf.push(liMatch[1]);
      continue;
    }
    flushList();
    paraBuf.push(line);
  }
  flushList();
  flushPara();
  return out.join('\n');
}
