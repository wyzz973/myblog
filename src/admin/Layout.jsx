import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from './AuthContext.jsx';

const NAV = [
  { to: '/admin/dashboard', label: 'Dashboard' },
  { to: '/admin/analytics', label: 'Analytics' },
  { to: '/admin/posts', label: 'Posts' },
  { to: '/admin/media', label: 'Media' },
  { to: '/admin/comments', label: 'Comments' },
  { to: '/admin/tags', label: 'Tags' },
  { to: '/admin/site', label: 'Site' },
  { to: '/admin/profile', label: 'Profile' },
  { to: '/admin/contacts', label: 'Contacts' },
  { to: '/admin/projects', label: 'Projects' },
  { to: '/admin/now', label: 'Now' },
  { to: '/admin/pet', label: 'Pet' },
  { to: '/admin/settings', label: 'Settings' },
];

export default function Layout() {
  const { email, logout } = useAuth();
  const navigate = useNavigate();

  function onLogout() {
    logout();
    navigate('/admin', { replace: true });
  }

  return (
    <div style={styles.shell}>
      <aside style={styles.sidebar}>
        <div style={styles.brand}>
          <span style={styles.brandDot} />
          <div>
            <div style={styles.brandTitle}>myblog</div>
            <div style={styles.brandSub}>admin console</div>
          </div>
        </div>
        <nav style={styles.nav}>
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              style={({ isActive }) => ({
                ...styles.navItem,
                ...(isActive ? styles.navItemActive : null),
              })}
            >
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>

      <div style={styles.main}>
        <header style={styles.topbar}>
          <div style={styles.crumbs}>
            <span style={styles.dim}>~</span>
            <span style={styles.sep}>/</span>
            <span>admin</span>
          </div>
          <div style={styles.userBox}>
            <span style={styles.userEmail}>{email || 'unknown'}</span>
            <button type="button" onClick={onLogout} style={styles.logout}>
              logout
            </button>
          </div>
        </header>

        <main style={styles.content}>
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
  nav: { display: 'flex', flexDirection: 'column', gap: 2 },
  navItem: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '8px 10px',
    fontSize: 12,
    color: 'var(--fg-2)',
    borderRadius: 4,
    textDecoration: 'none',
    border: '1px solid transparent',
  },
  navItemActive: {
    background: 'color-mix(in oklab, var(--accent) 14%, transparent)',
    border: '1px solid color-mix(in oklab, var(--accent) 40%, transparent)',
    color: 'var(--fg)',
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
