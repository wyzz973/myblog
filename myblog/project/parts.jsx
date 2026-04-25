// Reader, Palette, Konami, Tweaks panel
const { useState: useS, useEffect: useE, useMemo: useM, useRef: useR } = React;

function CodeBlock({ code }) {
  const [copied, setCopied] = useS(false);
  const lines = code.split('\n');
  const onCopy = () => {
    navigator.clipboard?.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  };
  const firstLine = lines[0] || '';
  const lang = firstLine.startsWith('#') ? 'sh'
    : firstLine.startsWith('//') ? 'java'
    : firstLine.toUpperCase().includes('SELECT') ? 'sql'
    : 'text';
  return (
    <div className="codeblock">
      <div className="codeblock-head">
        <span className="codeblock-dots">
          <span style={{background:'#ff5f57'}} /><span style={{background:'#febc2e'}} /><span style={{background:'#28c840'}} />
        </span>
        <span className="codeblock-lang">{lang}</span>
        <button className="codeblock-copy" onClick={onCopy}>{copied ? '✓ copied' : '⧉ copy'}</button>
      </div>
      <pre><code>
        {lines.map((line, i) => (
          <div className="codeline" key={i}>
            <span className="ln">{i + 1}</span>
            <span className="lc">{line || ' '}</span>
          </div>
        ))}
      </code></pre>
    </div>
  );
}

function Reader({ post, onBack, onOpenPost }) {
  const scrollRef = useR(null);
  const [progress, setProgress] = useS(0);
  const [activeHeading, setActiveHeading] = useS(0);
  const [liked, setLiked] = useS(false);
  const [likes, setLikes] = useS(20);

  useE(() => {
    if (!post) return;
    const stored = parseInt(localStorage.getItem(`bl.likes.${post.id}`) || '0', 10);
    setLikes(stored || Math.floor(Math.random()*80 + 20));
    setLiked(!!localStorage.getItem(`bl.liked.${post.id}`));
  }, [post?.id]);

  useE(() => {
    if (!post) return;
    const el = scrollRef.current;
    const onScroll = () => {
      if (!el) return;
      const max = el.scrollHeight - el.clientHeight;
      setProgress(max > 0 ? Math.min(100, (el.scrollTop / max) * 100) : 0);
      const heads = el.querySelectorAll('h2[data-h]');
      let active = 0;
      heads.forEach((h, i) => { if (h.getBoundingClientRect().top < 140) active = i; });
      setActiveHeading(active);
    };
    el?.addEventListener('scroll', onScroll, { passive: true });
    return () => el?.removeEventListener('scroll', onScroll);
  }, [post]);

  useE(() => { scrollRef.current?.scrollTo(0, 0); setProgress(0); }, [post?.id]);

  if (!post) return null;
  const isZh = post.lang === 'zh';
  const wordCount = (post.body || []).reduce((s, b) => s + (b.c || '').length, 0);
  const headings = (post.body || []).reduce((arr, b, i) => {
    if (b.t === 'h2') arr.push({ idx: i, text: b.c });
    return arr;
  }, []);
  const related = window.POSTS.filter(p => p.tag === post.tag && p.id !== post.id).slice(0, 3);
  const postIdx = window.POSTS.findIndex(p => p.id === post.id);
  const prevPost = window.POSTS[postIdx + 1];
  const nextPost = window.POSTS[postIdx - 1];
  const tagColor = { backend: 'var(--blue)', ai: 'var(--violet)', ml: 'var(--accent-2)', devtools: 'var(--accent)', infra: 'var(--danger)' }[post.tag] || 'var(--accent)';

  const onLike = () => {
    if (liked) return;
    setLiked(true);
    const n = likes + 1; setLikes(n);
    localStorage.setItem(`bl.likes.${post.id}`, String(n));
    localStorage.setItem(`bl.liked.${post.id}`, '1');
  };

  return (
    <div className="reader-shell" ref={scrollRef}>
      <div className="reader-progress" style={{transform: `scaleX(${progress/100})`}} />
      <div className="reader-layout">
        <aside className="reader-toc">
          <a className="back" onClick={onBack} href="#" onClickCapture={(e)=>e.preventDefault()}>
            <span>←</span> <span>back to index</span>
          </a>
          {headings.length > 0 && (
            <>
              <div className="toc-label">on this page</div>
              <ul className="toc-list">
                {headings.map((h, i) => (
                  <li key={i} className={i === activeHeading ? 'active' : ''}>
                    <a href={`#h-${i}`} onClick={(e) => {
                      e.preventDefault();
                      scrollRef.current?.querySelector(`#h-${i}`)?.scrollIntoView({behavior:'smooth', block:'start'});
                    }}>
                      <span className="toc-n">{String(i+1).padStart(2,'0')}</span>
                      <span className="toc-t">{h.text}</span>
                    </a>
                  </li>
                ))}
              </ul>
            </>
          )}
          <div className="toc-stats">
            <div className="stat-row"><span>read</span><span>{post.read}</span></div>
            <div className="stat-row"><span>chars</span><span>{wordCount.toLocaleString()}</span></div>
            <div className="stat-row"><span>tag</span><span style={{color: tagColor}}>#{post.tag}</span></div>
            <div className="stat-row"><span>updated</span><span>{post.date}</span></div>
          </div>
        </aside>

        <div className="reader">
          <div className="reader-hero" style={{'--tagc': tagColor}}>
            <div className="reader-eyebrow">
              <span className="n">#{post.n}</span>
              <span className="dot-sep">·</span>
              <span>{post.date}</span>
              <span className="dot-sep">·</span>
              <span className="tag-chip">#{post.tag}</span>
              <span className="dot-sep">·</span>
              <span>◷ {post.read} read</span>
            </div>
            <h1 className={isZh ? 'zh' : ''}>{post.title}</h1>
            <div className="subtitle" style={{fontFamily: isZh ? "'Noto Serif SC', serif" : "'Newsreader', serif"}}>
              {post.subtitle}
            </div>
          </div>

          {post.tldr && (
            <div className="tldr"><b>TL;DR</b> {post.tldr}</div>
          )}

          <div className={`reader-body ${isZh ? 'zh' : ''}`}>
            {(post.body && post.body.length > 0) ? (() => {
              let hIdx = 0;
              return post.body.map((b, i) => {
                if (b.t === 'h2') {
                  const id = `h-${hIdx++}`;
                  return <h2 key={i} id={id} data-h><span className="h-anchor">§</span>{b.c}</h2>;
                }
                if (b.t === 'code') return <CodeBlock key={i} code={b.c} />;
                const parts = (b.c || '').split(/(`[^`]+`)/);
                return (
                  <p key={i}>
                    {parts.map((pt, j) => pt.startsWith('`') && pt.endsWith('`')
                      ? <code key={j} className="inline-code">{pt.slice(1,-1)}</code>
                      : pt)}
                  </p>
                );
              });
            })() : (
              <div className="reader-stub">
                <p style={{color:'var(--fg-3)',fontStyle:'italic'}}>
                  [ full article draft in progress — the summary below captures the thesis ]
                </p>
                <p style={{color:'var(--fg-2)', fontSize:16, lineHeight:1.7}}>{post.summary}</p>
              </div>
            )}
          </div>

          <div className="reader-reactions">
            <button className={`like-btn ${liked ? 'liked' : ''}`} onClick={onLike}>
              <span className="like-ico">{liked ? '♥' : '♡'}</span>
              <span>{likes}</span>
              <span className="like-label">{liked ? 'thanks!' : 'useful?'}</span>
            </button>
            <div className="share-row">
              <button className="share-btn" onClick={() => navigator.clipboard?.writeText(location.href)}>
                <span>⎘</span> copy link
              </button>
              <a className="share-btn" href={`https://twitter.com/intent/tweet?text=${encodeURIComponent(post.title)}`} target="_blank" rel="noreferrer">
                <span>↗</span> tweet
              </a>
            </div>
          </div>

          <div className="reader-author">
            <div className="author-ava">W</div>
            <div className="author-meta">
              <div className="author-name">{window.SITE.name}</div>
              <div className="author-bio">{window.SITE.subtitle}</div>
            </div>
            <div className="author-links">
              <a href="#">github</a><span className="dot-sep">·</span>
              <a href="#">twitter</a><span className="dot-sep">·</span>
              <a href="#">rss</a>
            </div>
          </div>

          {related.length > 0 && (
            <div className="reader-related">
              <div className="related-head">related · #{post.tag}</div>
              <div className="related-grid">
                {related.map(r => (
                  <div key={r.id} className="related-card" onClick={() => onOpenPost?.(r)}>
                    <div className="r-n">#{r.n}</div>
                    <div className={`r-title ${r.lang === 'zh' ? 'zh' : ''}`}>{r.title}</div>
                    <div className="r-meta">{r.date} · {r.read}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="reader-navfoot">
            {prevPost ? (
              <button className="nav-prev" onClick={() => onOpenPost?.(prevPost)}>
                <div className="nav-dir">← older</div>
                <div className={`nav-title ${prevPost.lang === 'zh' ? 'zh' : ''}`}>{prevPost.title}</div>
              </button>
            ) : <span />}
            {nextPost ? (
              <button className="nav-next" onClick={() => onOpenPost?.(nextPost)}>
                <div className="nav-dir">newer →</div>
                <div className={`nav-title ${nextPost.lang === 'zh' ? 'zh' : ''}`}>{nextPost.title}</div>
              </button>
            ) : <span />}
          </div>

          <div className="reader-signoff">
            <span>— {window.SITE.name}, {post.date}</span>
            <span>press <kbd>esc</kbd> to go back</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function Palette({ open, onClose, onOpenPost, setTheme, setLayout }) {
  const [q, setQ] = useS('');
  const [sel, setSel] = useS(0);
  const inputRef = useR(null);

  const items = useM(() => {
    const cmds = [
      { type: 'cmd', ico: '◐', label: 'Toggle theme · dark/light', run: () => setTheme(t => t === 'dark' ? 'light' : 'dark'), sub: 't' },
      { type: 'cmd', ico: '▤', label: 'Layout · Terminal', run: () => setLayout('A'), sub: '1' },
      { type: 'cmd', ico: '▥', label: 'Layout · Editorial', run: () => setLayout('B'), sub: '2' },
      { type: 'cmd', ico: '▦', label: 'Layout · Dashboard', run: () => setLayout('C'), sub: '3' },
    ];
    const posts = window.POSTS.map(p => ({
      type: 'post', ico: '✦', label: p.title, sub: `#${p.n} · ${p.tag}`, run: () => onOpenPost(p)
    }));
    const all = [...cmds, ...posts];
    if (!q) return all;
    const qq = q.toLowerCase();
    return all.filter(i => i.label.toLowerCase().includes(qq) || (i.sub||'').toLowerCase().includes(qq));
  }, [q]);

  useE(() => {
    if (open) { setQ(''); setSel(0); setTimeout(() => inputRef.current?.focus(), 10); }
  }, [open]);
  useE(() => { setSel(0); }, [q]);

  if (!open) return null;

  const run = (it) => { it.run(); onClose(); };

  return (
    <div className="palette-bg" onClick={onClose}>
      <div className="palette" onClick={(e) => e.stopPropagation()}>
        <input
          ref={inputRef}
          placeholder="> search posts, run commands…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') { setSel(s => Math.min(items.length-1, s+1)); e.preventDefault(); }
            if (e.key === 'ArrowUp') { setSel(s => Math.max(0, s-1)); e.preventDefault(); }
            if (e.key === 'Enter') { if (items[sel]) run(items[sel]); }
            if (e.key === 'Escape') onClose();
          }}
        />
        <div className="results">
          {items.length === 0 && <div style={{padding:20, color:'var(--fg-4)', fontSize:13}}>No matches. Try something else.</div>}
          {items.map((it, i) => (
            <div key={i} className={`pitem ${i === sel ? 'sel' : ''}`} onClick={() => run(it)} onMouseEnter={() => setSel(i)}>
              <span className="ico">{it.ico}</span>
              <span>{it.label}</span>
              <span className="sub">{it.sub}</span>
            </div>
          ))}
        </div>
        <div className="phint">
          <span><kbd>↑↓</kbd> navigate</span>
          <span><kbd>↵</kbd> run</span>
          <span><kbd>esc</kbd> close</span>
        </div>
      </div>
    </div>
  );
}

function Konami({ on }) {
  if (!on) return null;
  return (
    <div className="konami">
      <div className="card">
        <h2>GODMODE</h2>
        <p>◈ ◈ ◈  welcome, fellow traveler  ◈ ◈ ◈</p>
      </div>
    </div>
  );
}

function TweaksPanel({ open, layout, setLayout, theme, setTheme, accent, setAccent }) {
  if (!open) return null;
  return (
    <div className="tweaks">
      <h4>tweaks <span className="dot" /></h4>
      <div className="group">
        <div className="label">layout</div>
        <div className="opts">
          {['A','B','C'].map(v => (
            <button key={v} className={layout === v ? 'sel' : ''} onClick={() => setLayout(v)}>
              {v === 'A' ? 'Terminal' : v === 'B' ? 'Editorial' : 'Dashboard'}
            </button>
          ))}
        </div>
      </div>
      <div className="group">
        <div className="label">mode</div>
        <div className="opts two">
          <button className={theme === 'dark' ? 'sel' : ''} onClick={() => setTheme('dark')}>☾ dark</button>
          <button className={theme === 'light' ? 'sel' : ''} onClick={() => setTheme('light')}>☀ light</button>
        </div>
      </div>
      <div className="group">
        <div className="label">accent</div>
        <div className="opts">
          <button className={accent === 'green' ? 'sel' : ''} onClick={() => setAccent('green')} style={{color:'oklch(82% 0.17 152)'}}>green</button>
          <button className={accent === 'amber' ? 'sel' : ''} onClick={() => setAccent('amber')} style={{color:'oklch(80% 0.15 70)'}}>amber</button>
          <button className={accent === 'violet' ? 'sel' : ''} onClick={() => setAccent('violet')} style={{color:'oklch(72% 0.18 295)'}}>violet</button>
        </div>
      </div>
      <div style={{fontSize:10, color:'var(--fg-4)', marginTop:8, paddingTop:8, borderTop:'1px dashed var(--line)'}}>
        <kbd style={{padding:'0 4px',border:'1px solid var(--line)',borderRadius:2}}>⌘K</kbd> palette ·
        <kbd style={{padding:'0 4px',border:'1px solid var(--line)',borderRadius:2, marginLeft:4}}>j/k</kbd> nav ·
        try the konami code
      </div>
    </div>
  );
}

Object.assign(window, { Reader, Palette, Konami, TweaksPanel });
