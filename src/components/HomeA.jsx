import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useSite, useProjects, useContrib, useContacts } from '../api/hooks.js';
import ContactRow from './ContactRow.jsx';
import { copyToClipboard } from './CopyText.jsx';

function HeroA() {
  const { data: site } = useSite();
  const handle = site?.handle || 'me';
  const name = site?.name || '';
  const nameEn = site?.name_en || '';
  const chips = site?.stack_chips || [];
  const checkmarks = chips.slice(0, 3).map((c) => c.toLowerCase());
  const full = (site?.typing_line || '').trimEnd();

  const [typed, setTyped] = useState('');
  useEffect(() => {
    if (!full) return;
    setTyped('');
    let i = 0;
    const id = setInterval(() => {
      i += 1;
      setTyped(full.slice(0, i));
      if (i >= full.length) clearInterval(id);
    }, 18);
    return () => clearInterval(id);
  }, [full]);

  return (
    <section className="hero">
      <div className="wrap hero-inner">
        <div className="hero-text">
          <div className="prompt">
            <span className="tag">~/{handle}</span>
            <span className="muted">on</span>
            <span className="accent">main</span>
            {checkmarks.length > 0 && (
              <>
                <span className="muted">·</span>
                <span>{checkmarks.map((c) => `${c} ✓`).join(' ')}</span>
              </>
            )}
          </div>
          <h1>
            <span className="muted">$</span> whoami<br />
            {name && (
              <>
                <span className="glow">{name}</span>
                {nameEn && nameEn !== name && (
                  <>{' '}<span className="muted">—</span> {nameEn}</>
                )}
                <br />
              </>
            )}
            <span style={{ color: 'var(--fg-2)' }}>Backend · AI</span>{' '}
            <span className="strike">Fullstack</span>
            <span className="cursor" />
          </h1>
          {full && (
            <div
              className="sub serif"
              style={{ whiteSpace: 'pre-wrap', fontFamily: 'JetBrains Mono, monospace', color: 'var(--accent)' }}
            >
              {typed}
            </div>
          )}
          {chips.length > 0 && (
            <div className="meta-row">
              <span>{chips.map((c, i) => <span key={c}>{i > 0 && ' · '}<b>{c}</b></span>)}</span>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

const WEEKDAY_NAMES = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];

function ContribGraph({ grid, counts, months: monthsProp }) {
  const months = monthsProp && monthsProp.length > 0
    ? monthsProp
    : ['May','Jun','Jul','Aug','Sep','Oct','Nov','Dec','Jan','Feb','Mar','Apr'];
  const gridRef = useRef(null);
  const rafRef = useRef(0);
  const [tip, setTip] = useState(null); // { x, y, arrowX, date, weekday, count } | null

  const weeksTotal = grid.length;
  // Columns are weekday-aligned: the rightmost column is the Sun→Sat
  // week containing today. di=0 Sun .. di=6 Sat.
  const cellDate = (wi, di) => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const lastSat = new Date(today);
    lastSat.setDate(lastSat.getDate() + (6 - today.getDay()));
    const colSun = new Date(lastSat);
    colSun.setDate(colSun.getDate() - (weeksTotal - 1 - wi) * 7 - 6);
    const d = new Date(colSun);
    d.setDate(d.getDate() + di);
    // Local YYYY-MM-DD: toISOString() reinterprets in UTC and shifts the
    // date by a day in non-UTC timezones (CN: -1d), corrupting tooltips.
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${dd}`;
  };

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
    setTip(null);
  };

  const onCellEnter = (e, wi, di) => {
    const date = cellDate(wi, di);
    const count = counts?.[wi]?.[di] ?? 0;
    const el = gridRef.current;
    const r = e.currentTarget.getBoundingClientRect();
    const scrollport = el?.parentElement;
    if (!scrollport) return;
    const viewport = scrollport.getBoundingClientRect();
    const cellX = r.left + r.width / 2;
    const visibleLeft = viewport.left + 8;
    const visibleRight = viewport.right - 8;
    const tooltipHalf = Math.min(92, Math.max(70, scrollport.clientWidth / 2 - 12));
    const x = Math.max(visibleLeft + tooltipHalf, Math.min(visibleRight - tooltipHalf, cellX));
    setTip({
      x,
      y: r.top,
      arrowX: cellX - x,
      date,
      weekday: WEEKDAY_NAMES[di],
      count,
    });
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
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginBottom: 4,
          fontSize: 10,
          color: 'var(--fg-4)',
        }}
      >
        {months.map((m, i) => <span key={`${m}-${i}`}>{m}</span>)}
      </div>
      <div className="contrib">
        <div
          className="contrib-grid"
          ref={gridRef}
          onMouseMove={onMove}
          onMouseLeave={onLeave}
          role="grid"
          aria-label="GitHub contributions, last 52 weeks"
        >
          {grid.map((col, wi) =>
            col.map((lvl, di) => {
              const date = cellDate(wi, di);
              const count = counts?.[wi]?.[di] ?? 0;
              const label = `${WEEKDAY_NAMES[di]} ${date}: ${
                count === 0 ? 'no commits' : `${count} commit${count === 1 ? '' : 's'}`
              }`;
              return (
                <div
                  key={`${wi}-${di}`}
                  className="contrib-cell"
                  data-l={lvl}
                  role="gridcell"
                  aria-label={label}
                  onMouseEnter={(e) => onCellEnter(e, wi, di)}
                />
              );
            }),
          )}
          {tip && (
            createPortal(
              <div
                className="contrib-tip contrib-tip-fixed"
                style={{ left: tip.x, top: tip.y, '--arrow-x': `${tip.arrowX}px` }}
                role="tooltip"
              >
                <div className="contrib-tip-count">
                  {tip.count === 0
                    ? 'no commits'
                    : `${tip.count} commit${tip.count === 1 ? '' : 's'}`}
                </div>
                <div className="contrib-tip-date">{tip.weekday} · {tip.date}</div>
              </div>,
              document.body,
            )
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
  const { data: contactsList } = useContacts();

  const SITE = site || { commits52w: 0, email: '', github: '', name: '' };
  const PROJECTS = projects || [];
  const CONTRIB = contribResp?.grid || [];
  const CONTRIB_COUNTS = contribResp?.counts || [];
  const CONTRIB_MONTHS = contribResp?.months || [];
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
          <span className="label"><span className="n">02 /</span> contributions · 52 weeks</span>
          <span className="count">{(SITE.commits52w || 0).toLocaleString()} commits</span>
        </div>
        <ContribGraph grid={CONTRIB} counts={CONTRIB_COUNTS} months={CONTRIB_MONTHS} />

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
            <a
              className="proj-card"
              key={p.name}
              href={SITE.github ? `https://github.com/${SITE.github}/${p.name}` : '#'}
              target="_blank"
              rel="noopener noreferrer"
            >
              <div className="name">{p.name}</div>
              <div className="desc">{p.desc}</div>
              <div className="meta">
                <span>{p.lang}</span>
                <span className="stars">★ {p.stars}</span>
                <span className="right">{p.status}</span>
              </div>
            </a>
          ))}
        </div>

        <div className="section-head" id="contact">
          <span className="label"><span className="n">05 /</span> /contact</span>
          <span className="count">reach out</span>
        </div>
        <ContactRow contacts={contactsList} site={SITE} />
      </div>
    </>
  );
}
