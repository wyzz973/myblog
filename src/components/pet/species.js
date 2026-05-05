// Imported from dead1786/buddy-skin-editor (MIT). 18 templates verbatim.
// Each species: 3 frames × 5 lines × 12 chars; `{E}` marks eye positions.
// Lines padded to exactly 12 chars after {E}→X substitution (trailing spaces adjusted).

export const RARITY_ORDER = ['common', 'uncommon', 'rare', 'epic', 'legendary'];

export const RARITY_COLOR = {
  common:    '#9aa6b3',
  uncommon:  '#7dbf8e',
  rare:      '#5c9ddc',
  epic:      '#b89cf0',
  legendary: '#f5b44c',
};

export const RARITY_STARS = {
  common: '★',
  uncommon: '★★',
  rare: '★★★',
  epic: '★★★★',
  legendary: '★★★★★',
};

export const STAT_KEYS = ['debugging', 'patience', 'chaos', 'wisdom', 'snark'];

const RARITY_STAT_BASE = {
  common:    { debugging: 42, patience: 64, chaos: 30, wisdom: 38, snark: 24 },
  uncommon:  { debugging: 55, patience: 58, chaos: 38, wisdom: 52, snark: 34 },
  rare:      { debugging: 68, patience: 50, chaos: 52, wisdom: 62, snark: 48 },
  epic:      { debugging: 78, patience: 44, chaos: 66, wisdom: 72, snark: 58 },
  legendary: { debugging: 88, patience: 40, chaos: 80, wisdom: 84, snark: 72 },
};

const PET_PROFILES = {
  duck:      { trait: 'rubber debugger', personality: 'Cheerful, literal, and suspicious of silent failures.', description: 'A tiny desk duck that listens first and quacks only when a bug is obvious.', stats: { patience: 78, snark: 12 } },
  goose:     { trait: 'strict reviewer', personality: 'Loud, protective, and impossible to ignore.', description: 'Guards the page like a build gate and honks at vague requirements.', stats: { debugging: 58, chaos: 55, snark: 50 } },
  blob:      { trait: 'soft buffer', personality: 'Calm, squishy, and good at absorbing messy context.', description: 'Turns scattered thoughts into one small, usable next step.', stats: { patience: 82, chaos: 18 } },
  cat:       { trait: 'terminal familiar', personality: 'Curious, picky, and quietly helpful when it feels like it.', description: 'A classic coding companion with sharp eyes and selective affection.', stats: { debugging: 62, snark: 44 } },
  rabbit:    { trait: 'quick scanner', personality: 'Fast, gentle, and easily distracted by edge cases.', description: 'Hops through drafts and catches tiny inconsistencies before they multiply.', stats: { debugging: 56, chaos: 42 } },
  penguin:   { trait: 'release keeper', personality: 'Orderly, cool-headed, and fond of clean deploys.', description: 'Keeps its feathers neat and its checklists shorter than they look.', stats: { patience: 72, wisdom: 68 } },
  owl:       { trait: 'night analyst', personality: 'Quiet, observant, and annoyingly right after midnight.', description: 'Watches the whole code path before blinking once.', stats: { wisdom: 82, snark: 42 } },
  turtle:    { trait: 'steady shipper', personality: 'Slow, stubborn, and deeply resistant to panic.', description: 'Prefers durable fixes, small diffs, and migrations that can be explained.', stats: { patience: 88, chaos: 14 } },
  capybara:  { trait: 'team mediator', personality: 'Unbothered, warm, and useful during ambiguous product debates.', description: 'Sits beside hard tradeoffs until they stop looking dramatic.', stats: { patience: 86, snark: 18 } },
  mushroom:  { trait: 'spore profiler', personality: 'Odd, patient, and quietly excellent at finding hidden growth.', description: 'Finds patterns in dark corners and leaves tiny notes behind.', stats: { wisdom: 70, chaos: 58 } },
  ghost:     { trait: 'regression haunt', personality: 'Playful, elusive, and obsessed with bugs that came back.', description: 'Floats through old assumptions and rattles the flaky tests.', stats: { debugging: 74, chaos: 70 } },
  snail:     { trait: 'latency oracle', personality: 'Methodical, dry, and never rushed by a progress bar.', description: 'Measures twice, crawls once, and still reaches the root cause.', stats: { patience: 92, wisdom: 76 } },
  cactus:    { trait: 'boundary guard', personality: 'Prickly, concise, and excellent at saying no.', description: 'Protects APIs, scopes, and personal space with the same energy.', stats: { patience: 46, snark: 70 } },
  chonk:     { trait: 'cache warmer', personality: 'Cozy, loyal, and very serious about snack breaks.', description: 'Stabilizes the room and occasionally sits on over-engineered ideas.', stats: { patience: 74, snark: 38 } },
  octopus:   { trait: 'parallel thinker', personality: 'Clever, restless, and always holding three contexts at once.', description: 'Juggles options, traces data flow, and still has an arm free for notes.', stats: { debugging: 86, chaos: 74 } },
  jellyfish: { trait: 'signal drifter', personality: 'Elegant, weird, and lightly judgmental about bad abstractions.', description: 'Glows when the architecture is clean and stings when it is not.', stats: { wisdom: 84, snark: 76 } },
  axolotl:   { trait: 'recovery mode', personality: 'Hopeful, resilient, and strangely good at undoing damage.', description: 'Regenerates broken flows from the smallest surviving invariant.', stats: { patience: 72, chaos: 64 } },
  robot:     { trait: 'lint engine', personality: 'Precise, tireless, and allergic to inconsistent formatting.', description: 'Runs on structured inputs, crisp errors, and exactly one source of truth.', stats: { debugging: 92, snark: 54 } },
  dragon:    { trait: 'prod firekeeper', personality: 'Proud, intense, and happiest near difficult launches.', description: 'Breathes controlled fire at blockers and hoards useful logs.', stats: { debugging: 96, chaos: 90 } },
  phoenix:   { trait: 'rollback rebirth', personality: 'Dramatic, optimistic, and excellent after incidents.', description: 'Turns failed deploys into cleaner release rituals.', stats: { wisdom: 92, chaos: 86 } },
  fox:       { trait: 'clever scout', personality: 'Sharp, sly, and quick to spot the shortcut that is actually safe.', description: 'Sneaks through edge cases and returns with the missing assumption.', stats: { debugging: 90, snark: 82 } },
  shiba:     { trait: 'approval gate', personality: 'Confident, expressive, and unconvinced by vague success metrics.', description: 'Barks once for unclear acceptance criteria and twice for flaky demos.', stats: { snark: 88, patience: 34 } },
  mochi:     { trait: 'sweet stabilizer', personality: 'Soft, cheerful, and surprisingly strict about polish.', description: 'Makes rough interactions feel finished without making a fuss.', stats: { patience: 76, wisdom: 78 } },
  panda:     { trait: 'calm operator', personality: 'Gentle, sleepy, and very hard to shake during outages.', description: 'Reads the dashboard slowly and finds the one number that matters.', stats: { patience: 90, wisdom: 88 } },
  hamster:   { trait: 'tiny optimizer', personality: 'Busy, bright-eyed, and prone to over-indexing on details.', description: 'Stores small improvements for later and occasionally finds a big one.', stats: { debugging: 84, chaos: 76 } },
  bee:       { trait: 'workflow pollinator', personality: 'Energetic, social, and obsessed with moving useful context around.', description: 'Connects ideas, comments, and TODOs until the whole garden ships.', stats: { chaos: 82, patience: 52 } },
  otter:     { trait: 'playful debugger', personality: 'Inventive, mischievous, and happiest with a failing repro.', description: 'Plays with the problem until the root cause floats up.', stats: { debugging: 94, snark: 80 } },
};

function withProfile(key, species) {
  const profile = PET_PROFILES[key] || {};
  const baseStats = RARITY_STAT_BASE[species.rarity] || RARITY_STAT_BASE.common;
  return {
    ...species,
    trait: profile.trait || 'desk companion',
    personality: profile.personality || 'Curious, compact, and tuned for quiet help.',
    description: profile.description || `A ${species.rarity} buddy assigned to this visitor.`,
    stats: { ...baseStats, ...(profile.stats || {}) },
  };
}

export function rarityStars(rarity) {
  return RARITY_STARS[rarity] || RARITY_STARS.common;
}

const SPECIES_BASE = {
  duck: {
    rarity: 'common', color: '#f5d44c',
    frames: [
      ["            ","    __      ","  <({E} )___  ","   (  ._>   ","    `--´    "],
      ["            ","    __      ","  <({E} )___  ","   (  ._>   ","    `--´~   "],
      ["            ","    __      ","  <({E} )___  ","   (  .__>  ","    `--´    "],
    ],
  },
  goose: {
    rarity: 'common', color: '#e8e8e8',
    frames: [
      ["            ","     ({E}>    ","     ||     ","   _(__)_   ","    ^^^^    "],
      ["            ","    ({E}>     ","     ||     ","   _(__)_   ","    ^^^^    "],
      ["            ","     ({E}>>   ","     ||     ","   _(__)_   ","    ^^^^    "],
    ],
  },
  blob: {
    rarity: 'common', color: '#7dd3a4',
    frames: [
      ["            ","   .----.   ","  ( {E}  {E} )  ","  (      )  ","   `----´   "],
      ["            ","  .------.  "," (  {E}  {E}  ) "," (        ) ","  `------´  "],
      ["            ","    .--.    ","   ({E}  {E})   ","   (    )   ","    `--´    "],
    ],
  },
  cat: {
    rarity: 'common', color: '#e0a96d',
    frames: [
      // cat line4 source is 13 chars; trimmed 1 trailing space to reach 12
      ["            ","   /\\__/\\   ","  ( {E}  {E} )  ","  (  ω   )  ",'  (")__(")  '],
      ["            ","   /\\__/\\   ","  ( {E}  {E} )  ","  (  ω   )  ",'  (")__(")~ '],
      ["            ","   /\\--/\\   ","  ( {E}  {E} )  ","  (  ω   )  ",'  (")__(")  '],
    ],
  },
  rabbit: {
    rarity: 'common', color: '#f0d8e0',
    frames: [
      ["            ","   (\\__/)   ","  ( {E}  {E} )  "," =(  ..  )= ",'  (")__(")  '],
      ["            ","   (|__/)   ","  ( {E}  {E} )  "," =(  ..  )= ",'  (")__(")  '],
      ["            ","   (\\__/)   ","  ( {E}  {E} )  "," =( .  . )= ",'  (")__(")  '],
    ],
  },
  penguin: {
    rarity: 'uncommon', color: '#5c7ec4',
    frames: [
      ["            "," .-o-OO-o-. ","(__________)","   |{E}  {E}|   ","   |____|   "],
      ["            "," .-O-oo-O-. ","(__________)","   |{E}  {E}|   ","   |____|   "],
      ["   . o  .   "," .-o-OO-o-. ","(__________)","   |{E}  {E}|   ","   |____|   "],
    ],
  },
  owl: {
    rarity: 'uncommon', color: '#a89060',
    frames: [
      ["            ","   /\\  /\\   ","  (({E})({E}))  ","  (  ><  )  ","   `----´   "],
      ["            ","   /\\  /\\   ","  (({E})({E}))  ","  (  ><  )  ","   .----.   "],
      ["            ","   /\\  /\\   ","  (({E})(-))  ","  (  ><  )  ","   `----´   "],
    ],
  },
  turtle: {
    rarity: 'uncommon', color: '#7da888',
    frames: [
      ["            ","   _,--._   ","  ( {E}  {E} )  "," /[______]\\ ","  ``    ``  "],
      ["            ","   _,--._   ","  ( {E}  {E} )  "," /[______]\\ ","   ``  ``   "],
      ["            ","   _,--._   ","  ( {E}  {E} )  "," /[======]\\ ","  ``    ``  "],
    ],
  },
  capybara: {
    rarity: 'uncommon', color: '#d4a574',
    frames: [
      ["            ","  n______n  "," ( {E}    {E} ) "," (   oo   ) ","  `------´  "],
      ["            ","  n______n  "," ( {E}    {E} ) "," (   Oo   ) ","  `------´  "],
      ["    ~  ~    ","  u______n  "," ( {E}    {E} ) "," (   oo   ) ","  `------´  "],
    ],
  },
  mushroom: {
    rarity: 'rare', color: '#d05a5a',
    frames: [
      ["            ","  .---.     ","  ({E}>{E})     "," /(   )\\    ","  `---´     "],
      ["            ","  .---.     ","  ({E}>{E})     "," |(   )|    ","  `---´     "],
      ["  .---.     ","  ({E}>{E})     "," /(   )\\    ","  `---´     ","   ~ ~      "],
    ],
  },
  ghost: {
    rarity: 'rare', color: '#c8c8e0',
    frames: [
      ["            ","   .----.   ","  / {E}  {E} \\  ","  |      |  ","  ~`~``~`~  "],
      ["            ","   .----.   ","  / {E}  {E} \\  ","  |      |  ","  `~`~~`~`  "],
      ["    ~  ~    ","   .----.   ","  / {E}  {E} \\  ","  |      |  ","  ~~`~~`~~  "],
    ],
  },
  snail: {
    rarity: 'rare', color: '#b89060',
    frames: [
      ["            "," {E}    .--.  ","  \\  ( @ )  ","   \\_`--´   ","  ~~~~~~~   "],
      ["            ","  {E}   .--.  ","  |  ( @ )  ","   \\_`--´   ","  ~~~~~~~   "],
      ["            "," {E}    .--.  ","  \\  ( @  ) ","   \\_`--´   ","   ~~~~~~   "],
    ],
  },
  cactus: {
    rarity: 'rare', color: '#7dbf8e',
    frames: [
      ["            "," n  ____  n "," | |{E}  {E}| | "," |_|    |_| ","   |    |   "],
      ["            ","    ____    "," n |{E}  {E}| n "," |_|    |_| ","   |    |   "],
      [" n        n "," |  ____  | "," | |{E}  {E}| | "," |_|    |_| ","   |    |   "],
    ],
  },
  chonk: {
    rarity: 'rare', color: '#c4a484',
    frames: [
      ["            ","  /\\    /\\  "," ( {E}    {E} ) "," (   ..   ) ","  `------´  "],
      ["            ","  /\\    /|  "," ( {E}    {E} ) "," (   ..   ) ","  `------´  "],
      ["            ","  /\\    /\\  "," ( {E}    {E} ) "," (   ..   ) ","  `------´~ "],
    ],
  },
  octopus: {
    rarity: 'epic', color: '#b89cf0',
    frames: [
      ["            ","   .----.   ","  ( {E}  {E} )  ","  (______)  ","  /\\/\\/\\/\\  "],
      ["            ","   .----.   ","  ( {E}  {E} )  ","  (______)  ","  \\/\\/\\/\\/  "],
      ["     o      ","   .----.   ","  ( {E}  {E} )  ","  (______)  ","  /\\/\\/\\/\\  "],
    ],
  },
  jellyfish: {
    rarity: 'epic', color: '#a4d4e8',
    // jellyfish lines 1-4 were 11 chars wide; 1 trailing space added to each to reach 12
    frames: [
      ["            ","  ╭━━━━━━╮  "," ╭  {E}  {E}  ╮ ","  ╰┬┬┬┬┬┬╯  ","   ┆┆┆┆┆┆   "],
      ["            ","  ╭━━━━━━╮  "," ╭  {E}  {E}  ╮ ","  ╰┬┬┬┬┬┬╯  ","   ∫∫∫∫∫∫   "],
      ["            ","  ╭━━━━━━╮  "," ╭  {E}  {E}  ╮ ","  ╰┬┬┬┬┬┬╯  ","   ┆┆┆┆┆┆   "],
    ],
  },
  axolotl: {
    rarity: 'epic', color: '#f0a4d4',
    frames: [
      ["            ","}~(______)~{","}~({E} .. {E})~{","  ( .--. )  ","  (_/  \\_)  "],
      ["            ","~}(______){~","~}({E} .. {E}){~","  ( .--. )  ","  (_/  \\_)  "],
      ["            ","}~(______)~{","}~({E} .. {E})~{","  (  --  )  ","  ~_/  \\_~  "],
    ],
  },
  robot: {
    rarity: 'epic', color: '#7cc7f0',
    frames: [
      ["            ","   .[||].   ","  [ {E}  {E} ]  ","  [ ==== ]  ","  `------´  "],
      ["            ","   .[||].   ","  [ {E}  {E} ]  ","  [ -==- ]  ","  `------´  "],
      ["     *      ","   .[||].   ","  [ {E}  {E} ]  ","  [ ==== ]  ","  `------´  "],
    ],
  },
  dragon: {
    rarity: 'legendary', color: '#ff7a5c',
    frames: [
      ["            ","  /^\\  /^\\  "," <  {E}  {E}  > "," (   ~~   ) ","  `-vvvv-´  "],
      ["            ","  /^\\  /^\\  "," <  {E}  {E}  > "," (        ) ","  `-vvvv-´  "],
      ["   ~    ~   ","  /^\\  /^\\  "," <  {E}  {E}  > "," (   ~~   ) ","  `-vvvv-´  "],
    ],
  },

  // ===== Hand-authored legendary buddies =====

  phoenix: {
    rarity: 'legendary', color: '#ff9544',
    frames: [
      ["    ^^^^    ","   /^v^\\    ","  ( {E}  {E} )  ","   \\___/    ","   ^^^^^    "],
      ["   ^^^^^    ","   /^v^\\    ","  ( {E}  {E} )  ","   \\___/    ","  ^vvvvv^   "],
      ["    *  *    ","   /^v^\\    ","  ( {E}  {E} )  ","   \\___/    ","   ^^^^^    "],
    ],
  },

  fox: {
    rarity: 'legendary', color: '#f08c5c',
    frames: [
      ["            ","   /\\__/\\   ","  ( {E}><{E} )  ","   \\_vv_/   ","   /    \\~  "],
      ["            ","   /\\__/\\   ","  ( {E}>>{E} )  ","   \\_vv_/   ","  ~/    \\   "],
      ["            ","   /\\__/\\   ","  ( {E}><{E} )  ","   \\_..__/  ","   /    \\~  "],
    ],
  },

  shiba: {
    rarity: 'legendary', color: '#e8a474',
    frames: [
      ["            ","  /\\____/\\  "," (  {E}  {E}  ) "," (   ww   ) ","  `--uu--´  "],
      ["            ","  /\\____/|  "," (  {E}  {E}  ) "," (   ww   ) ","  `--uu--´  "],
      ["    *       ","  /\\____/\\  "," (  {E}  {E}  ) "," (   ww   ) ","  `--uu--´  "],
    ],
  },

  mochi: {
    rarity: 'legendary', color: '#fff0e8',
    frames: [
      ["            ","   .----.   ","  ( {E} ω {E} ) ","   `----´   ","   ~~~~~~   "],
      ["            ","  .------.  "," ( {E}  ω  {E} )"," (        ) ","   ~~~~~~   "],
      ["    ~~      ","   .----.   ","  ( {E} ω {E} ) ","   `----´   ","   ~~~~~~   "],
    ],
  },

  // ===== Cute additions (round 2) =====

  panda: {
    rarity: 'legendary', color: '#f5f5f5',
    frames: [
      ["            "," .--------. "," ( o{E}  {E}o ) "," (   ω    ) ","  `------´  "],
      ["            "," .--------. "," ( O{E}  {E}O ) "," (   o    ) ","  `------´  "],
      ["     **     "," .--------. "," ( o{E}  {E}o ) "," (   ω    ) ","  `------´  "],
    ],
  },

  hamster: {
    rarity: 'legendary', color: '#f0c890',
    frames: [
      ["            ","  ((____))  "," ( {E} ω {E} )  ","  \\  ()  /  ","   ¯¯¯¯¯¯   "],
      ["            ","  ((====))  "," ( {E} º {E} )  ","  \\ (oo) /  ","   ¯¯¯¯¯¯   "],
      ["    .       ","  ((____))  "," ( {E} ω {E} )  ","  \\  ()  /  ","   ¯¯¯¯¯¯   "],
    ],
  },

  bee: {
    rarity: 'legendary', color: '#f5d44c',
    frames: [
      ["    ^^^^    "," ( ====== ) "," ( {E} ω {E} )  "," ( ====== ) ","   `wwww´   "],
      ["     vv     "," ( ------ ) "," ( {E} º {E} )  "," ( ------ ) ","   `wwww´   "],
      ["   ^^^^^^   "," ( ====== ) "," ( {E} ω {E} )  "," ( ====== ) ","   `wwww´   "],
    ],
  },

  otter: {
    rarity: 'legendary', color: '#a4906c',
    frames: [
      ["            ","   .---.    ","  ( {E}ω{E} )   ","   \\_*_/    ","   /( )\\    "],
      ["            ","   .---.    ","  ( {E}ω{E} )   ","   \\_★_/    ","   /( )\\    "],
      ["     z      ","   .---.    ","  ( {E}-{E} )   ","   \\_*_/    ","   /( )\\    "],
    ],
  },
};

export const SPECIES = Object.fromEntries(
  Object.entries(SPECIES_BASE).map(([key, species]) => [key, withProfile(key, species)]),
);

export const SPECIES_BEHAVIOR = {
  cat: { proactiveLevel: 1, idleFrequency: 'low', localLines: ['显然，可以。', '这段值得再看一眼。'] },
  rabbit: { proactiveLevel: 5, idleFrequency: 'high', localLines: ['啊！要我看看吗？', '哦哦哦我发现一点！'] },
  robot: { proactiveLevel: 2, idleFrequency: 'normal', localLines: ['[ACK] context ready.', '[BEEP] 需要输入。'] },
  turtle: { proactiveLevel: 1, idleFrequency: 'low', localLines: ['慢慢看，别急。', '老朽先记下此处。'] },
  fox: { proactiveLevel: 4, idleFrequency: 'normal', localLines: ['小狐嗅到玄机啦～', '要不要追一下这里？'] },
  bee: { proactiveLevel: 4, idleFrequency: 'normal', localLines: ['任务：需要我拆解吗？', '嗡，下一步很清楚。'] },
  default: { proactiveLevel: 3, idleFrequency: 'normal', localLines: ['要我看看这里吗？', '我在这儿。'] },
};

export function byRarity() {
  const out = {};
  for (const r of RARITY_ORDER) out[r] = [];
  for (const [key, sp] of Object.entries(SPECIES)) {
    out[sp.rarity].push({ key, ...sp });
  }
  // drop empty buckets so the panel doesn't render blank rows
  for (const r of RARITY_ORDER) {
    if (out[r].length === 0) delete out[r];
  }
  return out;
}

// Mapping from pet state to {E} substitute character.
export const STATE_EYE = {
  idle:         '·',
  thinking:     '°',
  typing:       '·',
  building:     'o',
  juggling:     '^',
  conducting:   '^',
  error:        '×',
  happy:        '✦',
  notification: '>',
  sweeping:     '-',
  carrying:     'o',
  sleeping:     '-',
  yawning:      '>',
  startled:     '◉',
};
