const PRESETS = {
  strict:    { per_ip_per_min: 6,  per_ip_per_day: 30,   global_per_day: 500,  unlimited: false },
  relaxed:   { per_ip_per_min: 30, per_ip_per_day: 500,  global_per_day: 5000, unlimited: false },
  unlimited: { per_ip_per_min: 30, per_ip_per_day: 500,  global_per_day: 5000, unlimited: true  },
};

function detectPreset(config) {
  for (const [name, p] of Object.entries(PRESETS)) {
    if (
      config.per_ip_per_min === p.per_ip_per_min
      && config.per_ip_per_day === p.per_ip_per_day
      && config.global_per_day === p.global_per_day
      && !!config.unlimited === p.unlimited
    ) return name;
  }
  return 'custom';
}

export default function PetBehavior({ config, patch }) {
  const preset = detectPreset(config);
  return (
    <div className="form pad">
      <label>
        <input type="checkbox" checked={config.enabled}
               onChange={(e) => patch({ enabled: e.target.checked })} />
        Enabled
      </label>
      <label>
        <input type="checkbox" checked={config.visitor_can_change}
               onChange={(e) => patch({ visitor_can_change: e.target.checked })} />
        Visitor can change species
      </label>
      <label>
        <input type="checkbox" checked={config.enable_article_context}
               onChange={(e) => patch({ enable_article_context: e.target.checked })} />
        Article context awareness
      </label>

      <fieldset>
        <legend>Providers (fallback chain)</legend>
        <input type="text" value={(config.providers || []).join(', ')}
               onChange={(e) => patch({
                 providers: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
               })}
               placeholder="zhipu, qwen, doubao, deepseek, anthropic" />
      </fieldset>

      <fieldset>
        <legend>Rate limit</legend>
        {['strict','relaxed','unlimited'].map((p) => (
          <label key={p}>
            <input type="radio" name="preset" checked={preset === p}
                   onChange={() => patch(PRESETS[p])} />
            {p}
          </label>
        ))}
        {preset === 'custom' && <span className="hint">(custom)</span>}
        <details>
          <summary>Advanced</summary>
          <label>per_ip_per_min: <input type="number" min="1" max="120"
            value={config.per_ip_per_min}
            onChange={(e) => patch({ per_ip_per_min: Number(e.target.value) })} /></label>
          <label>per_ip_per_day: <input type="number" min="1" max="10000"
            value={config.per_ip_per_day}
            onChange={(e) => patch({ per_ip_per_day: Number(e.target.value) })} /></label>
          <label>global_per_day: <input type="number" min="10" max="100000"
            value={config.global_per_day}
            onChange={(e) => patch({ global_per_day: Number(e.target.value) })} /></label>
          <label>hard_ceiling_per_day: <input type="number" min="100" max="100000"
            value={config.hard_ceiling_per_day}
            onChange={(e) => patch({ hard_ceiling_per_day: Number(e.target.value) })} /></label>
          <label>
            <input type="checkbox" checked={!!config.unlimited}
                   onChange={(e) => patch({ unlimited: e.target.checked })} />
            unlimited (skip 3-layer, only enforce hard_ceiling)
          </label>
        </details>
      </fieldset>

      <fieldset>
        <legend>Fallback lines (one per line)</legend>
        <textarea rows={4}
          value={(config.fallback_lines || []).join('\n')}
          onChange={(e) => patch({
            fallback_lines: e.target.value.split('\n').filter((l) => l.trim()),
          })} />
      </fieldset>

      <fieldset>
        <legend>Tired lines (rate-limited reply)</legend>
        <textarea rows={4}
          value={(config.tired_lines || []).join('\n')}
          onChange={(e) => patch({
            tired_lines: e.target.value.split('\n').filter((l) => l.trim()),
          })} />
      </fieldset>
    </div>
  );
}
