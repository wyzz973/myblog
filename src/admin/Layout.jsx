import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from './AuthContext.jsx';

// Six workflow groups, mirroring the public site's `01 / 02 / 03` numbered
// section motif (HomeA.jsx). Routes are unchanged in this rebuild step;
// future tasks split / merge specific pages (e.g. Profile + Site → 站点身份,
// Settings sub-tabs → top-level entries).
const NAV_GROUPS = [
  {
    n: '01',
    label: '运营中枢',
    items: [{ to: '/admin/dashboard', label: '仪表盘' }],
  },
  {
    n: '02',
    label: '内容',
    items: [
      { to: '/admin/posts', label: '文章' },
      { to: '/admin/tags', label: '标签' },
      { to: '/admin/media', label: '媒体' },
      { to: '/admin/now', label: '近况' },
      { to: '/admin/projects', label: '项目' },
    ],
  },
  {
    n: '03',
    label: '观察',
    items: [
      { to: '/admin/analytics', label: '数据分析' },
      { to: '/admin/comments', label: '评论' },
    ],
  },
  {
    n: '04',
    label: '首页与品牌',
    items: [
      { to: '/admin/profile', label: '作者资料' },
      { to: '/admin/site', label: '站点' },
      { to: '/admin/contacts', label: '联系方式' },
    ],
  },
  {
    n: '05',
    label: '宠物',
    items: [{ to: '/admin/pet', label: '宠物助手' }],
  },
  {
    n: '06',
    label: '系统',
    items: [{ to: '/admin/settings', label: '设置' }],
  },
];

// Flat lookup so the topbar can render a breadcrumb without re-walking the
// nav tree on every render.
const ROUTE_INDEX = (() => {
  const idx = {};
  for (const g of NAV_GROUPS) {
    for (const it of g.items) {
      idx[it.to] = { n: g.n, group: g.label, label: it.label };
    }
  }
  return idx;
})();

function findCrumb(pathname) {
  if (!pathname) return null;
  // Exact match first; fall back to the longest registered prefix so
  // /admin/posts/__new__ still resolves to the 文章 entry.
  if (ROUTE_INDEX[pathname]) return ROUTE_INDEX[pathname];
  let best = null;
  for (const route of Object.keys(ROUTE_INDEX)) {
    if (pathname === route || pathname.startsWith(route + '/')) {
      if (!best || route.length > best.length) best = route;
    }
  }
  return best ? ROUTE_INDEX[best] : null;
}

export default function Layout() {
  const { email, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const crumb = findCrumb(location.pathname);

  function onLogout() {
    logout();
    navigate('/admin', { replace: true });
  }

  return (
    <div className="admin-shell" style={styles.shell}>
      <aside className="admin-sidebar" style={styles.sidebar}>
        <div className="admin-brand" style={styles.brand}>
          <span className="admin-brand-dot" style={styles.brandDot} />
          <div>
            <div style={styles.brandTitle}>myblog</div>
            <div style={styles.brandSub}>管理后台</div>
          </div>
        </div>
        <nav className="admin-nav" style={styles.nav} aria-label="admin navigation">
          {NAV_GROUPS.map((group) => (
            <div key={group.n} style={styles.navGroup} data-testid={`nav-group-${group.n}`}>
              <div style={styles.navGroupHead}>
                <span style={styles.navGroupNum}>{group.n}</span>
                <span style={styles.navGroupLabel}>{group.label}</span>
              </div>
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className="admin-nav-item"
                  style={({ isActive }) => ({
                    ...styles.navItem,
                    ...(isActive ? styles.navItemActive : null),
                  })}
                >
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
      </aside>

      <div className="admin-main" style={styles.main}>
        <header className="admin-topbar" style={styles.topbar}>
          <div className="admin-crumbs" style={styles.crumbs} data-testid="breadcrumb">
            <span style={styles.dim}>~</span>
            <span style={styles.sep}>/</span>
            <span>admin</span>
            {crumb && (
              <>
                <span style={styles.sep}>/</span>
                <span style={styles.crumbGroup}>
                  <span style={styles.crumbGroupNum}>{crumb.n}</span>
                  <span style={styles.crumbGroupSep}>·</span>
                  <span>{crumb.group}</span>
                </span>
                <span style={styles.sep}>/</span>
                <span style={styles.crumbLeaf}>{crumb.label}</span>
              </>
            )}
          </div>
          <div className="admin-user-box" style={styles.userBox}>
            <span className="admin-user-email" style={styles.userEmail}>{email || 'unknown'}</span>
            <button type="button" onClick={onLogout} style={styles.logout}>
              退出
            </button>
          </div>
        </header>

        <main className="admin-content" style={styles.content}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}

const styles = {
  shell: {
    minHeight: '100vh',
    display: 'grid',
    gridTemplateColumns: '232px 1fr',
    background: 'var(--bg)',
    color: 'var(--fg)',
    fontFamily: "'JetBrains Mono', ui-monospace, Menlo, monospace",
  },
  sidebar: {
    borderRight: '1px solid var(--line)',
    background: 'var(--bg-2)',
    padding: '18px 12px',
    position: 'sticky',
    top: 0,
    alignSelf: 'start',
    height: '100vh',
    overflowY: 'auto',
  },
  brand: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '6px 10px 18px',
    borderBottom: '1px solid var(--line)',
    marginBottom: 12,
  },
  brandDot: {
    width: 10,
    height: 10,
    borderRadius: 999,
    background: 'var(--accent)',
    boxShadow: '0 0 10px var(--accent-glow)',
  },
  brandTitle: { fontSize: 13, fontWeight: 600, color: 'var(--fg)' },
  brandSub: { fontSize: 10, color: 'var(--fg-3)', letterSpacing: '0.06em' },
  nav: { display: 'flex', flexDirection: 'column', gap: 12 },
  navGroup: { display: 'flex', flexDirection: 'column', gap: 2 },
  navGroupHead: {
    display: 'flex',
    alignItems: 'baseline',
    gap: 6,
    padding: '4px 10px 6px',
    fontSize: 9,
    letterSpacing: '0.12em',
    textTransform: 'uppercase',
    color: 'var(--fg-4)',
  },
  navGroupNum: {
    color: 'var(--accent)',
    fontWeight: 600,
  },
  navGroupLabel: {},
  navItem: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '7px 10px 7px 12px',
    fontSize: 12,
    color: 'var(--fg-2)',
    borderRadius: 4,
    textDecoration: 'none',
    borderLeft: '2px solid transparent',
  },
  navItemActive: {
    background: 'color-mix(in oklab, var(--accent) 14%, transparent)',
    color: 'var(--fg)',
    fontWeight: 600,
    borderLeft: '2px solid var(--accent)',
  },
  main: {
    display: 'flex',
    flexDirection: 'column',
    minWidth: 0,
  },
  topbar: {
    position: 'sticky',
    top: 0,
    zIndex: 5,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '10px 22px',
    background: 'color-mix(in oklab, var(--bg) 85%, transparent)',
    backdropFilter: 'blur(8px)',
    borderBottom: '1px solid var(--line)',
    fontSize: 12,
  },
  crumbs: { display: 'flex', alignItems: 'center', gap: 6, color: 'var(--fg-2)' },
  crumbGroup: {
    display: 'inline-flex',
    alignItems: 'baseline',
    gap: 4,
    color: 'var(--fg-3)',
  },
  crumbGroupNum: {
    color: 'var(--accent)',
    fontSize: 10,
    letterSpacing: '0.08em',
  },
  crumbGroupSep: { color: 'var(--fg-4)' },
  crumbLeaf: { color: 'var(--fg)' },
  dim: { color: 'var(--fg-4)' },
  sep: { color: 'var(--fg-4)' },
  userBox: { display: 'flex', alignItems: 'center', gap: 12 },
  userEmail: { color: 'var(--fg-3)' },
  logout: {
    color: 'var(--fg)',
    background: 'transparent',
    border: '1px solid var(--line-2)',
    padding: '4px 10px',
    borderRadius: 4,
    fontSize: 11,
    fontFamily: 'inherit',
    cursor: 'pointer',
  },
  content: {
    padding: '22px 24px 40px',
    flex: 1,
    minWidth: 0,
  },
};
