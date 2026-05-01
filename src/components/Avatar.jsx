import { useEffect, useState } from 'react';
import PixelAvatar from './PixelAvatar.jsx';

const CACHE_KEY = 'myblog.site.github';

function readCache() {
  try {
    return localStorage.getItem(CACHE_KEY) || null;
  } catch {
    return null;
  }
}

function writeCache(handle) {
  try {
    if (handle) localStorage.setItem(CACHE_KEY, handle);
    else localStorage.removeItem(CACHE_KEY);
  } catch { /* ignore */ }
}

function avatarUrl(handle) {
  return `https://github.com/${encodeURIComponent(handle)}.png?size=128`;
}

/**
 * Renders the user's GitHub avatar. To avoid the flash of the SVG fallback
 * on every page load (useSite is async), the GitHub handle is cached in
 * localStorage so subsequent loads can render the <img> on the first paint.
 *
 * Update path: when /api/site eventually returns a different handle, the
 * cache is refreshed and the new image swaps in. The browser's HTTP cache
 * also makes the actual byte-fetch instant after the first visit.
 *
 * Fallbacks: if no handle is known (cache miss + no prop) or the image
 * fails to load, the SVG pixel face renders instead.
 */
export default function Avatar({ github: ghProp, pixelSize = 16, className = '' }) {
  // Effective handle for THIS render — prefer the live prop, fall back to
  // whatever was last cached so the very first paint already has an image.
  const [errored, setErrored] = useState(false);
  const [cached] = useState(readCache);
  const github = ghProp || cached;

  // Refresh the cache + clear the error flag whenever the live prop changes.
  useEffect(() => {
    if (!ghProp) return;
    if (ghProp !== readCache()) {
      writeCache(ghProp);
      setErrored(false);
    }
  }, [ghProp]);

  if (github && !errored) {
    return (
      <img
        key={github}
        src={avatarUrl(github)}
        alt=""
        className={`gh-avatar ${className}`.trim()}
        loading="eager"
        decoding="async"
        onError={() => setErrored(true)}
      />
    );
  }
  return <PixelAvatar size={pixelSize} />;
}
