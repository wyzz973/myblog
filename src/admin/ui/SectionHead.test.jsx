import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import SectionHead from './SectionHead.jsx';
import Kbd from './Kbd.jsx';

afterEach(() => cleanup());

describe('SectionHead', () => {
  it('renders n + title + count with the public .section-head class', () => {
    render(<SectionHead n="02" title="文章" count="42 entries" />);
    const head = screen.getByTestId('section-head-02');
    expect(head.className).toBe('section-head');
    // n appears with the accent <span class="n">02 /</span>
    const n = head.querySelector('.label .n');
    expect(n.textContent).toBe('02 /');
    expect(head.textContent).toContain('文章');
    expect(head.querySelector('.count').textContent).toBe('42 entries');
  });

  it('omits the count when not provided', () => {
    render(<SectionHead n="01" title="仪表盘" />);
    const head = screen.getByTestId('section-head-01');
    expect(head.querySelector('.count')).toBeNull();
  });

  it('renders the lead paragraph below the rule when provided', () => {
    render(<SectionHead n="03" title="评论" lead="待审核 5 条" />);
    expect(screen.getByText('待审核 5 条').className).toBe('section-lead');
  });

  it('renders without the n prefix when n is missing', () => {
    render(<SectionHead title="孤立头" />);
    // testid carries undefined when n is missing — fall back to class lookup
    const head = document.querySelector('.section-head');
    expect(head.querySelector('.label .n')).toBeNull();
    expect(head.textContent).toContain('孤立头');
  });
});

describe('Kbd', () => {
  it('renders a <kbd> with admin-kbd class and forwards children', () => {
    render(<Kbd>⌘K</Kbd>);
    const el = screen.getByText('⌘K');
    expect(el.tagName).toBe('KBD');
    expect(el.className).toBe('admin-kbd');
  });

  it('forwards arbitrary props', () => {
    render(<Kbd data-testid="k">g</Kbd>);
    expect(screen.getByTestId('k').textContent).toBe('g');
  });
});
