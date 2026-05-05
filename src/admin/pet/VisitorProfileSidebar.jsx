import { useState } from 'react';
import { Link } from 'react-router-dom';
import { apiPet } from '../../api/pet.js';

// Sidebar block on the conversation detail page surfacing the
// pet_visitor_profile row for one visitor — owner needs to see what
// the pet remembered before deciding whether to mute / reset / forget.

export default function VisitorProfileSidebar({ profile, visitorHash, onMutated }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [confirmReset, setConfirmReset] = useState(false);

  if (!profile) {
    return (
      <aside style={styles.sidebar} data-testid="visitor-profile-sidebar">
        <div style={styles.head}>
          <span style={styles.headTitle}>访客档案</span>
        </div>
        <div style={styles.empty}>
          [ 这位访客尚未生成档案 — 通常因为对话过短或来自旧版本 ]
        </div>
      </aside>
    );
  }

  async function patch(action) {
    setBusy(true);
    setError(null);
    try {
      const res = await apiPet.patchProfile(visitorHash, action);
      if (res?.ok === false) {
        throw new Error(res.error || '操作失败');
      }
      onMutated?.();
    } catch (err) {
      setError(err?.detail || err?.message || '操作失败');
    } finally {
      setBusy(false);
    }
  }

  const muted = profile.proactive_muted_until && new Date(profile.proactive_muted_until) > new Date();

  return (
    <aside style={styles.sidebar} data-testid="visitor-profile-sidebar">
      <div style={styles.head}>
        <span style={styles.headTitle}>访客档案</span>
      </div>

      <Row k="visitor_hash" v={profile.visitor_hash} mono />
      <Row k="species" v={profile.species} />
      <Row k="locale" v={profile.locale || '—'} />
      <Row k="preferred_language" v={profile.preferred_language || '—'} />
      <Row k="interaction_count" v={profile.interaction_count ?? 0} />
      <Row k="last_seen" v={fmtAgo(profile.last_seen_at)} />
      <Row k="last_interaction" v={fmtAgo(profile.last_interaction_at)} />

      <div style={styles.section}>
        <div style={styles.sectionTitle}>interest_tags</div>
        {profile.interest_tags && profile.interest_tags.length > 0 ? (
          <div style={styles.chips}>
            {profile.interest_tags.map((t) => (
              <span key={t} style={styles.chip}>{t}</span>
            ))}
          </div>
        ) : (
          <div style={styles.muted}>[ 暂无 ]</div>
        )}
      </div>

      <div style={styles.section}>
        <div style={styles.sectionTitle}>recent_post_ids</div>
        {profile.recent_post_ids && profile.recent_post_ids.length > 0 ? (
          <ul style={styles.postList}>
            {profile.recent_post_ids.map((id) => (
              <li key={id}>
                <Link to={`/p/${id}`} style={styles.postLink}>/p/{id}</Link>
              </li>
            ))}
          </ul>
        ) : (
          <div style={styles.muted}>[ 暂无 ]</div>
        )}
      </div>

      {profile.style_summary && (
        <div style={styles.section}>
          <div style={styles.sectionTitle}>style_summary</div>
          <pre style={styles.summary}>{profile.style_summary}</pre>
        </div>
      )}
      {profile.memory_summary && (
        <div style={styles.section}>
          <div style={styles.sectionTitle}>memory_summary</div>
          <pre style={styles.summary}>{profile.memory_summary}</pre>
        </div>
      )}

      <div style={styles.section}>
        <div style={styles.sectionTitle}>proactive_muted_until</div>
        <div style={styles.muteRow}>
          <span style={styles.muteValue}>
            {profile.proactive_muted_until ? new Date(profile.proactive_muted_until).toLocaleString() : '—'}
          </span>
          {muted && (
            <button
              type="button"
              onClick={() => patch('unmute')}
              disabled={busy}
              style={styles.btn}
              data-testid="unmute-btn"
            >
              解除静默
            </button>
          )}
        </div>
      </div>

      <div style={styles.actionRow}>
        {!confirmReset ? (
          <button
            type="button"
            onClick={() => setConfirmReset(true)}
            disabled={busy}
            style={styles.btnDanger}
            data-testid="reset-profile-btn"
          >
            重置档案
          </button>
        ) : (
          <>
            <span style={styles.confirmHint}>
              清空 summaries / 兴趣标签 / 计数？消息保留。
            </span>
            <button
              type="button"
              onClick={async () => {
                await patch('reset');
                setConfirmReset(false);
              }}
              disabled={busy}
              style={styles.btnDangerSolid}
              data-testid="reset-confirm-btn"
            >
              {busy ? '处理中…' : '确定重置'}
            </button>
            <button
              type="button"
              onClick={() => setConfirmReset(false)}
              disabled={busy}
              style={styles.btn}
            >
              取消
            </button>
          </>
        )}
      </div>

      {error && <div style={styles.error}>! {error}</div>}
    </aside>
  );
}

function Row({ k, v, mono = false }) {
  return (
    <div style={styles.row}>
      <span style={styles.rowK}>{k}</span>
      <span style={{ ...styles.rowV, ...(mono ? styles.rowMono : null) }}>{v}</span>
    </div>
  );
}

function fmtAgo(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const ms = Date.now() - d.getTime();
  if (ms < 0) return d.toLocaleString();
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

const styles = {
  sidebar: {
    background: 'var(--bg-2)',
    border: '1px solid var(--line)',
    borderRadius: 6,
    padding: 14,
    fontSize: 11,
    color: 'var(--fg-2)',
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
  },
  head: { paddingBottom: 8, borderBottom: '1px solid var(--line)', marginBottom: 6 },
  headTitle: {
    color: 'var(--fg)', fontSize: 11, letterSpacing: '0.06em',
    textTransform: 'lowercase', fontWeight: 600,
  },
  empty: { color: 'var(--fg-4)', fontStyle: 'italic', padding: '8px 0' },
  row: {
    display: 'grid',
    gridTemplateColumns: '120px 1fr',
    gap: 8,
    padding: '3px 0',
    fontVariantNumeric: 'tabular-nums',
  },
  rowK: { color: 'var(--fg-4)', textTransform: 'lowercase', letterSpacing: '0.06em' },
  rowV: { color: 'var(--fg-2)', overflow: 'hidden', textOverflow: 'ellipsis' },
  rowMono: { color: 'var(--fg)', fontFamily: 'inherit' },
  section: { marginTop: 8 },
  sectionTitle: {
    fontSize: 10,
    color: 'var(--fg-4)',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    marginBottom: 4,
  },
  chips: { display: 'flex', flexWrap: 'wrap', gap: 4 },
  chip: {
    fontSize: 10,
    padding: '2px 7px',
    borderRadius: 999,
    background: 'color-mix(in oklab, var(--accent) 14%, transparent)',
    border: '1px solid color-mix(in oklab, var(--accent) 40%, transparent)',
    color: 'var(--fg)',
  },
  muted: { color: 'var(--fg-4)', fontSize: 10, fontStyle: 'italic' },
  postList: { margin: 0, padding: '0 0 0 16px', color: 'var(--fg-2)' },
  postLink: { color: 'var(--accent)', textDecoration: 'none' },
  summary: {
    margin: 0,
    padding: '6px 8px',
    background: 'var(--bg)',
    border: '1px solid var(--line)',
    borderRadius: 3,
    fontSize: 10,
    color: 'var(--fg-2)',
    fontFamily: 'inherit',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
  },
  muteRow: { display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' },
  muteValue: { color: 'var(--fg-2)', flex: 1 },
  actionRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    paddingTop: 8,
    marginTop: 8,
    borderTop: '1px dashed var(--line)',
    flexWrap: 'wrap',
  },
  confirmHint: { color: 'var(--fg-3)', fontSize: 10, flexBasis: '100%' },
  btn: {
    background: 'transparent',
    border: '1px solid var(--line-2)',
    color: 'var(--fg-2)',
    padding: '4px 10px',
    borderRadius: 3,
    fontFamily: 'inherit',
    fontSize: 10,
    cursor: 'pointer',
  },
  btnDanger: {
    background: 'transparent',
    border: '1px solid color-mix(in oklab, var(--danger) 60%, transparent)',
    color: 'var(--danger)',
    padding: '4px 10px',
    borderRadius: 3,
    fontFamily: 'inherit',
    fontSize: 10,
    cursor: 'pointer',
  },
  btnDangerSolid: {
    background: 'var(--danger)',
    border: 0,
    color: '#0a0b0d',
    padding: '4px 10px',
    borderRadius: 3,
    fontFamily: 'inherit',
    fontSize: 10,
    fontWeight: 600,
    cursor: 'pointer',
  },
  error: {
    marginTop: 8,
    color: 'var(--danger)',
    fontSize: 10,
    border: '1px solid var(--danger)',
    padding: '5px 8px',
    borderRadius: 3,
  },
};
