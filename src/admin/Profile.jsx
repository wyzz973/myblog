import { useEffect, useMemo, useState } from 'react';
import { apiProfile } from '../api/profile.js';
import { mediaUrl } from '../api/media.js';

// Field set per backend `ProfileIn` (routers/admin/site.py). The admin
// /profile endpoint manages the *author* identity (display name, bio,
// avatar). It is distinct from /session (the admin account info).
const TEXT_FIELDS = [
  { key: 'name', label: '姓名', placeholder: '汪洋' },
  { key: 'name_en', label: '英文名', placeholder: 'Wang Yang' },
  { key: 'role', label: '角色', placeholder: 'software engineer' },
  { key: 'location', label: '所在地', placeholder: 'Beijing, CN' },
  { key: 'pronouns', label: '称谓', placeholder: 'they/them' },
  { key: 'typing_line', label: '打字机文案', placeholder: 'building things...' },
];

export default function Profile() {
  const [profile, setProfile] = useState(null);
  const [draft, setDraft] = useState(null);
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState(null);
  const [pickerOpen, setPickerOpen] = useState(false);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    Promise.all([
      apiProfile.get(),
      apiProfile.session().catch(() => null),
    ])
      .then(([p, sess]) => {
        if (!mounted) return;
        setProfile(p);
        setDraft({
          ...p,
          stack_chips: Array.isArray(p?.stack_chips) ? p.stack_chips : [],
        });
        setSession(sess);
        setError(null);
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err?.detail || err?.message || '加载失败');
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!toast) return undefined;
    const id = setTimeout(() => setToast(null), 2500);
    return () => clearTimeout(id);
  }, [toast]);

  const dirty = useMemo(() => {
    if (!profile || !draft) return false;
    for (const f of TEXT_FIELDS) {
      if (norm(profile[f.key]) !== norm(draft[f.key])) return true;
    }
    if (norm(profile.bio) !== norm(draft.bio)) return true;
    if ((profile.avatar_id ?? null) !== (draft.avatar_id ?? null)) return true;
    if (chipsKey(profile.stack_chips) !== chipsKey(draft.stack_chips)) return true;
    return false;
  }, [profile, draft]);

  function setField(k, v) {
    setDraft((d) => ({ ...d, [k]: v }));
  }

  function reset() {
    setDraft({
      ...profile,
      stack_chips: Array.isArray(profile?.stack_chips) ? profile.stack_chips : [],
    });
  }

  async function save(e) {
    e?.preventDefault?.();
    if (!draft) return;
    setSaving(true);
    try {
      const patch = {};
      for (const f of TEXT_FIELDS) {
        if (norm(profile[f.key]) !== norm(draft[f.key])) {
          patch[f.key] = draft[f.key] === '' ? null : draft[f.key];
        }
      }
      if (norm(profile.bio) !== norm(draft.bio)) {
        patch.bio = draft.bio || '';
      }
      if ((profile.avatar_id ?? null) !== (draft.avatar_id ?? null)) {
        patch.avatar_id = draft.avatar_id ?? null;
      }
      if (chipsKey(profile.stack_chips) !== chipsKey(draft.stack_chips)) {
        patch.stack_chips = draft.stack_chips || [];
      }
      const updated = await apiProfile.put(patch);
      setProfile(updated);
      setDraft({
        ...updated,
        stack_chips: Array.isArray(updated?.stack_chips) ? updated.stack_chips : [],
      });
      setToast('已保存');
    } catch (err) {
      setToast(`错误：${err?.detail || err.message}`);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div style={styles.muted}>正在加载作者资料...</div>;
  if (error) return <div style={styles.error}>错误：{error}</div>;
  if (!draft) return <div style={styles.muted}>暂无数据</div>;

  return (
    <div>
      <header style={styles.header}>
        <h1 style={styles.h1}>作者资料</h1>
        <p style={styles.lead}>
          管理读者可见的公开作者身份。账号邮箱和安全设置请在“系统设置”中维护。
        </p>
      </header>

      <form onSubmit={save} style={styles.panel}>
        <div style={styles.panelHead}>
          <span style={styles.panelTitle}>作者资料</span>
          <span style={styles.panelHint}>PUT /profile</span>
        </div>
        <div style={styles.panelBody}>
          <div style={styles.avatarRow}>
            <AvatarPreview path={draft.avatar_path} />
            <div style={styles.avatarActions}>
              <button
                type="button"
                style={styles.btn}
                onClick={() => setPickerOpen(true)}
              >
                从媒体库选择...
              </button>
              {draft.avatar_id != null && (
                <button
                  type="button"
                  style={styles.btnGhostDanger}
                  onClick={() => setDraft((d) => ({ ...d, avatar_id: null, avatar_path: null }))}
                >
                  移除头像
                </button>
              )}
              <div style={styles.avatarPath}>
                {draft.avatar_path || <span style={styles.dim}>未设置头像</span>}
              </div>
            </div>
          </div>

          <div style={styles.grid}>
            {TEXT_FIELDS.map((f) => (
              <label key={f.key} style={styles.label}>
                <span style={styles.labelText}>{f.label}</span>
                <input
                  type="text"
                  value={draft[f.key] ?? ''}
                  placeholder={f.placeholder}
                  onChange={(e) => setField(f.key, e.target.value)}
                  style={styles.input}
                />
              </label>
            ))}
          </div>

          <label style={styles.labelFull}>
            <span style={styles.labelText}>简介</span>
            <textarea
              rows={5}
              value={draft.bio ?? ''}
              onChange={(e) => setField('bio', e.target.value)}
              style={styles.textarea}
              placeholder="用一小段文字介绍自己。"
            />
          </label>

          <StackChipsEditor
            value={draft.stack_chips || []}
            onChange={(next) => setField('stack_chips', next)}
          />
        </div>
        <div style={styles.panelFoot}>
          <button
            type="submit"
            style={styles.btnPrimary}
            disabled={saving || !dirty}
          >
            {saving ? '保存中...' : '保存'}
          </button>
          <button
            type="button"
            style={styles.btn}
            onClick={reset}
            disabled={saving || !dirty}
          >
            重置
          </button>
        </div>
      </form>

      <section style={styles.panel}>
        <div style={styles.panelHead}>
          <span style={styles.panelTitle}>账号</span>
          <span style={styles.panelHint}>GET /session · read-only</span>
        </div>
        <div style={styles.panelBody}>
          <Row label="邮箱" value={session?.email ?? '—'} />
          <Row
            label="两步验证"
            value={
              session
                ? session.tfa_enabled
                  ? '已启用'
                  : '未启用'
                : '—'
            }
          />
          <p style={styles.note}>
            账号邮箱和密码变更请在“系统设置”中管理。
          </p>
        </div>
      </section>

      {pickerOpen && (
        <AvatarPicker
          current={draft.avatar_id}
          onClose={() => setPickerOpen(false)}
          onPick={(item) => {
            setDraft((d) => ({ ...d, avatar_id: item.id, avatar_path: item.url }));
            setPickerOpen(false);
          }}
        />
      )}

      {toast && <div style={styles.toast}>{toast}</div>}
    </div>
  );
}

function AvatarPreview({ path }) {
  if (!path) {
    return <div style={styles.avatarBox}><span style={styles.dim}>未设置头像</span></div>;
  }
  const url = /^https?:\/\//i.test(path) ? path : mediaUrl(path);
  return (
    <div style={styles.avatarBox}>
      <img src={url} alt="头像预览" style={styles.avatarImg} />
    </div>
  );
}

function StackChipsEditor({ value, onChange }) {
  const [draft, setDraft] = useState('');

  function add() {
    const v = draft.trim();
    if (!v) return;
    if (value.includes(v)) {
      setDraft('');
      return;
    }
    onChange([...value, v]);
    setDraft('');
  }

  function remove(i) {
    onChange(value.filter((_, j) => j !== i));
  }

  return (
    <div style={styles.labelFull}>
      <span style={styles.labelText}>技术标签</span>
      <div style={styles.chipsWrap}>
        {value.map((chip, i) => (
          <span key={`${chip}-${i}`} style={styles.chip}>
            {chip}
            <button
              type="button"
              onClick={() => remove(i)}
              style={styles.chipX}
              aria-label={`移除 ${chip}`}
            >
              ×
            </button>
          </span>
        ))}
        {value.length === 0 && (
          <span style={styles.dim}>暂无标签</span>
        )}
      </div>
      <div style={styles.chipAddRow}>
        <input
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              add();
            }
          }}
          placeholder="例如 typescript"
          style={{ ...styles.input, flex: 1 }}
        />
        <button type="button" onClick={add} style={styles.btn}>
          添加标签
        </button>
      </div>
    </div>
  );
}

function AvatarPicker({ current, onClose, onPick }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    apiProfile
      .listImages()
      .then((list) => {
        if (!mounted) return;
        const images = (list || []).filter(
          (m) => typeof m.mime_type === 'string' && m.mime_type.startsWith('image/'),
        );
        setItems(images);
      })
      .catch((err) => mounted && setError(err?.detail || err?.message || '加载失败'));
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <div style={styles.modalShell} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div style={styles.modalHead}>
          <span style={styles.modalTitle}>选择头像</span>
          <button type="button" onClick={onClose} style={styles.iconBtn}>
            关闭 ✕
          </button>
        </div>
        <div style={styles.modalBody}>
          {items === null && !error && (
            <div style={styles.muted}>正在加载图片...</div>
          )}
          {error && <div style={styles.error}>错误：{error}</div>}
          {items && items.length === 0 && (
            <div style={styles.muted}>
              媒体库还没有图片，请先到“媒体库”上传一张。
            </div>
          )}
          {items && items.length > 0 && (
            <div style={styles.pickerGrid}>
              {items.map((m) => {
                const active = m.id === current;
                return (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => onPick(m)}
                    style={{
                      ...styles.pickerTile,
                      ...(active ? styles.pickerTileActive : null),
                    }}
                    title={m.filename}
                  >
                    <img src={mediaUrl(m)} alt={m.alt || m.filename} style={styles.pickerImg} />
                  </button>
                );
              })}
            </div>
          )}
        </div>
        <div style={styles.modalFoot}>
          <span style={{ flex: 1 }} />
          <button type="button" style={styles.btn} onClick={onClose}>
            取消
          </button>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div style={styles.factRow}>
      <span style={styles.factK}>{label}</span>
      <span style={styles.factV}>{value}</span>
    </div>
  );
}

function norm(v) {
  if (v == null) return '';
  return String(v);
}

function chipsKey(arr) {
  if (!Array.isArray(arr)) return '';
  return arr.join('');
}

const styles = {
  header: { marginBottom: 18 },
  h1: { fontSize: 20, margin: 0, fontWeight: 600, color: 'var(--fg)' },
  lead: { fontSize: 12, color: 'var(--fg-3)', margin: '4px 0 0' },
  panel: {
    background: 'var(--bg-2)',
    border: '1px solid var(--line)',
    borderRadius: 6,
    marginBottom: 16,
  },
  panelHead: {
    padding: '10px 14px',
    borderBottom: '1px solid var(--line)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  panelTitle: {
    fontSize: 11,
    color: 'var(--fg-2)',
    textTransform: 'lowercase',
    letterSpacing: '0.06em',
  },
  panelHint: { fontSize: 10, color: 'var(--fg-4)' },
  panelBody: {
    padding: 16,
    display: 'flex',
    flexDirection: 'column',
    gap: 14,
  },
  panelFoot: {
    padding: '10px 14px',
    borderTop: '1px solid var(--line)',
    display: 'flex',
    gap: 8,
    alignItems: 'center',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
    gap: 12,
  },
  label: { display: 'flex', flexDirection: 'column', gap: 6 },
  labelFull: { display: 'flex', flexDirection: 'column', gap: 6 },
  labelText: {
    fontSize: 11,
    color: 'var(--fg-3)',
    textTransform: 'lowercase',
    letterSpacing: '0.06em',
  },
  input: {
    background: 'var(--bg)',
    border: '1px solid var(--line-2)',
    color: 'var(--fg)',
    padding: '9px 11px',
    fontFamily: 'inherit',
    fontSize: 12,
    borderRadius: 4,
    outline: 'none',
  },
  textarea: {
    background: 'var(--bg)',
    border: '1px solid var(--line-2)',
    color: 'var(--fg)',
    padding: '10px 12px',
    fontFamily: 'inherit',
    fontSize: 12,
    borderRadius: 4,
    outline: 'none',
    resize: 'vertical',
  },
  avatarRow: {
    display: 'flex',
    gap: 14,
    alignItems: 'center',
    flexWrap: 'wrap',
  },
  avatarBox: {
    width: 96,
    height: 96,
    border: '1px solid var(--line)',
    borderRadius: 6,
    background: 'var(--bg)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
    flexShrink: 0,
  },
  avatarImg: { width: '100%', height: '100%', objectFit: 'cover' },
  avatarActions: {
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
    minWidth: 0,
    flex: 1,
  },
  avatarPath: {
    fontSize: 11,
    color: 'var(--fg-3)',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  chipsWrap: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 6,
    minHeight: 32,
    padding: '6px 8px',
    border: '1px dashed var(--line-2)',
    borderRadius: 4,
    alignItems: 'center',
  },
  chip: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
    padding: '3px 8px',
    background: 'color-mix(in oklab, var(--accent) 14%, transparent)',
    border: '1px solid color-mix(in oklab, var(--accent) 40%, transparent)',
    borderRadius: 999,
    fontSize: 11,
    color: 'var(--fg)',
  },
  chipX: {
    background: 'transparent',
    border: 0,
    color: 'var(--fg-3)',
    cursor: 'pointer',
    fontFamily: 'inherit',
    fontSize: 12,
    padding: 0,
    lineHeight: 1,
  },
  chipAddRow: { display: 'flex', gap: 8 },
  factRow: {
    display: 'grid',
    gridTemplateColumns: '120px 1fr',
    fontSize: 12,
    color: 'var(--fg-2)',
    padding: '4px 0',
  },
  factK: {
    color: 'var(--fg-4)',
    textTransform: 'lowercase',
    letterSpacing: '0.06em',
    fontSize: 11,
  },
  factV: { color: 'var(--fg-2)' },
  note: {
    fontSize: 11,
    color: 'var(--fg-4)',
    margin: '8px 0 0',
  },
  dim: { color: 'var(--fg-4)', fontSize: 11 },
  btn: {
    background: 'var(--bg)',
    border: '1px solid var(--line-2)',
    color: 'var(--fg)',
    padding: '8px 12px',
    borderRadius: 4,
    fontFamily: 'inherit',
    fontSize: 12,
    cursor: 'pointer',
  },
  btnGhostDanger: {
    background: 'transparent',
    border: '1px solid var(--line-2)',
    color: 'var(--danger)',
    padding: '8px 12px',
    borderRadius: 4,
    fontFamily: 'inherit',
    fontSize: 12,
    cursor: 'pointer',
  },
  btnPrimary: {
    background: 'var(--accent)',
    color: '#0a0b0d',
    border: 0,
    padding: '8px 14px',
    borderRadius: 4,
    fontFamily: 'inherit',
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
  },
  iconBtn: {
    background: 'transparent',
    border: '1px solid var(--line-2)',
    color: 'var(--fg-3)',
    padding: '4px 10px',
    borderRadius: 4,
    fontFamily: 'inherit',
    fontSize: 11,
    cursor: 'pointer',
  },
  modalShell: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,0.6)',
    backdropFilter: 'blur(4px)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
    zIndex: 50,
  },
  modal: {
    background: 'var(--bg-2)',
    border: '1px solid var(--line)',
    borderRadius: 8,
    width: '100%',
    maxWidth: 720,
    maxHeight: '85vh',
    display: 'flex',
    flexDirection: 'column',
    fontFamily: "'JetBrains Mono', ui-monospace, Menlo, monospace",
  },
  modalHead: {
    padding: '12px 16px',
    borderBottom: '1px solid var(--line)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  modalTitle: { fontSize: 13, color: 'var(--fg)' },
  modalBody: {
    padding: 16,
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
    overflow: 'auto',
  },
  modalFoot: {
    padding: '12px 16px',
    borderTop: '1px solid var(--line)',
    display: 'flex',
    gap: 8,
    alignItems: 'center',
  },
  pickerGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))',
    gap: 10,
  },
  pickerTile: {
    background: 'var(--bg)',
    border: '1px solid var(--line)',
    borderRadius: 6,
    padding: 0,
    overflow: 'hidden',
    cursor: 'pointer',
    aspectRatio: '1 / 1',
  },
  pickerTileActive: {
    border: '1px solid var(--accent)',
    boxShadow: '0 0 0 1px var(--accent) inset',
  },
  pickerImg: { width: '100%', height: '100%', objectFit: 'cover' },
  toast: {
    position: 'fixed',
    bottom: 20,
    right: 20,
    background: 'var(--bg-2)',
    border: '1px solid var(--accent)',
    color: 'var(--fg)',
    padding: '10px 14px',
    borderRadius: 4,
    fontSize: 12,
    boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
    zIndex: 60,
  },
  muted: { color: 'var(--fg-3)', fontSize: 12, padding: '24px 0' },
  error: {
    color: 'var(--danger)',
    fontSize: 12,
    border: '1px solid var(--danger)',
    padding: '10px 12px',
    borderRadius: 4,
  },
};
