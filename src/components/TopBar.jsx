import { useSite } from '../api/hooks.js';
import Avatar from './Avatar.jsx';

function Logo({ github }) {
  return (
    <div className="logo" aria-label="myblog">
      <Avatar github={github} pixelSize={16} />
    </div>
  );
}

function scrollToId(id) {
  const el = document.getElementById(id);
  if (el) {
    const y = el.getBoundingClientRect().top + window.scrollY - 80;
    window.scrollTo({ top: y, behavior: 'smooth' });
  }
}

export default function TopBar({ theme, setTheme, onOpenPalette, onNav }) {
  const { data: site } = useSite();
  const go = (e, id) => {
    e.preventDefault();
    onNav?.('home');
    setTimeout(() => (id === 'top' ? window.scrollTo({ top: 0, behavior: 'smooth' }) : scrollToId(id)), 50);
  };
  return (
    <header className="topbar">
      <a className="brand" href="#" onClick={(e) => go(e, 'top')}>
        <Logo github={site?.github} />
        <span>my<span className="accent">blog</span></span>
      </a>
      <nav>
        <a href="#top" onClick={(e) => go(e, 'top')}>~/</a>
        <a href="#writing" onClick={(e) => go(e, 'writing')}>/writing</a>
        <a href="#projects" onClick={(e) => go(e, 'projects')}>/projects</a>
        <a href="#now" onClick={(e) => go(e, 'now')}>/now</a>
        <a href="#contact" onClick={(e) => go(e, 'contact')}>/contact</a>
      </nav>
      <div className="spacer" />
      <span className="row" style={{ gap: 6 }}>
        <span className="dot" />
        <span>online{site?.location ? ` · ${site.location}` : ''}</span>
      </span>
      <button className="kbd-hint" onClick={onOpenPalette}>
        <kbd>⌘</kbd><kbd>K</kbd> search
      </button>
      <button
        className="kbd-hint"
        onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
        title="Toggle theme"
      >
        {theme === 'dark' ? '☾ dark' : '☀ light'}
      </button>
    </header>
  );
}
