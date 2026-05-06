// Reader 顶部的 admin-only 评论审核浮条 (Task 68).
//
// 仅当 localStorage 里存着 admin token 时才挂载。从 /api/admin/comments
// 拉当前 post 的 pending 评论数量；如果 >0 则显示一个浮动条，提供
// 「批准全部 / 标全部为垃圾 / 跳到详细审核页」三个动作。
//
// 这条不依赖公开 Reader 渲染评论（PRD §8 显式 out of scope），它纯粹
// 是给登录管理员的快速通道：浏览公开页 → 看到这篇有 N 条待审 →
// 一键批量处理。任何动作都会刷新计数。

import { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { commentsApi } from '../api/comments.js';

const TOKEN_KEY = 'myblog.admin.token';

function readToken() {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}

export default function ReaderAdminBar({ postId }) {
  const [token, setToken] = useState(readToken);
  const [count, setCount] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [tick, setTick] = useState(0);

  // 当用户在另一个 tab 登入/登出时同步状态。storage 事件不会在同 tab
  // 触发，所以同 tab 切登入态时本浮条会维持原值，刷新即同步。
  useEffect(() => {
    const onStorage = (e) => {
      if (e.key === TOKEN_KEY) setToken(readToken());
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  const refresh = useCallback(() => {
    if (!postId || !token) return;
    let cancelled = false;
    setError(null);
    commentsApi
      .list({ status: 'pending', post_id: postId, limit: 100 })
      .then((rows) => {
        if (cancelled) return;
        const arr = Array.isArray(rows) ? rows : (rows?.items || []);
        setCount(arr.length);
      })
      .catch((e) => {
        if (cancelled) return;
        // 401 → token 过期或已注销；隐藏浮条。
        if (e?.status === 401) setToken(null);
        else setError(e?.detail || e?.message || '加载失败');
      });
    return () => { cancelled = true; };
  }, [postId, token]);

  useEffect(() => { refresh(); }, [refresh, tick]);

  if (!token || !postId) return null;
  if (count == null && !error) return null; // 静默初次加载
  if (count === 0) return null;              // 没待审 → 不打扰

  async function bulk(action) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const list = await commentsApi.list({
        status: 'pending', post_id: postId, limit: 100,
      });
      const ids = (Array.isArray(list) ? list : list?.items || []).map((c) => c.id);
      if (ids.length === 0) {
        setCount(0);
        return;
      }
      await commentsApi.bulk(action, ids);
      setTick((t) => t + 1);
    } catch (e) {
      setError(e?.detail || e?.message || '批量操作失败');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={styles.bar} data-testid="reader-admin-bar">
      <span style={styles.label}>
        <strong style={styles.count}>{count}</strong> 条待审评论
      </span>
      <span style={{ flex: 1 }} />
      {error && <span style={styles.error}>! {error}</span>}
      <button
        type="button"
        onClick={() => bulk('approve')}
        style={styles.btnPrimary}
        disabled={busy}
        data-testid="reader-admin-approve-all"
      >
        {busy ? '处理中…' : '全部通过'}
      </button>
      <button
        type="button"
        onClick={() => bulk('spam')}
        style={styles.btnGhost}
        disabled={busy}
        data-testid="reader-admin-spam-all"
      >
        全部标垃圾
      </button>
      <Link
        to={`/admin/comments?post_id=${encodeURIComponent(postId)}&status=pending`}
        style={styles.btnGhost}
        target="_blank"
        rel="noopener noreferrer"
      >
        ↗ 详细审核
      </Link>
    </div>
  );
}

const styles = {
  bar: {
    position: 'sticky',
    top: 0,
    zIndex: 60,
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '10px 14px',
    background: 'color-mix(in oklab, var(--accent) 12%, var(--bg))',
    border: '1px solid color-mix(in oklab, var(--accent) 40%, transparent)',
    borderRadius: 4,
    fontSize: 12,
    color: 'var(--fg-2)',
    margin: '0 0 12px',
  },
  count: { color: 'var(--accent)', fontVariantNumeric: 'tabular-nums' },
  label: { letterSpacing: '0.02em' },
  error: { color: 'var(--danger)', fontSize: 11, marginRight: 8 },
  btnPrimary: {
    background: 'var(--accent)', color: '#0a0b0d', border: 0,
    padding: '4px 10px', borderRadius: 3, cursor: 'pointer',
    fontFamily: 'inherit', fontSize: 11, fontWeight: 600,
    letterSpacing: '0.04em',
  },
  btnGhost: {
    background: 'transparent',
    border: '1px solid var(--line-2)',
    color: 'var(--fg-2)',
    padding: '4px 10px', borderRadius: 3, cursor: 'pointer',
    fontFamily: 'inherit', fontSize: 11,
    textDecoration: 'none', display: 'inline-block',
  },
};
