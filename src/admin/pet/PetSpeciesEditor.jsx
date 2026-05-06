// Owner-facing editor for the pet species catalogue (Task 21d).
//
// Stays consistent with the rest of the pet tabs: rarity-grouped <details>
// sections, terse inline forms, no SaaS-template chrome. Frame editing is
// intentionally not wired up here — frames are a 3-frame ASCII spec with
// strict layout rules that deserve a dedicated frame composer; for now we
// surface a "N frames" badge and let owner edit frames via the API. Adding
// the composer is a follow-up task (likely 21f).
//
// Why per-row save instead of bulk-save like the other Pet tabs: the
// catalogue is N rows owned independently. A single Save would lose the
// "edit one row, ignore others" affordance and surface 409 conflicts in
// confusing ways.

import { useEffect, useState } from 'react';
import { apiPetSpecies } from '../../api/petSpecies.js';
import { useConfirm } from '../ui/UIProvider.jsx';

const RARITY_ORDER = ['common', 'uncommon', 'rare', 'epic', 'legendary'];
const RARITY_COLOR = {
  common: '#9aa6b3',
  uncommon: '#7dbf8e',
  rare: '#5c9ddc',
  epic: '#b89cf0',
  legendary: '#f5b44c',
};

function groupByRarity(rows) {
  const out = {};
  for (const r of RARITY_ORDER) out[r] = [];
  for (const row of rows) {
    if (out[row.rarity]) out[row.rarity].push(row);
    else (out[row.rarity] = [row]);
  }
  return out;
}

function emptyDraft() {
  return {
    id: '',
    name: '',
    rarity: 'common',
    color: '#888',
    trait_zh: '',
    personality_zh: '',
    description_zh: '',
    frames: [],
    behavior: { proactiveLevel: 3, idleFrequency: 'normal', localLines: [] },
    stats: {},
    visible: true,
    sort_order: 999,
  };
}

export default function PetSpeciesEditor() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);
  const [savingId, setSavingId] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [drafts, setDrafts] = useState({});       // id -> partial overrides
  const [newDraft, setNewDraft] = useState(null); // null when add-form closed
  const [framesOpenId, setFramesOpenId] = useState(null); // id of expanded frames panel
  const confirm = useConfirm();

  useEffect(() => {
    let mounted = true;
    apiPetSpecies.list()
      .then((res) => mounted && (setRows(res), setError(null)))
      .catch((e) => mounted && setError(e?.detail || e?.message || 'load failed'));
    return () => { mounted = false; };
  }, []);

  function rowDraft(id) {
    const base = rows.find((r) => r.id === id);
    return { ...base, ...(drafts[id] || {}) };
  }

  function setDraftField(id, key, value) {
    setDrafts((prev) => ({ ...prev, [id]: { ...(prev[id] || {}), [key]: value } }));
  }

  // Task 21f: replace one frame's lines (a list of strings) inside the
  // draft. Frames is the only field where users edit a nested array, so
  // it gets a dedicated helper instead of going through setDraftField.
  function setDraftFrame(id, frameIndex, frameLines) {
    setDrafts((prev) => {
      const base = (prev[id] && prev[id].frames) ?? rows.find((r) => r.id === id)?.frames ?? [];
      const next = [...base];
      next[frameIndex] = frameLines;
      return { ...prev, [id]: { ...(prev[id] || {}), frames: next } };
    });
  }

  const dirty = (id) => Boolean(drafts[id] && Object.keys(drafts[id]).length);

  async function saveRow(id) {
    if (!dirty(id)) return;
    setSavingId(id);
    setError(null);
    try {
      const updated = await apiPetSpecies.patch(id, drafts[id]);
      setRows((prev) => prev.map((r) => (r.id === id ? updated : r)));
      setDrafts((prev) => {
        const { [id]: _, ...rest } = prev;
        return rest;
      });
    } catch (e) {
      setError(`${id}: ${e?.detail || e?.message || 'save failed'}`);
    } finally {
      setSavingId(null);
    }
  }

  async function removeRow(id) {
    const ok = await confirm({
      title: '删除物种',
      message: `确定删除物种「${id}」吗？此操作不可撤销。`,
      confirmLabel: '删除',
      destructive: true,
    });
    if (!ok) return;
    setDeletingId(id);
    setError(null);
    try {
      await apiPetSpecies.delete(id);
      setRows((prev) => prev.filter((r) => r.id !== id));
      setDrafts((prev) => {
        const { [id]: _, ...rest } = prev;
        return rest;
      });
    } catch (e) {
      setError(`${id}: ${e?.detail || e?.message || 'delete failed'}`);
    } finally {
      setDeletingId(null);
    }
  }

  async function createNew() {
    if (!newDraft) return;
    setSavingId('__new__');
    setError(null);
    try {
      const created = await apiPetSpecies.create(newDraft);
      setRows((prev) => [...prev, created]);
      setNewDraft(null);
    } catch (e) {
      setError(`new: ${e?.detail || e?.message || 'create failed'}`);
    } finally {
      setSavingId(null);
    }
  }

  if (rows === null) {
    return error
      ? <div className="pad err" data-testid="species-error">{error}</div>
      : <div className="pad">loading…</div>;
  }

  const groups = groupByRarity(rows);

  return (
    <div className="form pad" data-testid="species-editor">
      <p className="hint">
        管理 AsciiPet 物种目录。按稀有度分组；每行独立保存。隐藏（visible=false）
        的物种不会出现在公共 <code>/api/pet/species</code>，但已分配的访客 cookie
        仍能继续使用，直到被重新分配。
      </p>

      {error && (
        <div className="pad err" role="alert" data-testid="species-error" style={{ marginBottom: 8 }}>
          {error}
          <button type="button" onClick={() => setError(null)} style={{ marginLeft: 12 }}>
            dismiss
          </button>
        </div>
      )}

      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <button
          type="button"
          data-testid="species-add-toggle"
          onClick={() => setNewDraft(newDraft ? null : emptyDraft())}
        >{newDraft ? '取消新增' : '+ 新增物种'}</button>
        <span className="grow" />
        <span className="hint">共 {rows.length} 个</span>
      </div>

      {newDraft && (
        <fieldset className="species-row" data-testid="species-new-row" style={{ marginBottom: 16 }}>
          <legend>新增物种</legend>
          <div className="species-grid">
            <label>
              id (slug)
              <input
                data-testid="species-new-id"
                value={newDraft.id}
                onChange={(e) => setNewDraft({ ...newDraft, id: e.target.value })}
                placeholder="kraken"
              />
            </label>
            <label>
              名称
              <input
                data-testid="species-new-name"
                value={newDraft.name}
                onChange={(e) => setNewDraft({ ...newDraft, name: e.target.value })}
              />
            </label>
            <label>
              稀有度
              <select
                data-testid="species-new-rarity"
                value={newDraft.rarity}
                onChange={(e) => setNewDraft({ ...newDraft, rarity: e.target.value })}
              >
                {RARITY_ORDER.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </label>
            <label>
              颜色
              <input
                type="color"
                data-testid="species-new-color"
                value={newDraft.color}
                onChange={(e) => setNewDraft({ ...newDraft, color: e.target.value })}
              />
            </label>
          </div>
          <div style={{ marginTop: 8 }}>
            <button
              type="button"
              className="primary"
              data-testid="species-new-create"
              onClick={createNew}
              disabled={savingId === '__new__' || !newDraft.id || !newDraft.name}
            >{savingId === '__new__' ? '创建中…' : '创建'}</button>
          </div>
        </fieldset>
      )}

      {RARITY_ORDER.map((rarity) => {
        const list = groups[rarity];
        if (!list || list.length === 0) return null;
        return (
          <details key={rarity} open data-testid={`species-group-${rarity}`}>
            <summary>
              <span className="rarity-dot" style={{ background: RARITY_COLOR[rarity] }} />
              {rarity} ({list.length})
            </summary>
            {list.map((r) => {
              const d = rowDraft(r.id);
              const isDirty = dirty(r.id);
              return (
                <fieldset
                  key={r.id}
                  className="species-row"
                  data-testid={`species-row-${r.id}`}
                  data-dirty={isDirty ? 'true' : 'false'}
                >
                  <legend>
                    <code>{r.id}</code>
                    {!r.visible && <span className="hint" style={{ marginLeft: 8 }}>· 隐藏</span>}
                  </legend>
                  <div className="species-grid">
                    <label>
                      名称
                      <input
                        data-testid={`species-name-${r.id}`}
                        value={d.name}
                        onChange={(e) => setDraftField(r.id, 'name', e.target.value)}
                      />
                    </label>
                    <label>
                      稀有度
                      <select
                        data-testid={`species-rarity-${r.id}`}
                        value={d.rarity}
                        onChange={(e) => setDraftField(r.id, 'rarity', e.target.value)}
                      >
                        {RARITY_ORDER.map((rr) => <option key={rr} value={rr}>{rr}</option>)}
                      </select>
                    </label>
                    <label>
                      颜色
                      <input
                        type="color"
                        data-testid={`species-color-${r.id}`}
                        value={d.color}
                        onChange={(e) => setDraftField(r.id, 'color', e.target.value)}
                      />
                    </label>
                    <label>
                      sort_order
                      <input
                        type="number"
                        min={0}
                        data-testid={`species-sort-${r.id}`}
                        value={d.sort_order}
                        onChange={(e) => setDraftField(r.id, 'sort_order', parseInt(e.target.value, 10) || 0)}
                      />
                    </label>
                    <label className="span-2">
                      特点 (trait_zh)
                      <input
                        data-testid={`species-trait-${r.id}`}
                        value={d.trait_zh || ''}
                        onChange={(e) => setDraftField(r.id, 'trait_zh', e.target.value)}
                      />
                    </label>
                    <label className="span-2">
                      人格 (personality_zh)
                      <textarea
                        rows={2}
                        data-testid={`species-personality-${r.id}`}
                        value={d.personality_zh || ''}
                        onChange={(e) => setDraftField(r.id, 'personality_zh', e.target.value)}
                      />
                    </label>
                    <label className="span-2">
                      描述 (description_zh)
                      <textarea
                        rows={2}
                        data-testid={`species-description-${r.id}`}
                        value={d.description_zh || ''}
                        onChange={(e) => setDraftField(r.id, 'description_zh', e.target.value)}
                      />
                    </label>
                  </div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 8 }}>
                    <label style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                      <input
                        type="checkbox"
                        data-testid={`species-visible-${r.id}`}
                        checked={d.visible}
                        onChange={(e) => setDraftField(r.id, 'visible', e.target.checked)}
                      />
                      可见
                    </label>
                    <button
                      type="button"
                      data-testid={`species-frames-toggle-${r.id}`}
                      onClick={() => setFramesOpenId(framesOpenId === r.id ? null : r.id)}
                      aria-expanded={framesOpenId === r.id}
                    >
                      {framesOpenId === r.id ? '收起帧' : `编辑帧 (${(d.frames || []).length})`}
                    </button>
                    <span className="grow" />
                    <button
                      type="button"
                      className="primary"
                      data-testid={`species-save-${r.id}`}
                      disabled={!isDirty || savingId === r.id}
                      onClick={() => saveRow(r.id)}
                    >{savingId === r.id ? 'saving…' : '保存'}</button>
                    <button
                      type="button"
                      className="danger"
                      data-testid={`species-delete-${r.id}`}
                      disabled={deletingId === r.id}
                      onClick={() => removeRow(r.id)}
                    >{deletingId === r.id ? 'deleting…' : '删除'}</button>
                  </div>
                  {framesOpenId === r.id && (
                    <FramesPanel
                      speciesId={r.id}
                      frames={d.frames || []}
                      onChange={(frameIdx, lines) => setDraftFrame(r.id, frameIdx, lines)}
                    />
                  )}
                </fieldset>
              );
            })}
          </details>
        );
      })}
    </div>
  );
}

// Task 21f: ASCII frame editor.
//
// AsciiPet's renderer expects each frame to be a list of 5 lines, each 12
// chars wide after `{E}` is substituted with a one-char eye marker. We
// don't BLOCK saves on layout drift — sometimes a wider sprite is
// intentional — but we surface a hint per row that's off-spec so the
// owner sees what the public renderer will think is "wrong".
const SPEC_LINES = 5;
const SPEC_WIDTH = 12;

// Task 40: render a frame's lines exactly the way AsciiPet does for the
// `idle` state — the most neutral preview, since it's what visitors first
// see when no interaction is in flight. The eye marker `·` mirrors
// STATE_EYE.idle in src/components/pet/species.js (we don't import it
// to avoid coupling the admin to the pet renderer's hydration cycle).
const PREVIEW_EYE = '·';
export function renderFrameForPreview(lines) {
  if (!Array.isArray(lines)) return '';
  return lines
    .map((line) => (typeof line === 'string' ? line.replaceAll('{E}', PREVIEW_EYE) : ''))
    .join('\n');
}

export function frameLayoutHint(lines) {
  if (!Array.isArray(lines)) return null;
  const issues = [];
  if (lines.length !== SPEC_LINES) {
    issues.push(`${lines.length} 行（应 ${SPEC_LINES}）`);
  }
  for (let i = 0; i < lines.length; i++) {
    // Be defensive: stale draft state or a malformed API response could
    // hand us a non-string line. Treating it as empty just suppresses the
    // hint for that row rather than crashing the panel.
    const raw = typeof lines[i] === 'string' ? lines[i] : '';
    const w = raw.replace(/\{E\}/g, 'X').length;
    if (w !== SPEC_WIDTH) {
      issues.push(`第 ${i + 1} 行 ${w} 字符（应 ${SPEC_WIDTH}）`);
    }
  }
  return issues.length ? issues.join('；') : null;
}

function FramesPanel({ speciesId, frames, onChange }) {
  // Pad to 3 frames so the editor always has 3 columns even for new
  // species; user can leave extras empty (saving will keep them as empty
  // arrays which AsciiPet handles by skipping that frame index).
  const slots = frames.length < 3
    ? [...frames, ...Array(3 - frames.length).fill([])]
    : frames;

  return (
    <div
      data-testid={`species-frames-panel-${speciesId}`}
      style={{
        marginTop: 12, padding: '10px 12px',
        border: '1px dashed var(--line)', borderRadius: 4,
        background: 'var(--bg)',
      }}
    >
      <div style={{ fontSize: 11, color: 'var(--fg-3)', marginBottom: 8 }}>
        每只精灵 3 帧 ASCII，每帧 5 行 × 12 字符（替换 <code>{'{E}'}</code> 后计算宽度）。
      </div>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: 12,
      }}>
        {slots.slice(0, 3).map((frame, idx) => {
          const text = (frame || []).join('\n');
          const hint = frameLayoutHint(frame);
          return (
            <div key={idx}>
              <label style={{ fontSize: 11, color: 'var(--fg-3)' }}>
                帧 {idx + 1}
              </label>
              <textarea
                data-testid={`species-frame-${speciesId}-${idx}`}
                value={text}
                rows={SPEC_LINES}
                onChange={(e) => onChange(idx, e.target.value.split('\n'))}
                style={{
                  width: '100%',
                  fontFamily: "'JetBrains Mono', ui-monospace, monospace",
                  fontSize: 12,
                  background: 'var(--bg-2)',
                  color: 'var(--fg)',
                  border: '1px solid var(--line)',
                  borderRadius: 3,
                  padding: '4px 6px',
                  whiteSpace: 'pre',
                  overflowX: 'auto',
                }}
                spellCheck={false}
                wrap="off"
              />
              {/* Live preview: shows the frame as AsciiPet would render it
                  for the `idle` state (eye marker · substituted in for {E}).
                  Updates as the textarea changes. */}
              <pre
                data-testid={`species-frame-preview-${speciesId}-${idx}`}
                style={{
                  margin: '4px 0 0',
                  padding: '4px 6px',
                  fontFamily: "'JetBrains Mono', ui-monospace, monospace",
                  fontSize: 12,
                  lineHeight: 1.1,
                  color: 'var(--accent)',
                  background: 'var(--bg-2)',
                  border: '1px dashed var(--line)',
                  borderRadius: 3,
                  whiteSpace: 'pre',
                  overflowX: 'auto',
                  minHeight: '5em',
                }}
                aria-label={`帧 ${idx + 1} 预览`}
              >{renderFrameForPreview(frame)}</pre>
              {hint && (
                <div
                  data-testid={`species-frame-hint-${speciesId}-${idx}`}
                  style={{ fontSize: 10, color: 'var(--accent)', marginTop: 2 }}
                >
                  {hint}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
