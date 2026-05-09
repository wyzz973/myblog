// Site identity — the merged workflow that owns every public-facing
// identity field on the home + reader pages. Replaces the old split
// between /admin/profile and /admin/site (PRD §5.2 04 · 首页与品牌).
//
// Backend keeps two endpoints (PUT /profile + PUT /site) — both write to
// the same site_meta singleton. This page presents one form and saves
// only the changed fields per endpoint, so a partial failure on one
// surface doesn't lose work on the other.

import { useEffect, useMemo, useState } from 'react';
import { apiProfile } from '../api/profile.js';
import { apiSite } from '../api/site.js';
import { mediaUrl } from '../api/media.js';

const PROFILE_TEXT_FIELDS = [
  { key: 'name', label: '昵称', placeholder: '汪洋' },
  { key: 'name_en', label: '英文名', placeholder: 'Wang Yang' },
  { key: 'role', label: '身份', placeholder: 'software engineer' },
  { key: 'location', label: '地点', placeholder: 'Beijing, CN' },
  { key: 'pronouns', label: '人称', placeholder: 'they/them' },
  { key: 'typing_line', label: '终端动效文案', placeholder: 'building things…' },
];

const SITE_TEXT_FIELDS = [
  { key: 'handle', label: '账号 handle', placeholder: 'wangyang' },
  { key: 'tagline', label: '一句话简介', placeholder: 'a short one-liner' },
  { key: 'email', label: '联系邮箱', placeholder: 'you@example.com' },
  { key: 'github', label: 'github 用户名', placeholder: 'username' },
  { key: 'footer_note', label: 'footer 文案', placeholder: '' },
  { key: 'icp_beian', label: 'ICP 备案号', placeholder: '蜀ICP备XXXXXXXXX号-1' },
  { key: 'launched_at', label: '上线日期', placeholder: '2026-01-01' },
];

const THEME_OPTIONS = [
  { value: 'dark', label: 'dark' },
  { value: 'light', label: 'light' },
];

function norm(v) {
  if (v == null) return '';
  return String(v);
}

function chipsKey(arr) {
  if (!Array.isArray(arr)) return '';
  return arr.join('\x1f');
}

export default function SiteIdentity() {
  const [profile, setProfile] = useState(null);
  const [site, setSite] = useState(null);
  const [pDraft, setPDraft] = useState(null);
  const [sDraft, setSDraft] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState(null);
  const [pickerOpen, setPickerOpen] = useState(false);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    Promise.all([apiProfile.get(), apiSite.getSite()])
      .then(([p, s]) => {
        if (!mounted) return;
        setProfile(p);
        setSite(s);
        setPDraft({ ...p, stack_chips: Array.isArray(p?.stack_chips) ? p.stack_chips : [] });
        setSDraft({ ...s });
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
    const id = setTimeout(() => setToast(null), 3000);
    return () => clearTimeout(id);
  }, [toast]);

  const profilePatch = useMemo(() => {
    if (!profile || !pDraft) return null;
    const patch = {};
    for (const f of PROFILE_TEXT_FIELDS) {
      if (norm(profile[f.key]) !== norm(pDraft[f.key])) {
        patch[f.key] = pDraft[f.key] === '' ? null : pDraft[f.key];
      }
    }
    if (norm(profile.bio) !== norm(pDraft.bio)) patch.bio = pDraft.bio || '';
    if ((profile.avatar_id ?? null) !== (pDraft.avatar_id ?? null)) {
      patch.avatar_id = pDraft.avatar_id ?? null;
    }
    if (chipsKey(profile.stack_chips) !== chipsKey(pDraft.stack_chips)) {
      patch.stack_chips = pDraft.stack_chips || [];
    }
    return patch;
  }, [profile, pDraft]);

  const sitePatch = useMemo(() => {
    if (!site || !sDraft) return null;
    const patch = {};
    for (const f of SITE_TEXT_FIELDS) {
      if (norm(site[f.key]) !== norm(sDraft[f.key])) {
        patch[f.key] = sDraft[f.key] === '' ? null : sDraft[f.key];
      }
    }
    if (norm(site.default_theme) !== norm(sDraft.default_theme)) {
      patch.default_theme = sDraft.default_theme;
    }
    return patch;
  }, [site, sDraft]);

  const dirty = useMemo(() => {
    return (
      (profilePatch && Object.keys(profilePatch).length > 0) ||
      (sitePatch && Object.keys(sitePatch).length > 0)
    );
  }, [profilePatch, sitePatch]);

  function setProfileField(k, v) {
    setPDraft((d) => ({ ...d, [k]: v }));
  }
  function setSiteField(k, v) {
    setSDraft((d) => ({ ...d, [k]: v }));
  }

  function reset() {
    if (profile) {
      setPDraft({
        ...profile,
        stack_chips: Array.isArray(profile.stack_chips) ? profile.stack_chips : [],
      });
    }
    if (site) setSDraft({ ...site });
  }

  async function save(e) {
    e?.preventDefault?.();
    if (!dirty) return;
    setSaving(true);
    const failures = [];
    try {
      // Save in parallel — order doesn't matter; partial success is
      // surfaced explicitly so the owner knows which surface needs retry.
      const tasks = [];
      const profileChanges = Object.keys(profilePatch || {}).length > 0;
      const siteChanges = Object.keys(sitePatch || {}).length > 0;
      if (profileChanges) {
        tasks.push(
          apiProfile.put(profilePatch).then((updated) => {
            setProfile(updated);
            setPDraft({
              ...updated,
              stack_chips: Array.isArray(updated?.stack_chips) ? updated.stack_chips : [],
            });
          }).catch((err) => failures.push(['profile', err])),
        );
      }
      if (siteChanges) {
        tasks.push(
          apiSite.putSite(sitePatch).then((updated) => {
            setSite(updated);
            setSDraft({ ...updated });
          }).catch((err) => failures.push(['site', err])),
        );
      }
      await Promise.all(tasks);
      if (failures.length === 0) {
        setToast('已保存');
      } else {
        const summary = failures.map(([sec, err]) => `${sec}: ${err?.detail || err.message}`).join(' · ');
        setToast(`部分保存失败 — ${summary}`);
      }
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div style={styles.muted}>加载站点身份中…</div>;
  if (error) return <div style={styles.error}>错误：{error}</div>;
  if (!pDraft || !sDraft) return <div style={styles.muted}>暂无数据</div>;

  return (
    <div data-testid="site-identity">
      <header style={styles.header}>
        <h1 style={styles.h1}>
          <span style={styles.headN}>04</span>{' '}
          <span style={styles.headSlash}>/</span> 站点身份
        </h1>
        <p style={styles.lead}>
          首页、Reader、TopBar、footer 的对外身份在这里集中维护。一次保存会同时
          写入 <code>PUT /profile</code> 和 <code>PUT /site</code>。
        </p>
      </header>

      <form onSubmit={save}>
        <Panel title="标识" hint="basic identity">
          <div style={styles.avatarRow}>
            <AvatarPreview path={pDraft.avatar_path} />
            <div style={styles.avatarActions}>
              <button type="button" style={styles.btn} onClick={() => setPickerOpen(true)}>
                从媒体库选择…
              </button>
              {pDraft.avatar_id != null && (
                <button
                  type="button"
                  style={styles.btnGhostDanger}
                  onClick={() => setPDraft((d) => ({ ...d, avatar_id: null, avatar_path: null }))}
                >
                  移除头像
                </button>
              )}
              <div style={styles.avatarPath}>
                {pDraft.avatar_path || <span style={styles.dim}>未设置头像</span>}
              </div>
            </div>
          </div>

          <div style={styles.grid}>
            {PROFILE_TEXT_FIELDS.map((f) => (
              <Field
                key={f.key}
                f={f}
                value={pDraft[f.key]}
                onChange={(v) => setProfileField(f.key, v)}
                testid={`p-${f.key}`}
              />
            ))}
          </div>
        </Panel>

        <Panel title="文案" hint="bio">
          <label style={styles.labelFull}>
            <span style={styles.labelText}>个人简介</span>
            <textarea
              rows={5}
              value={pDraft.bio ?? ''}
              onChange={(e) => setProfileField('bio', e.target.value)}
              style={styles.textarea}
              placeholder="一段描述你自己的话。"
              data-testid="p-bio"
            />
          </label>
          <StackChipsEditor
            value={pDraft.stack_chips || []}
            onChange={(next) => setProfileField('stack_chips', next)}
          />
        </Panel>

        <Panel title="站点" hint="public site">
          <div style={styles.grid}>
            {SITE_TEXT_FIELDS.map((f) => (
              <Field
                key={f.key}
                f={f}
                value={sDraft[f.key]}
                onChange={(v) => setSiteField(f.key, v)}
                testid={`s-${f.key}`}
              />
            ))}
            <label style={styles.label}>
              <span style={styles.labelText}>默认主题</span>
              <select
                value={sDraft.default_theme || 'dark'}
                onChange={(e) => setSiteField('default_theme', e.target.value)}
                style={styles.input}
                data-testid="s-default_theme"
              >
                {THEME_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </label>
          </div>
        </Panel>

        <div style={styles.actionRow}>
          <button
            type="submit"
            style={styles.btnPrimary}
            disabled={saving || !dirty}
            data-testid="save-btn"
          >
            {saving ? '保存中…' : '保存'}
          </button>
          <button
            type="button"
            style={styles.btn}
            onClick={reset}
            disabled={saving || !dirty}
          >
            重置
          </button>
          <span style={styles.dirtyHint}>
            {dirty ? '有未保存的更改' : '已与后端一致'}
          </span>
        </div>
      </form>

      {pickerOpen && (
        <AvatarPicker
          current={pDraft.avatar_id}
          onClose={() => setPickerOpen(false)}
          onPick={(item) => {
            setPDraft((d) => ({ ...d, avatar_id: item.id, avatar_path: item.url }));
            setPickerOpen(false);
          }}
        />
      )}

      {toast && <div style={styles.toast}>{toast}</div>}
    </div>
  );
}

function Panel({ title, hint, children }) {
  return (
    <section style={styles.panel}>
      <div style={styles.panelHead}>
        <span style={styles.panelTitle}>{title}</span>
        {hint && <span style={styles.panelHint}>{hint}</span>}
      </div>
      <div style={styles.panelBody}>{children}</div>
    </section>
  );
}

function Field({ f, value, onChange, testid }) {
  return (
    <label style={styles.label}>
      <span style={styles.labelText}>{f.label}</span>
      <input
        type="text"
        value={value ?? ''}
        placeholder={f.placeholder}
        onChange={(e) => onChange(e.target.value)}
        style={styles.input}
        data-testid={testid}
      />
    </label>
  );
}

function AvatarPreview({ path }) {
  if (!path) {
    return <div style={styles.avatarBox}><span style={styles.dim}>未设置头像</span></div>;
  }
  const url = /^https?:\/\//i.test(path) ? path : mediaUrl(path);
  return (
    <div style={styles.avatarBox}>
      <img src={url} alt="avatar preview" style={styles.avatarImg} />
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
      <span style={styles.labelText}>stack chips</span>
      <div style={styles.chipsWrap} data-testid="stack-chips">
        {value.map((chip, i) => (
          <span key={`${chip}-${i}`} style={styles.chip}>
            {chip}
            <button type="button" onClick={() => remove(i)} style={styles.chipX}>×</button>
          </span>
        ))}
        {value.length === 0 && <span style={styles.dim}>暂无 chip</span>}
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
        <button type="button" onClick={add} style={styles.btn}>添加</button>
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
    return () => { mounted = false; };
  }, []);

  return (
    <div style={styles.modalShell} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div style={styles.modalHead}>
          <span style={styles.modalTitle}>选择头像</span>
          <button type="button" onClick={onClose} style={styles.iconBtn}>关闭 ✕</button>
        </div>
        <div style={styles.modalBody}>
          {items === null && !error && <div style={styles.muted}>加载图片中…</div>}
          {error && <div style={styles.error}>错误：{error}</div>}
          {items && items.length === 0 && (
            <div style={styles.muted}>媒体库还没有图片 — 请先在「媒体」上传。</div>
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
                    style={{ ...styles.pickerTile, ...(active ? styles.pickerTileActive : null) }}
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
          <button type="button" style={styles.btn} onClick={onClose}>取消</button>
        </div>
      </div>
    </div>
  );
}

const styles = {
  header: { marginBottom: 18 },
  h1: { fontSize: 20, margin: 0, fontWeight: 600, color: 'var(--fg)' },
  headN: { color: 'var(--accent)', fontSize: 14, letterSpacing: '0.06em' },
  headSlash: { color: 'var(--fg-4)' },
  lead: { fontSize: 12, color: 'var(--fg-3)', margin: '4px 0 0' },
  panel: {
    background: 'var(--bg-2)',
    border: '1px solid var(--line)',
    borderRadius: 6,
    marginBottom: 14,
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
  panelBody: { padding: 16, display: 'flex', flexDirection: 'column', gap: 14 },
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
  avatarRow: { display: 'flex', gap: 14, alignItems: 'center', flexWrap: 'wrap' },
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
  avatarActions: { display: 'flex', flexDirection: 'column', gap: 6, minWidth: 0, flex: 1 },
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
  dim: { color: 'var(--fg-4)', fontSize: 11 },
  actionRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '14px 0',
  },
  dirtyHint: { color: 'var(--fg-4)', fontSize: 11 },
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
    borderColor: 'var(--accent)',
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
