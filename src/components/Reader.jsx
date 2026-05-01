import { useEffect, useRef, useState } from 'react';
import { useSite, usePosts, usePost } from '../api/hooks.js';
import { sendHit } from '../utils/beacon.js';
import CopyText from './CopyText.jsx';
import Avatar from './Avatar.jsx';

function renderInline(items) {
  if (!items) return null;
  return items.map((it, i) => {
    const k = it.kind;
    if (k === 'text') return <span key={i}>{it.s}</span>;
    if (k === 'code') return <code key={i} className="inline-code">{it.s}</code>;
    if (k === 'b') return <strong key={i}>{renderInline(it.children)}</strong>;
    if (k === 'i') return <em key={i}>{renderInline(it.children)}</em>;
    if (k === 'a') return (
      <a key={i} href={it.href} target="_blank" rel="noopener noreferrer">
        {renderInline(it.children)}
      </a>
    );
    return null;
  });
}

function CodeBlock({ code }) {
  const [copied, setCopied] = useState(false);
  const lines = code.split('\n');
  const onCopy = () => {
    navigator.clipboard?.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  };
  const firstLine = lines[0] || '';
  const lang = firstLine.startsWith('#') ? 'sh'
    : firstLine.startsWith('//') ? 'java'
    : firstLine.toUpperCase().includes('SELECT') ? 'sql'
    : 'text';
  return (
    <div className="codeblock">
      <div className="codeblock-head">
        <span className="codeblock-dots">
          <span style={{ background: '#ff5f57' }} />
          <span style={{ background: '#febc2e' }} />
          <span style={{ background: '#28c840' }} />
        </span>
        <span className="codeblock-lang">{lang}</span>
        <button className="codeblock-copy" onClick={onCopy}>
          {copied ? '✓ copied' : '⧉ copy'}
        </button>
      </div>
      <pre><code>
        {lines.map((line, i) => (
          <div className="codeline" key={i}>
            <span className="ln">{i + 1}</span>
            <span className="lc">{line || ' '}</span>
          </div>
        ))}
      </code></pre>
    </div>
  );
}

export default function Reader({ post: postSummary, onBack, onOpenPost, onSelection }) {
  const scrollRef = useRef(null);
  const [progress, setProgress] = useState(0);
  const [activeHeading, setActiveHeading] = useState(0);
  const [liked, setLiked] = useState(false);
  const [likes, setLikes] = useState(0);
  const [linkCopied, setLinkCopied] = useState(false);

  const { data: site } = useSite();
  const { data: postsResp } = usePosts({ limit: 100 });
  const { data: detail } = usePost(postSummary?.id);
  const post = detail || postSummary;
  const SITE = site || { name: '', tagline: '', github: '', email: '' };
  const POSTS = postsResp?.items || [];

  useEffect(() => {
    if (!post) return;
    const stored = parseInt(localStorage.getItem(`bl.likes.${post.id}`) || '0', 10);
    setLikes(stored || 0);
    setLiked(!!localStorage.getItem(`bl.liked.${post.id}`));
  }, [post?.id]);

  useEffect(() => {
    if (!post) return;
    const el = scrollRef.current;
    const onScroll = () => {
      if (!el) return;
      const max = el.scrollHeight - el.clientHeight;
      setProgress(max > 0 ? Math.min(100, (el.scrollTop / max) * 100) : 0);
      const heads = el.querySelectorAll('h2[data-h]');
      let active = 0;
      heads.forEach((h, i) => {
        if (h.getBoundingClientRect().top < 140) active = i;
      });
      setActiveHeading(active);
    };
    el?.addEventListener('scroll', onScroll, { passive: true });
    return () => el?.removeEventListener('scroll', onScroll);
  }, [post]);

  useEffect(() => {
    scrollRef.current?.scrollTo(0, 0);
    setProgress(0);
  }, [post?.id]);

  useEffect(() => {
    if (!post?.id) return;
    sendHit({ path: window.location.pathname, post_id: post.id });
  }, [post?.id]);

  useEffect(() => {
    if (!onSelection) return undefined;
    let timer = null;
    const handler = () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        const sel = (window.getSelection?.()?.toString() || '').trim();
        if (sel.length >= 5) {
          onSelection({ text: 'click pet to explain ↑', kind: 'explain' });
          // auto-clear after 2s
          setTimeout(() => onSelection(null), 2000);
        }
      }, 200);
    };
    document.addEventListener('selectionchange', handler);
    return () => {
      document.removeEventListener('selectionchange', handler);
      clearTimeout(timer);
    };
  }, [onSelection]);

  if (!post) return null;
  const isZh = post.lang === 'zh';
  const wordCount = post.word_count ?? (post.body || []).reduce((s, b) => s + (b.c || '').length, 0);
  const headings = (post.body || []).reduce((arr, b, i) => {
    if (b.t === 'h2') arr.push({ idx: i, text: b.c });
    return arr;
  }, []);
  const related = POSTS.filter((p) => p.tag === post.tag && p.id !== post.id).slice(0, 3);
  const postIdx = POSTS.findIndex((p) => p.id === post.id);
  const prevPost = POSTS[postIdx + 1];
  const nextPost = POSTS[postIdx - 1];
  const tagColor = {
    backend: 'var(--blue)',
    ai: 'var(--violet)',
    ml: 'var(--accent-2)',
    devtools: 'var(--accent)',
    infra: 'var(--danger)',
  }[post.tag] || 'var(--accent)';

  const onLike = () => {
    if (liked) return;
    setLiked(true);
    const n = likes + 1;
    setLikes(n);
    localStorage.setItem(`bl.likes.${post.id}`, String(n));
    localStorage.setItem(`bl.liked.${post.id}`, '1');
  };

  return (
    <div className="reader-shell" ref={scrollRef}>
      <div className="reader-progress" style={{ transform: `scaleX(${progress / 100})` }} />
      <div className="reader-layout">
        <aside className="reader-toc">
          <a className="back" href="#" onClick={(e) => { e.preventDefault(); onBack(); }}>
            <span>←</span> <span>back to index</span>
          </a>
          {headings.length > 0 && (
            <>
              <div className="toc-label">on this page</div>
              <ul className="toc-list">
                {headings.map((h, i) => (
                  <li key={i} className={i === activeHeading ? 'active' : ''}>
                    <a
                      href={`#h-${i}`}
                      onClick={(e) => {
                        e.preventDefault();
                        scrollRef.current
                          ?.querySelector(`#h-${i}`)
                          ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                      }}
                    >
                      <span className="toc-n">{String(i + 1).padStart(2, '0')}</span>
                      <span className="toc-t">{h.text}</span>
                    </a>
                  </li>
                ))}
              </ul>
            </>
          )}
          <div className="toc-stats">
            <div className="stat-row"><span>read</span><span>{post.read}</span></div>
            <div className="stat-row"><span>chars</span><span>{wordCount.toLocaleString()}</span></div>
            <div className="stat-row"><span>tag</span><span style={{ color: tagColor }}>#{post.tag}</span></div>
            <div className="stat-row"><span>updated</span><span>{post.date}</span></div>
          </div>
        </aside>

        <div className="reader">
          <div className="reader-hero" style={{ '--tagc': tagColor }}>
            <div className="reader-eyebrow">
              <span className="n">#{post.n}</span>
              <span className="dot-sep">·</span>
              <span>{post.date}</span>
              <span className="dot-sep">·</span>
              <span className="tag-chip">#{post.tag}</span>
              <span className="dot-sep">·</span>
              <span>◷ {post.read} read</span>
            </div>
            <h1 className={isZh ? 'zh' : ''}>{post.title}</h1>
            <div
              className="subtitle"
              style={{ fontFamily: isZh ? "'Noto Serif SC', serif" : "'Newsreader', serif" }}
            >
              {post.subtitle}
            </div>
          </div>

          {post.tldr && (
            <div className="tldr"><b>TL;DR</b> {post.tldr}</div>
          )}

          <div className={`reader-body ${isZh ? 'zh' : ''}`}>
            {post.body && post.body.length > 0 ? (() => {
              let hIdx = 0;
              return post.body.map((b, i) => {
                if (b.t === 'h2') {
                  const id = `h-${hIdx++}`;
                  return (
                    <h2 key={i} id={id} data-h>
                      <span className="h-anchor">§</span>
                      {b.inline ? renderInline(b.inline) : b.c}
                    </h2>
                  );
                }
                if (b.t === 'h3') return <h3 key={i}>{b.inline ? renderInline(b.inline) : b.c}</h3>;
                if (b.t === 'h4') return <h4 key={i}>{b.inline ? renderInline(b.inline) : b.c}</h4>;
                if (b.t === 'code') return <CodeBlock key={i} code={b.c} />;
                if (b.t === 'hr') return <hr key={i} className="reader-hr" />;
                if (b.t === 'quote') return (
                  <blockquote key={i} className="reader-quote">
                    {b.inline ? renderInline(b.inline) : b.c}
                  </blockquote>
                );
                if (b.t === 'ul' || b.t === 'ol') {
                  const Tag = b.t;
                  return (
                    <Tag key={i} className="reader-list">
                      {(b.items || []).map((it, j) => (
                        <li key={j}>{it.inline ? renderInline(it.inline) : it.c}</li>
                      ))}
                    </Tag>
                  );
                }
                if (b.t === 'table') return (
                  <div key={i} className="reader-table-wrap">
                    <table className="reader-table">
                      {b.header && b.header.length > 0 && (
                        <thead>
                          <tr>
                            {b.header.map((h, j) => (
                              <th key={j} style={{ textAlign: (b.align && b.align[j]) || 'left' }}>{h}</th>
                            ))}
                          </tr>
                        </thead>
                      )}
                      <tbody>
                        {(b.rows || []).map((row, ri) => (
                          <tr key={ri}>
                            {row.map((cell, ci) => (
                              <td key={ci} style={{ textAlign: (b.align && b.align[ci]) || 'left' }}>{cell}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                );
                return <p key={i}>{b.inline ? renderInline(b.inline) : b.c}</p>;
              });
            })() : (
              <div className="reader-stub">
                <p style={{ color: 'var(--fg-3)', fontStyle: 'italic' }}>
                  [ full article draft in progress — the summary below captures the thesis ]
                </p>
                <p style={{ color: 'var(--fg-2)', fontSize: 16, lineHeight: 1.7 }}>{post.summary}</p>
              </div>
            )}
          </div>

          <div className="reader-reactions">
            <button className={`like-btn ${liked ? 'liked' : ''}`} onClick={onLike}>
              <span className="like-ico">{liked ? '♥' : '♡'}</span>
              <span>{likes}</span>
              <span className="like-label">{liked ? 'thanks!' : 'useful?'}</span>
            </button>
            <div className="share-row">
              <button
                className="share-btn"
                onClick={async () => {
                  const url = window.location.href;
                  try {
                    if (navigator.clipboard?.writeText) {
                      await navigator.clipboard.writeText(url);
                    } else {
                      const ta = document.createElement('textarea');
                      ta.value = url;
                      ta.style.position = 'fixed';
                      ta.style.opacity = '0';
                      document.body.appendChild(ta);
                      ta.select();
                      document.execCommand('copy');
                      document.body.removeChild(ta);
                    }
                    setLinkCopied(true);
                    setTimeout(() => setLinkCopied(false), 1400);
                  } catch { /* user blocked clipboard */ }
                }}
              >
                <span>{linkCopied ? '✓' : '⎘'}</span>
                {linkCopied ? ' copied' : ' copy link'}
              </button>
              <button
                className="share-btn"
                onClick={async () => {
                  const data = { title: post.title, url: window.location.href };
                  try {
                    if (navigator.share) {
                      await navigator.share(data);
                    } else {
                      await navigator.clipboard?.writeText(window.location.href);
                    }
                  } catch { /* user canceled */ }
                }}
              >
                <span>↗</span> share
              </button>
            </div>
          </div>

          <div className="reader-author">
            <div className="author-ava" aria-hidden="true">
              <Avatar github={SITE.github} pixelSize={36} />
            </div>
            <div className="author-meta">
              <div className="author-name">{SITE.name}</div>
              <div className="author-bio">{SITE.tagline}</div>
            </div>
            <div className="author-links">
              {SITE.github && (
                <a
                  href={`https://github.com/${SITE.github}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >github</a>
              )}
              {SITE.email && (
                <>
                  {SITE.github && <span className="dot-sep">·</span>}
                  <CopyText
                    label="email"
                    value={SITE.email}
                    copiedLabel="✓ copied"
                    className="author-link-btn"
                  />
                </>
              )}
            </div>
          </div>

          {related.length > 0 && (
            <div className="reader-related">
              <div className="related-head">related · #{post.tag}</div>
              <div className="related-grid">
                {related.map((r) => (
                  <div key={r.id} className="related-card" onClick={() => onOpenPost?.(r)}>
                    <div className="r-n">#{r.n}</div>
                    <div className={`r-title ${r.lang === 'zh' ? 'zh' : ''}`}>{r.title}</div>
                    <div className="r-meta">{r.date} · {r.read}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="reader-navfoot">
            {prevPost ? (
              <button className="nav-prev" onClick={() => onOpenPost?.(prevPost)}>
                <div className="nav-dir">← older</div>
                <div className={`nav-title ${prevPost.lang === 'zh' ? 'zh' : ''}`}>{prevPost.title}</div>
              </button>
            ) : <span />}
            {nextPost ? (
              <button className="nav-next" onClick={() => onOpenPost?.(nextPost)}>
                <div className="nav-dir">newer →</div>
                <div className={`nav-title ${nextPost.lang === 'zh' ? 'zh' : ''}`}>{nextPost.title}</div>
              </button>
            ) : <span />}
          </div>

          <div className="reader-signoff">
            <span>— {SITE.name}, {post.date}</span>
            <span>press <kbd>esc</kbd> to go back</span>
          </div>
        </div>
      </div>
    </div>
  );
}
