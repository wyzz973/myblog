import { useEffect, useState } from 'react';
import { apiPet } from '../../api/pet.js';

export default function PetUsage() {
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    apiPet.getUsage()
      .then((res) => mounted && (setItems(res.items || []), setError(null)))
      .catch((e) => mounted && setError(e?.detail || e?.message || 'failed to load usage'))
      .finally(() => mounted && setLoading(false));
    return () => { mounted = false; };
  }, []);

  if (loading) return <div className="hint pad">loading…</div>;
  if (error) return <div className="err pad">{error}</div>;

  return (
    <div className="form pad">
      <h2 style={{ margin: 0, fontSize: 14 }}>Usage</h2>
      <div className="pet-usage-table">
        <div className="pet-usage-head">
          <span>day</span><span>mode</span><span>source</span><span>calls</span><span>tokens</span>
        </div>
        {items.map((row, i) => (
          <div className="pet-usage-row" key={`${row.day}-${row.mode}-${row.source}-${i}`}>
            <span>{row.day}</span>
            <span>{row.mode}</span>
            <span>{row.source}</span>
            <span>{row.calls}</span>
            <span>{row.estimated_total_tokens}</span>
          </div>
        ))}
        {items.length === 0 && <div className="hint">no usage yet</div>}
      </div>
    </div>
  );
}
