import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useSite, usePosts, useTags } from './api/hooks.js';
import { setDocumentMeta } from './utils/documentMeta.js';
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
  // Task 54: URL-driven tag filter so `/?tag=devtools` deep-links to a
  // filtered home view. `activeTag` is now derived from the search
  // param ('all' when missing/empty), and setActiveTag pushes the new
  // value back into the URL so back/forward + sharing both work.
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTag = searchParams.get('tag') || 'all';
  const setActiveTag = useCallback((next) => {
    setSearchParams((prev) => {
      const sp = new URLSearchParams(prev);
      if (!next || next === 'all') sp.delete('tag');
      else sp.set('tag', next);
      return sp;
    }, { replace: false });
  }, [setSearchParams]);
  const [focusIdx, setFocusIdx] = useState(0);
  const [readingId, setReadingId] = useState(() => {
    const m = window.location.pathname.match(/^\/p\/([^/]+)/);
    return m ? decodeURIComponent(m[1]) : null;
  });
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [konamiOn, setKonamiOn] = useState(false);
  const [petHint, setPetHint] = useState(null);

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
    // Task 69: 同时更新 OG/Twitter meta，让 SPA 内部跳转后 head 跟得上。
    if (reading?.title) {
      setDocumentMeta({
        title: `${reading.title} — ${siteData?.name_en || 'myblog'}`,
        description: reading.summary || siteData?.tagline || 'A self-hosted personal blog.',
        type: 'article',
      });
    } else {
      setDocumentMeta({
        title: siteData?.name_en || 'myblog',
        description: siteData?.tagline || 'A self-hosted personal blog.',
        type: 'website',
      });
    }
  }, [reading?.title, reading?.summary, siteData?.name_en, siteData?.tagline]);

  useEffect(() => {
    if (reading) return;
    const focusedPost = posts[focusIdx] || posts[0] || null;
    const visiblePosts = posts.slice(0, 8).map((p) => {
      const subtitle = p.subtitle ? ` — ${p.subtitle}` : '';
      return `${p.title}${subtitle} [${p.tag || 'untagged'}]`;
    });
    const activeTagMeta = (tagsData || []).find((t) => t.id === activeTag);
    const activeTagLabel = activeTag === 'all'
      ? 'all'
      : (activeTagMeta?.label || activeTag);
    window.__petScene = () => ({
      page_type: 'home',
      path: window.location.pathname,
      title: document.title,
      active_tag: activeTagLabel,
      tag: activeTagLabel,
      post_count: posts.length,
      focused_post_title: focusedPost?.title,
      focused_post_tag: focusedPost?.tag,
      focused_post_subtitle: focusedPost?.subtitle,
      active_heading: focusedPost?.title,
      visible_posts: visiblePosts,
      home_digest: visiblePosts.length
        ? `Home index filtered by ${activeTagLabel}; focused: ${focusedPost?.title || 'none'}; candidates: ${visiblePosts.join(' | ')}`
        : `Home index filtered by ${activeTagLabel}; posts are still loading or empty.`,
      recent_action: 'browsing_home_index',
      locale: navigator.language,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    });
  }, [reading, posts, focusIdx, activeTag, tagsData]);

  // Apply backend-managed theme variables to the root element so admin
  // theme edits land on the public site without a deploy. utils/accent.js
  // still owns the per-visitor `green / amber / violet` overlay; the
  // root vars below set the *defaults* that overlay sits on top of.
  useEffect(() => {
    if (!siteData) return;
    const root = document.documentElement;
    const map = {
      '--accent': siteData.accent_color,
      '--accent-2': siteData.accent2_color,
      '--violet': siteData.violet_color,
      '--danger': siteData.danger_color,
    };
    for (const [name, value] of Object.entries(map)) {
      if (typeof value === 'string' && value.length > 0) {
        root.style.setProperty(name, value);
      }
    }
    if (typeof siteData.accent_color === 'string') {
      root.style.setProperty(
        '--accent-glow',
        `color-mix(in oklab, ${siteData.accent_color} 40%, transparent)`,
      );
    }
  }, [
    siteData?.accent_color,
    siteData?.accent2_color,
    siteData?.violet_color,
    siteData?.danger_color,
  ]);

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
    <Reader post={reading} onBack={closePost} onOpenPost={openPost} onSelection={setPetHint} />
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
          <div data-testid="footer-note">
            © {new Date().getFullYear()} {siteData?.name_en || siteData?.handle || 'myblog'} ·{' '}
            {siteData?.footer_note?.trim()
              ? siteData.footer_note
              : (
                <>
                  hand-coded · no trackers ·{' '}
                  <span className="accent">powered by coffee</span>
                </>
              )}
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
          {siteData?.icp_beian?.trim() && (
            <div className="footer-beian" data-testid="footer-beian">
              <a
                href="https://beian.miit.gov.cn/"
                target="_blank"
                rel="noopener noreferrer"
              >{siteData.icp_beian}</a>
            </div>
          )}
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
      <AsciiPet hint={petHint} />
    </div>
  );
}
