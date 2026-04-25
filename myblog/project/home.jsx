// Homepage variants: A (Terminal), B (Editorial), C (Dashboard)
const { useState, useEffect, useMemo, useRef } = React;

function Logo() {
  return <div className="logo">w</div>;
}

function Avatar() {
  const [src, setSrc] = useState(() => localStorage.getItem('bl.avatar') || '');
  const fileRef = useRef(null);
  const onPick = (e) => {
    const f = e.target.files && e.target.files[0];
    if (!f) return;
    const r = new FileReader();
    r.onload = () => { setSrc(r.result); localStorage.setItem('bl.avatar', r.result); };
    r.readAsDataURL(f);
  };
  return (
    <div className="avatar" onClick={() => fileRef.current?.click()} title="Click to upload your photo">
      {src
        ? <img src={src} alt="avatar" style={{width:'100%',height:'100%',objectFit:'cover',borderRadius:8}} />
        : <>
            <span>汪</span>
            <div className="avatar-upload">+ upload</div>
          </>
      }
      <input ref={fileRef} type="file" accept="image/*" onChange={onPick} style={{display:'none'}} />
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

function TopBar({ theme, setTheme, layout, onOpenPalette, onNav }) {
  const go = (e, id) => {
    e.preventDefault();
    onNav('home');
    setTimeout(() => id === 'top' ? window.scrollTo({top:0, behavior:'smooth'}) : scrollToId(id), 50);
  };
  return (
    <header className="topbar">
      <a className="brand" href="#" onClick={(e) => go(e, 'top')}>
        <Logo />
        <span>wangyang<span className="accent">.dev</span></span>
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
        <span>online · {window.SITE.location}</span>
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

/* ===== VARIANT A: Terminal ===== */
function HeroA() {
  const [typed, setTyped] = useState("");
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
            <span style={{ color: 'var(--fg-2)' }}>Backend · AI</span> <span className="strike">Fullstack</span> <span className="glow">Everything</span><span className="cursor"/>
          </h1>
          <div className="sub serif" style={{ whiteSpace: 'pre-wrap', fontFamily: 'JetBrains Mono, monospace', color: 'var(--accent)' }}>
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
  const gridRef = React.useRef(null);
  const rafRef = React.useRef(0);
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
    const el = gridRef.current; if (!el) return;
    if (!el._measured) measure(el);
    const r = el.getBoundingClientRect();
    const mx = e.clientX - r.left, my = e.clientY - r.top;
    if (rafRef.current) return;
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = 0;
      const cells = el.children;
      const R = 80;
      for (let i = 0; i < cells.length; i++) {
        const c = cells[i];
        const cx = c._cx, cy = c._cy;
        const dx = cx - mx, dy = cy - my;
        const d = Math.hypot(dx, dy);
        if (d > R) {
          if (c._lit) { c.style.transform = ''; c.style.filter = ''; c.style.boxShadow = ''; c.style.zIndex = ''; c._lit = false; }
        } else {
          const n = 1 - d / R;
          c.style.transform = `translateY(${(-5*n).toFixed(2)}px) scale(${(1 + 0.8*n).toFixed(3)})`;
          c.style.filter = `brightness(${(1 + 1.0*n).toFixed(2)}) saturate(${(1 + n).toFixed(2)})`;
          c.style.boxShadow = `0 ${(6*n).toFixed(1)}px ${(14*n).toFixed(1)}px color-mix(in oklab, var(--accent) ${(50*n).toFixed(0)}%, transparent)`;
          c.style.zIndex = String(Math.round(n*10) + 1);
          c._lit = true;
        }
      }
    });
  };
  const onLeave = () => {
    const el = gridRef.current; if (!el) return;
    for (const c of el.children) {
      c.style.transform = ''; c.style.filter = ''; c.style.boxShadow = ''; c.style.zIndex = '';
      c._lit = false;
    }
  };
  React.useEffect(() => {
    const el = gridRef.current; if (!el) return;
    const ro = new ResizeObserver(() => { el._measured = false; });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return (
    <div>
      <div style={{display:'flex', justifyContent:'space-between', fontSize:10, color:'var(--fg-4)', marginBottom:4, paddingLeft:22}}>
        {months.map(m => <span key={m}>{m}</span>)}
      </div>
      <div className="contrib">
        <div className="days">
          <span>Mon</span><span></span><span>Wed</span><span></span><span>Fri</span><span></span><span></span>
        </div>
        <div className="contrib-grid" ref={gridRef} onMouseMove={onMove} onMouseLeave={onLeave}>
          {grid.map((col, wi) => col.map((lvl, di) => (
            <div
              key={`${wi}-${di}`}
              className="contrib-cell"
              data-l={lvl}
              data-cx={wi*14 + 6}
              data-cy={di*14 + 6}
              title={`Week ${wi+1}, ${['Sun','Mon','Tue','Wed','Thu','Fri','Sat'][di]}`}
            />
          )))}
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

function HomeA({ posts, activeTag, setTag, focusIdx, onOpenPost }) {
  return (
    <>
      <HeroA />
      <div className="wrap">
        <div className="section-head" id="now">
          <span className="label"><span className="n">02 /</span> contributions · 52w</span>
          <span className="count">{window.SITE.commits52w.toLocaleString()} commits</span>
        </div>
        <ContribGraph grid={window.CONTRIB} />

        <div className="section-head" id="writing">
          <span className="label"><span className="n">03 /</span> ./posts</span>
          <span className="count">{posts.length} entries</span>
        </div>
        <div className="tagbar">
          {window.TAGS.map(t => (
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
          <span className="count">{window.PROJECTS.length} repos</span>
        </div>
        <div className="proj-grid">
          {window.PROJECTS.map(p => (
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
          <a href="mailto:hi@wangyang.dev" className="contact-item">
            <span className="contact-k">email</span>
            <span className="contact-v">hi@wangyang.dev</span>
          </a>
          <a href="https://github.com/wangyang" className="contact-item">
            <span className="contact-k">github</span>
            <span className="contact-v">@wangyang</span>
          </a>
          <a href="https://xiaohongshu.com/user/profile/your-id" className="contact-item" target="_blank" rel="noopener">
            <span className="contact-k">小红书</span>
            <span className="contact-v">@汪洋</span>
          </a>
          <a href="https://douyin.com/user/your-id" className="contact-item" target="_blank" rel="noopener">
            <span className="contact-k">抖音</span>
            <span className="contact-v">@wangyang</span>
          </a>
        </div>
      </div>
    </>
  );
}
function HomeB({ posts, activeTag, setTag, focusIdx, onOpenPost }) {
  return (
    <div className="layout-B">
      <section className="hero">
        <div className="wrap" style={{display:'contents'}}>
          <div>
            <div className="prompt" style={{marginBottom:32}}>
              <span className="tag">~ wangyang</span>
              <span className="muted">·</span>
              <span>essay no. 047 · spring 2026</span>
            </div>
            <h1>
              Notes from<br />
              the <span className="glow">backend</span>,<br />
              where the<br />
              <i>bugs</i> actually<br />
              live.
            </h1>
            <p className="sub" style={{marginTop:24, marginBottom:0}}>
              A journal by <b style={{color:'var(--fg)'}}>Wang Yang</b> — Java, Python,
              PyTorch and whatever else the incident requires. Written from
              Hangzhou, usually between 23:00 and 02:00.
            </p>
          </div>
          <aside className="side-card">
            <h3>·/now</h3>
            <div className="row"><div className="dot" /> shipping an agent runtime for JVM services</div>
            <hr style={{border:0,borderTop:'1px dashed var(--line)', margin:0}} />
            <div className="row">reading: <b style={{color:'var(--fg)',marginLeft:'auto'}}>Designing Data-Intensive Apps</b></div>
            <div className="row">listening: <b style={{color:'var(--fg)',marginLeft:'auto'}}>Nils Frahm · All Melody</b></div>
            <hr style={{border:0,borderTop:'1px dashed var(--line)', margin:0}} />
            <h3>./stats</h3>
            <div className="row">posts <span style={{marginLeft:'auto',color:'var(--fg)'}}>{window.SITE.posts}</span></div>
            <div className="row">words <span style={{marginLeft:'auto',color:'var(--fg)'}}>{window.SITE.words.toLocaleString()}</span></div>
            <div className="row">uptime <span style={{marginLeft:'auto',color:'var(--accent)'}}>{window.SITE.uptime}</span></div>
          </aside>
        </div>
      </section>
      <div className="wrap">
        <div className="section-head">
          <span className="label serif" style={{fontStyle:'italic',textTransform:'none',fontSize:14,letterSpacing:0,color:'var(--fg)'}}><i>Recent entries</i></span>
          <span className="count">{posts.length} of {window.SITE.posts}</span>
        </div>
        <div className="tagbar">
          {window.TAGS.map(t => (
            <button key={t.id} className={`pill ${activeTag === t.id ? 'active' : ''}`} onClick={() => setTag(t.id)}>
              <span>#{t.label}</span><span className="n">{t.n}</span>
            </button>
          ))}
        </div>
        <div className="posts-editorial">
          {posts.map((p, i) => (
            <div key={p.id} className={`post-row-ed ${i === focusIdx ? 'focus' : ''}`} onClick={() => onOpenPost(p)}>
              <div className="n">№ {p.n}</div>
              <div>
                <h2>
                  <span className={p.lang === 'zh' ? 'zh' : ''}>{p.title}</span>
                </h2>
                <div className="summary serif" style={{fontSize:15, fontStyle: p.lang === 'zh' ? 'normal' : 'italic', fontFamily: p.lang === 'zh' ? "'Noto Serif SC', serif" : "'Newsreader', serif"}}>
                  {p.summary}
                </div>
              </div>
              <div className="right">
                <div>{p.date}</div>
                <div style={{color:'var(--accent)'}}>#{p.tag}</div>
                <div title="estimated read time">◷ {p.read} read</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ===== VARIANT C: Dashboard ===== */
function HomeC({ posts, activeTag, setTag, focusIdx, onOpenPost }) {
  return (
    <div className="layout-C">
      <div className="wrap">
        <div className="dash">
          <div className="dash-card identity-card">
            <Avatar />
            <div className="who">
              <h1>汪洋 <span className="muted" style={{fontSize:20}}>/ Wang Yang</span></h1>
              <div className="role">{window.SITE.role}</div>
              <div className="bio">{window.SITE.bio}</div>
            </div>
            <div className="stats">
              <div><div className="stat-v">{window.SITE.posts}</div><div className="stat-l">posts</div></div>
              <div><div className="stat-v">{(window.SITE.words/1000).toFixed(0)}k</div><div className="stat-l">words</div></div>
              <div><div className="stat-v" style={{color:'var(--accent)'}}>{window.SITE.uptime}</div><div className="stat-l">uptime</div></div>
            </div>
          </div>

          <div className="dash-card" style={{gridColumn: '1 / -1'}}>
            <h3>commit activity · 52 weeks</h3>
            <ContribGraph grid={window.CONTRIB} />
          </div>

          <div className="dash-card">
            <h3>status</h3>
            <div className="status-grid">
              <div>
                <div className="status-row"><span className="k">build</span><span className="v ok">passing</span></div>
                <div className="status-row"><span className="k">coffee</span><span className="v warn">2/3 cup</span></div>
                <div className="status-row"><span className="k">incidents</span><span className="v ok">none</span></div>
                <div className="status-row"><span className="k">inbox</span><span className="v">12</span></div>
              </div>
              <div>
                <div className="status-row"><span className="k">env</span><span className="v">prod · HZ-1</span></div>
                <div className="status-row"><span className="k">node</span><span className="v">v22.4.1</span></div>
                <div className="status-row"><span className="k">gpu</span><span className="v ok">RTX 4090 · 42°C</span></div>
                <div className="status-row"><span className="k">tmux</span><span className="v">4 sessions</span></div>
              </div>
            </div>
          </div>

          <div className="dash-card">
            <h3>now playing · listening</h3>
            <div style={{display:'flex', gap:14, alignItems:'center'}}>
              <div style={{width:56, height:56, borderRadius:4, background:'linear-gradient(135deg, var(--violet), var(--accent))', flexShrink:0}} />
              <div>
                <div style={{color:'var(--fg)', fontWeight:500}}>All Melody</div>
                <div style={{color:'var(--fg-3)',fontSize:12}}>Nils Frahm</div>
                <div style={{marginTop:8, width:180, height:2, background:'var(--line)', borderRadius:1, overflow:'hidden'}}>
                  <div style={{width:'64%', height:'100%', background:'var(--accent)'}} />
                </div>
              </div>
            </div>
            <div style={{borderTop:'1px dashed var(--line)', margin:'16px 0'}} />
            <h3 style={{marginTop:0}}>reading</h3>
            <div style={{color:'var(--fg-2)', fontSize:12}}>
              <b style={{color:'var(--fg)'}}>Designing Data-Intensive Apps</b> — Kleppmann · <span className="accent">ch. 7</span>
            </div>
          </div>

          <div className="dash-card" style={{gridColumn:'1 / -1'}}>
            <h3>recent posts</h3>
            <div className="tagbar">
              {window.TAGS.map(t => (
                <button key={t.id} className={`pill ${activeTag === t.id ? 'active' : ''}`} onClick={() => setTag(t.id)}>
                  <span>#{t.label}</span><span className="n">{t.n}</span>
                </button>
              ))}
            </div>
            <div className="posts">
              {posts.slice(0, 8).map((p, i) => (
                <PostRowA key={p.id} p={p} focused={i === focusIdx} onClick={() => onOpenPost(p)} />
              ))}
            </div>
          </div>

          <div className="dash-card" style={{gridColumn:'1 / -1'}}>
            <h3>./projects</h3>
            <div className="proj-grid">
              {window.PROJECTS.map(p => (
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
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { TopBar, HomeA, HomeB, HomeC });
