import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import App from './App.jsx';
import AdminApp from './admin/index.jsx';
import './styles.css';
import { sendHit } from './utils/beacon.js';
import { loadSpecies } from './components/pet/species.js';

// Kick off the species catalogue fetch as early as possible — runs in
// parallel with React tree mount so AsciiPet usually renders against a
// populated catalogue on first commit.
loadSpecies().catch(() => { /* offline / blocked — pet falls back to "loading" */ });

// Prime the favicon from a cached GitHub handle BEFORE React mounts. This
// avoids the brief flash of the inline pixel-art icon on every page load
// (the cached handle stays valid until the site config changes; App.jsx
// refreshes both the cache and the favicon once /api/site responds).
(() => {
  try {
    const cached = localStorage.getItem('myblog.site.github');
    if (!cached) return;
    const link = document.querySelector("link[rel='icon']");
    if (!link) return;
    link.type = 'image/png';
    link.href = `https://github.com/${encodeURIComponent(cached)}.png?size=64`;
  } catch { /* localStorage blocked — keep inline pixel favicon */ }
})();

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        {/* Admin SPA (auth + dashboard + placeholders) */}
        <Route path="/admin/*" element={<AdminApp />} />
        {/* Public site — App.jsx manages its own internal navigation */}
        <Route path="/*" element={<App />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);

sendHit({ path: window.location.pathname, post_id: null });
