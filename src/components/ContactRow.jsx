// Contact tiles for HomeA's /contact section. Reads from /api/contacts
// (the admin-managed list). When the list is empty (fresh install /
// migration), we fall back to email + github built from the site row so
// the home page never shows a blank section.

import { copyToClipboard } from './CopyText.jsx';

export function fallbackContacts(site) {
  const out = [];
  if (site?.email) {
    out.push({ id: 'fb-email', label: 'email', value: site.email, href: `mailto:${site.email}` });
  }
  if (site?.github) {
    out.push({
      id: 'fb-github',
      label: 'github',
      value: `@${site.github}`,
      href: `https://github.com/${site.github}`,
    });
  }
  return out;
}

export default function ContactRow({ contacts, site }) {
  const items = Array.isArray(contacts) && contacts.length > 0
    ? contacts
    : fallbackContacts(site);
  if (items.length === 0) return null;
  return (
    <div className="contact-row" data-testid="contact-row">
      {items.map((c, i) => (
        <ContactTile key={c.id ?? `${c.label}-${i}`} item={c} />
      ))}
    </div>
  );
}

export function ContactTile({ item }) {
  const href = (item?.href || '').trim();
  const value = item?.value || '';
  const label = item?.label || '';
  // External link if href has a protocol the browser can navigate to.
  const isLink = /^(https?:|mailto:|tel:|\/)/i.test(href);
  if (isLink) {
    const isExternal = /^https?:/i.test(href);
    return (
      <a
        href={href}
        className="contact-item"
        target={isExternal ? '_blank' : undefined}
        rel={isExternal ? 'noopener noreferrer' : undefined}
        data-testid={`contact-${label}`}
      >
        <span className="contact-k">{label}</span>
        <span className="contact-v">{value}</span>
      </a>
    );
  }
  // No protocol → click-to-copy. Useful for handles like "604691290"
  // that have no clickable URL.
  return (
    <button
      type="button"
      className="contact-item"
      onClick={async (e) => {
        const btn = e.currentTarget;
        await copyToClipboard(value);
        const v = btn.querySelector('.contact-v');
        if (v) {
          const orig = v.textContent;
          v.textContent = '已复制 ✓';
          setTimeout(() => { v.textContent = orig; }, 1400);
        }
      }}
      title={`点击复制 ${label}`}
      data-testid={`contact-${label}`}
    >
      <span className="contact-k">{label}</span>
      <span className="contact-v">{value}</span>
    </button>
  );
}
