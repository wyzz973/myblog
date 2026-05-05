import { useNow } from '../api/hooks.js';
import { renderNowMarkdown } from '../admin/nowMarkdown.js';

// /now panel rendered between contributions and ./posts on HomeA.
// Reads the current entry from /api/now (returned shape:
// { current, history }). Displays nothing if no current entry exists.
export default function NowPanel() {
  const { data, loading, error } = useNow();
  if (loading || error) return null;
  const cur = data?.current;
  if (!cur) return null;

  return (
    <section className="now-panel" id="now" data-testid="now-panel">
      <div className="section-head">
        <span className="label">
          <span className="n">02b /</span> ./now
        </span>
        <span className="count">{fmtAgo(cur.created_at)}</span>
      </div>
      <div className="now-card">
        <div
          className="now-body"
          dangerouslySetInnerHTML={{ __html: renderNowMarkdown(cur.body_md) }}
        />
        {(cur.listening || cur.reading) && (
          <div className="now-meta">
            {cur.listening && (
              <div>
                <span className="now-meta-label">listening</span>
                <span>{cur.listening}</span>
              </div>
            )}
            {cur.reading && (
              <div>
                <span className="now-meta-label">reading</span>
                <span>{cur.reading}</span>
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

function fmtAgo(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const ms = Date.now() - d.getTime();
  if (ms < 0) return d.toLocaleDateString();
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const days = Math.floor(h / 24);
  if (days < 7) return `${days}d ago`;
  return d.toLocaleDateString();
}
