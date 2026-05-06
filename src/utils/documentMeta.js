// Lightweight document.head meta updater (Task 69).
//
// 我们没有 SSR，所以这层只对「会执行 JS 的爬虫」（Slack 的某些场景、
// 站长本地分享前手动检查 head 的工具）生效。Twitter / Facebook 的爬虫
// 不会 hydrate，它们只读 index.html 里的静态默认。
//
// upsert：找到 (selector) 元素，更新 content；找不到就 createElement
// 插入。返回一个 cleanup 函数，组件卸载时把覆盖的 tag 还原成 index.html
// 的默认值（避免一个页面留下的 og:image 被下一个页面继承）。

const DEFAULTS = {
  title: 'myblog',
  description: 'A self-hosted personal blog.',
};

function upsertMeta(selector, attr, value) {
  const head = document.head;
  if (!head) return null;
  let el = head.querySelector(selector);
  const previous = el ? el.getAttribute('content') : null;
  if (!el) {
    el = document.createElement('meta');
    const [, key, name] = selector.match(/^meta\[(\w+)="([^"]+)"\]/) || [];
    if (key && name) el.setAttribute(key, name);
    head.appendChild(el);
  }
  if (typeof value === 'string') el.setAttribute('content', value);
  return previous;
}

export function setDocumentMeta({ title, description, type = 'website', image } = {}) {
  const t = title || DEFAULTS.title;
  const d = description || DEFAULTS.description;
  const previous = {};
  previous.title = document.title;
  document.title = t;
  previous.ogTitle = upsertMeta('meta[property="og:title"]', 'property', t);
  previous.ogDesc = upsertMeta('meta[property="og:description"]', 'property', d);
  previous.ogType = upsertMeta('meta[property="og:type"]', 'property', type);
  previous.twTitle = upsertMeta('meta[name="twitter:title"]', 'name', t);
  previous.twDesc = upsertMeta('meta[name="twitter:description"]', 'name', d);
  previous.metaDesc = upsertMeta('meta[name="description"]', 'name', d);
  if (image) {
    previous.ogImage = upsertMeta('meta[property="og:image"]', 'property', image);
    previous.twImage = upsertMeta('meta[name="twitter:image"]', 'name', image);
  }
  return previous;
}

export function restoreDocumentMeta(previous) {
  if (!previous) return;
  if (previous.title != null) document.title = previous.title;
  // 不删除我们插入的 tag — 只把 content 还原回 index.html 默认。
  upsertMeta('meta[property="og:title"]', 'property', DEFAULTS.title);
  upsertMeta('meta[property="og:description"]', 'property', DEFAULTS.description);
  upsertMeta('meta[name="twitter:title"]', 'name', DEFAULTS.title);
  upsertMeta('meta[name="twitter:description"]', 'name', DEFAULTS.description);
  upsertMeta('meta[name="description"]', 'name', DEFAULTS.description);
}
