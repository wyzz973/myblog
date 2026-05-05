// The catalogue itself comes from /api/pet/species (Task 21e); we group by
// rarity here just for form layout. While the catalogue is loading, we show
// a small placeholder rather than an empty 0-count tree.
import { RARITY_COLOR, RARITY_ORDER, useSpecies } from '../../components/pet/species.js';

export default function PetPersonas({ config, patch, saving, onReset }) {
  const personas = config.personas || {};
  const { ready, species } = useSpecies();
  function setPersona(speciesKey, value) {
    patch({ personas: { ...personas, [speciesKey]: value } });
  }

  const speciesByRarity = RARITY_ORDER.reduce((acc, r) => {
    acc[r] = Object.keys(species).filter((k) => species[k].rarity === r);
    return acc;
  }, {});

  return (
    <div className="form pad">
      <p className="hint">
        每个物种都有独立说话风格。人格文本会在每次回复前注入系统提示词。
      </p>
      {!ready ? (
        <p className="hint">加载物种目录中…</p>
      ) : (
        <div>
          {RARITY_ORDER.map((rarity) => {
            const list = speciesByRarity[rarity];
            if (!list || list.length === 0) return null;
            return (
              <details key={rarity} open={rarity === 'common'}>
                <summary>
                  <span className="rarity-dot" style={{ background: RARITY_COLOR[rarity] }} />
                  {rarity} ({list.length})
                </summary>
                {list.map((s) => (
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
      )}
      <button type="button" onClick={onReset} disabled={saving} className="danger">
        将全部人格重置为默认值
      </button>
    </div>
  );
}
