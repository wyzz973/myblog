// Single frontend source of truth for the species roster lives in
// src/components/pet/species.js (which the renderer also consumes).
// Group it by rarity here for the admin form layout.
import { RARITY_COLOR, RARITY_ORDER, SPECIES } from '../../components/pet/species.js';

const SPECIES_BY_RARITY = RARITY_ORDER.reduce((acc, r) => {
  acc[r] = Object.keys(SPECIES).filter((k) => SPECIES[k].rarity === r);
  return acc;
}, {});

export default function PetPersonas({ config, patch, saving, onReset }) {
  const personas = config.personas || {};
  function setPersona(species, value) {
    patch({ personas: { ...personas, [species]: value } });
  }
  return (
    <div className="form pad">
      <p className="hint">
        每个物种都有独立说话风格。人格文本会在每次回复前注入系统提示词。
      </p>
      <div>
        {RARITY_ORDER.map((rarity) => {
          const species = SPECIES_BY_RARITY[rarity];
          return (
            <details key={rarity} open={rarity === 'common'}>
              <summary>
                <span className="rarity-dot" style={{ background: RARITY_COLOR[rarity] }} />
                {rarity} ({species.length})
              </summary>
              {species.map((s) => (
                <div className="persona-row" key={s}>
                  <label className="species-label">{s}</label>
                  <textarea rows={3} maxLength={400}
                    value={personas[s] || ''}
                    onChange={(e) => setPersona(s, e.target.value)} />
                </div>
              ))}
            </details>
          );
        })}
      </div>
      <button type="button" onClick={onReset} disabled={saving} className="danger">
        将全部人格重置为默认值
      </button>
    </div>
  );
}
