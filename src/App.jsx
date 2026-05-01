import { useState, useEffect, useCallback } from 'react';
import { useSite, usePosts, useTags } from './api/hooks.js';
import { applyAccent } from './utils/accent.js';
import TopBar from './components/TopBar.jsx';
import HomeA from './components/HomeA.jsx';
import Reader from './components/Reader.jsx';
import Palette from './components/Palette.jsx';
import Konami from './components/Konami.jsx';
import AsciiPet from './components/AsciiPet.jsx';
import CopyText from './components/CopyText.jsx';

const KONAMI = [
  'ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown',
  'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight',
  'b', 'a',
];

export default function App() {
  const [theme, setThemeRaw] = useState(() => localStorage.getItem('bl.theme') || 'dark');
  const [accent, setAccentRaw] = useState(() => localStorage.getItem('bl.accent') || 'green');
  const [activeTag, setActiveTag] = useState('all');
  const [focusIdx, setFocusIdx] = useState(0);
  const [readingId, setReadingId] = useState(() => {
    const m = window.location.pathname.match(/^\/p\/([^/]+)/);
    return m ? decodeURIComponent(m[1]) : null;
  });
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [konamiOn, setKonamiOn] = useState(false);

  const setTheme = useCallback((v) => {
    setThemeRaw((prev) => {
      const val = typeof v === 'function' ? v(prev) : v;
      localStorage.setItem('bl.theme', val);
      return val;
    });
  }, []);
  const setAccent = useCallback((v) => {
    setAccentRaw(v);
    localStorage.setItem('bl.accent', v);
  }, []);

  useEffect(() => {
    document.body.classList.toggle('theme-light', theme === 'light');
    applyAccent(accent);
  }, [theme, accent]);

  const { data: siteData } = useSite();
  const { data: postsResp, loading: postsLoading } = usePosts({
    tag: activeTag === 'all' ? undefined : activeTag,
    limit: 100,
  });
  const { data: tagsData } = useTags();
  const posts = postsResp?.items || [];

  useEffect(() => { setFocusIdx(0); }, [activeTag]);

  // Resolve current article from URL: prefer the loaded summary so the
  // sidebar/related lists work without a second fetch; fall back to a stub
  // so the URL still works on direct hits / refreshes.
  const reading = readingId
    ? (posts.find((p) => p.id === readingId) || { id: readingId })
    : null;

  useEffect(() => {
    document.title = reading?.title ? `${reading.title} — myblog` : 'myblog';
  }, [reading?.title]);

  // Sync the browser tab favicon to the configured GitHub avatar — auto-
  // updates whenever the user changes their avatar on github.com. The
  // handle is also cached so main.jsx can prime the favicon BEFORE React
  // mounts on subsequent loads (no flash of the inline pixel icon).
  useEffect(() => {
    const gh = siteData?.github;
    if (!gh) return;
    try {
      if (localStorage.getItem('myblog.site.github') !== gh) {
        localStorage.setItem('myblog.site.github', gh);
      }
    } catch { /* localStorage blocked */ }
    const link = document.querySelector("link[rel='icon']");
    if (!link) return;
    link.type = 'image/png';
    link.href = `https://github.com/${encodeURIComponent(gh)}.png?size=64`;
  }, [siteData?.github]);

  // Sync route changes triggered by browser back/forward.
  useEffect(() => {
    const onPop = () => {
      const m = window.location.pathname.match(/^\/p\/([^/]+)/);
      setReadingId(m ? decodeURIComponent(m[1]) : null);
    };
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  const openPost = useCallback((p) => {
    if (!p?.id) return;
    const url = `/p/${encodeURIComponent(p.id)}`;
    if (window.location.pathname !== url) {
      window.history.pushState({}, '', url);
    }
    setReadingId(p.id);
    window.scrollTo(0, 0);
  }, []);
  const closePost = useCallback(() => {
    if (window.location.pathname !== '/') {
      window.history.pushState({}, '', '/');
    }
    setReadingId(null);
  }, []);

  // Keyboard shortcuts
  useEffect(() => {
    let buf = [];
    const handler = (e) => {
      // ⌘K / ^K — toggle palette
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setPaletteOpen((o) => !o);
        return;
      }
      if (paletteOpen) return;
      if (reading) {
        if (e.key === 'Escape') closePost();
        return;
      }
      if (e.target && /input|textarea/i.test(e.target.tagName)) return;

      if (e.key === '/') { e.preventDefault(); setPaletteOpen(true); return; }
      if (e.key === 'j') setFocusIdx((i) => Math.min(posts.length - 1, i + 1));
      if (e.key === 'k') setFocusIdx((i) => Math.max(0, i - 1));
      if (e.key === 'Enter' && posts[focusIdx]) openPost(posts[focusIdx]);
      if (e.key === 't') setTheme((t) => (t === 'dark' ? 'light' : 'dark'));

      // Konami
      buf.push(e.key);
      if (buf.length > KONAMI.length) buf = buf.slice(buf.length - KONAMI.length);
      if (buf.length === KONAMI.length && buf.every((k, i) => k === KONAMI[i])) {
        setKonamiOn(true);
        setTimeout(() => setKonamiOn(false), 2400);
        buf = [];
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [paletteOpen, reading, posts, focusIdx, openPost, closePost, setTheme]);

  const Page = reading ? (
    <Reader post={reading} onBack={closePost} onOpenPost={openPost} />
  ) : (
    <>
      <HomeA
        posts={posts}
        tags={tagsData || []}
        activeTag={activeTag}
        setTag={setActiveTag}
        focusIdx={focusIdx}
        onOpenPost={openPost}
        loading={postsLoading}
      />
      <div className="wrap">
        <footer className="footer">
          <div>
            © 2026 {siteData?.name_en || siteData?.handle || 'myblog'} · hand-coded · no trackers ·{' '}
            <span className="accent">powered by coffee</span>
          </div>
          <div className="footer-links">
            {siteData?.github && (
              <>
                <a
                  href={`https://github.com/${siteData.github}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >github</a>
                {' · '}
              </>
            )}
            {siteData?.email && (
              <CopyText label="email" value={siteData.email} />
            )}
          </div>
        </footer>
      </div>
    </>
  );

  return (
    <div className="app" data-screen-label={reading ? `Reading: ${reading.title || reading.id}` : 'Home · Terminal'}>
      <TopBar
        theme={theme}
        setTheme={setTheme}
        onOpenPalette={() => setPaletteOpen(true)}
        onNav={(v) => { if (v === 'home') closePost(); }}
      />
      {Page}
      <Palette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onOpenPost={openPost}
        setTheme={setTheme}
        setAccent={setAccent}
      />
      <Konami on={konamiOn} />
      <AsciiPet />
    </div>
  );
}
