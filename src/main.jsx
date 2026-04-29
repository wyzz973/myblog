import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import App from './App.jsx';
import AdminApp from './admin/index.jsx';
import './styles.css';
import { sendHit } from './utils/beacon.js';

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
