import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiPet } from '../../api/pet.js';

function ago(iso) {
  const t = Date.now() - new Date(iso).getTime();
  const m = Math.floor(t / 60000);
  if (m < 1) return '刚刚';
  if (m < 60) return `${m} 分钟前`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} 小时前`;
  const d = Math.floor(h / 24);
  return `${d} 天前`;
}

export default function PetConversations() {
  const [items, setItems] = useState([]);
  const [cursor, setCursor] = useState(null);
  const [species, setSpecies] = useState('');
  const [hashQuery, setHashQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hasMore, setHasMore] = useState(false);

  async function loadPage(reset = false) {
    setLoading(true);
    try {
      const params = {};
      if (!reset && cursor) params.cursor = cursor;
      if (species) params.species = species;
      if (hashQuery.trim()) params.q = hashQuery.trim();
      const r = await apiPet.listConversations(params);
      setItems((prev) => (reset ? r.items : [...prev, ...r.items]));
      setCursor(r.next_cursor);
      setHasMore(!!r.next_cursor);
      setError(null);
    } catch (e) {
      setError(e?.detail || e?.message || '加载失败');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadPage(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [species, hashQuery]);

  return (
    <div className="form pad">
      <p className="hint">
        按访客聚合宠物助手对话，点击任一行查看完整消息时间线。
      </p>
      <div style={{ display: 'flex', gap: 12, marginBottom: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        <label>
          物种：&nbsp;
          <input
            type="text"
            value={species}
            placeholder="任意"
            onChange={(e) => setSpecies(e.target.value)}
            style={{ width: 120 }}
          />
        </label>
        <label>
          访客哈希前缀：&nbsp;
          <input
            type="search"
            value={hashQuery}
            placeholder="如 388cd0b07caa"
            onChange={(e) => setHashQuery(e.target.value)}
            style={{ width: 200 }}
            data-testid="conv-search"
          />
        </label>
        {hashQuery && (
          <button
            type="button"
            onClick={() => setHashQuery('')}
            data-testid="conv-search-clear"
          >清除</button>
        )}
      </div>
      {error && <div className="err">{error}</div>}
      {loading && items.length === 0 && <div className="hint">加载中...</div>}
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
              <span className="conv-count">{it.message_count} 条消息</span>
              <span className="conv-when">{ago(it.last_msg_at)}</span>
            </div>
            <div className="conv-preview">{it.last_reply_preview}</div>
          </Link>
        ))}
      </div>
      {hasMore && (
        <button type="button" onClick={() => loadPage(false)} disabled={loading}>
          {loading ? '加载中...' : '加载更多'}
        </button>
      )}
    </div>
  );
}
