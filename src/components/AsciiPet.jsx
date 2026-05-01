// Clawd-on-desk style ASCII desktop pet.
// State machine inspired by MIT-licensed rullerzhou-afk/clawd-on-desk;
// sprites are original.
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { buildSummonPayload } from './pet/payload.js';

const BODY = {
  capybara: {
    name: 'Capybara', color: '#d4a574', rarity: 'rare',
    base: [
`   _________
  /  {L}   {R}  \\
 |    {M}     |
  \\_________/
    U     U`,
`   _________
  /  {L}   {R}  \\
 |    {M}     |
  \\_________/
    U     U`,
    ],
  },
  cat: {
    name: 'Cat', color: '#e0a96d', rarity: 'common',
    base: [
`   /\\___/\\
  (  {L} {R}  )
  (   {M}   )
   \\_____/
    U   U`,
`   /\\___/\\
  (  {L} {R}  )
  (   {M}   )
   \\_____/
    U   U`,
    ],
  },
  dragon: {
    name: 'Dragon', color: '#ff7a5c', rarity: 'legendary',
    base: [
`   /\\___/\\
  ( {L}   {R} )
  (    {M}   )
  ~\\_______/~
      ^^^`,
`   /\\___/\\
  ( {L}   {R} )
  (    {M}   )
  ~\\_______/~
      ^^^`,
    ],
  },
  octopus: {
    name: 'Octopus', color: '#b89cf0', rarity: 'epic',
    base: [
`   _______
  /  {L} {R}  \\
  \\   {M}   /
   \\|||||/
  / | | | \\`,
`   _______
  /  {L} {R}  \\
  \\   {M}   /
   \\|||||/
 /  |  |  |  \\`,
    ],
  },
  robot: {
    name: 'Robot', color: '#7cc7f0', rarity: 'uncommon',
    base: [
` .-------.
 |  {L} {R}  |
 |   {M}   |
 \`-------'
   ||  ||`,
` .-------.
 |  {L} {R}  |
 |   {M}   |
 \`-------'
   ||  ||`,
    ],
  },
};

const BODY_ORDER = ['capybara', 'cat', 'dragon', 'octopus', 'robot'];

const STATES = {
  idle:         { label: 'idle',         eyes: ['o','o'], mouth: '__', bob: 2.8, tint: null,      icon: null,  hint: 'idle' },
  thinking:     { label: 'thinking',     eyes: ['o','o'], mouth: '..', bob: 1.4, tint: null,      icon: '?',   hint: 'thinking…' },
  typing:       { label: 'typing',       eyes: ['·','·'], mouth: '__', bob: 0.6, tint: null,      icon: '⌨',   hint: 'typing' },
  building:     { label: 'building',     eyes: ['o','o'], mouth: 'oo', bob: 0.4, tint: '#f5b44c', icon: '🔨',  hint: 'building' },
  juggling:     { label: 'juggling',     eyes: ['^','^'], mouth: 'w',  bob: 0.3, tint: null,      icon: '●●',  hint: 'juggling agents' },
  conducting:   { label: 'conducting',   eyes: ['^','^'], mouth: 'w',  bob: 0.3, tint: '#c48cf5', icon: '♫',   hint: 'conducting' },
  error:        { label: 'error',        eyes: ['x','x'], mouth: 'o',  bob: 0.5, tint: '#ff5c5c', icon: '!',   hint: 'error' },
  happy:        { label: 'happy',        eyes: ['^','^'], mouth: 'v',  bob: 1.2, tint: '#7dbf8e', icon: '✓',   hint: 'done' },
  notification: { label: 'notification', eyes: ['>','<'], mouth: 'o',  bob: 0.8, tint: '#f5b44c', icon: '!',   hint: 'notify' },
  sweeping:     { label: 'sweeping',     eyes: ['-','-'], mouth: '_',  bob: 0.8, tint: null,      icon: '🧹',  hint: 'sweeping' },
  carrying:     { label: 'carrying',     eyes: ['o','o'], mouth: '_',  bob: 0.8, tint: null,      icon: '📦',  hint: 'carrying' },
  sleeping:     { label: 'sleeping',     eyes: ['-','-'], mouth: '_',  bob: 0.4, tint: null,      icon: 'Z',   hint: 'sleeping…' },
  yawning:      { label: 'yawning',      eyes: ['>','<'], mouth: 'O',  bob: 0.8, tint: null,      icon: '~',   hint: 'yawn…' },
  startled:     { label: 'startled',     eyes: ['O','O'], mouth: 'O',  bob: 0.1, tint: '#f5b44c', icon: '!',   hint: '!' },
};

const TEST_STATES = [
  'idle','thinking','typing','building','juggling','conducting',
  'error','happy','notification','sweeping','carrying','sleeping',
];

const PERSONA = {
  capybara: 'a zen capybara lounging in hot logs',
  cat: 'a sly cat that lives on HN',
  dragon: 'an ancient dragon hoarding repos',
  octopus: 'an 8-threaded octopus in async/await',
  robot: 'a tiny robot that tails logs',
};

const QUIPS = ['meow.', 'purr…', 'have you committed?', 'seg loss ok ✓', '*yawn*'];

function renderSprite(body, L, R, M) {
  return body.replaceAll('{L}', L).replaceAll('{R}', R).replaceAll('{M}', M);
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
  const [bodyKey, setBodyKey] = useState(() => localStorage.getItem('pet.body') || 'capybara');
  const body = BODY[bodyKey] || BODY.capybara;
  const [state, setState] = useState('idle');
  const [frame, setFrame] = useState(0);
  const [speech, setSpeech] = useState(null);
  const [pos, setPos] = useState(() => {
    const saved = localStorage.getItem('pet.pos');
    if (saved) {
      try { return JSON.parse(saved); } catch (_) { /* fall through */ }
    }
    return { x: window.innerWidth - 220, y: window.innerHeight - 260 };
  });
  const [mini, setMini] = useState(() => localStorage.getItem('pet.mini') === '1');
  const [peeking, setPeeking] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const [hidden, setHidden] = useState(false);
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
  const tempStateUntil = useRef(0);

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
      lastActivity.current = Date.now();
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
    if (e.target.closest('.pet-panel, .pet-panel-btn, .pet-ctl')) return;
    dragging.current = true;
    dragMoved.current = false;
    lastActivity.current = Date.now();
    if (state === 'sleeping' || state === 'yawning') setState('startled');
    const rect = petRef.current.getBoundingClientRect();
    dragOffset.current = { x: e.clientX - rect.left, y: e.clientY - rect.top };
    try { petRef.current.setPointerCapture(e.pointerId); } catch (_) { /* ignore */ }
    e.preventDefault();
  };

  const onPointerMove = (e) => {
    if (!dragging.current) return;
    if (Math.abs(e.movementX) + Math.abs(e.movementY) > 1) dragMoved.current = true;
    const nx = Math.max(-40, Math.min(window.innerWidth - 120, e.clientX - dragOffset.current.x));
    const ny = Math.max(0, Math.min(window.innerHeight - 140, e.clientY - dragOffset.current.y));
    setPos({ x: nx, y: ny });
  };

  const onPointerUp = (e) => {
    if (!dragging.current) return;
    dragging.current = false;
    try { petRef.current.releasePointerCapture(e.pointerId); } catch (_) { /* ignore */ }
    if (pos.x > window.innerWidth - 160) {
      setMini(true);
      localStorage.setItem('pet.mini', '1');
      setPos((p) => ({ x: window.innerWidth - 60, y: p.y }));
    } else {
      setMini(false);
      localStorage.setItem('pet.mini', '0');
      localStorage.setItem('pet.pos', JSON.stringify(pos));
    }
    if (!dragMoved.current) handleClick();
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

  const summonSpeech = async () => {
    clearTimeout(speechTimer.current);
    setSpeech({ text: '…', thinking: true });
    setState('thinking');
    tempStateUntil.current = Date.now() + 8000;
    let text = null;
    try {
      const payload = buildSummonPayload(500);
      const r = await fetch('/api/pet/summon', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (r.ok) {
        const j = await r.json();
        text = (j.quip || '').trim().slice(0, 80);
      }
    } catch (_) { /* fall through to canned reply */ }
    if (!text) text = QUIPS[Math.floor(Math.random() * QUIPS.length)];
    setSpeech({ text });
    setState('happy');
    tempStateUntil.current = Date.now() + 1400;
    clearTimeout(speechTimer.current);
    speechTimer.current = setTimeout(() => setSpeech(null), 8000);
  };

  // Public API: trigger states from blog events
  useEffect(() => {
    window.__pet = {
      trigger(s, duration = 2500) {
        if (!STATES[s]) return;
        setState(s);
        tempStateUntil.current = Date.now() + duration;
        lastActivity.current = Date.now();
        setTimeout(() => {
          if (tempStateUntil.current <= Date.now()) setState('idle');
        }, duration);
      },
      setBody: setBodyKey,
    };
    const onKey = (e) => {
      if (e.metaKey && e.key === 'k') window.__pet.trigger('juggling', 1500);
      lastActivity.current = Date.now();
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
        bring {body.name.toLowerCase()} back
      </button>
    );
  }

  const cfg = STATES[state] || STATES.idle;
  let L = cfg.eyes[0];
  let R = cfg.eyes[1];
  if (state === 'idle') {
    if (gaze.x < -0.3) { L = '◂'; R = '◂'; }
    else if (gaze.x > 0.3) { L = '▸'; R = '▸'; }
    else if (gaze.y < -0.3) { L = '°'; R = '°'; }
    else if (gaze.y > 0.3) { L = '.'; R = '.'; }
  }
  const M = cfg.mouth;
  const sprite = renderSprite(body.base[frame], L, R, M);
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
      {(() => {
        const bubbleText = speech?.text || hint?.text;
        const bubbleThinking = speech?.thinking;
        return bubbleText && !mini ? (
          <div className="clawd-bubble" style={{ borderColor: color, color }}>
            <span>{bubbleThinking ? <Dots /> : bubbleText}</span>
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
          onClick={(e) => { e.stopPropagation(); setPanelOpen((o) => !o); }}
          onPointerDown={(e) => e.stopPropagation()}
          style={{ cursor: 'pointer' }}
          title="open settings"
        >
          <span className="clawd-dot" style={{ background: color }} />
          <span>{cfg.hint}</span>
          <span style={{ opacity: 0.5, marginLeft: 4 }}>⚙</span>
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
            >species</div>
            <div className="pet-panel-grid" style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {BODY_ORDER.map((k) => (
                <button
                  key={k}
                  className={`pet-panel-chip ${k === bodyKey ? 'on' : ''}`}
                  onClick={() => { setBodyKey(k); localStorage.setItem('pet.body', k); }}
                  style={{
                    '--c': BODY[k].color,
                    fontSize: 10, padding: '4px 7px', border: '1px solid var(--line)',
                    borderRadius: 3,
                    background: k === bodyKey ? `color-mix(in oklab, ${BODY[k].color} 14%, var(--bg-3))` : 'var(--bg-3)',
                    color: k === bodyKey ? BODY[k].color : 'var(--fg-3)',
                    cursor: 'pointer', whiteSpace: 'nowrap',
                    fontFamily: "'JetBrains Mono', monospace",
                  }}
                >{BODY[k].name.toLowerCase()}</button>
              ))}
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
        </div>,
        document.body,
      )}
    </div>
  );
}
