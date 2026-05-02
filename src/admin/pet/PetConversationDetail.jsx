import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { apiPet } from '../../api/pet.js';

export default function PetConversationDetail() {
  const { visitorHash } = useParams();
  const nav = useNavigate();
  const [items, setItems] = useState([]);
  const [cursor, setCursor] = useState(null);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  async function loadPage(reset = false) {
    setLoading(true);
    try {
      const params = {};
      if (!reset && cursor) params.cursor = cursor;
      const r = await apiPet.getConversation(visitorHash, params);
      setItems((prev) => (reset ? r.items : [...prev, ...r.items]));
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
  }, [visitorHash]);

  async function handleDelete() {
    if (!confirm(`Delete ALL messages for ${visitorHash}? This cannot be undone.`)) return;
    try {
      await apiPet.deleteConversation(visitorHash);
      nav('/admin/pet?tab=conversations');
    } catch (e) {
      setError(e?.detail || e?.message || 'delete failed');
    }
  }

  if (loading && items.length === 0) return <div className="hint pad">loading…</div>;
  if (error) return <div className="err pad">{error}</div>;

  return (
    <div className="form pad">
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
        <h2 style={{ margin: 0, fontSize: 14 }}>
          {visitorHash} · {items.length > 0 && items[0].species} · {items.length} messages
        </h2>
        <span className="grow" />
        <button type="button" onClick={handleDelete} className="danger">
          Delete all
        </button>
      </div>
      <div>
        {items.map((m) => (
          <div key={m.id} className="conv-msg">
            <div className="conv-msg-head">
              <span>{new Date(m.created_at).toLocaleString()}</span>
              <span className="conv-msg-mode">{m.mode}</span>
              {m.post_id && <span className="conv-msg-path">/p/{m.post_id}</span>}
              <span className="grow" />
              <span className="conv-msg-source">[{m.source}]</span>
            </div>
            {m.selection && (
              <div className="conv-msg-sel">
                <code>{m.selection}</code>
              </div>
            )}
            <div className="conv-msg-reply" data-testid="reply-text">
              {m.reply}
            </div>
            <details className="conv-msg-debug">
              <summary>debug</summary>
              <pre>{m.system_prompt}</pre>
              <pre>{JSON.stringify(m.prior_turns, null, 2)}</pre>
            </details>
          </div>
        ))}
      </div>
      {hasMore && (
        <button type="button" onClick={() => loadPage(false)} disabled={loading}>
          {loading ? 'loading…' : 'load older'}
        </button>
      )}
    </div>
  );
}
