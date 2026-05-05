import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ContactRow, { fallbackContacts } from './ContactRow.jsx';

describe('fallbackContacts', () => {
  it('builds email + github tiles from site', () => {
    const fb = fallbackContacts({ email: 'a@b.c', github: 'octocat' });
    expect(fb).toHaveLength(2);
    expect(fb[0].href).toBe('mailto:a@b.c');
    expect(fb[1].href).toBe('https://github.com/octocat');
  });

  it('skips fields the site does not have', () => {
    expect(fallbackContacts({ email: 'a@b.c' })).toHaveLength(1);
    expect(fallbackContacts({ github: 'gh' })).toHaveLength(1);
    expect(fallbackContacts({})).toHaveLength(0);
  });
});

describe('ContactRow rendering', () => {
  it('renders each API item as its own tile', () => {
    const contacts = [
      { id: 1, label: 'email', value: 'me@example.com', href: 'mailto:me@example.com' },
      { id: 2, label: 'github', value: '@octocat', href: 'https://github.com/octocat' },
      { id: 3, label: '小红书', value: '主页 ↗', href: 'https://xhslink.com/m/abc' },
      { id: 4, label: '抖音', value: '604691290', href: '' },
    ];
    render(<ContactRow contacts={contacts} site={{}} />);
    expect(screen.getByTestId('contact-row')).toBeInTheDocument();
    for (const c of contacts) {
      expect(screen.getByTestId(`contact-${c.label}`)).toBeInTheDocument();
    }
  });

  it('http-protocol items render as anchors with target=_blank', () => {
    const contacts = [
      { id: 1, label: 'github', value: '@me', href: 'https://github.com/me' },
    ];
    render(<ContactRow contacts={contacts} site={{}} />);
    const tile = screen.getByTestId('contact-github');
    expect(tile.tagName).toBe('A');
    expect(tile.getAttribute('target')).toBe('_blank');
    expect(tile.getAttribute('href')).toBe('https://github.com/me');
  });

  it('items without a protocol render as a copy-to-clipboard button', () => {
    const contacts = [
      { id: 1, label: '抖音', value: '604691290', href: '' },
    ];
    render(<ContactRow contacts={contacts} site={{}} />);
    const tile = screen.getByTestId('contact-抖音');
    expect(tile.tagName).toBe('BUTTON');
  });

  it('falls back to site-derived tiles when contacts list is empty', () => {
    render(<ContactRow contacts={[]} site={{ email: 'a@b.c', github: 'octocat' }} />);
    expect(screen.getByTestId('contact-email')).toBeInTheDocument();
    expect(screen.getByTestId('contact-github')).toBeInTheDocument();
  });

  it('renders nothing when neither contacts nor site has data', () => {
    const { container } = render(<ContactRow contacts={[]} site={{}} />);
    expect(container.querySelector('[data-testid=contact-row]')).toBeNull();
  });
});
