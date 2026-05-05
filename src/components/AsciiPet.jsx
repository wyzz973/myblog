// Clawd-on-desk style ASCII desktop pet.
// State machine inspired by MIT-licensed rullerzhou-afk/clawd-on-desk;
// sprites are original.
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { buildSummonPayload } from './pet/payload.js';
import {
  SPECIES,
  SPECIES_BEHAVIOR,
  RARITY_COLOR,
  STATE_EYE,
  STAT_KEYS,
  rarityStars,
} from './pet/species.js';

const STATES = {
  idle:         { label: 'idle',         bob: 2.8, tint: null,      icon: null,  hint: 'idle' },
  thinking:     { label: 'thinking',     bob: 1.4, tint: null,      icon: '?',   hint: 'thinking…' },
  typing:       { label: 'typing',       bob: 0.6, tint: null,      icon: '⌨',   hint: 'typing' },
  building:     { label: 'building',     bob: 0.4, tint: '#f5b44c', icon: '🔨',  hint: 'building' },
  juggling:     { label: 'juggling',     bob: 0.3, tint: null,      icon: '●●',  hint: 'juggling agents' },
  conducting:   { label: 'conducting',   bob: 0.3, tint: '#c48cf5', icon: '♫',   hint: 'conducting' },
  error:        { label: 'error',        bob: 0.5, tint: '#ff5c5c', icon: '!',   hint: 'error' },
  happy:        { label: 'happy',        bob: 1.2, tint: '#7dbf8e', icon: '✓',   hint: 'done' },
  notification: { label: 'notification', bob: 0.8, tint: '#f5b44c', icon: '!',   hint: 'notify' },
  sweeping:     { label: 'sweeping',     bob: 0.8, tint: null,      icon: '🧹',  hint: 'sweeping' },
  carrying:     { label: 'carrying',     bob: 0.8, tint: null,      icon: '📦',  hint: 'carrying' },
  sleeping:     { label: 'sleeping',     bob: 0.4, tint: null,      icon: 'Z',   hint: 'sleeping…' },
  yawning:      { label: 'yawning',      bob: 0.8, tint: null,      icon: '~',   hint: 'yawn…' },
  startled:     { label: 'startled',     bob: 0.1, tint: '#f5b44c', icon: '!',   hint: '!' },
};

const TEST_STATES = [
  'idle','thinking','typing','building','juggling','conducting',
  'error','happy','notification','sweeping','carrying','sleeping',
];

const QUIPS = ['meow.', 'purr…', 'have you committed?', 'seg loss ok ✓', '*yawn*'];
export const IDLE_MONOLOGUE_MS = 90000;
export const IDLE_MONOLOGUE_COOLDOWN_MS = 240000;
export const PROACTIVE_CHECK_MS = 1200;
export const QUIET_MODE_MS = 30 * 60 * 1000;

const LEGACY_BODY_MAP = {
  capybara: 'capybara',
  cat: 'cat',
  dragon: 'dragon',
  octopus: 'octopus',
  robot: 'robot',
};

function renderSprite(frame, eye) {
  return frame.map((line) => line.replaceAll('{E}', eye)).join('\n');
}

function Dots() {
  const [n, setN] = useState(1);
  useEffect(() => {
    const id = setInterval(() => setN((x) => (x % 3) + 1), 350);
    return () => clearInterval(id);
  }, []);
  return <span>{'.'.repeat(n)}</span>;
}

export default function AsciiPet({ hint = null }) {
  // Server picks the species deterministically from (ip, user-agent) so
  // visitors can't reroll by clearing localStorage. localStorage is only
  // a fast-paint cache; on mount we fetch /api/pet/config and trust the
  // server's `assigned_species` as the source of truth.
  const [bodyKey, setBodyKey] = useState(() => {
    const saved = localStorage.getItem('pet.body');
    if (saved && SPECIES[saved]) return saved;
    if (saved && LEGACY_BODY_MAP[saved] && SPECIES[LEGACY_BODY_MAP[saved]]) {
      return LEGACY_BODY_MAP[saved];
    }
    return 'cat';  // placeholder; replaced on first /api/pet/config response
  });
  const [petEnabled, setPetEnabled] = useState(true);
  const [celebrate, setCelebrate] = useState(null);  // species key when celebrating
  useEffect(() => {
    let alive = true;
    fetch('/api/pet/config')
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => {
        if (!alive || !j?.assigned_species) return;
        setPetEnabled(j.enabled !== false);
        const k = j.assigned_species;
        if (!SPECIES[k]) return;
        if (k !== bodyKey) {
          setBodyKey(k);
          try { localStorage.setItem('pet.body', k); } catch { /* ignore */ }
        }
        // First time this visitor sees this specific legendary buddy → celebrate.
        if (SPECIES[k].rarity === 'legendary') {
          const seenKey = `pet.celebrated.${k}`;
          let seen = false;
          try { seen = localStorage.getItem(seenKey) === '1'; } catch { /* ignore */ }
          if (!seen) {
            setCelebrate(k);
            try { localStorage.setItem(seenKey, '1'); } catch { /* ignore */ }
            setTimeout(() => alive && setCelebrate(null), 1100);
          }
        }
      })
      .catch(() => { /* offline / blocked — keep cached buddy */ });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const body = SPECIES[bodyKey] || SPECIES.cat;
  const [state, setState] = useState('idle');
  const [frame, setFrame] = useState(0);
  const [speech, setSpeech] = useState(null);
  const [pos, setPos] = useState(() => {
    const saved = localStorage.getItem('pet.pos');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        return {
          x: Math.max(-40, Math.min(window.innerWidth - 120, Number(parsed.x) || 0)),
          y: Math.max(0, Math.min(window.innerHeight - 140, Number(parsed.y) || 0)),
        };
      } catch (_) { /* fall through */ }
    }
    if (window.innerWidth <= 720) {
      return { x: window.innerWidth - 60, y: window.innerHeight - 110 };
    }
    return { x: window.innerWidth - 220, y: window.innerHeight - 260 };
  });
  const posRef = useRef(pos);
  const [mini, setMini] = useState(() => {
    const saved = localStorage.getItem('pet.mini');
    if (saved != null) return saved === '1';
    return window.innerWidth <= 720;
  });
  const [peeking, setPeeking] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [hidden, setHidden] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatText, setChatText] = useState('');
  const [proactivePrompt, setProactivePrompt] = useState(null);
  const [gaze, setGaze] = useState({ x: 0, y: 0 });
  const [flail, setFlail] = useState(false);
  const [poke, setPoke] = useState(false);

  const petRef = useRef(null);
  const dragging = useRef(false);
  const dragMoved = useRef(false);
  const dragOffset = useRef({ x: 0, y: 0 });
  const lastActivity = useRef(Date.now());
  const speechTimer = useRef(null);
  const clickTimer = useRef(null);
  const clickCount = useRef(0);
  const longPressTimer = useRef(null);
  const longPressFired = useRef(false);
  const suppressClickOnce = useRef(false);
  const tempStateUntil = useRef(0);
  const quietUntil = useRef(Number(localStorage.getItem('pet.quietUntil') || 0));
  const proactiveSeen = useRef(new Set());
  const proactiveCount = useRef(0);

  useEffect(() => {
    return () => clearTimeout(longPressTimer.current);
  }, []);

  const getScene = () => {
    try {
      const scene = window.__petScene?.();
      return scene && typeof scene === 'object' ? scene : {};
    } catch {
      return {};
    }
  };

  const currentBehavior = () => SPECIES_BEHAVIOR[bodyKey] || SPECIES_BEHAVIOR.default;
  const idleDelay = () => {
    const freq = currentBehavior().idleFrequency;
    if (freq === 'high') return Math.round(IDLE_MONOLOGUE_MS * 0.72);
    if (freq === 'low') return Math.round(IDLE_MONOLOGUE_MS * 1.35);
    return IDLE_MONOLOGUE_MS;
  };
  const idleCooldown = () => {
    const freq = currentBehavior().idleFrequency;
    if (freq === 'high') return Math.round(IDLE_MONOLOGUE_COOLDOWN_MS * 0.75);
    if (freq === 'low') return Math.round(IDLE_MONOLOGUE_COOLDOWN_MS * 1.35);
    return IDLE_MONOLOGUE_COOLDOWN_MS;
  };
  const localLine = () => {
    const lines = currentBehavior().localLines || SPECIES_BEHAVIOR.default.localLines;
    return lines[Math.floor(Math.random() * lines.length)] || QUIPS[Math.floor(Math.random() * QUIPS.length)];
  };

  useEffect(() => {
    if (!profileOpen) return undefined;
    const onPointerDownCapture = (e) => {
      if (petRef.current?.contains(e.target)) return;
      setProfileOpen(false);
    };
    const onKeyDown = (e) => {
      if (e.key === 'Escape') setProfileOpen(false);
    };
    document.addEventListener('pointerdown', onPointerDownCapture, true);
    window.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('pointerdown', onPointerDownCapture, true);
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [profileOpen]);

  // Idle timeout → yawn → sleep
  useEffect(() => {
    const tick = setInterval(() => {
      if (dragging.current || mini) return;
      if (tempStateUntil.current > Date.now()) return;
      const elapsed = Date.now() - lastActivity.current;
      if (elapsed > 60000 && state !== 'sleeping' && state !== 'yawning') {
        setState('yawning');
        setTimeout(() => setState('sleeping'), 1800);
      } else if (elapsed > 2500 && state !== 'idle' && state !== 'sleeping' && state !== 'yawning' && tempStateUntil.current < Date.now()) {
        setState('idle');
      }
    }, 800);
    return () => clearInterval(tick);
  }, [state, mini]);

  // Frame animation
  useEffect(() => {
    const speed = state === 'typing' ? 180
      : state === 'building' ? 240
      : state === 'sleeping' ? 1600
      : 540;
    const id = setInterval(() => setFrame((f) => (f + 1) % 2), speed);
    return () => clearInterval(id);
  }, [state]);

  // Eye tracking + startle on mouse move
  useEffect(() => {
    const onMove = (e) => {
      markActivity();
      if (state === 'sleeping' || state === 'yawning') {
        setState('startled');
        tempStateUntil.current = Date.now() + 900;
        setTimeout(() => {
          if (tempStateUntil.current <= Date.now()) setState('idle');
        }, 900);
      }
      if (petRef.current) {
        const r = petRef.current.getBoundingClientRect();
        const cx = r.left + r.width / 2;
        const cy = r.top + r.height / 2;
        const dx = Math.max(-1, Math.min(1, (e.clientX - cx) / 300));
        const dy = Math.max(-1, Math.min(1, (e.clientY - cy) / 300));
        setGaze({ x: dx, y: dy });
      }
    };
    window.addEventListener('mousemove', onMove);
    return () => window.removeEventListener('mousemove', onMove);
  }, [state]);

  // Drag (pointer events for flick protection)
  const onPointerDown = (e) => {
    if (e.target.closest('.pet-panel, .pet-profile, .pet-panel-btn, .pet-ctl, .pet-chat')) return;
    if (profileOpen) {
      setProfileOpen(false);
      suppressClickOnce.current = true;
    }
    dragging.current = true;
    dragMoved.current = false;
    longPressFired.current = false;
    markActivity();
    if (state === 'sleeping' || state === 'yawning') setState('startled');
    const rect = petRef.current.getBoundingClientRect();
    dragOffset.current = { x: e.clientX - rect.left, y: e.clientY - rect.top };
    try { petRef.current.setPointerCapture(e.pointerId); } catch (_) { /* ignore */ }
    clearTimeout(longPressTimer.current);
    longPressTimer.current = setTimeout(() => {
      if (!dragging.current || dragMoved.current) return;
      longPressFired.current = true;
      dragging.current = false;
      setProfileOpen(true);
      setPanelOpen(false);
      setState('thinking');
      tempStateUntil.current = Date.now() + 1600;
      setTimeout(() => {
        if (tempStateUntil.current <= Date.now()) setState('idle');
      }, 1600);
    }, 650);
    e.preventDefault();
  };

  const onPointerMove = (e) => {
    if (!dragging.current) return;
    if (Math.abs(e.movementX) + Math.abs(e.movementY) > 1) {
      dragMoved.current = true;
      clearTimeout(longPressTimer.current);
    }
    const nx = Math.max(-40, Math.min(window.innerWidth - 120, e.clientX - dragOffset.current.x));
    const ny = Math.max(0, Math.min(window.innerHeight - 140, e.clientY - dragOffset.current.y));
    const next = { x: nx, y: ny };
    posRef.current = next;
    setPos(next);
  };

  const onPointerUp = (e) => {
    clearTimeout(longPressTimer.current);
    if (longPressFired.current) {
      longPressFired.current = false;
      try { petRef.current.releasePointerCapture(e.pointerId); } catch (_) { /* ignore */ }
      return;
    }
    if (!dragging.current) return;
    dragging.current = false;
    try { petRef.current.releasePointerCapture(e.pointerId); } catch (_) { /* ignore */ }
    const latestPos = posRef.current;
    if (latestPos.x > window.innerWidth - 160) {
      setMini(true);
      localStorage.setItem('pet.mini', '1');
      const next = { x: window.innerWidth - 60, y: latestPos.y };
      posRef.current = next;
      setPos(next);
    } else {
      setMini(false);
      localStorage.setItem('pet.mini', '0');
      localStorage.setItem('pet.pos', JSON.stringify(latestPos));
    }
    if (!dragMoved.current && !suppressClickOnce.current) handleClick();
    suppressClickOnce.current = false;
  };

  const handleClick = () => {
    clickCount.current += 1;
    clearTimeout(clickTimer.current);
    clickTimer.current = setTimeout(() => {
      const n = clickCount.current;
      clickCount.current = 0;
      if (n >= 4) {
        setFlail(true);
        setState('startled');
        tempStateUntil.current = Date.now() + 1200;
        setTimeout(() => { setFlail(false); setState('idle'); }, 1200);
      } else if (n === 2) {
        setPoke(true);
        tempStateUntil.current = Date.now() + 400;
        setTimeout(() => setPoke(false), 400);
        summonSpeech();
      } else {
        summonSpeech();
      }
    }, 260);
  };

  const streamAbort = useRef(null);
  const summoning = useRef(false);
  const nextIdleMonologueAt = useRef(Date.now() + IDLE_MONOLOGUE_MS);

  const markActivity = () => {
    const now = Date.now();
    lastActivity.current = now;
    nextIdleMonologueAt.current = now + idleDelay();
  };

  // Parse a single accumulated buffer for complete SSE frames; returns
  // { events: [...], rest: '...' } where rest is the unfinished tail.
  const parseSSE = (buf) => {
    const events = [];
    let rest = buf;
    while (true) {
      const i = rest.indexOf('\n\n');
      if (i < 0) break;
      const frame = rest.slice(0, i);
      rest = rest.slice(i + 2);
      for (const line of frame.split('\n')) {
        if (line.startsWith('data: ')) {
          try { events.push(JSON.parse(line.slice(6))); } catch { /* skip */ }
        }
      }
    }
    return { events, rest };
  };

  const summonSpeech = async (payloadOverride = null) => {
    if (summoning.current) return;
    summoning.current = true;
    clearTimeout(speechTimer.current);
    if (streamAbort.current) streamAbort.current.abort();
    streamAbort.current = new AbortController();
    setSpeech({ text: '', full: '', thinking: true });
    setState('thinking');
    tempStateUntil.current = Date.now() + 12000;

    let accumulated = '';
    let firstChunkReceived = false;
    let terminal = null; // 'done' | 'fallback' | 'rate_limited' | 'error'
    try {
      const payload = payloadOverride || buildSummonPayload({
        maxSelectionChars: 500,
        clientContext: getScene(),
      });
      const r = await fetch('/api/pet/summon/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: streamAbort.current.signal,
      });
      if (!r.ok || !r.body) throw new Error(`http ${r.status}`);
      const reader = r.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const { events, rest } = parseSSE(buffer);
        buffer = rest;
        for (const evt of events) {
          if (evt.type === 'chunk') {
            if (!firstChunkReceived) {
              firstChunkReceived = true;
              setState('happy');
              tempStateUntil.current = Date.now() + 12000;
            }
            accumulated += evt.text || '';
            setSpeech({ text: accumulated, full: accumulated, typing: true });
          } else if (evt.type === 'done') {
            terminal = 'done';
            setSpeech({ text: accumulated, full: accumulated, typing: false });
          } else if (evt.type === 'fallback' || evt.type === 'rate_limited') {
            terminal = evt.type;
            const txt = (evt.text || '').trim();
            accumulated = txt;
            setSpeech({ text: txt, full: txt, typing: false });
            if (evt.type === 'rate_limited') setState('error');
          } else if (evt.type === 'error') {
            terminal = 'error';
          }
          // 'meta' just informs of mode/species; nothing to render.
        }
      }
    } catch (e) {
      if (e?.name !== 'AbortError') {
        // network or http error before we got chunks — fall back to canned.
      }
    }

    if (!accumulated) {
      const text = localLine();
      accumulated = text;
      setSpeech({ text, full: text, typing: false });
    }
    if (terminal !== 'rate_limited') {
      setState('happy');
      tempStateUntil.current = Date.now() + 1400;
    }
    clearTimeout(speechTimer.current);
    speechTimer.current = setTimeout(() => setSpeech(null), 9000);
    nextIdleMonologueAt.current = Date.now() + idleCooldown();
    summoning.current = false;
  };

  const submitChat = (mode = null, message = chatText, intent = null) => {
    const text = (message || '').trim();
    setChatText('');
    setChatOpen(false);
    setProactivePrompt(null);
    if (!text && !mode) {
      summonSpeech();
      return;
    }
    const payload = buildSummonPayload({
      message: text,
      mode,
      intent,
      clientContext: getScene(),
      maxSelectionChars: 500,
      maxMessageChars: 500,
    });
    summonSpeech(payload);
  };

  const setQuietMode = () => {
    const until = Date.now() + QUIET_MODE_MS;
    quietUntil.current = until;
    try { localStorage.setItem('pet.quietUntil', String(until)); } catch { /* ignore */ }
    setProactivePrompt(null);
    setSpeech({ text: '安静 30 分钟。', full: '安静 30 分钟。', typing: false });
    clearTimeout(speechTimer.current);
    speechTimer.current = setTimeout(() => setSpeech(null), 5000);
  };

  useEffect(() => {
    if (!petEnabled || hidden || panelOpen || profileOpen || mini) return undefined;
    const id = setInterval(() => {
      const now = Date.now();
      if (summoning.current || speech) return;
      if (dragging.current || tempStateUntil.current > now) return;
      if (now - lastActivity.current < idleDelay()) return;
      if (now < nextIdleMonologueAt.current) return;
      nextIdleMonologueAt.current = now + idleCooldown();
      summonSpeech({ mode: 'idle_monologue' });
    }, 1000);
    return () => clearInterval(id);
  }, [petEnabled, hidden, panelOpen, profileOpen, mini, speech, bodyKey]);

  useEffect(() => {
    if (!petEnabled || hidden || panelOpen || profileOpen || mini || chatOpen) return undefined;
    const id = setInterval(() => {
      if (Date.now() < quietUntil.current) return;
      if (summoning.current || speech || proactivePrompt) return;
      if (proactiveCount.current >= 4) return;
      const scene = getScene();
      if (scene.page_type !== 'post') return;
      const behavior = currentBehavior();
      if ((behavior.proactiveLevel || 0) <= 0) return;
      if (scene.recent_action === 'reached_end' || Number(scene.read_progress || 0) >= 98) {
        const key = `done:${scene.post_id || scene.path || 'post'}`;
        if (!proactiveSeen.current.has(key)) {
          proactiveSeen.current.add(key);
          proactiveCount.current += 1;
          setProactivePrompt({
            key,
            text: '要我总结一下吗？',
            mode: 'article_finished',
            intent: 'article_finished',
          });
        }
        return;
      }
      if (
        (scene.visible_block_type === 'code' || scene.selection_kind === 'code')
        && Number(scene.dwell_seconds || 0) >= 20
      ) {
        const key = `code:${scene.post_id || scene.path || 'post'}:${scene.active_heading || ''}`;
        if (!proactiveSeen.current.has(key)) {
          proactiveSeen.current.add(key);
          proactiveCount.current += 1;
          setProactivePrompt({
            key,
            text: '要我解释这段吗？',
            mode: 'code_assist',
            intent: 'code_assist',
          });
        }
      }
    }, PROACTIVE_CHECK_MS);
    return () => clearInterval(id);
  }, [petEnabled, hidden, panelOpen, profileOpen, mini, chatOpen, speech, proactivePrompt, bodyKey]);

  // Public API: trigger states from blog events
  useEffect(() => {
    window.__pet = {
      trigger(s, duration = 2500) {
        if (!STATES[s]) return;
        setState(s);
        tempStateUntil.current = Date.now() + duration;
        markActivity();
        setTimeout(() => {
          if (tempStateUntil.current <= Date.now()) setState('idle');
        }, duration);
      },
    };
    const onKey = (e) => {
      if (e.metaKey && e.key === 'k') window.__pet.trigger('juggling', 1500);
      markActivity();
    };
    const onPostHover = (e) => {
      if (e.target.closest?.('.post-row')) window.__pet.trigger('thinking', 1200);
    };
    const onPostClick = (e) => {
      if (e.target.closest?.('.post-row')) window.__pet.trigger('typing', 1800);
    };
    window.addEventListener('keydown', onKey);
    document.addEventListener('mouseover', onPostHover);
    document.addEventListener('click', onPostClick);
    return () => {
      window.removeEventListener('keydown', onKey);
      document.removeEventListener('mouseover', onPostHover);
      document.removeEventListener('click', onPostClick);
    };
  }, [bodyKey]);

  if (!petEnabled) return null;

  if (hidden) {
    return (
      <button
        onClick={() => setHidden(false)}
        style={{
          position: 'fixed', bottom: 24, right: 24, zIndex: 80,
          padding: '8px 12px', border: `1px solid ${body.color}`,
          background: 'var(--bg-2)', color: body.color,
          fontFamily: "'JetBrains Mono', monospace", fontSize: 12,
          borderRadius: 20, cursor: 'pointer',
        }}
      >
        bring {bodyKey} back
      </button>
    );
  }

  const cfg = STATES[state] || STATES.idle;
  let eye = STATE_EYE[state] || '·';
  if (state === 'idle') {
    if (gaze.x < -0.3) eye = '◂';
    else if (gaze.x > 0.3) eye = '▸';
    else if (gaze.y < -0.3) eye = '°';
    else if (gaze.y > 0.3) eye = '.';
  }
  const sprite = renderSprite(body.frames[frame % body.frames.length], eye);
  const color = cfg.tint || body.color;

  const miniStyle = mini
    ? { left: window.innerWidth - (peeking ? 85 : 60), transition: 'left 0.2s ease' }
    : {};

  return (
    <div
      ref={petRef}
      className={`clawd-pet ${state} ${mini ? 'mini' : ''} ${flail ? 'flail' : ''} ${poke ? 'poke' : ''}`}
      style={{
        position: 'fixed',
        left: pos.x, top: pos.y,
        zIndex: 80,
        userSelect: 'none', touchAction: 'none',
        cursor: dragging.current ? 'grabbing' : 'grab',
        ...miniStyle,
        '--c': color,
      }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
      onMouseEnter={() => { if (mini) setPeeking(true); }}
      onMouseLeave={() => { if (mini) setPeeking(false); }}
    >
      {celebrate && createPortal(
        <div className="legendary-celebrate" style={{ '--c': SPECIES[celebrate]?.color || color }}>
          <span className="legendary-text">✦ legendary ✦</span>
          <span className="legendary-sub">{celebrate}</span>
          <span className="legendary-spark s1">✦</span>
          <span className="legendary-spark s2">✧</span>
          <span className="legendary-spark s3">✦</span>
          <span className="legendary-spark s4">✧</span>
          <span className="legendary-spark s5">✦</span>
          <span className="legendary-spark s6">✧</span>
        </div>,
        document.body,
      )}

      {!mini && !profileOpen && (
        <button
          type="button"
          className="pet-chat-toggle pet-ctl"
          title="chat with pet"
          onClick={(e) => {
            e.stopPropagation();
            setChatOpen((o) => !o);
            setPanelOpen(false);
            setProactivePrompt(null);
          }}
          onPointerDown={(e) => e.stopPropagation()}
          style={{ borderColor: color, color }}
        >
          ?
        </button>
      )}

      {chatOpen && !mini && !profileOpen && (
        <form
          className="pet-chat"
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => e.stopPropagation()}
          onSubmit={(e) => {
            e.preventDefault();
            submitChat();
          }}
          style={{ '--c': color }}
        >
          <input
            aria-label="message pet"
            value={chatText}
            maxLength={500}
            autoFocus
            onChange={(e) => setChatText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Escape') {
                e.preventDefault();
                setChatOpen(false);
                setChatText('');
              } else if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                submitChat();
              }
            }}
            placeholder="ask..."
            disabled={summoning.current}
          />
          <button type="submit" disabled={summoning.current} title="send to pet">↵</button>
          <button
            type="button"
            onClick={() => {
              setChatOpen(false);
              setChatText('');
            }}
            title="close chat"
          >×</button>
        </form>
      )}

      {proactivePrompt && !mini && !profileOpen && !chatOpen && (
        <button
          type="button"
          className="pet-proactive"
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => {
            e.stopPropagation();
            submitChat(proactivePrompt.mode, '', proactivePrompt.intent);
          }}
          style={{ '--c': color }}
        >
          {proactivePrompt.text}
        </button>
      )}

      {(() => {
        const bubbleText = speech?.text ?? hint?.text ?? '';
        const bubbleFull = speech?.full ?? hint?.text ?? '';
        const bubbleThinking = speech?.thinking;
        const isTyping = !!speech?.typing;
        const hasHiddenTail = bubbleFull.length > bubbleText.length;
        const bubbleVisible = (bubbleText || bubbleThinking) && !mini && !profileOpen;
        return bubbleVisible ? (
          <div className="clawd-bubble" style={{ borderColor: color, color }}>
            {bubbleThinking ? (
              <Dots />
            ) : (
              <span className="clawd-bubble-text">
                <span>{bubbleText}</span>
                {isTyping && <span className="clawd-caret">▍</span>}
                {hasHiddenTail && (
                  <span className="clawd-bubble-tail" aria-hidden="true">
                    {bubbleFull.slice(bubbleText.length)}
                  </span>
                )}
              </span>
            )}
            <span className="clawd-bubble-arrow" style={{ '--bc': color }} />
          </div>
        ) : null;
      })()}

      {cfg.icon && !mini && (
        <div className="clawd-icon" style={{ color }}>{cfg.icon}</div>
      )}

      {state === 'sleeping' && !mini && <div className="clawd-zzz">z z z</div>}

      <pre
        className="clawd-art"
        style={{
          color,
          textShadow: `0 0 10px color-mix(in oklab, ${color} 40%, transparent)`,
          animationDuration: `${cfg.bob}s`,
          filter: `drop-shadow(0 6px 14px color-mix(in oklab, ${color} 50%, transparent))`,
        }}
      >
        {sprite}
      </pre>

      <div
        className="clawd-shadow"
        style={{
          width: 70 + Math.abs(gaze.x) * 20,
          opacity: state === 'sleeping' ? 0.15 : 0.28,
        }}
      />

      {!mini && (
        <div
          className="clawd-strip"
          onClick={(e) => { e.stopPropagation(); setPanelOpen((o) => !o); setProfileOpen(false); }}
          onPointerDown={(e) => e.stopPropagation()}
          style={{ cursor: 'pointer' }}
          title="open settings"
        >
          <span className="clawd-dot" style={{ background: color }} />
          <span>{cfg.hint}</span>
          <span style={{ opacity: 0.5, marginLeft: 4 }}>⚙</span>
        </div>
      )}

      {profileOpen && (
        <div
          role="dialog"
          aria-label={`${bodyKey} profile`}
          className="pet-profile"
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => e.stopPropagation()}
          style={{ '--c': color }}
        >
          <button
            type="button"
            className="pet-profile-close"
            onClick={() => setProfileOpen(false)}
            aria-label="close pet profile"
          >×</button>
          <div className="pet-profile-head">
            <div>
              <div className="pet-profile-name">{bodyKey}</div>
              <div className="pet-profile-trait">{body.trait}</div>
            </div>
            <div className="pet-profile-rarity" style={{ color: RARITY_COLOR[body.rarity] }}>
              <span>{body.rarity}</span>
              <span aria-label={`${body.rarity} rarity`}>{rarityStars(body.rarity)}</span>
            </div>
          </div>
          <p className="pet-profile-desc">{body.description}</p>
          <div className="pet-profile-personality">
            <span>personality</span>
            <strong>{body.personality}</strong>
          </div>
          <div className="pet-profile-stats">
            {STAT_KEYS.map((stat) => (
              <div className="pet-stat" key={stat}>
                <span className="pet-stat-name">{stat}</span>
                <span className="pet-stat-track" aria-hidden="true">
                  <span className="pet-stat-fill" style={{ width: `${body.stats[stat]}%` }} />
                </span>
                <span className="pet-stat-value">{body.stats[stat]}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {panelOpen && !mini && createPortal(
        <div
          className="pet-panel"
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => e.stopPropagation()}
          style={{
            position: 'fixed', right: 20, bottom: 20, width: 260, maxWidth: 'calc(100vw - 40px)',
            boxSizing: 'border-box', background: 'var(--bg-2)', border: '1px solid var(--line)',
            borderRadius: 8, padding: 14, boxShadow: '0 16px 40px rgba(0,0,0,0.6)',
            display: 'flex', flexDirection: 'column', gap: 12, zIndex: 90,
            fontFamily: "'JetBrains Mono', monospace",
          }}
        >
          <button
            className="pet-panel-close"
            onClick={() => setPanelOpen(false)}
            style={{
              position: 'absolute', top: 6, right: 8, background: 'transparent', border: 0,
              color: 'var(--fg-4)', fontSize: 14, cursor: 'pointer', width: 18, height: 18,
            }}
          >×</button>

          <div className="pet-panel-row" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div
              className="pet-panel-label"
              style={{ fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--fg-4)' }}
            >your buddy</div>
            <div style={{
              display: 'flex', alignItems: 'baseline', gap: 8,
              padding: '6px 8px', borderRadius: 3,
              border: `1px solid ${body.rarity === 'legendary' ? '#f5b44c' : 'var(--line)'}`,
              background: `color-mix(in oklab, ${body.color} 12%, var(--bg-3))`,
            }}>
              <span style={{
                fontSize: 13, color: body.color, fontFamily: "'JetBrains Mono', monospace",
              }}>{bodyKey}</span>
              <span style={{
                fontSize: 9, letterSpacing: '0.1em', textTransform: 'uppercase',
                color: RARITY_COLOR[body.rarity],
              }}>{body.rarity}</span>
            </div>
            <div style={{ fontSize: 10, color: 'var(--fg-4)', lineHeight: 1.4 }}>
              your buddy is bound to your IP + browser — same combo always
              gets the same pet, no matter how many times you clear cache.
            </div>
          </div>

          <div className="pet-panel-row" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div
              className="pet-panel-label"
              style={{ fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--fg-4)' }}
            >test states</div>
            <div className="pet-panel-grid" style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {TEST_STATES.map((s) => (
                <button
                  key={s}
                  className={`pet-panel-chip ${state === s ? 'on' : ''}`}
                  onClick={() => window.__pet?.trigger(s, 4000)}
                  style={{
                    fontSize: 10, padding: '4px 7px',
                    border: `1px solid ${state === s ? 'var(--accent)' : 'var(--line)'}`,
                    borderRadius: 3, background: 'var(--bg-3)',
                    color: state === s ? 'var(--accent)' : 'var(--fg-3)',
                    cursor: 'pointer', whiteSpace: 'nowrap',
                    fontFamily: "'JetBrains Mono', monospace",
                  }}
                >{s}</button>
              ))}
            </div>
          </div>

          <div className="pet-panel-row" style={{ display: 'flex', gap: 4 }}>
            <button
              onClick={() => { submitChat('pet_care', '摸摸你', 'pet_care'); setPanelOpen(false); }}
              style={{
                flex: 1, fontSize: 10, padding: '6px 8px', border: '1px solid var(--line)',
                borderRadius: 3, background: 'var(--bg-3)', color: 'var(--fg-3)', cursor: 'pointer',
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >pet</button>
            <button
              onClick={() => { setQuietMode(); setPanelOpen(false); }}
              style={{
                flex: 1, fontSize: 10, padding: '6px 8px', border: '1px solid var(--line)',
                borderRadius: 3, background: 'var(--bg-3)', color: 'var(--fg-3)', cursor: 'pointer',
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >quiet</button>
          </div>

          <div className="pet-panel-row" style={{ display: 'flex', gap: 4 }}>
            <button
              onClick={() => { setMini(true); localStorage.setItem('pet.mini', '1'); setPanelOpen(false); }}
              style={{
                flex: 1, fontSize: 10, padding: '6px 8px', border: '1px solid var(--line)',
                borderRadius: 3, background: 'var(--bg-3)', color: 'var(--fg-3)', cursor: 'pointer',
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >→ mini mode</button>
            <button
              onClick={() => { setHidden(true); setPanelOpen(false); }}
              style={{
                flex: 1, fontSize: 10, padding: '6px 8px', border: '1px solid var(--line)',
                borderRadius: 3, background: 'var(--bg-3)', color: 'var(--fg-3)', cursor: 'pointer',
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >hide pet</button>
          </div>

          <button
            onClick={async () => {
              try {
                await fetch('/api/pet/forget', { method: 'POST' });
                localStorage.removeItem('pet.pos');
                localStorage.removeItem('pet.quietUntil');
                setSpeech({ text: '记忆已清。', full: '记忆已清。', typing: false });
              } catch {
                setSpeech({ text: '清理失败。', full: '清理失败。', typing: false });
              }
              setPanelOpen(false);
            }}
            style={{
              fontSize: 10, padding: '6px 8px', border: '1px solid var(--line)',
              borderRadius: 3, background: 'var(--bg-3)', color: 'var(--fg-3)', cursor: 'pointer',
              fontFamily: "'JetBrains Mono', monospace",
            }}
          >forget me</button>
        </div>,
        document.body,
      )}
    </div>
  );
}
