const SPECIES_BY_RARITY = {
  common:    ['duck', 'goose', 'blob', 'cat', 'rabbit'],
  uncommon:  ['penguin', 'owl', 'turtle', 'capybara'],
  rare:      ['mushroom', 'ghost', 'snail', 'cactus', 'chonk'],
  epic:      ['octopus', 'jellyfish', 'axolotl', 'robot'],
  legendary: ['dragon', 'phoenix', 'fox', 'shiba', 'mochi',
              'panda', 'hamster', 'bee', 'otter'],
};

const RARITY_COLOR = {
  common: '#9aa6b3', uncommon: '#7dbf8e', rare: '#5c9ddc',
  epic: '#b89cf0', legendary: '#f5b44c',
};

export default function PetPersonas({ config, patch, onReset }) {
  const personas = config.personas || {};
  function setPersona(species, value) {
    patch({ personas: { ...personas, [species]: value } });
  }
  return (
    <div className="form pad">
      <p className="hint">
        Each species speaks in its own voice. The persona text is injected
        into the system prompt before every reply.
      </p>
      <div>
        {Object.entries(SPECIES_BY_RARITY).map(([rarity, species]) => (
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
        ))}
      </div>
      <button type="button" onClick={onReset} className="danger">
        Reset all personas to defaults
      </button>
    </div>
  );
}
