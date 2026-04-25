// Clawd-on-desk style pet behavior, ported to ASCII.
// Original ASCII sprites (not Anthropic's Clawd); state machine inspired by
// MIT-licensed rullerzhou-afk/clawd-on-desk.
const { useState: uP, useEffect: eP, useRef: rP, useMemo: mP } = React;

// ---------- Sprite library ----------
// Each pet has multi-frame animations for every state. Frames are monospace grids.
// Build a compact library — Capybara as the default star, plus a few alts.
const BODY = {
  capybara: {
    name: "Capybara", color: "#d4a574", rarity: "rare",
    // Per-state frames. We reuse body across states and swap eyes/mouth/arms.
    // Eyes markers: {L} {R} → replaced by eye glyphs based on state + cursor.
    // Mouth marker: {M} → replaced per state.
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
    name: "Cat", color: "#e0a96d", rarity: "common",
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
    name: "Dragon", color: "#ff7a5c", rarity: "legendary",
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
    name: "Octopus", color: "#b89cf0", rarity: "epic",
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
    name: "Robot", color: "#7cc7f0", rarity: "uncommon",
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
const BODY_ORDER = ["capybara","cat","dragon","octopus","robot"];

// State → eye / mouth glyphs + motion + speech overlay
const STATES = {
  idle:         { label: "idle",         eyes: ["o","o"], mouth: "__", bob: 2.8,  tint: null,        icon: null,   hint: "idle" },
  thinking:     { label: "thinking",     eyes: ["o","o"], mouth: "..", bob: 1.4,  tint: null,        icon: "?",    hint: "thinking…" },
  typing:       { label: "typing",       eyes: ["·","·"], mouth: "__", bob: 0.6,  tint: null,        icon: "⌨",    hint: "typing" },
  building:     { label: "building",     eyes: ["o","o"], mouth: "oo", bob: 0.4,  tint: "#f5b44c",   icon: "🔨",  hint: "building" },
  juggling:     { label: "juggling",     eyes: ["^","^"], mouth: "w", bob: 0.3,   tint: null,        icon: "●●", hint: "juggling agents" },
  conducting:   { label: "conducting",   eyes: ["^","^"], mouth: "w", bob: 0.3,   tint: "#c48cf5",   icon: "♫",   hint: "conducting" },
  error:        { label: "error",        eyes: ["x","x"], mouth: "o", bob: 0.5,   tint: "#ff5c5c",   icon: "!",   hint: "error" },
  happy:        { label: "happy",        eyes: ["^","^"], mouth: "v", bob: 1.2,   tint: "#7dbf8e",   icon: "✓",   hint: "done" },
  notification: { label: "notification", eyes: [">","<"], mouth: "o", bob: 0.8,   tint: "#f5b44c",   icon: "!",   hint: "notify" },
  sweeping:     { label: "sweeping",     eyes: ["-","-"], mouth: "_", bob: 0.8,   tint: null,        icon: "🧹",  hint: "sweeping" },
  carrying:     { label: "carrying",     eyes: ["o","o"], mouth: "_", bob: 0.8,   tint: null,        icon: "📦",  hint: "carrying" },
  sleeping:     { label: "sleeping",     eyes: ["-","-"], mouth: "_", bob: 0.4,   tint: null,        icon: "Z",   hint: "sleeping…" },
  yawning:      { label: "yawning",      eyes: [">","<"], mouth: "O", bob: 0.8,   tint: null,        icon: "~",   hint: "yawn…" },
  startled:     { label: "startled",     eyes: ["O","O"], mouth: "O", bob: 0.1,   tint: "#f5b44c",   icon: "!",   hint: "!" },
};

// Render a sprite by replacing {L}{R}{M} markers
function renderSprite(body, L, R, M) {
  return body
    .replaceAll("{L}", L)
    .replaceAll("{R}", R)
    .replaceAll("{M}", M);
}

// Deterministic hash (for rarity/stats if we extend later)
function fnv1a(str) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}

function ClawdPet() {
  const [bodyKey, setBodyKey] = uP(() => localStorage.getItem('pet.body') || 'capybara');
  const body = BODY[bodyKey] || BODY.capybara;
  const [state, setState] = uP('idle');
  const [frame, setFrame] = uP(0);
  const [speech, setSpeech] = uP(null);
  const [pos, setPos] = uP(() => {
    const saved = localStorage.getItem('pet.pos');
    if (saved) try { return JSON.parse(saved); } catch(e){}
    return { x: window.innerWidth - 220, y: window.innerHeight - 260 };
  });
  const [mini, setMini] = uP(() => localStorage.getItem('pet.mini') === '1');
  const [peeking, setPeeking] = uP(false);
  const [panelOpen, setPanelOpen] = uP(false);
  const [hidden, setHidden] = uP(false);
  const [gaze, setGaze] = uP({x:0, y:0});
  const [flail, setFlail] = uP(false);
  const [poke, setPoke] = uP(false);

  const petRef = rP(null);
  const dragging = rP(false);
  const dragMoved = rP(false);
  const dragOffset = rP({x:0, y:0});
  const lastActivity = rP(Date.now());
  const speechTimer = rP(null);
  const stateTimer = rP(null);
  const clickTimer = rP(null);
  const clickCount = rP(0);
  const tempStateUntil = rP(0);

  // --- Idle timeout → sleep sequence ---
  eP(() => {
    const tick = setInterval(() => {
      if (dragging.current || mini) return;
      if (tempStateUntil.current > Date.now()) return;
      const elapsed = Date.now() - lastActivity.current;
      if (elapsed > 60000 && state !== 'sleeping' && state !== 'yawning') {
        // sequence: yawn → sleep
        setState('yawning');
        setTimeout(() => setState('sleeping'), 1800);
      } else if (elapsed > 2500 && state !== 'idle' && state !== 'sleeping' && state !== 'yawning' && tempStateUntil.current < Date.now()) {
        setState('idle');
      }
    }, 800);
    return () => clearInterval(tick);
  }, [state, mini]);

  // --- Frame animation ---
  eP(() => {
    const cfg = STATES[state] || STATES.idle;
    const speed = state === 'typing' ? 180 : state === 'building' ? 240 : state === 'sleeping' ? 1600 : 540;
    const id = setInterval(() => setFrame(f => (f + 1) % 2), speed);
    return () => clearInterval(id);
  }, [state]);

  // --- Eye tracking + startle on mouse move ---
  eP(() => {
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
        const cx = r.left + r.width/2, cy = r.top + r.height/2;
        const dx = Math.max(-1, Math.min(1, (e.clientX - cx) / 300));
        const dy = Math.max(-1, Math.min(1, (e.clientY - cy) / 300));
        setGaze({x: dx, y: dy});
      }
    };
    window.addEventListener('mousemove', onMove);
    return () => window.removeEventListener('mousemove', onMove);
  }, [state]);

  // --- Drag (pointer events for flick protection) ---
  const onPointerDown = (e) => {
    if (e.target.closest('.pet-panel, .pet-panel-btn, .pet-ctl')) return;
    dragging.current = true;
    dragMoved.current = false;
    lastActivity.current = Date.now();
    if (state === 'sleeping' || state === 'yawning') setState('startled');
    const rect = petRef.current.getBoundingClientRect();
    dragOffset.current = { x: e.clientX - rect.left, y: e.clientY - rect.top };
    try { petRef.current.setPointerCapture(e.pointerId); } catch(_){}
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
    try { petRef.current.releasePointerCapture(e.pointerId); } catch(_){}
    // Check mini mode: dragged past right edge?
    if (pos.x > window.innerWidth - 160) {
      setMini(true); localStorage.setItem('pet.mini', '1');
      setPos(p => ({ x: window.innerWidth - 60, y: p.y }));
    } else {
      setMini(false); localStorage.setItem('pet.mini', '0');
      localStorage.setItem('pet.pos', JSON.stringify(pos));
    }
    if (!dragMoved.current) handleClick(e);
  };

  const handleClick = (e) => {
    clickCount.current++;
    clearTimeout(clickTimer.current);
    clickTimer.current = setTimeout(() => {
      const n = clickCount.current;
      clickCount.current = 0;
      if (n >= 4) {
        // flail
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
    setState('thinking'); tempStateUntil.current = Date.now() + 8000;
    const persona = {
      capybara:"a zen capybara lounging in hot logs",
      cat:"a sly cat that lives on HN",
      dragon:"an ancient dragon hoarding repos",
      octopus:"an 8-threaded octopus in async/await",
      robot:"a tiny robot that tails logs",
    }[bodyKey] || "a cheerful desktop pet";
    let text = null;
    try {
      if (window.claude?.complete) {
        const reply = await window.claude.complete(
          `You are a tiny ASCII desktop pet — ${persona}, living on 汪洋's blog (Chinese backend/AI engineer). ` +
          `User poked you. Reply ONE short playful line (max 10 words), mix English/Chinese naturally, no quotes/emoji.`
        );
        text = (reply||'').trim().replace(/^["'`]|["'`]$/g,'').slice(0,80);
      }
    } catch(_){}
    if (!text) text = ["meow.","purr…","have you committed?","seg loss ok ✓","*yawn*"][Math.floor(Math.random()*5)];
    setSpeech({ text });
    setState('happy'); tempStateUntil.current = Date.now() + 1400;
    clearTimeout(speechTimer.current);
    speechTimer.current = setTimeout(() => setSpeech(null), 8000);
  };

  // --- Public API: trigger states from blog events ---
  eP(() => {
    window.__pet = {
      trigger(s, duration = 2500) {
        if (!STATES[s]) return;
        setState(s); tempStateUntil.current = Date.now() + duration;
        lastActivity.current = Date.now();
        setTimeout(() => {
          if (tempStateUntil.current <= Date.now()) setState('idle');
        }, duration);
      },
      setBody: setBodyKey,
    };
    // Hook a few blog-level events
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
          position:'fixed', bottom:24, right:24, zIndex:80,
          padding:'8px 12px', border:`1px solid ${body.color}`,
          background:'var(--bg-2)', color:body.color,
          fontFamily:"'JetBrains Mono', monospace", fontSize:12,
          borderRadius:20, cursor:'pointer',
        }}
      >bring {body.name.toLowerCase()} back</button>
    );
  }

  const cfg = STATES[state] || STATES.idle;
  // Gaze-modulated eyes: shift glyph based on cursor direction (idle only)
  let L = cfg.eyes[0], R = cfg.eyes[1];
  if (state === 'idle') {
    if (gaze.x < -0.3) { L = R = '◂'; }
    else if (gaze.x > 0.3) { L = R = '▸'; }
    else if (gaze.y < -0.3) { L = R = '°'; }
    else if (gaze.y > 0.3) { L = R = '.'; }
  }
  const M = cfg.mouth;
  const sprite = renderSprite(body.base[frame], L, R, M);

  const miniStyle = mini ? {
    left: window.innerWidth - (peeking ? 85 : 60),
    transition: 'left 0.2s ease',
  } : {};

  const color = cfg.tint || body.color;

  return (
    <div
      ref={petRef}
      className={`clawd-pet ${state} ${mini?'mini':''} ${flail?'flail':''} ${poke?'poke':''}`}
      style={{
        position:'fixed',
        left: pos.x, top: pos.y,
        zIndex: 80,
        userSelect:'none', touchAction:'none',
        cursor: dragging.current ? 'grabbing':'grab',
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
      {/* Speech bubble */}
      {speech && !mini && (
        <div className="clawd-bubble" style={{borderColor: color, color}}>
          <span>{speech.thinking ? <Dots/> : speech.text}</span>
          <span className="clawd-bubble-arrow" style={{'--bc': color}}/>
        </div>
      )}

      {/* State icon badge (thought bubble, hammer, etc.) */}
      {cfg.icon && !mini && (
        <div className="clawd-icon" style={{color}}>{cfg.icon}</div>
      )}

      {/* Sleep Z's */}
      {state === 'sleeping' && !mini && <div className="clawd-zzz">z z z</div>}

      {/* Sprite */}
      <pre
        className="clawd-art"
        style={{
          color,
          textShadow: `0 0 10px color-mix(in oklab, ${color} 40%, transparent)`,
          animationDuration: cfg.bob + 's',
          filter: `drop-shadow(0 6px 14px color-mix(in oklab, ${color} 50%, transparent))`,
        }}
      >{sprite}</pre>

      {/* Shadow */}
      <div className="clawd-shadow" style={{
        width: 70 + Math.abs(gaze.x)*20,
        opacity: state === 'sleeping' ? 0.15 : 0.28,
      }}/>

      {/* State strip with settings trigger */}
      {!mini && (
        <div
          className="clawd-strip"
          onClick={(e) => { e.stopPropagation(); setPanelOpen(o => !o); }}
          onPointerDown={(e) => e.stopPropagation()}
          style={{cursor:'pointer'}}
          title="open settings"
        >
          <span className="clawd-dot" style={{background: color}}/>
          <span>{cfg.hint}</span>
          <span style={{opacity:0.5, marginLeft:4}}>⚙</span>
        </div>
      )}

      {panelOpen && !mini && ReactDOM.createPortal(
        <div className="pet-panel" onPointerDown={(e)=>e.stopPropagation()} onClick={(e)=>e.stopPropagation()}
          style={{
            position:'fixed', right:20, bottom:20, width:260, maxWidth:'calc(100vw - 40px)',
            boxSizing:'border-box', background:'var(--bg-2)', border:'1px solid var(--line)',
            borderRadius:8, padding:14, boxShadow:'0 16px 40px rgba(0,0,0,0.6)',
            display:'flex', flexDirection:'column', gap:12, zIndex:90,
            fontFamily:"'JetBrains Mono', monospace",
          }}>
          <button className="pet-panel-close" onClick={()=>setPanelOpen(false)}
            style={{position:'absolute', top:6, right:8, background:'transparent', border:0, color:'var(--fg-4)', fontSize:14, cursor:'pointer', width:18, height:18}}>×</button>
          <div className="pet-panel-row" style={{display:'flex', flexDirection:'column', gap:6}}>
            <div className="pet-panel-label" style={{fontSize:9, letterSpacing:'0.12em', textTransform:'uppercase', color:'var(--fg-4)'}}>species</div>
            <div className="pet-panel-grid" style={{display:'flex', flexWrap:'wrap', gap:4}}>
              {BODY_ORDER.map(k => (
                <button key={k}
                  className={`pet-panel-chip ${k===bodyKey?'on':''}`}
                  onClick={() => { setBodyKey(k); localStorage.setItem('pet.body', k); }}
                  style={{'--c': BODY[k].color, fontSize:10, padding:'4px 7px', border:'1px solid var(--line)', borderRadius:3, background: k===bodyKey?`color-mix(in oklab, ${BODY[k].color} 14%, var(--bg-3))`:'var(--bg-3)', color: k===bodyKey?BODY[k].color:'var(--fg-3)', cursor:'pointer', whiteSpace:'nowrap', fontFamily:"'JetBrains Mono', monospace"}}
                >{BODY[k].name.toLowerCase()}</button>
              ))}
            </div>
          </div>
          <div className="pet-panel-row" style={{display:'flex', flexDirection:'column', gap:6}}>
            <div className="pet-panel-label" style={{fontSize:9, letterSpacing:'0.12em', textTransform:'uppercase', color:'var(--fg-4)'}}>test states</div>
            <div className="pet-panel-grid" style={{display:'flex', flexWrap:'wrap', gap:4}}>
              {["idle","thinking","typing","building","juggling","conducting","error","happy","notification","sweeping","carrying","sleeping"].map(s => (
                <button key={s} className={`pet-panel-chip ${state===s?'on':''}`}
                  onClick={() => window.__pet.trigger(s, 4000)}
                  style={{fontSize:10, padding:'4px 7px', border:`1px solid ${state===s?'var(--accent)':'var(--line)'}`, borderRadius:3, background:'var(--bg-3)', color: state===s?'var(--accent)':'var(--fg-3)', cursor:'pointer', whiteSpace:'nowrap', fontFamily:"'JetBrains Mono', monospace"}}>{s}</button>
              ))}
            </div>
          </div>
          <div className="pet-panel-row" style={{display:'flex', gap:4}}>
            <button onClick={()=>{setMini(true);localStorage.setItem('pet.mini','1');setPanelOpen(false);}}
              style={{flex:1, fontSize:10, padding:'6px 8px', border:'1px solid var(--line)', borderRadius:3, background:'var(--bg-3)', color:'var(--fg-3)', cursor:'pointer', fontFamily:"'JetBrains Mono', monospace"}}>→ mini mode</button>
            <button onClick={()=>{setHidden(true);setPanelOpen(false);}}
              style={{flex:1, fontSize:10, padding:'6px 8px', border:'1px solid var(--line)', borderRadius:3, background:'var(--bg-3)', color:'var(--fg-3)', cursor:'pointer', fontFamily:"'JetBrains Mono', monospace"}}>hide pet</button>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}

function Dots() {
  const [n, setN] = uP(1);
  eP(() => { const id = setInterval(()=>setN(x=>(x%3)+1), 350); return ()=>clearInterval(id); }, []);
  return <span>{'.'.repeat(n)}</span>;
}

window.AsciiPet = ClawdPet;
