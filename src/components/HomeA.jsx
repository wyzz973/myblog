import { useEffect, useRef, useState } from 'react';
import { useSite, useProjects, useContrib } from '../api/hooks.js';

function HeroA() {
  const [typed, setTyped] = useState('');
  const full = "// building backends that don't flinch. \n// training models that ship.";
  useEffect(() => {
    let i = 0;
    const id = setInterval(() => {
      i += 1;
      setTyped(full.slice(0, i));
      if (i >= full.length) clearInterval(id);
    }, 18);
    return () => clearInterval(id);
  }, []);
  return (
    <section className="hero">
      <div className="wrap hero-inner">
        <div className="hero-text">
          <div className="prompt">
            <span className="tag">~/wangyang</span>
            <span className="muted">on</span>
            <span className="accent">main</span>
            <span className="muted">·</span>
            <span>last deploy 2h ago</span>
            <span className="muted">·</span>
            <span>bun ✓ postgres ✓ triton ✓</span>
          </div>
          <h1>
            <span className="muted">$</span> whoami<br />
            <span className="glow">汪洋</span> <span className="muted">—</span> Wang Yang<br />
            <span style={{ color: 'var(--fg-2)' }}>Backend · AI</span>{' '}
            <span className="strike">Fullstack</span>{' '}
            <span className="glow">Everything</span>
            <span className="cursor" />
          </h1>
          <div
            className="sub serif"
            style={{ whiteSpace: 'pre-wrap', fontFamily: 'JetBrains Mono, monospace', color: 'var(--accent)' }}
          >
            {typed}
          </div>
          <div className="meta-row">
            <span><b>Java</b> · <b>Python</b> · <b>PyTorch</b> · <b>Agents</b> · <b>Segmentation</b></span>
          </div>
        </div>
      </div>
    </section>
  );
}

function ContribGraph({ grid }) {
  const months = ['May','Jun','Jul','Aug','Sep','Oct','Nov','Dec','Jan','Feb','Mar','Apr'];
  const gridRef = useRef(null);
  const rafRef = useRef(0);

  const measure = (el) => {
    const gr = el.getBoundingClientRect();
    for (const c of el.children) {
      const cr = c.getBoundingClientRect();
      c._cx = cr.left - gr.left + cr.width / 2;
      c._cy = cr.top - gr.top + cr.height / 2;
    }
    el._measured = true;
  };

  const onMove = (e) => {
    const el = gridRef.current;
    if (!el) return;
    if (!el._measured) measure(el);
    const r = el.getBoundingClientRect();
    const mx = e.clientX - r.left;
    const my = e.clientY - r.top;
    if (rafRef.current) return;
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = 0;
      const cells = el.children;
      const R = 80;
      for (let i = 0; i < cells.length; i++) {
        const c = cells[i];
        const dx = c._cx - mx;
        const dy = c._cy - my;
        const d = Math.hypot(dx, dy);
        if (d > R) {
          if (c._lit) {
            c.style.transform = '';
            c.style.filter = '';
            c.style.boxShadow = '';
            c.style.zIndex = '';
            c._lit = false;
          }
        } else {
          const n = 1 - d / R;
          c.style.transform = `translateY(${(-5 * n).toFixed(2)}px) scale(${(1 + 0.8 * n).toFixed(3)})`;
          c.style.filter = `brightness(${(1 + 1.0 * n).toFixed(2)}) saturate(${(1 + n).toFixed(2)})`;
          c.style.boxShadow = `0 ${(6 * n).toFixed(1)}px ${(14 * n).toFixed(1)}px color-mix(in oklab, var(--accent) ${(50 * n).toFixed(0)}%, transparent)`;
          c.style.zIndex = String(Math.round(n * 10) + 1);
          c._lit = true;
        }
      }
    });
  };

  const onLeave = () => {
    const el = gridRef.current;
    if (!el) return;
    for (const c of el.children) {
      c.style.transform = '';
      c.style.filter = '';
      c.style.boxShadow = '';
      c.style.zIndex = '';
      c._lit = false;
    }
  };

  useEffect(() => {
    const el = gridRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => { el._measured = false; });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--fg-4)', marginBottom: 4, paddingLeft: 22 }}>
        {months.map((m) => <span key={m}>{m}</span>)}
      </div>
      <div className="contrib">
        <div className="days">
          <span>Mon</span><span /><span>Wed</span><span /><span>Fri</span><span /><span />
        </div>
        <div className="contrib-grid" ref={gridRef} onMouseMove={onMove} onMouseLeave={onLeave}>
          {grid.map((col, wi) =>
            col.map((lvl, di) => (
              <div
                key={`${wi}-${di}`}
                className="contrib-cell"
                data-l={lvl}
                title={`Week ${wi + 1}, ${['Sun','Mon','Tue','Wed','Thu','Fri','Sat'][di]}`}
              />
            )),
          )}
        </div>
      </div>
      <div className="contrib-legend">
        <span>less</span>
        <div className="contrib-cell" data-l="0" />
        <div className="contrib-cell" data-l="1" />
        <div className="contrib-cell" data-l="2" />
        <div className="contrib-cell" data-l="3" />
        <div className="contrib-cell" data-l="4" />
        <span>more</span>
      </div>
    </div>
  );
}

function PostRowA({ p, focused, onClick }) {
  const isZh = p.lang === 'zh';
  return (
    <div className={`post-row ${focused ? 'focus' : ''}`} onClick={onClick}>
      <span className="n">#{p.n}</span>
      <span className="date">{p.date}</span>
      <span className="title">
        <span className={isZh ? 'zh' : ''}>{p.title}</span>
        <span className="sub">— {p.subtitle}</span>
      </span>
      <span className={`tag t-${p.tag}`}>{p.tag}</span>
      <span className="read" title="estimated read time">
        <span className="read-ico">◷</span> {p.read} read
      </span>
    </div>
  );
}

export default function HomeA({ posts, tags, activeTag, setTag, focusIdx, onOpenPost, loading }) {
  const { data: site } = useSite();
  const { data: projects } = useProjects();
  const { data: contribResp } = useContrib(52);

  const SITE = site || { commits52w: 0, email: '', github: '', name: '' };
  const PROJECTS = projects || [];
  const CONTRIB = contribResp?.grid || [];
  const TAGS = tags || [];

  if (loading && posts.length === 0) {
    return (
      <div className="hero">
        <div className="wrap">
          <div className="prompt">loading…</div>
        </div>
      </div>
    );
  }

  return (
    <>
      <HeroA />
      <div className="wrap">
        <div className="section-head" id="now">
          <span className="label"><span className="n">02 /</span> contributions · 52w</span>
          <span className="count">{(SITE.commits52w || 0).toLocaleString()} commits</span>
        </div>
        <ContribGraph grid={CONTRIB} />

        <div className="section-head" id="writing">
          <span className="label"><span className="n">03 /</span> ./posts</span>
          <span className="count">{posts.length} entries</span>
        </div>
        <div className="tagbar">
          {TAGS.map((t) => (
            <button
              key={t.id}
              className={`pill ${activeTag === t.id ? 'active' : ''}`}
              onClick={() => setTag(t.id)}
            >
              <span>#{t.label}</span>
              <span className="n">{t.n}</span>
            </button>
          ))}
        </div>
        <div className="posts">
          {posts.map((p, i) => (
            <PostRowA key={p.id} p={p} focused={i === focusIdx} onClick={() => onOpenPost(p)} />
          ))}
        </div>

        <div className="section-head" id="projects">
          <span className="label"><span className="n">04 /</span> ~/projects</span>
          <span className="count">{PROJECTS.length} repos</span>
        </div>
        <div className="proj-grid">
          {PROJECTS.map((p) => (
            <div className="proj-card" key={p.name}>
              <div className="name">{p.name}</div>
              <div className="desc">{p.desc}</div>
              <div className="meta">
                <span>{p.lang}</span>
                <span className="stars">★ {p.stars}</span>
                <span className="right">{p.status}</span>
              </div>
            </div>
          ))}
        </div>

        <div className="section-head" id="contact">
          <span className="label"><span className="n">05 /</span> /contact</span>
          <span className="count">reach out</span>
        </div>
        <div className="contact-row">
          <a href={`mailto:${SITE.email}`} className="contact-item">
            <span className="contact-k">email</span>
            <span className="contact-v">{SITE.email}</span>
          </a>
          <a href={`https://github.com/${SITE.github}`} className="contact-item">
            <span className="contact-k">github</span>
            <span className="contact-v">@{SITE.github}</span>
          </a>
          <a href="https://xiaohongshu.com" className="contact-item" target="_blank" rel="noopener noreferrer">
            <span className="contact-k">小红书</span>
            <span className="contact-v">@汪洋</span>
          </a>
          <a href="https://douyin.com" className="contact-item" target="_blank" rel="noopener noreferrer">
            <span className="contact-k">抖音</span>
            <span className="contact-v">@wangyang</span>
          </a>
        </div>
      </div>
    </>
  );
}
