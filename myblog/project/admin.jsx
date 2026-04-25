/* Admin shell — sidebar nav + topbar + status bar + screen routing */
const { useState, useEffect, useMemo } = React;

const NAV = [
  { group: 'overview', items: [
    { id: 'dashboard', label: 'dashboard', icon: '◇' },
    { id: 'analytics', label: 'analytics', icon: '↗' },
  ]},
  { group: 'content', items: [
    { id: 'posts', label: 'posts', icon: '⌘', badge: '38' },
    { id: 'media', label: 'media', icon: '◫', badge: '142' },
    { id: 'comments', label: 'comments', icon: '✎', badge: '2' },
    { id: 'tags', label: 'tags', icon: '#' },
  ]},
  { group: 'site config', items: [
    { id: 'site', label: 'site', icon: '⚙' },
    { id: 'profile', label: 'profile', icon: '@' },
    { id: 'contacts', label: 'contacts', icon: '✉' },
    { id: 'projects', label: 'projects', icon: '◴' },
    { id: 'now', label: 'now', icon: '●' },
    { id: 'pet', label: 'pet', icon: '🐾' },
  ]},
  { group: 'system', items: [
    { id: 'settings', label: 'settings', icon: '⌥' },
  ]},
];

const SCREENS = {
  dashboard: ScreenDashboard, analytics: ScreenAnalytics,
  posts: ScreenPosts, media: ScreenMedia, comments: ScreenComments, tags: ScreenTags,
  site: ScreenSite, profile: ScreenProfile, contacts: ScreenContacts,
  projects: ScreenProjects, now: ScreenNow, pet: ScreenPet, settings: ScreenSettings,
};

const TITLES = {
  dashboard: ['~/', 'dashboard', 'at-a-glance · activity log · build status'],
  analytics: ['~/', 'analytics', 'visitors · referrers · top posts'],
  posts: ['~/', 'posts', 'list · create · edit · publish'],
  media: ['~/', 'media', 'upload · browse · attach to posts'],
  comments: ['~/', 'comments', 'moderation queue · spam · replies'],
  tags: ['~/', 'tags', 'manage colors · slugs · counts'],
  site: ['~/', 'site', 'title · theme · layout · domain'],
  profile: ['~/', 'profile', 'identity · bio · avatar · hero'],
  contacts: ['~/', 'contacts', 'channels shown on /contact section'],
  projects: ['~/', 'projects', 'repos & side-projects'],
  now: ['~/', 'now', 'what you are doing now · history'],
  pet: ['~/', 'pet', 'desktop companion · llm config'],
  settings: ['~/', 'settings', 'account · api tokens · integrations'],
};

function MiniGraph() {
  const bars = useMemo(() => Array.from({length: 24}, () => 20 + Math.random()*100), []);
  return (
    <div className="adm-mini-graph">
      {bars.map((h, i) => <i key={i} style={{height: h+'%'}} />)}
    </div>
  );
}

function App() {
  const [route, setRoute] = useState(() => {
    const h = location.hash.slice(1);
    return SCREENS[h] ? h : 'dashboard';
  });
  useEffect(() => { location.hash = route; }, [route]);
  useEffect(() => {
    const onHash = () => { const h = location.hash.slice(1); if (SCREENS[h]) setRoute(h); };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  const Screen = SCREENS[route];
  const [, title, sub] = TITLES[route];

  return (
    <div className="admin-shell">
      <header className="adm-topbar">
        <div className="adm-brand">
          <span className="lock">●</span>
          <span>wangyang<span className="accent">.dev</span></span>
          <span className="adm-muted" style={{marginLeft:6}}>/admin</span>
        </div>
        <div className="adm-breadcrumb">
          <span>~</span><span className="sep">/</span><b>{title}</b>
        </div>
        <div className="adm-spacer" />
        <span className="adm-muted" style={{fontSize:10, marginRight:6}}><span className="adm-kbd">⌘</span> <span className="adm-kbd">K</span> palette</span>
        <a href="index.html" target="_blank" rel="noopener" className="adm-topbar-action">view site ↗</a>
        <button className="adm-topbar-action primary">⟲ deploy</button>
        <div className="adm-user">
          <div className="av">汪</div>
          <span>@wangyang ▾</span>
        </div>
      </header>

      <aside className="adm-sidebar">
        {NAV.map(g => (
          <div className="adm-nav-group" key={g.group}>
            <div className="adm-nav-label">{g.group}</div>
            {g.items.map(item => (
              <div key={item.id}
                className={`adm-nav-item ${route===item.id?'active':''}`}
                onClick={() => setRoute(item.id)}>
                <span className="adm-nav-icon">{item.icon}</span>
                <span>{item.label}</span>
                {item.badge && <span className="adm-nav-badge">{item.badge}</span>}
              </div>
            ))}
          </div>
        ))}
        <div className="adm-sidebar-foot">
          <div><b>uptime</b> 99.98% · 30d</div>
          <div><b>build</b> <span style={{color:'var(--accent)'}}>passing</span> · 7c4a2f3</div>
          <MiniGraph />
          <div className="adm-muted" style={{fontSize:9, marginTop:4}}>visitors · 24h</div>
        </div>
      </aside>

      <main className="adm-main">
        <div className="adm-page-head">
          <div>
            <h1 className="adm-page-title">
              <span className="prefix">~/</span>
              <span>{title}</span>
            </h1>
            <div className="adm-page-sub">{sub}</div>
          </div>
          <div className="adm-page-actions">
            <span className="adm-muted" style={{fontSize:10}}>last save · 2m ago</span>
          </div>
        </div>
        <Screen />
      </main>

      <footer className="adm-statusbar">
        <span className="seg ok">db · postgres</span>
        <span className="seg ok">redis</span>
        <span className="seg info">ws · 2 clients</span>
        <span className="seg ok">vercel · ready</span>
        <span className="seg warn">2 pending comments</span>
        <span className="seg right">{new Date().toISOString().slice(0,19).replace('T',' ')} UTC</span>
        <span className="seg">v0.4.2</span>
      </footer>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
