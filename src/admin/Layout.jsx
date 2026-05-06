import { useCallback, useEffect, useMemo, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from './AuthContext.jsx';
import CommandPalette from './CommandPalette.jsx';
import ShortcutsHelp from './ShortcutsHelp.jsx';
import useGlobalShortcuts from './useGlobalShortcuts.js';
import UIProvider from './ui/UIProvider.jsx';
import { postsApi } from '../api/posts.js';
import { apiAdmin, getToken } from '../api/admin.js';

// Six workflow groups, mirroring the public site's `01 / 02 / 03` numbered
// section motif (HomeA.jsx). Routes are unchanged in this rebuild step;
// future tasks split / merge specific pages (e.g. Profile + Site → 站点身份,
// Settings sub-tabs → top-level entries).
export const NAV_GROUPS = [
  {
    n: '01',
    label: '运营中枢',
    items: [
      { to: '/admin/dashboard', label: '仪表盘' },
      { to: '/admin/inbox', label: '收件箱' },
    ],
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
      { to: '/admin/site-identity', label: '站点身份' },
      { to: '/admin/contacts', label: '联系方式' },
      // 主题 lives at /admin/theme; legacy /admin/site redirects there
      // so any external bookmark / analytics URL still works.
      { to: '/admin/theme', label: '主题' },
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
    items: [
      { to: '/admin/settings', label: '设置' },
      { to: '/admin/activity-log', label: '活动日志' },
    ],
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

// Task 48: derive per-route counters from a /api/admin/dashboard payload.
// Each entry maps a NavLink `to` to the actionable count rendered as a
// sidebar badge. Add an entry here to surface a new counter — anything
// already in the dashboard payload is one line away.
//
// Counters intentionally favor "needs-attention" over "inventory":
//   - comments.pending — moderation queue (blocked on owner)
//   - posts.draft      — work in progress; reminder to finish
// Inventory-only fields (posts.published, media.count, etc.) are
// omitted so the sidebar doesn't broadcast non-actionable noise.
export function pickNavCounters(dashboard) {
  if (!dashboard) return {};
  return {
    '/admin/comments': dashboard?.comments?.pending ?? 0,
    '/admin/posts': dashboard?.posts?.draft ?? 0,
  };
}

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
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  // 移动端 sidebar 抽屉。桌面 ≥768px 时 sidebar 一直展开，state 不影响布局；
  // <768px 时 sidebar 默认收起，用 hamburger 切换并叠加遮罩。
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  // 切路由时自动关抽屉，不留在屏幕中央。
  useEffect(() => { setMobileNavOpen(false); }, [location.pathname]);
  // Task 47/48: per-route actionable counters from /api/admin/dashboard.
  // Map is keyed by NavLink `to` so each entry is rendered as a badge
  // beside its sidebar item. Polled every 60s and refreshed on route
  // change so an action that updates the underlying number reflects
  // immediately on the next page transition.
  const [navCounters, setNavCounters] = useState({});
  useEffect(() => {
    let alive = true;
    function refresh() {
      apiAdmin.dashboard()
        .then((res) => {
          if (!alive) return;
          setNavCounters(pickNavCounters(res));
        })
        .catch(() => { /* silent — sidebar still works */ });
    }
    refresh();
    const id = setInterval(refresh, 60_000);
    return () => { alive = false; clearInterval(id); };
  }, [location.pathname]); // refresh on route change too
  const showHelp = useCallback(() => setHelpOpen(true), []);
  useGlobalShortcuts({ navigate, onShowHelp: showHelp });

  function onLogout() {
    logout();
    navigate('/admin', { replace: true });
  }

  // ⌘K / Ctrl+K toggles the palette. The shortcut is suppressed while the
  // user is composing inside an editable surface (textarea, contenteditable),
  // so PostEditor / Now composer keep their normal typing behavior.
  useEffect(() => {
    function onKey(e) {
      if (!(e.metaKey || e.ctrlKey)) return;
      if (e.key !== 'k' && e.key !== 'K') return;
      const t = e.target;
      const tag = t?.tagName;
      const editable =
        tag === 'TEXTAREA' ||
        (tag === 'INPUT' && /^(text|search|email|password|url)$/i.test(t.type || 'text')) ||
        t?.isContentEditable;
      // ⌘K should still work even from editor inputs — it overrides browser
      // history search. We simply do not insert a "k" character.
      e.preventDefault();
      e.stopPropagation();
      void editable;
      setPaletteOpen((o) => !o);
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const loadPosts = useCallback(
    () => postsApi.list({ limit: 100 }).then((r) => r?.items || []),
    [],
  );

  const runners = useMemo(
    () => ({
      go: (path) => navigate(path),
      newPost: () => navigate('/admin/posts', { state: { editPost: '__new__' } }),
      openPost: (id) => navigate('/admin/posts', { state: { editPost: id } }),
      copyToken: async () => {
        try {
          await navigator.clipboard?.writeText?.(getToken() || '');
        } catch {
          /* clipboard may be blocked — silent */
        }
      },
      openPublic: () => window.open('/', '_blank', 'noopener,noreferrer'),
      logout: onLogout,
    }),
    [navigate], // eslint-disable-line react-hooks/exhaustive-deps
  );

  return (
    <UIProvider>
    {/* 移动端响应式：把 sidebar 折成 hamburger 抽屉。
        桌面 ≥768px：grid 双列保持原状。
        移动 <768px：单列；sidebar fixed 全屏 80% 抽屉，translateX 切换。 */}
    <style>{`
      @media (max-width: 767px) {
        .admin-shell { grid-template-columns: 1fr !important; }
        .admin-sidebar {
          position: fixed !important;
          inset: 0 auto 0 0 !important;
          width: 280px !important;
          max-width: 86vw !important;
          height: 100vh !important;
          z-index: 80 !important;
          transform: translateX(-100%);
          transition: transform 200ms ease;
          box-shadow: 0 0 24px rgba(0,0,0,0.45);
        }
        .admin-sidebar[data-open="true"] { transform: translateX(0); }
        .admin-mobile-burger { display: inline-flex !important; }
        .admin-backdrop { display: block !important; }
        .admin-topbar { padding-left: 12px !important; padding-right: 12px !important; }
        .admin-content { padding: 16px 12px !important; }
      }
      @media (min-width: 768px) {
        .admin-mobile-burger, .admin-backdrop { display: none !important; }
      }
    `}</style>
    <div className="admin-shell" style={styles.shell}>
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        navGroups={NAV_GROUPS}
        currentPath={location.pathname}
        runners={runners}
        loadPosts={loadPosts}
      />
      <ShortcutsHelp open={helpOpen} onClose={() => setHelpOpen(false)} />
      {mobileNavOpen && (
        <div
          className="admin-backdrop"
          style={styles.backdrop}
          onClick={() => setMobileNavOpen(false)}
          aria-hidden
          data-testid="admin-backdrop"
        />
      )}
      <aside
        className="admin-sidebar"
        style={styles.sidebar}
        data-open={mobileNavOpen ? 'true' : 'false'}
        data-testid="admin-sidebar"
      >
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
              {group.items.map((item) => {
                const count = navCounters[item.to] ?? 0;
                const badge = count > 0 ? count : null;
                return (
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
                    {badge !== null && (
                      <span
                        style={styles.navBadge}
                        data-testid={`nav-badge-${item.to.replace(/\//g, '-')}`}
                        aria-label={`${badge} 待审核`}
                      >{badge}</span>
                    )}
                  </NavLink>
                );
              })}
            </div>
          ))}
        </nav>
      </aside>

      <div className="admin-main" style={styles.main}>
        <header className="admin-topbar" style={styles.topbar}>
          <button
            type="button"
            className="admin-mobile-burger"
            style={styles.burger}
            onClick={() => setMobileNavOpen((v) => !v)}
            aria-label={mobileNavOpen ? '关闭导航' : '打开导航'}
            aria-expanded={mobileNavOpen}
            data-testid="admin-burger"
          >
            {mobileNavOpen ? '×' : '☰'}
          </button>
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
            <span className="admin-user-email" style={styles.userEmail}>{email || '未知账号'}</span>
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
    </UIProvider>
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
  navBadge: {
    // Task 47: actionable counter chip — accent background so it draws
    // attention only when it actually has a number. Subtle padding so
    // single-digit counts don't visually float.
    minWidth: 18,
    height: 18,
    padding: '0 6px',
    borderRadius: 9,
    background: 'var(--accent)',
    color: '#0a0b0d',
    fontSize: 10,
    fontWeight: 600,
    fontVariantNumeric: 'tabular-nums',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
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
  // 移动端 hamburger（桌面隐藏）；图标用 ☰/× 字符避免再引入 SVG。
  burger: {
    display: 'none', // 默认隐藏，<768px 媒体查询里覆盖成 inline-flex
    alignItems: 'center',
    justifyContent: 'center',
    width: 36,
    height: 36,
    background: 'transparent',
    border: '1px solid var(--line-2)',
    color: 'var(--fg)',
    fontSize: 18,
    fontFamily: 'inherit',
    cursor: 'pointer',
    borderRadius: 4,
    marginRight: 12,
  },
  // 抽屉打开时的遮罩 — 桌面始终隐藏。
  backdrop: {
    display: 'none', // 默认隐藏；媒体查询里 mobile 显示
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,0.55)',
    zIndex: 70,
  },
};
