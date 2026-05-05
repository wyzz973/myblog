import { useEffect, useState } from 'react';
import { apiPet } from '../../api/pet.js';

// All 12 modes the backend's PetModeTemplates schema accepts. The split is
// for the UX only — backend treats every mode the same. Order within each
// group reflects how a visitor encounters them.
const PROACTIVE_MODES = [
  { id: 'greet', label: 'greet', hint: 'visitor summoned with no article context' },
  { id: 'idle_monologue', label: 'idle_monologue', hint: 'pet speaks after a quiet stretch' },
  { id: 'recommend_next', label: 'recommend_next', hint: 'home view — what to read next' },
  { id: 'article_finished', label: 'article_finished', hint: 'reader hit ~98% of the article' },
  { id: 'reading_assist', label: 'reading_assist', hint: 'long dwell on a paragraph' },
  { id: 'code_assist', label: 'code_assist', hint: 'long dwell on a code block' },
  { id: 'pet_care', label: 'pet_care', hint: 'visitor opened the pet panel' },
];

const RESPONSIVE_MODES = [
  { id: 'summary_react', label: 'summary_react', hint: 'visitor on article, no selection' },
  { id: 'selection_explain', label: 'selection_explain', hint: 'selected code/snippet' },
  { id: 'selection_qa', label: 'selection_qa', hint: 'selected prose' },
  { id: 'free_chat', label: 'free_chat', hint: 'visitor typed a message' },
  { id: 'follow_up', label: 'follow_up', hint: 'visitor reopened mid-conversation' },
];

const ALL_MODES = [...PROACTIVE_MODES, ...RESPONSIVE_MODES];
const MAX_LEN = 800;

export default function PetTemplates({ config, patch, saving, onReset }) {
  const tpl = config?.mode_templates || {};
  const [defaults, setDefaults] = useState(null);
  const [defaultsErr, setDefaultsErr] = useState(null);

  // Pull defaults lazily so a per-mode "重置默认" button can write the
  // backend default for just that mode without touching the others.
  useEffect(() => {
    let mounted = true;
    apiPet
      .fetchDefaults()
      .then((d) => mounted && setDefaults(d?.templates || d?.mode_templates || {}))
      .catch((err) => mounted && setDefaultsErr(err?.detail || err?.message || ''));
    return () => { mounted = false; };
  }, []);

  function setTpl(mode, value) {
    patch({ mode_templates: { ...tpl, [mode]: value } });
  }

  function resetOne(mode) {
    if (!defaults || defaults[mode] == null) return;
    setTpl(mode, defaults[mode]);
  }

  return (
    <div className="form pad" data-testid="pet-templates-form">
      <p className="hint">
        模板内可用占位符：
        {' '}<code>{'{title}'}</code> <code>{'{tag}'}</code>
        {' '}<code>{'{summary}'}</code> <code>{'{selection}'}</code>。
        系统会自动前置 persona；模板里的 <code>{'{persona}'}</code> 保持原样。
      </p>

      <ModeGroup
        title="主动 · proactive"
        hint="宠物不等访客发话就触发的场景"
        modes={PROACTIVE_MODES}
        tpl={tpl}
        defaults={defaults}
        onChange={setTpl}
        onResetOne={resetOne}
      />
      <ModeGroup
        title="响应 · responsive"
        hint="访客行为触发的回复"
        modes={RESPONSIVE_MODES}
        tpl={tpl}
        defaults={defaults}
        onChange={setTpl}
        onResetOne={resetOne}
      />

      <div style={{ marginTop: 14, display: 'flex', alignItems: 'center', gap: 12 }}>
        <button type="button" onClick={onReset} disabled={saving} className="danger">
          全部恢复默认
        </button>
        {defaultsErr && (
          <span style={{ color: 'var(--danger)', fontSize: 11 }}>
            默认值加载失败：{defaultsErr}
          </span>
        )}
        <span style={{ color: 'var(--fg-4)', fontSize: 11 }}>
          {ALL_MODES.length} 个 mode · 每条 {MAX_LEN} 字符上限
        </span>
      </div>
    </div>
  );
}

function ModeGroup({ title, hint, modes, tpl, defaults, onChange, onResetOne }) {
  return (
    <section style={{ marginTop: 14 }} data-testid={`mode-group-${title.split(' ')[0]}`}>
      <header style={groupHead}>
        <span style={groupTitle}>{title}</span>
        <span style={groupHint}>{hint}</span>
      </header>
      {modes.map((m) => (
        <Mode
          key={m.id}
          mode={m}
          value={tpl[m.id] || ''}
          defaultValue={defaults ? defaults[m.id] : null}
          onChange={onChange}
          onResetOne={onResetOne}
        />
      ))}
    </section>
  );
}

function Mode({ mode, value, defaultValue, onChange, onResetOne }) {
  const len = (value || '').length;
  const overflowSoon = len > MAX_LEN * 0.9;
  const dirty = defaultValue != null && value !== defaultValue;
  return (
    <fieldset data-testid={`mode-${mode.id}`}>
      <legend>
        <span style={legendId}>{mode.label}</span>
        <span style={legendHint}> — {mode.hint}</span>
      </legend>
      <textarea
        rows={6}
        maxLength={MAX_LEN}
        value={value}
        onChange={(e) => onChange(mode.id, e.target.value)}
        style={{ fontFamily: 'monospace' }}
        data-testid={`textarea-${mode.id}`}
      />
      <div style={modeFoot}>
        <span style={{ color: overflowSoon ? 'var(--danger)' : 'var(--fg-4)', fontSize: 10 }}>
          {len} / {MAX_LEN}
        </span>
        <button
          type="button"
          onClick={() => onResetOne(mode.id)}
          disabled={defaultValue == null || !dirty}
          style={resetBtnStyle}
          data-testid={`reset-${mode.id}`}
          title={defaultValue == null ? '默认值未加载' : dirty ? '恢复后端默认' : '已是默认'}
        >
          重置默认
        </button>
      </div>
    </fieldset>
  );
}

const groupHead = {
  display: 'flex',
  alignItems: 'baseline',
  gap: 10,
  paddingBottom: 8,
  marginBottom: 6,
  borderBottom: '1px dashed var(--line)',
};
const groupTitle = {
  fontSize: 11,
  color: 'var(--fg-2)',
  letterSpacing: '0.06em',
};
const groupHint = {
  fontSize: 10,
  color: 'var(--fg-4)',
};
const legendId = { color: 'var(--fg)', fontSize: 11 };
const legendHint = { color: 'var(--fg-4)', fontSize: 10 };
const modeFoot = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'flex-end',
  gap: 10,
  marginTop: 4,
};
const resetBtnStyle = {
  background: 'transparent',
  border: '1px solid var(--line-2)',
  color: 'var(--fg-3)',
  fontFamily: 'inherit',
  fontSize: 10,
  padding: '3px 8px',
  borderRadius: 3,
  cursor: 'pointer',
};
