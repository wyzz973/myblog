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
        启用宠物助手
      </label>
      <label>
        <input type="checkbox" checked={config.visitor_can_change}
               onChange={(e) => patch({ visitor_can_change: e.target.checked })} />
        允许访客切换物种
      </label>
      <label>
        <input type="checkbox" checked={config.enable_article_context}
               onChange={(e) => patch({ enable_article_context: e.target.checked })} />
        启用文章上下文感知
      </label>
      <label>
        <input type="checkbox" checked={config.enable_free_chat !== false}
               onChange={(e) => patch({ enable_free_chat: e.target.checked })} />
        启用自由聊天
      </label>
      <label>
        <input type="checkbox" checked={config.enable_proactive !== false}
               onChange={(e) => patch({ enable_proactive: e.target.checked })} />
        启用主动提示
      </label>
      <label>
        <input type="checkbox" checked={config.enable_long_term_memory !== false}
               onChange={(e) => patch({ enable_long_term_memory: e.target.checked })} />
        启用匿名长期记忆
      </label>

      <fieldset>
        <legend>模型提供商（按顺序兜底）</legend>
        <input type="text" value={(config.providers || []).join(', ')}
               onChange={(e) => patch({
                 providers: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
               })}
               placeholder="zhipu, qwen, doubao, deepseek, anthropic" />
      </fieldset>

      <fieldset>
        <legend>限流配置</legend>
        {['strict','relaxed','unlimited'].map((p) => (
          <label key={p}>
            <input type="radio" name="preset" checked={preset === p}
                   onChange={() => patch(PRESETS[p])} />
            {p}
          </label>
        ))}
        {preset === 'custom' && <span className="hint">（自定义）</span>}
        <details>
          <summary>高级配置</summary>
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
            不限量（跳过三层限流，只保留硬上限）
          </label>
        </details>
      </fieldset>

      <fieldset>
        <legend>模式预算</legend>
        <details>
          <summary>各模式高级限制</summary>
          {Object.keys(config.per_mode_output_budget || {}).map((mode) => (
            <div key={mode} style={{ display: 'grid', gridTemplateColumns: '130px 1fr 1fr 1fr', gap: 8, alignItems: 'center' }}>
              <span className="hint">{mode}</span>
              <label>每日 <input type="number" min="0" max="10000"
                value={config.per_mode_daily_limit?.[mode] ?? 0}
                onChange={(e) => patch({
                  per_mode_daily_limit: {
                    ...(config.per_mode_daily_limit || {}),
                    [mode]: Number(e.target.value),
                  },
                })} /></label>
              <label>输入 <input type="number" min="100" max="4000"
                value={config.per_mode_input_budget?.[mode] ?? 1000}
                onChange={(e) => patch({
                  per_mode_input_budget: {
                    ...(config.per_mode_input_budget || {}),
                    [mode]: Number(e.target.value),
                  },
                })} /></label>
              <label>输出 <input type="number" min="10" max="500"
                value={config.per_mode_output_budget?.[mode] ?? 100}
                onChange={(e) => patch({
                  per_mode_output_budget: {
                    ...(config.per_mode_output_budget || {}),
                    [mode]: Number(e.target.value),
                  },
                })} /></label>
            </div>
          ))}
        </details>
      </fieldset>

      <fieldset>
        <legend>兜底回复（每行一条）</legend>
        <textarea rows={4}
          value={(config.fallback_lines || []).join('\n')}
          onChange={(e) => patch({
            fallback_lines: e.target.value.split('\n').filter((l) => l.trim()),
          })} />
      </fieldset>

      <fieldset>
        <legend>限流回复（每行一条）</legend>
        <textarea rows={4}
          value={(config.tired_lines || []).join('\n')}
          onChange={(e) => patch({
            tired_lines: e.target.value.split('\n').filter((l) => l.trim()),
          })} />
      </fieldset>
    </div>
  );
}
