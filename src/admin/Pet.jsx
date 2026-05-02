import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { apiPet } from '../api/pet.js';

import PetBehavior from './pet/PetBehavior.jsx';
import PetPersonas from './pet/PetPersonas.jsx';
import PetTemplates from './pet/PetTemplates.jsx';

const TABS = [
  { id: 'behavior', label: 'Behavior' },
  { id: 'personas', label: 'Personas' },
  { id: 'templates', label: 'Prompt templates' },
];

export default function Pet() {
  const [params, setParams] = useSearchParams();
  const tab = TABS.some((t) => t.id === params.get('tab')) ? params.get('tab') : 'behavior';

  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [savedTick, setSavedTick] = useState(0);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    apiPet.get()
      .then((res) => mounted && (setConfig(res), setError(null)))
      .catch((err) => mounted && setError(err?.detail || err?.message || 'failed to load'))
      .finally(() => mounted && setLoading(false));
    return () => { mounted = false; };
  }, []);

  function patch(partial) {
    setConfig((prev) => ({ ...prev, ...partial }));
  }

  async function save() {
    if (!config) return;
    setSaving(true);
    try {
      const next = await apiPet.put(config);
      setConfig(next);
      setSavedTick((t) => t + 1);
      setError(null);
    } catch (e) {
      setError(e?.detail || e?.message || 'save failed');
    } finally {
      setSaving(false);
    }
  }

  async function resetSection(section) {
    if (!confirm(`Reset all ${section} to defaults? This cannot be undone.`)) return;
    setSaving(true);
    try {
      const next = await apiPet.resetSection(section);
      setConfig(next);
      setSavedTick((t) => t + 1);
      setError(null);
    } catch (e) {
      setError(e?.detail || e?.message || 'reset failed');
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="pad">loading…</div>;
  // Initial-load failure (no config to edit): full-page error.
  if (error && !config) return <div className="pad err">{error}</div>;
  if (!config) return null;

  return (
    <div className="admin-pet">
      <nav className="tabs">
        {TABS.map((t) => (
          <button
            type="button"
            key={t.id}
            className={`tab ${tab === t.id ? 'active' : ''}`}
            onClick={() => setParams({ tab: t.id })}
          >{t.label}</button>
        ))}
        <span className="grow" />
        <button type="button" className="primary" onClick={save} disabled={saving}>
          {saving ? 'saving…' : 'Save'}
        </button>
        {savedTick > 0 && <span className="saved-hint">✓ saved</span>}
      </nav>

      {/* Inline error banner (save / reset failure) — keeps the form usable. */}
      {error && config && (
        <div className="pad err" role="alert" style={{ marginBottom: 8 }}>
          {error}
          <button type="button" onClick={() => setError(null)} style={{ marginLeft: 12 }}>
            dismiss
          </button>
        </div>
      )}

      {tab === 'behavior' && <PetBehavior config={config} patch={patch} />}
      {tab === 'personas' && (
        <PetPersonas
          config={config} patch={patch} saving={saving}
          onReset={() => resetSection('personas')}
        />
      )}
      {tab === 'templates' && (
        <PetTemplates
          config={config} patch={patch} saving={saving}
          onReset={() => resetSection('templates')}
        />
      )}
    </div>
  );
}
