import { useState } from 'react';
import Integrations from './settings/Integrations.jsx';
import ApiTokens from './settings/ApiTokens.jsx';
import Account from './settings/Account.jsx';
import DangerZone from './settings/DangerZone.jsx';

const TABS = [
  { id: 'integrations', label: '集成配置', Cmp: Integrations },
  { id: 'api-tokens', label: 'API 令牌', Cmp: ApiTokens },
  { id: 'account', label: '账号安全', Cmp: Account },
  { id: 'danger', label: '危险操作', Cmp: DangerZone },
];

export default function Settings() {
  const [tab, setTab] = useState('integrations');
  const Active = (TABS.find((t) => t.id === tab) || TABS[0]).Cmp;
  return (
    <div>
      <header style={styles.header}>
        <h1 style={styles.h1}>系统设置</h1>
        <p style={styles.lead}>管理第三方集成、访问令牌、账号安全和高风险操作。</p>
      </header>

      <div style={styles.tabStrip} role="tablist">
        {TABS.map((t) => {
          const active = t.id === tab;
          const danger = t.id === 'danger';
          return (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => setTab(t.id)}
              style={{
                ...styles.tab,
                ...(active ? styles.tabActive : null),
                ...(danger ? styles.tabDanger : null),
                ...(active && danger ? styles.tabDangerActive : null),
              }}
            >
              {t.label}
            </button>
          );
        })}
      </div>

      <div style={styles.body}>
        <Active />
      </div>
    </div>
  );
}

const styles = {
  header: { marginBottom: 18 },
  h1: { fontSize: 20, margin: 0, fontWeight: 600, color: 'var(--fg)' },
  lead: { fontSize: 12, color: 'var(--fg-3)', margin: '4px 0 0' },
  tabStrip: {
    display: 'flex',
    gap: 2,
    borderBottom: '1px solid var(--line)',
    marginBottom: 16,
    flexWrap: 'wrap',
  },
  tab: {
    background: 'transparent',
    border: '1px solid transparent',
    borderBottom: 'none',
    color: 'var(--fg-3)',
    padding: '8px 14px',
    fontFamily: 'inherit',
    fontSize: 12,
    cursor: 'pointer',
    borderTopLeftRadius: 4,
    borderTopRightRadius: 4,
    letterSpacing: '0.04em',
    marginBottom: -1,
  },
  tabActive: {
    background: 'var(--bg-2)',
    border: '1px solid var(--line)',
    borderBottom: '1px solid var(--bg-2)',
    color: 'var(--fg)',
  },
  tabDanger: { color: 'var(--danger)' },
  tabDangerActive: {
    color: 'var(--danger)',
    border: '1px solid var(--danger)',
    borderBottom: '1px solid var(--bg-2)',
  },
  body: {},
};
