const MODES = [
  { id: 'greet', label: 'greet — visitor summoned with no article context' },
  { id: 'idle_monologue', label: 'idle_monologue — pet speaks after quiet time' },
  { id: 'summary_react', label: 'summary_react — visitor on article, no selection' },
  { id: 'selection_explain', label: 'selection_explain — selected code/snippet' },
  { id: 'selection_qa', label: 'selection_qa — selected prose' },
];

export default function PetTemplates({ config, patch, saving, onReset }) {
  const tpl = config.mode_templates || {};
  function setTpl(mode, value) {
    patch({ mode_templates: { ...tpl, [mode]: value } });
  }
  return (
    <div className="form pad">
      <p className="hint">
        Available placeholders in templates:
        {' '}<code>{'{title}'}</code> <code>{'{tag}'}</code>
        {' '}<code>{'{summary}'}</code> <code>{'{selection}'}</code>.
        The persona is auto-prepended; <code>{'{persona}'}</code> in templates
        is left literal.
      </p>
      {MODES.map((m) => (
        <fieldset key={m.id}>
          <legend>{m.label}</legend>
          <textarea rows={6} maxLength={800}
            value={tpl[m.id] || ''}
            onChange={(e) => setTpl(m.id, e.target.value)}
            style={{ fontFamily: 'monospace' }} />
        </fieldset>
      ))}
      <button type="button" onClick={onReset} disabled={saving} className="danger">
        Reset all templates to defaults
      </button>
    </div>
  );
}
