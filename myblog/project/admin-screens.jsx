/* Admin screens — rendered by the shell based on route */
const { useState: aS, useEffect: aE, useMemo: aM } = React;

/* Mock data store */
const ADMIN_DEFAULTS = {
  site: {
    title: "wangyang.dev",
    tagline: "backend · ai engineer · 写一些不flinch的服务",
    layout: "A",
    theme: "dark",
    location: "Shanghai · UTC+8",
    footerNote: "© 2026 wangyang · powered by jetlag and matcha",
  },
  profile: {
    name: "汪洋",
    role: "Backend / AI Full-stack Engineer",
    bio: "Java / Python / PyTorch · 写后端、调模型、做 agent。",
    avatar: "",
    typingLine: "// building backends that don't flinch.\n// training models that learn fast.",
  },
  contacts: [
    { id: 1, k: "email", v: "hi@wangyang.dev", href: "mailto:hi@wangyang.dev", visible: true },
    { id: 2, k: "github", v: "@wangyang", href: "https://github.com/wangyang", visible: true },
    { id: 3, k: "小红书", v: "@汪洋", href: "https://xiaohongshu.com/user/...", visible: true },
    { id: 4, k: "抖音", v: "@wangyang", href: "https://douyin.com/user/...", visible: true },
  ],
  tags: [
    { id: 1, slug: "backend", name: "backend", color: "#7aa7ff", count: 12 },
    { id: 2, slug: "ai", name: "ai", color: "#b794ff", count: 8 },
    { id: 3, slug: "ml", name: "ml", color: "#ffb86b", count: 5 },
    { id: 4, slug: "devtools", name: "devtools", color: "#7dd3a4", count: 9 },
    { id: 5, slug: "infra", name: "infra", color: "#f47174", count: 3 },
  ],
  now: "Shipping an agent runtime for JVM services. Also reading: 'Designing Data-Intensive Applications' (再读一遍).",
  pet: { species: "capybara", hat: "none", systemPrompt: "你是一只懒洋洋的水豚，住在 wangyang.dev 的右下角。用 1-2 句中英混杂的口吻回应，偶尔吐槽前端。", model: "claude-haiku-4-5", enabled: true },
};

/* ============ DASHBOARD ============ */
function ScreenDashboard() {
  const bars = aM(() => Array.from({length: 30}, () => 25 + Math.random()*55), []);
  const stream = [
    { ts: "16:42:01", lvl: "ok", msg: "post /writing/termius-utf8 published", who: "@you" },
    { ts: "16:38:55", lvl: "info", msg: "deploy 7c4a2f3 → vercel · 28s · ✓", who: "ci" },
    { ts: "16:21:09", lvl: "warn", msg: "comment flagged for moderation: '...check this link...'", who: "system" },
    { ts: "15:02:18", lvl: "info", msg: "draft saved: 'PageHelper 分页失效踩坑指南'", who: "@you" },
    { ts: "14:51:02", lvl: "ok", msg: "tag #devtools attached to 2 posts", who: "@you" },
    { ts: "12:11:44", lvl: "err", msg: "rss feed regenerate failed (timeout) — retried, ok", who: "system" },
    { ts: "09:33:20", lvl: "info", msg: "1,204 unique visitors in last 24h (+8.2%)", who: "analytics" },
  ];
  return (
    <>
      <div className="adm-grid-4" style={{marginBottom: 18}}>
        <Stat l="POSTS" v="38" delta="+2 this week" />
        <Stat l="VISITORS · 30D" v="24.1k" delta="+12.4%" tone="violet" />
        <Stat l="COMMENTS" v="86" delta="3 pending" tone="amber" />
        <Stat l="UPTIME" v="99.98%" delta="✓ all systems" tone="blue" />
      </div>

      <div className="adm-grid-2" style={{alignItems:'start'}}>
        <div className="adm-card">
          <div className="adm-card-head">
            <h3 className="adm-card-title"><span className="pound">#</span>visitors · last 30 days</h3>
            <span className="adm-muted" style={{fontSize:10}}>peak <b style={{color:'var(--accent)'}}>1,847</b> · today <b style={{color:'var(--fg)'}}>1,204</b></span>
          </div>
          <div className="adm-bars">
            {bars.map((h, i) => <i key={i} style={{height: h+"%"}} title={`${Math.round(h*20)} visits`} />)}
          </div>
          <div className="adm-bars-x">
            <span>30d</span><span>20d</span><span>10d</span><span>today</span>
          </div>
        </div>

        <div className="adm-card">
          <div className="adm-card-head">
            <h3 className="adm-card-title"><span className="pound">$</span>recent activity</h3>
            <button className="adm-btn ghost" style={{fontSize:10}}>tail -f →</button>
          </div>
          <div className="adm-stream">
            {stream.map((r, i) => (
              <div key={i} className="adm-stream-row">
                <span className="ts">{r.ts}</span>
                <span className={`lvl ${r.lvl}`}>[{r.lvl}]</span>
                <span>{r.msg}</span>
                <span className="who">{r.who}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="adm-grid-3" style={{marginTop: 16}}>
        <div className="adm-card">
          <div className="adm-card-head"><h3 className="adm-card-title"><span className="pound">#</span>top posts · 7d</h3></div>
          {[
            ["Termius 中文乱码解决方案", 412],
            ["科学上网搭建教程", 298],
            ["PageHelper 分页失效踩坑指南", 244],
            ["训练 SAM 在自定义数据集", 187],
            ["Spring AI agent: tool-calling 实战", 156],
          ].map(([t, n], i) => (
            <div key={i} style={{display:'flex', justifyContent:'space-between', padding:'6px 0', fontSize:12, borderBottom:'1px dashed var(--line)'}}>
              <span style={{color:'var(--fg-2)'}}>{t}</span>
              <span style={{color:'var(--accent)'}}>{n.toLocaleString()}</span>
            </div>
          ))}
        </div>
        <div className="adm-card">
          <div className="adm-card-head"><h3 className="adm-card-title"><span className="pound">#</span>build · last deploy</h3></div>
          <div style={{fontSize:11, color:'var(--fg-3)', lineHeight:1.7}}>
            <div><span className="adm-muted">commit</span> <span style={{color:'var(--accent)'}}>7c4a2f3</span></div>
            <div><span className="adm-muted">branch</span> main</div>
            <div><span className="adm-muted">message</span> fix: contact section anchors</div>
            <div><span className="adm-muted">duration</span> 28s</div>
            <div><span className="adm-muted">status</span> <span className="adm-status published" style={{textTransform:'lowercase'}}>passing</span></div>
          </div>
          <div style={{display:'flex', gap:6, marginTop:12, paddingTop:10, borderTop:'1px dashed var(--line)'}}>
            <button className="adm-btn primary">redeploy</button>
            <button className="adm-btn">view logs ↗</button>
          </div>
        </div>
        <div className="adm-card">
          <div className="adm-card-head"><h3 className="adm-card-title"><span className="pound">#</span>quick actions</h3></div>
          <div style={{display:'flex', flexDirection:'column', gap:6}}>
            <button className="adm-btn">+ new post <span className="adm-kbd" style={{marginLeft:'auto'}}>⌘ N</span></button>
            <button className="adm-btn">↑ upload media <span className="adm-kbd" style={{marginLeft:'auto'}}>⌘ U</span></button>
            <button className="adm-btn">⟲ rebuild rss <span className="adm-kbd" style={{marginLeft:'auto'}}>⌘ R</span></button>
            <button className="adm-btn">⛏ open shell <span className="adm-kbd" style={{marginLeft:'auto'}}>⌘ \\</span></button>
          </div>
        </div>
      </div>
    </>
  );
}

function Stat({ l, v, delta, tone }) {
  return (
    <div className={`adm-stat ${tone||''}`}>
      <div className="l">{l}</div>
      <div className="v">{v}</div>
      <div className="delta">{delta}</div>
    </div>
  );
}

/* ============ POSTS ============ */
function ScreenPosts() {
  const POSTS = [
    { id: 1, n: "001", title: "Termius 中文乱码解决方案 — UTF8 编码配置指南", tag: "devtools", date: "2026-04-22", read: "6 min", status: "published", lang: "zh" },
    { id: 2, n: "002", title: "科学上网搭建教程", tag: "infra", date: "2026-04-15", read: "12 min", status: "published", lang: "zh" },
    { id: 3, n: "003", title: "PageHelper 分页失效踩坑指南", tag: "backend", date: "2026-04-08", read: "5 min", status: "published", lang: "zh" },
    { id: 4, n: "004", title: "训练 SAM 在自定义医学影像数据集", tag: "ml", date: "2026-03-29", read: "18 min", status: "published", lang: "zh" },
    { id: 5, n: "005", title: "Spring AI · 给 JVM 服务装上 agent runtime", tag: "ai", date: "2026-03-21", read: "11 min", status: "published", lang: "zh" },
    { id: 6, n: "006", title: "Java 21 虚拟线程 vs 协程：实测踩坑", tag: "backend", date: "2026-03-12", read: "9 min", status: "draft", lang: "zh" },
    { id: 7, n: "007", title: "PyTorch 2.5 的 compile() 真的能加速吗", tag: "ml", date: "2026-04-30", read: "14 min", status: "scheduled", lang: "zh" },
    { id: 8, n: "008", title: "On building tools you actually use", tag: "devtools", date: "2026-02-28", read: "7 min", status: "published", lang: "en" },
  ];
  const [active, setActive] = aS(POSTS[0]);
  const [filter, setFilter] = aS('all');
  const filtered = POSTS.filter(p => filter === 'all' || p.status === filter);

  return (
    <>
      <div className="adm-toolbar">
        <div className="adm-search"><input placeholder="search posts… (filter by title, tag, content)" /></div>
        <div className="adm-pills">
          {['all', 'published', 'draft', 'scheduled'].map(f => (
            <button key={f} className={`adm-pill ${filter===f?'on':''}`} onClick={() => setFilter(f)}>{f}</button>
          ))}
        </div>
        <button className="adm-btn primary">+ new post</button>
      </div>

      <div className="adm-split">
        <div className="adm-card">
          <div className="adm-card-head">
            <h3 className="adm-card-title"><span className="pound">~/</span>posts <span className="count">{filtered.length}</span></h3>
            <span className="adm-muted" style={{fontSize:10}}>sort: date ↓</span>
          </div>
          <div className="adm-list-scroll">
            {filtered.map(p => (
              <div key={p.id} className={`adm-list-row ${active.id===p.id?'active':''}`} onClick={() => setActive(p)}>
                <div className="top">
                  <span className="n">#{p.n}</span>
                  <span style={{flex:1, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap'}}>{p.title}</span>
                </div>
                <div className="meta">
                  <span className={`adm-status ${p.status}`}>{p.status}</span>
                  <span>·</span>
                  <span>#{p.tag}</span>
                  <span>·</span>
                  <span>{p.date}</span>
                  <span>·</span>
                  <span>{p.read}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="adm-card" style={{overflow:'auto'}}>
          <div className="adm-card-head">
            <h3 className="adm-card-title">
              <span className="pound">$</span>edit · <span style={{color:'var(--fg)', textTransform:'none', letterSpacing:0, fontSize:13}}>{active.title.split(' — ')[0]}</span>
            </h3>
            <div style={{display:'flex', gap:6}}>
              <span className={`adm-status ${active.status}`}>{active.status}</span>
              <button className="adm-btn">preview ↗</button>
              <button className="adm-btn">save draft</button>
              <button className="adm-btn primary">publish</button>
            </div>
          </div>

          <div className="adm-editor-frontmatter">
            <div className="h">frontmatter</div>
            <div className="adm-row-2">
              <div className="adm-field">
                <label className="adm-field-label">title<span className="req">*</span></label>
                <input className="adm-input" defaultValue={active.title} key={'t'+active.id} />
              </div>
              <div className="adm-field">
                <label className="adm-field-label">slug<span className="req">*</span></label>
                <div className="adm-field-wrap">
                  <span className="adm-field-prefix">/</span>
                  <input className="adm-input with-prefix" defaultValue={active.title.toLowerCase().replace(/\s+/g,'-').replace(/[^a-z0-9\-]/g,'').slice(0,40)} key={'s'+active.id} />
                </div>
              </div>
            </div>
            <div className="adm-row-3">
              <div className="adm-field">
                <label className="adm-field-label">tag</label>
                <select className="adm-select" defaultValue={active.tag} key={'g'+active.id}>
                  <option>backend</option><option>ai</option><option>ml</option><option>devtools</option><option>infra</option>
                </select>
              </div>
              <div className="adm-field">
                <label className="adm-field-label">date</label>
                <input className="adm-input" defaultValue={active.date} key={'d'+active.id} />
              </div>
              <div className="adm-field">
                <label className="adm-field-label">lang</label>
                <select className="adm-select" defaultValue={active.lang} key={'l'+active.id}>
                  <option value="zh">zh-CN</option><option value="en">en</option>
                </select>
              </div>
            </div>
            <div className="adm-field">
              <label className="adm-field-label">subtitle / tldr</label>
              <input className="adm-input" defaultValue="一句话总结：UTF-8 → Encoding → 重启，三连即可。" key={'st'+active.id} />
            </div>
          </div>

          <div className="adm-editor-toolbar">
            <button className="adm-btn icon" title="bold"><b>B</b></button>
            <button className="adm-btn icon" title="italic"><i>I</i></button>
            <button className="adm-btn icon" title="link">🔗</button>
            <span className="div" />
            <button className="adm-btn icon">H1</button>
            <button className="adm-btn icon">H2</button>
            <button className="adm-btn icon" title="quote">❝</button>
            <span className="div" />
            <button className="adm-btn icon" title="code">{`</>`}</button>
            <button className="adm-btn icon" title="image">🖼</button>
            <button className="adm-btn icon" title="table">▦</button>
            <span style={{flex:1}} />
            <span className="adm-muted" style={{fontSize:10}}>markdown · 1,247 words · ~6 min read</span>
          </div>
          <div className="adm-md" contentEditable suppressContentEditableWarning>
{`# ${active.title.split(' — ')[0]}

> tl;dr — 把 Termius 的字符编码改成 UTF-8，重启会话。完。

## 背景

每次连服务器都看到一片 ?????? 这种问号墙就头大。
Termius 默认用了系统编码，但很多 Linux 服务器的 locale 是 zh_CN.UTF-8。

## 解决步骤

\`\`\`bash
# 1. 在服务器上确认 locale
locale
# LANG=zh_CN.UTF-8 ✓

# 2. Termius → Settings → Terminal → Character set → UTF-8
\`\`\`

继续读 →`}
          </div>

          <div className="adm-grid-2" style={{marginTop: 14}}>
            <div className="adm-row-inline">
              <div className="l"><b>featured</b><div className="h">pin to top of /writing</div></div>
              <div className="adm-toggle on" />
            </div>
            <div className="adm-row-inline">
              <div className="l"><b>comments</b><div className="h">allow comments on this post</div></div>
              <div className="adm-toggle on" />
            </div>
            <div className="adm-row-inline">
              <div className="l"><b>scheduled</b><div className="h">publish at a specific time</div></div>
              <div className="adm-toggle" />
            </div>
            <div className="adm-row-inline">
              <div className="l"><b>private</b><div className="h">visible only with invite link</div></div>
              <div className="adm-toggle" />
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

/* ============ PROFILE ============ */
function ScreenProfile() {
  return (
    <>
      <div className="adm-grid-2" style={{alignItems:'start'}}>
        <div className="adm-card">
          <div className="adm-card-head"><h3 className="adm-card-title"><span className="pound">$</span>identity</h3></div>
          <div className="adm-row-2">
            <div className="adm-field"><label className="adm-field-label">display name</label><input className="adm-input" defaultValue="汪洋" /></div>
            <div className="adm-field"><label className="adm-field-label">handle</label>
              <div className="adm-field-wrap"><span className="adm-field-prefix">@</span><input className="adm-input with-prefix" defaultValue="wangyang" /></div>
            </div>
          </div>
          <div className="adm-field"><label className="adm-field-label">role / title</label><input className="adm-input" defaultValue="Backend / AI Full-stack Engineer" /></div>
          <div className="adm-field"><label className="adm-field-label">bio · 一句话简介</label>
            <textarea className="adm-textarea" defaultValue="Java / Python / PyTorch · 写后端、调模型、做 agent。深度学习 · 图像分割。"/>
            <div className="adm-field-hint">used in og:description and homepage hero</div>
          </div>
          <div className="adm-row-2">
            <div className="adm-field"><label className="adm-field-label">location</label><input className="adm-input" defaultValue="Shanghai · UTC+8" /></div>
            <div className="adm-field"><label className="adm-field-label">pronouns</label><input className="adm-input" defaultValue="he/him" /></div>
          </div>
        </div>

        <div className="adm-card">
          <div className="adm-card-head"><h3 className="adm-card-title"><span className="pound">$</span>avatar & hero</h3></div>
          <div style={{display:'flex', gap:14, alignItems:'center', marginBottom:14}}>
            <div style={{width:72, height:72, borderRadius:6, background:'linear-gradient(135deg, var(--accent), var(--violet))', color:'var(--bg)', display:'grid', placeItems:'center', fontSize:32, fontWeight:700, fontFamily:'JetBrains Mono'}}>汪</div>
            <div style={{flex:1}}>
              <button className="adm-btn">↑ upload avatar</button>
              <div className="adm-field-hint" style={{marginTop:6}}>1:1 PNG/JPG, max 2MB. fallback uses initial.</div>
            </div>
          </div>
          <div className="adm-field">
            <label className="adm-field-label">hero typing line</label>
            <textarea className="adm-textarea code" defaultValue={`// building backends that don't flinch.\n// training models that learn fast.\n// shipping agents that actually do the thing.`} />
            <div className="adm-field-hint">supports multi-line. shown with monospace cursor on home variant A.</div>
          </div>
          <div className="adm-field">
            <label className="adm-field-label">stack chips</label>
            <input className="adm-input" defaultValue="Java, Python, PyTorch, AI agents, deep learning, image segmentation" />
            <div className="adm-field-hint">comma-separated. rendered as monospace pills under the hero.</div>
          </div>
        </div>
      </div>
    </>
  );
}

/* ============ CONTACTS ============ */
function ScreenContacts() {
  const [items, setItems] = aS(ADMIN_DEFAULTS.contacts);
  return (
    <>
      <div className="adm-card">
        <div className="adm-card-head">
          <h3 className="adm-card-title"><span className="pound">~/</span>contact <span className="count">{items.length}</span></h3>
          <button className="adm-btn primary" onClick={() => setItems([...items, {id:Date.now(), k:'new', v:'value', href:'https://', visible:true}])}>+ add channel</button>
        </div>
        <table className="adm-table">
          <thead>
            <tr>
              <th style={{width:24}}></th>
              <th style={{width:140}}>label</th>
              <th style={{width:200}}>value</th>
              <th>url</th>
              <th style={{width:80}}>visible</th>
              <th style={{width:80}}></th>
            </tr>
          </thead>
          <tbody>
            {items.map((c, i) => (
              <tr key={c.id}>
                <td className="adm-muted">⋮⋮</td>
                <td><input className="adm-input" style={{padding:'4px 7px'}} defaultValue={c.k}/></td>
                <td><input className="adm-input" style={{padding:'4px 7px'}} defaultValue={c.v}/></td>
                <td><input className="adm-input" style={{padding:'4px 7px'}} defaultValue={c.href}/></td>
                <td><div className={`adm-toggle ${c.visible?'on':''}`} onClick={() => { const n=[...items]; n[i]={...c, visible:!c.visible}; setItems(n); }} /></td>
                <td><button className="adm-btn danger icon" onClick={() => setItems(items.filter(x=>x.id!==c.id))}>×</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="adm-field-hint" style={{marginTop:10}}>drag ⋮⋮ to reorder. invisible channels are hidden from /contact section but kept in the DB.</div>
      </div>
    </>
  );
}

/* ============ TAGS ============ */
function ScreenTags() {
  const [tags, setTags] = aS(ADMIN_DEFAULTS.tags);
  return (
    <div className="adm-card">
      <div className="adm-card-head">
        <h3 className="adm-card-title"><span className="pound">#</span>tags <span className="count">{tags.length}</span></h3>
        <button className="adm-btn primary">+ new tag</button>
      </div>
      {tags.map((t, i) => (
        <div className="adm-tag-row" key={t.id}>
          <span className="adm-tag-swatch" style={{background:t.color}} />
          <input className="adm-input" style={{padding:'4px 7px'}} defaultValue={t.name} />
          <input className="adm-input" style={{padding:'4px 7px'}} defaultValue={t.slug} />
          <input className="adm-input" style={{padding:'4px 7px'}} defaultValue={t.color} />
          <span className="adm-muted" style={{fontSize:11, textAlign:'right'}}>{t.count} posts</span>
          <button className="adm-btn danger icon">×</button>
        </div>
      ))}
    </div>
  );
}

/* ============ PROJECTS ============ */
function ScreenProjects() {
  const PROJECTS = [
    { name: "spring-ai-agent", desc: "JVM agent runtime · tool-calling, memory, traces", lang: "Java", stars: 248, status: "active" },
    { name: "sam-cli", desc: "fine-tune SAM on custom medical datasets", lang: "Python", stars: 67, status: "active" },
    { name: "termius-cn-fix", desc: "one-liner to fix Termius UTF-8 mojibake", lang: "Shell", stars: 31, status: "archived" },
    { name: "pgh-debug", desc: "PageHelper interceptor inspector", lang: "Java", stars: 89, status: "active" },
  ];
  return (
    <div className="adm-card">
      <div className="adm-card-head">
        <h3 className="adm-card-title"><span className="pound">~/</span>projects <span className="count">{PROJECTS.length}</span></h3>
        <button className="adm-btn primary">+ add project</button>
      </div>
      <table className="adm-table">
        <thead>
          <tr><th style={{width:24}}></th><th>name</th><th>description</th><th style={{width:80}}>lang</th><th style={{width:60}}>★</th><th style={{width:100}}>status</th><th style={{width:80}}></th></tr>
        </thead>
        <tbody>
          {PROJECTS.map((p, i) => (
            <tr key={i}>
              <td className="adm-muted">⋮⋮</td>
              <td><b style={{color:'var(--fg)'}}>{p.name}</b></td>
              <td className="adm-muted">{p.desc}</td>
              <td><span className="tag">{p.lang}</span></td>
              <td>{p.stars}</td>
              <td><span className={`adm-status ${p.status==='active'?'published':'draft'}`}>{p.status}</span></td>
              <td className="adm-actions-cell"><button className="adm-btn icon">edit</button><button className="adm-btn danger icon">×</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ============ NOW ============ */
function ScreenNow() {
  return (
    <div className="adm-grid-2" style={{alignItems:'start'}}>
      <div className="adm-card">
        <div className="adm-card-head"><h3 className="adm-card-title"><span className="pound">$</span>./now</h3></div>
        <div className="adm-field">
          <label className="adm-field-label">what are you doing now?</label>
          <textarea className="adm-textarea code" rows={6} defaultValue={ADMIN_DEFAULTS.now} />
          <div className="adm-field-hint">shown on homepage variant B/C sidebars and at /now. supports markdown links.</div>
        </div>
        <div className="adm-row-2">
          <div className="adm-field">
            <label className="adm-field-label">last updated</label>
            <input className="adm-input" defaultValue="2026-04-23" />
          </div>
          <div className="adm-field">
            <label className="adm-field-label">listening</label>
            <input className="adm-input" defaultValue="Lo-Fi · 椎名林檎 · 周深" />
          </div>
        </div>
        <div className="adm-field">
          <label className="adm-field-label">currently reading</label>
          <input className="adm-input" defaultValue="Designing Data-Intensive Applications · 再读一遍" />
        </div>
        <div style={{display:'flex', gap:6, justifyContent:'flex-end', marginTop:8}}>
          <button className="adm-btn">save draft</button>
          <button className="adm-btn primary">publish update</button>
        </div>
      </div>

      <div className="adm-card">
        <div className="adm-card-head"><h3 className="adm-card-title"><span className="pound">#</span>history</h3></div>
        {[
          ["2026-04-23", "Shipping agent runtime for JVM. Re-reading DDIA."],
          ["2026-04-10", "Training SAM on med-imaging. Drinking too much matcha."],
          ["2026-03-28", "Built a PageHelper debugger. Probably overkill."],
          ["2026-03-15", "Onboarded new juniors. They ask better questions than me."],
        ].map(([d, t], i) => (
          <div key={i} style={{display:'flex', gap:14, padding:'10px 0', borderBottom:'1px dashed var(--line)', fontSize:12}}>
            <span style={{color:'var(--fg-4)', fontSize:11, minWidth:80}}>{d}</span>
            <span style={{color:'var(--fg-3)'}}>{t}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ============ SITE ============ */
function ScreenSite() {
  const [layout, setLayout] = aS('A');
  return (
    <>
      <div className="adm-grid-2" style={{alignItems:'start'}}>
        <div className="adm-card">
          <div className="adm-card-head"><h3 className="adm-card-title"><span className="pound">$</span>basics</h3></div>
          <div className="adm-field"><label className="adm-field-label">site title</label><input className="adm-input" defaultValue="wangyang.dev" /></div>
          <div className="adm-field"><label className="adm-field-label">tagline</label><input className="adm-input" defaultValue="backend · ai engineer · shipping things that don't flinch" /></div>
          <div className="adm-field"><label className="adm-field-label">domain</label>
            <div className="adm-field-wrap"><span className="adm-field-prefix">https://</span><input className="adm-input with-prefix" defaultValue="wangyang.dev" /></div>
          </div>
          <div className="adm-row-2">
            <div className="adm-field"><label className="adm-field-label">timezone</label><select className="adm-select" defaultValue="Asia/Shanghai"><option>Asia/Shanghai</option><option>UTC</option><option>America/Los_Angeles</option></select></div>
            <div className="adm-field"><label className="adm-field-label">language</label><select className="adm-select" defaultValue="zh-CN"><option>zh-CN</option><option>en</option></select></div>
          </div>
          <div className="adm-field"><label className="adm-field-label">footer note</label><input className="adm-input" defaultValue="© 2026 wangyang · powered by jetlag and matcha" /></div>
        </div>

        <div className="adm-card">
          <div className="adm-card-head"><h3 className="adm-card-title"><span className="pound">$</span>theme · colors</h3></div>
          <div className="adm-row-2">
            <div className="adm-field"><label className="adm-field-label">accent</label>
              <div className="adm-field-wrap"><span className="adm-field-prefix" style={{background:'#7dd3a4', width:14, height:14, top:'50%', borderRadius:2, transform:'translateY(-50%)'}}></span><input className="adm-input with-prefix" defaultValue="#7dd3a4" /></div>
            </div>
            <div className="adm-field"><label className="adm-field-label">accent-2</label>
              <div className="adm-field-wrap"><span className="adm-field-prefix" style={{background:'#ffb86b', width:14, height:14, top:'50%', borderRadius:2, transform:'translateY(-50%)'}}></span><input className="adm-input with-prefix" defaultValue="#ffb86b" /></div>
            </div>
          </div>
          <div className="adm-row-2">
            <div className="adm-field"><label className="adm-field-label">violet</label>
              <div className="adm-field-wrap"><span className="adm-field-prefix" style={{background:'#b794ff', width:14, height:14, top:'50%', borderRadius:2, transform:'translateY(-50%)'}}></span><input className="adm-input with-prefix" defaultValue="#b794ff" /></div>
            </div>
            <div className="adm-field"><label className="adm-field-label">danger</label>
              <div className="adm-field-wrap"><span className="adm-field-prefix" style={{background:'#f47174', width:14, height:14, top:'50%', borderRadius:2, transform:'translateY(-50%)'}}></span><input className="adm-input with-prefix" defaultValue="#f47174" /></div>
            </div>
          </div>
          <div className="adm-row-inline" style={{marginTop:6}}>
            <div className="l"><b>default theme</b><div className="h">also respects system preference</div></div>
            <select className="adm-select" defaultValue="dark" style={{padding:'5px 8px'}}><option>dark</option><option>light</option><option>system</option></select>
          </div>
        </div>
      </div>

      <div className="adm-card" style={{marginTop:16}}>
        <div className="adm-card-head"><h3 className="adm-card-title"><span className="pound">$</span>default homepage layout</h3></div>
        <div className="adm-layout-tiles">
          {[
            ['A', 'Terminal', 'mono · contribution graph · post list'],
            ['B', 'Editorial', 'serif · italic display · numbered entries'],
            ['C', 'Dashboard', 'grid · stats · now/listening/posts cards'],
          ].map(([k, name, desc]) => (
            <button key={k} className={`adm-layout-tile ${layout===k?'on':''}`} onClick={() => setLayout(k)}>
              <div className="name"><span className="key">[{k}]</span> {name}</div>
              <div className="preview">
                <i className="title" />
                {k==='A' && <><i style={{width:'90%'}}/><i style={{width:'85%'}}/><i style={{width:'70%'}}/></>}
                {k==='B' && <><i style={{width:'40%', height:8}}/><i style={{width:'80%'}}/><i style={{width:'80%'}}/></>}
                {k==='C' && <div style={{display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:3, marginTop:3}}><i style={{height:14}}/><i style={{height:14}}/><i style={{height:14}}/></div>}
              </div>
              <div className="desc">{desc}</div>
            </button>
          ))}
        </div>
      </div>
    </>
  );
}

/* ============ MEDIA ============ */
function ScreenMedia() {
  const items = Array.from({length: 18}, (_, i) => ({ name: `img-${String(i+1).padStart(3,'0')}.png`, size: (50 + Math.random()*900).toFixed(0)+'kb' }));
  return (
    <div className="adm-card">
      <div className="adm-card-head">
        <h3 className="adm-card-title"><span className="pound">~/</span>media <span className="count">{items.length}</span></h3>
        <div style={{display:'flex', gap:6}}>
          <button className="adm-btn">↑ upload</button>
          <button className="adm-btn primary">drop files anywhere</button>
        </div>
      </div>
      <div className="adm-media-grid">
        {items.map((m, i) => (
          <div key={i} className="adm-media-tile">
            <div className="ph" style={{background: `linear-gradient(${(i*40)%360}deg, color-mix(in oklab, var(--accent) ${20+i*3}%, var(--bg-3)), var(--bg-2))`}}>
              <span style={{opacity:0.8}}>.png</span>
            </div>
            <div className="meta">
              <span style={{overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap'}}>{m.name}</span>
              <span>{m.size}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ============ COMMENTS ============ */
function ScreenComments() {
  const COMMENTS = [
    { id:1, who:'lin@example.com', post:'Termius 中文乱码', when:'2h ago', body:'Saved my afternoon. 终于不用看一片问号了，谢了。', status:'approved' },
    { id:2, who:'anon', post:'科学上网搭建教程', when:'5h ago', body:'check out my-totally-not-spam.link/promo', status:'pending', flag:'spam-suspected' },
    { id:3, who:'jiang@gmail', post:'PageHelper 分页失效', when:'1d ago', body:'第三步那个 SqlInterceptor 是不是要在 Spring AOP 启动之后再注册？我这边顺序不对就空指针。', status:'approved' },
    { id:4, who:'kai@dev', post:'Spring AI agent', when:'2d ago', body:'有没有 GitHub 例子？想看 tool-calling 的具体写法。', status:'pending' },
  ];
  return (
    <>
      <div className="adm-toolbar">
        <div className="adm-search"><input placeholder="search comments…" /></div>
        <div className="adm-pills">
          <button className="adm-pill on">all</button>
          <button className="adm-pill">pending <span style={{color:'var(--amber)'}}>2</span></button>
          <button className="adm-pill">approved</button>
          <button className="adm-pill">spam</button>
        </div>
      </div>
      {COMMENTS.map(c => (
        <div key={c.id} className="adm-comment">
          <div className="head">
            <b>{c.who}</b>
            <span>·</span>
            <span>on “{c.post}”</span>
            <span>·</span>
            <span>{c.when}</span>
            <span style={{flex:1}} />
            <span className={`adm-status ${c.status==='approved'?'published':'draft'}`}>{c.status}</span>
            {c.flag && <span style={{color:'var(--danger)', fontSize:10}}>⚠ {c.flag}</span>}
          </div>
          <div className="body">{c.body}</div>
          <div className="acts">
            <button className="adm-btn primary">approve</button>
            <button className="adm-btn">reply</button>
            <button className="adm-btn danger">mark spam</button>
            <button className="adm-btn danger ghost">delete</button>
          </div>
        </div>
      ))}
    </>
  );
}

/* ============ ANALYTICS ============ */
function ScreenAnalytics() {
  const days = aM(() => Array.from({length:30}, () => 200 + Math.random()*1600), []);
  return (
    <>
      <div className="adm-grid-4" style={{marginBottom: 18}}>
        <Stat l="VISITORS · 30D" v="24,108" delta="+12.4% vs last 30d" />
        <Stat l="PAGEVIEWS" v="68,422" delta="+9.1%" tone="violet" />
        <Stat l="AVG. SESSION" v="2m 18s" delta="+0:14" tone="amber" />
        <Stat l="BOUNCE" v="34.2%" delta="-2.1pp" tone="blue" />
      </div>
      <div className="adm-card">
        <div className="adm-card-head"><h3 className="adm-card-title"><span className="pound">#</span>visitors · 30 days</h3></div>
        <div className="adm-bars">
          {days.map((h, i) => <i key={i} style={{height: (h/18)+'%'}} />)}
        </div>
      </div>
      <div className="adm-grid-2" style={{marginTop:16}}>
        <div className="adm-card">
          <div className="adm-card-head"><h3 className="adm-card-title"><span className="pound">#</span>top referrers</h3></div>
          {[['hacker news', 4220], ['twitter / x', 2810], ['github', 1605], ['v2ex', 980], ['google', 7204]].map(([n, v], i) => (
            <div key={i} style={{display:'flex', justifyContent:'space-between', padding:'6px 0', fontSize:12, borderBottom:'1px dashed var(--line)'}}>
              <span>{n}</span><span style={{color:'var(--accent)'}}>{v.toLocaleString()}</span>
            </div>
          ))}
        </div>
        <div className="adm-card">
          <div className="adm-card-head"><h3 className="adm-card-title"><span className="pound">#</span>countries</h3></div>
          {[['🇨🇳 China', '58%'], ['🇺🇸 United States', '14%'], ['🇯🇵 Japan', '6%'], ['🇩🇪 Germany', '4%'], ['🇸🇬 Singapore', '3%'], ['rest', '15%']].map(([n, v], i) => (
            <div key={i} style={{display:'flex', justifyContent:'space-between', padding:'6px 0', fontSize:12, borderBottom:'1px dashed var(--line)'}}>
              <span>{n}</span><span style={{color:'var(--accent)'}}>{v}</span>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

/* ============ PET ============ */
function ScreenPet() {
  const SPECIES = ['cat','capybara','axolotl','robot','dragon','ghost','octopus','owl','penguin','turtle','snail','duck'];
  const [sp, setSp] = aS('capybara');
  return (
    <>
      <div className="adm-grid-2" style={{alignItems:'start'}}>
        <div className="adm-card">
          <div className="adm-card-head"><h3 className="adm-card-title"><span className="pound">$</span>species &amp; appearance</h3></div>
          <div className="adm-field">
            <label className="adm-field-label">default species</label>
            <div style={{display:'flex', flexWrap:'wrap', gap:4}}>
              {SPECIES.map(s => (
                <button key={s} className={`adm-pill ${sp===s?'on':''}`} onClick={() => setSp(s)}>{s}</button>
              ))}
            </div>
          </div>
          <div className="adm-row-2">
            <div className="adm-field"><label className="adm-field-label">hat</label><select className="adm-select" defaultValue="none"><option>none</option><option>top hat</option><option>crown</option><option>headphones</option><option>graduation cap</option></select></div>
            <div className="adm-field"><label className="adm-field-label">color tint</label>
              <div className="adm-field-wrap"><span className="adm-field-prefix" style={{background:'#7dd3a4', width:14, height:14, top:'50%', borderRadius:2, transform:'translateY(-50%)'}}></span><input className="adm-input with-prefix" defaultValue="#7dd3a4" /></div>
            </div>
          </div>
          <div className="adm-row-inline">
            <div className="l"><b>enabled on site</b><div className="h">show pet on every page</div></div>
            <div className="adm-toggle on" />
          </div>
          <div className="adm-row-inline">
            <div className="l"><b>visitors can change pet</b><div className="h">stored in their localStorage only</div></div>
            <div className="adm-toggle on" />
          </div>
        </div>

        <div className="adm-card">
          <div className="adm-card-head"><h3 className="adm-card-title"><span className="pound">$</span>llm config</h3></div>
          <div className="adm-row-2">
            <div className="adm-field"><label className="adm-field-label">model</label><select className="adm-select" defaultValue="claude-haiku-4-5"><option>claude-haiku-4-5</option><option>claude-sonnet-4-5</option><option>gpt-5-mini</option></select></div>
            <div className="adm-field"><label className="adm-field-label">max tokens</label><input className="adm-input" defaultValue="180" /></div>
          </div>
          <div className="adm-field">
            <label className="adm-field-label">system prompt</label>
            <textarea className="adm-textarea code" rows={6} defaultValue={ADMIN_DEFAULTS.pet.systemPrompt} />
            <div className="adm-field-hint">used when visitor clicks the pet to summon a fresh line.</div>
          </div>
          <div className="adm-field">
            <label className="adm-field-label">fallback lines · one per row</label>
            <textarea className="adm-textarea code" rows={4} defaultValue={`compiling… 慢慢来\nseg fault? skill issue.\nrun nya init\n摸了一会儿 GPU，凉的`} />
          </div>
          <div className="adm-row-inline">
            <div className="l"><b>rate limit</b><div className="h">per visitor per minute</div></div>
            <input className="adm-input" defaultValue="6" style={{width:60, textAlign:'center', padding:'4px'}}/>
          </div>
        </div>
      </div>
    </>
  );
}

/* ============ SETTINGS ============ */
function ScreenSettings() {
  return (
    <>
      <div className="adm-grid-2" style={{alignItems:'start'}}>
        <div className="adm-card">
          <div className="adm-card-head"><h3 className="adm-card-title"><span className="pound">$</span>account</h3></div>
          <div className="adm-field"><label className="adm-field-label">login email</label><input className="adm-input" defaultValue="hi@wangyang.dev" /></div>
          <div className="adm-field"><label className="adm-field-label">change password</label><input className="adm-input" type="password" defaultValue="••••••••••" /></div>
          <div className="adm-row-inline">
            <div className="l"><b>2FA · TOTP</b><div className="h">authenticator app required at sign-in</div></div>
            <div className="adm-toggle on" />
          </div>
          <div className="adm-row-inline">
            <div className="l"><b>magic-link only</b><div className="h">no password, just email link</div></div>
            <div className="adm-toggle" />
          </div>
        </div>

        <div className="adm-card">
          <div className="adm-card-head"><h3 className="adm-card-title"><span className="pound">$</span>api tokens</h3></div>
          <table className="adm-table">
            <thead><tr><th>name</th><th>scope</th><th>last used</th><th></th></tr></thead>
            <tbody>
              <tr><td>vercel deploy hook</td><td><span className="tag">deploy</span></td><td className="adm-muted">3h ago</td><td><button className="adm-btn danger icon">revoke</button></td></tr>
              <tr><td>github actions</td><td><span className="tag">read · write</span></td><td className="adm-muted">2d ago</td><td><button className="adm-btn danger icon">revoke</button></td></tr>
              <tr><td>obsidian sync</td><td><span className="tag">read</span></td><td className="adm-muted">never</td><td><button className="adm-btn danger icon">revoke</button></td></tr>
            </tbody>
          </table>
          <button className="adm-btn primary" style={{marginTop:10}}>+ new token</button>
        </div>

        <div className="adm-card">
          <div className="adm-card-head"><h3 className="adm-card-title"><span className="pound">$</span>integrations</h3></div>
          <div className="adm-row-inline">
            <div className="l"><b>vercel</b><div className="h">auto-deploy on push to main · last: 28s ago ✓</div></div>
            <span className="adm-status published">connected</span>
          </div>
          <div className="adm-row-inline">
            <div className="l"><b>github</b><div className="h">sync /projects from repos starred</div></div>
            <span className="adm-status published">connected</span>
          </div>
          <div className="adm-row-inline">
            <div className="l"><b>plausible analytics</b><div className="h">cookie-less analytics</div></div>
            <span className="adm-status draft">disconnected</span>
          </div>
          <div className="adm-row-inline">
            <div className="l"><b>anthropic api</b><div className="h">used by pet · model fallback</div></div>
            <span className="adm-status published">connected</span>
          </div>
        </div>

        <div className="adm-card" style={{borderColor:'color-mix(in oklab, var(--danger) 30%, var(--line))'}}>
          <div className="adm-card-head"><h3 className="adm-card-title" style={{color:'var(--danger)'}}><span className="pound" style={{color:'var(--danger)'}}>!</span>danger zone</h3></div>
          <div className="adm-row-inline">
            <div className="l"><b>export everything</b><div className="h">posts + media + db, .zip</div></div>
            <button className="adm-btn">↓ export</button>
          </div>
          <div className="adm-row-inline">
            <div className="l"><b>delete site</b><div className="h">cannot be undone. 7-day grace period.</div></div>
            <button className="adm-btn danger">delete</button>
          </div>
        </div>
      </div>
    </>
  );
}

Object.assign(window, {
  ScreenDashboard, ScreenPosts, ScreenProfile, ScreenContacts, ScreenTags,
  ScreenProjects, ScreenNow, ScreenSite, ScreenMedia, ScreenComments,
  ScreenAnalytics, ScreenPet, ScreenSettings,
});
