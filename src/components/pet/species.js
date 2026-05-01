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

export const SPECIES = {
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
