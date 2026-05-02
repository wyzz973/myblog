import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiPet } from '../../api/pet.js';

function ago(iso) {
  const t = Date.now() - new Date(iso).getTime();
  const m = Math.floor(t / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

export default function PetConversations() {
  const [items, setItems] = useState([]);
  const [cursor, setCursor] = useState(null);
  const [species, setSpecies] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hasMore, setHasMore] = useState(false);

  async function loadPage(reset = false) {
    setLoading(true);
    try {
      const params = {};
      if (!reset && cursor) params.cursor = cursor;
      if (species) params.species = species;
      const r = await apiPet.listConversations(params);
      setItems(reset ? r.items : [...items, ...r.items]);
      setCursor(r.next_cursor);
      setHasMore(!!r.next_cursor);
      setError(null);
    } catch (e) {
      setError(e?.detail || e?.message || 'failed to load');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadPage(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [species]);

  return (
    <div className="form pad">
      <p className="hint">
        All pet conversations grouped by visitor. Click a row to see the full
        message timeline.
      </p>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <label>
          species:&nbsp;
          <input
            type="text"
            value={species}
            placeholder="(any)"
            onChange={(e) => setSpecies(e.target.value)}
            style={{ width: 120 }}
          />
        </label>
      </div>
      {error && <div className="err">{error}</div>}
      {loading && items.length === 0 && <div className="hint">loading…</div>}
      <div>
        {items.map((it) => (
          <Link
            key={it.visitor_hash}
            to={`/admin/pet/conversations/${it.visitor_hash}`}
            className="conv-row"
          >
            <div className="conv-row-head">
              <span className="conv-vh">{it.visitor_hash.slice(0, 12)}…</span>
              <span className="conv-species">{it.species}</span>
              <span className="conv-count">{it.message_count} msgs</span>
              <span className="conv-when">{ago(it.last_msg_at)}</span>
            </div>
            <div className="conv-preview">{it.last_reply_preview}</div>
          </Link>
        ))}
      </div>
      {hasMore && (
        <button type="button" onClick={() => loadPage(false)} disabled={loading}>
          {loading ? 'loading…' : 'load more'}
        </button>
      )}
    </div>
  );
}
