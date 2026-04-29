const BASE = import.meta.env.VITE_API_BASE_URL || '';

export async function sendHit({ path, post_id }) {
  try {
    await fetch(`${BASE}/api/hit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        path: path || window.location.pathname,
        referrer: document.referrer || null,
        post_id: post_id || null,
      }),
      keepalive: true,
    });
  } catch {
    // beacon must be silent
  }
}
