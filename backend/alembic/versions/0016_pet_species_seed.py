"""seed pet_species rows from frontend species.js (Task 21b).

Idempotent: each row uses ON CONFLICT (id) DO NOTHING so re-running is a no-op
and the migration won't clobber owner edits to existing rows. The data is a
verbatim port of src/components/pet/species.js — once 21c lands the public
GET /api/pet/species endpoint, 21e can rip out the JS hardcode and read from
this seed (or any owner-edited replacement of it).

For frame data we keep the {E} eye-marker tokens unchanged so the frontend's
existing per-state substitution (STATE_EYE) keeps working.
"""
from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op


revision: str = "0016_pet_species_seed"
down_revision: str | None = "0015_pet_species"
branch_labels = None
depends_on = None


_RARITY_STAT_BASE = {
    "common":    {"debugging": 42, "patience": 64, "chaos": 30, "wisdom": 38, "snark": 24},
    "uncommon":  {"debugging": 55, "patience": 58, "chaos": 38, "wisdom": 52, "snark": 34},
    "rare":      {"debugging": 68, "patience": 50, "chaos": 52, "wisdom": 62, "snark": 48},
    "epic":      {"debugging": 78, "patience": 44, "chaos": 66, "wisdom": 72, "snark": 58},
    "legendary": {"debugging": 88, "patience": 40, "chaos": 80, "wisdom": 84, "snark": 72},
}

_PROFILES = {
    "duck":      ("rubber debugger",  "Cheerful, literal, and suspicious of silent failures.",   "A tiny desk duck that listens first and quacks only when a bug is obvious.",                    {"patience": 78, "snark": 12}),
    "goose":     ("strict reviewer",  "Loud, protective, and impossible to ignore.",             "Guards the page like a build gate and honks at vague requirements.",                            {"debugging": 58, "chaos": 55, "snark": 50}),
    "blob":      ("soft buffer",      "Calm, squishy, and good at absorbing messy context.",     "Turns scattered thoughts into one small, usable next step.",                                    {"patience": 82, "chaos": 18}),
    "cat":       ("terminal familiar","Curious, picky, and quietly helpful when it feels like it.","A classic coding companion with sharp eyes and selective affection.",                         {"debugging": 62, "snark": 44}),
    "rabbit":    ("quick scanner",    "Fast, gentle, and easily distracted by edge cases.",      "Hops through drafts and catches tiny inconsistencies before they multiply.",                    {"debugging": 56, "chaos": 42}),
    "penguin":   ("release keeper",   "Orderly, cool-headed, and fond of clean deploys.",        "Keeps its feathers neat and its checklists shorter than they look.",                            {"patience": 72, "wisdom": 68}),
    "owl":       ("night analyst",    "Quiet, observant, and annoyingly right after midnight.",  "Watches the whole code path before blinking once.",                                             {"wisdom": 82, "snark": 42}),
    "turtle":    ("steady shipper",   "Slow, stubborn, and deeply resistant to panic.",          "Prefers durable fixes, small diffs, and migrations that can be explained.",                     {"patience": 88, "chaos": 14}),
    "capybara":  ("team mediator",    "Unbothered, warm, and useful during ambiguous product debates.","Sits beside hard tradeoffs until they stop looking dramatic.",                             {"patience": 86, "snark": 18}),
    "mushroom":  ("spore profiler",   "Odd, patient, and quietly excellent at finding hidden growth.","Finds patterns in dark corners and leaves tiny notes behind.",                              {"wisdom": 70, "chaos": 58}),
    "ghost":     ("regression haunt", "Playful, elusive, and obsessed with bugs that came back.","Floats through old assumptions and rattles the flaky tests.",                                   {"debugging": 74, "chaos": 70}),
    "snail":     ("latency oracle",   "Methodical, dry, and never rushed by a progress bar.",    "Measures twice, crawls once, and still reaches the root cause.",                                {"patience": 92, "wisdom": 76}),
    "cactus":    ("boundary guard",   "Prickly, concise, and excellent at saying no.",           "Protects APIs, scopes, and personal space with the same energy.",                               {"patience": 46, "snark": 70}),
    "chonk":     ("cache warmer",     "Cozy, loyal, and very serious about snack breaks.",       "Stabilizes the room and occasionally sits on over-engineered ideas.",                           {"patience": 74, "snark": 38}),
    "octopus":   ("parallel thinker", "Clever, restless, and always holding three contexts at once.","Juggles options, traces data flow, and still has an arm free for notes.",                  {"debugging": 86, "chaos": 74}),
    "jellyfish": ("signal drifter",   "Elegant, weird, and lightly judgmental about bad abstractions.","Glows when the architecture is clean and stings when it is not.",                          {"wisdom": 84, "snark": 76}),
    "axolotl":   ("recovery mode",    "Hopeful, resilient, and strangely good at undoing damage.","Regenerates broken flows from the smallest surviving invariant.",                               {"patience": 72, "chaos": 64}),
    "robot":     ("lint engine",      "Precise, tireless, and allergic to inconsistent formatting.","Runs on structured inputs, crisp errors, and exactly one source of truth.",                  {"debugging": 92, "snark": 54}),
    "dragon":    ("prod firekeeper",  "Proud, intense, and happiest near difficult launches.",   "Breathes controlled fire at blockers and hoards useful logs.",                                  {"debugging": 96, "chaos": 90}),
    "phoenix":   ("rollback rebirth", "Dramatic, optimistic, and excellent after incidents.",    "Turns failed deploys into cleaner release rituals.",                                            {"wisdom": 92, "chaos": 86}),
    "fox":       ("clever scout",     "Sharp, sly, and quick to spot the shortcut that is actually safe.","Sneaks through edge cases and returns with the missing assumption.",                   {"debugging": 90, "snark": 82}),
    "shiba":     ("approval gate",    "Confident, expressive, and unconvinced by vague success metrics.","Barks once for unclear acceptance criteria and twice for flaky demos.",                  {"snark": 88, "patience": 34}),
    "mochi":     ("sweet stabilizer", "Soft, cheerful, and surprisingly strict about polish.",   "Makes rough interactions feel finished without making a fuss.",                                 {"patience": 76, "wisdom": 78}),
    "panda":     ("calm operator",    "Gentle, sleepy, and very hard to shake during outages.",  "Reads the dashboard slowly and finds the one number that matters.",                             {"patience": 90, "wisdom": 88}),
    "hamster":   ("tiny optimizer",   "Busy, bright-eyed, and prone to over-indexing on details.","Stores small improvements for later and occasionally finds a big one.",                        {"debugging": 84, "chaos": 76}),
    "bee":       ("workflow pollinator","Energetic, social, and obsessed with moving useful context around.","Connects ideas, comments, and TODOs until the whole garden ships.",                  {"chaos": 82, "patience": 52}),
    "otter":     ("playful debugger", "Inventive, mischievous, and happiest with a failing repro.","Plays with the problem until the root cause floats up.",                                       {"debugging": 94, "snark": 80}),
}

# (id, rarity, color, [frame_a, frame_b, frame_c]) — frames preserve {E} markers
# so the frontend's STATE_EYE substitution still works against the seeded data.
_FRAMES: list[tuple[str, str, str, list[list[str]]]] = [
    ("duck", "common", "#f5d44c", [
        ["            ", "    __      ", "  <({E} )___  ", "   (  ._>   ", "    `--´    "],
        ["            ", "    __      ", "  <({E} )___  ", "   (  ._>   ", "    `--´~   "],
        ["            ", "    __      ", "  <({E} )___  ", "   (  .__>  ", "    `--´    "],
    ]),
    ("goose", "common", "#e8e8e8", [
        ["            ", "     ({E}>    ", "     ||     ", "   _(__)_   ", "    ^^^^    "],
        ["            ", "    ({E}>     ", "     ||     ", "   _(__)_   ", "    ^^^^    "],
        ["            ", "     ({E}>>   ", "     ||     ", "   _(__)_   ", "    ^^^^    "],
    ]),
    ("blob", "common", "#7dd3a4", [
        ["            ", "   .----.   ", "  ( {E}  {E} )  ", "  (      )  ", "   `----´   "],
        ["            ", "  .------.  ", " (  {E}  {E}  ) ", " (        ) ", "  `------´  "],
        ["            ", "    .--.    ", "   ({E}  {E})   ", "   (    )   ", "    `--´    "],
    ]),
    ("cat", "common", "#e0a96d", [
        ["            ", "   /\\__/\\   ", "  ( {E}  {E} )  ", "  (  ω   )  ", '  (")__(")  '],
        ["            ", "   /\\__/\\   ", "  ( {E}  {E} )  ", "  (  ω   )  ", '  (")__(")~ '],
        ["            ", "   /\\--/\\   ", "  ( {E}  {E} )  ", "  (  ω   )  ", '  (")__(")  '],
    ]),
    ("rabbit", "common", "#f0d8e0", [
        ["            ", "   (\\__/)   ", "  ( {E}  {E} )  ", " =(  ..  )= ", '  (")__(")  '],
        ["            ", "   (|__/)   ", "  ( {E}  {E} )  ", " =(  ..  )= ", '  (")__(")  '],
        ["            ", "   (\\__/)   ", "  ( {E}  {E} )  ", " =( .  . )= ", '  (")__(")  '],
    ]),
    ("penguin", "uncommon", "#5c7ec4", [
        ["            ", " .-o-OO-o-. ", "(__________)", "   |{E}  {E}|   ", "   |____|   "],
        ["            ", " .-O-oo-O-. ", "(__________)", "   |{E}  {E}|   ", "   |____|   "],
        ["   . o  .   ", " .-o-OO-o-. ", "(__________)", "   |{E}  {E}|   ", "   |____|   "],
    ]),
    ("owl", "uncommon", "#a89060", [
        ["            ", "   /\\  /\\   ", "  (({E})({E}))  ", "  (  ><  )  ", "   `----´   "],
        ["            ", "   /\\  /\\   ", "  (({E})({E}))  ", "  (  ><  )  ", "   .----.   "],
        ["            ", "   /\\  /\\   ", "  (({E})(-))  ", "  (  ><  )  ", "   `----´   "],
    ]),
    ("turtle", "uncommon", "#7da888", [
        ["            ", "   _,--._   ", "  ( {E}  {E} )  ", " /[______]\\ ", "  ``    ``  "],
        ["            ", "   _,--._   ", "  ( {E}  {E} )  ", " /[______]\\ ", "   ``  ``   "],
        ["            ", "   _,--._   ", "  ( {E}  {E} )  ", " /[======]\\ ", "  ``    ``  "],
    ]),
    ("capybara", "uncommon", "#d4a574", [
        ["            ", "  n______n  ", " ( {E}    {E} ) ", " (   oo   ) ", "  `------´  "],
        ["            ", "  n______n  ", " ( {E}    {E} ) ", " (   Oo   ) ", "  `------´  "],
        ["    ~  ~    ", "  u______n  ", " ( {E}    {E} ) ", " (   oo   ) ", "  `------´  "],
    ]),
    ("mushroom", "rare", "#d05a5a", [
        ["            ", "  .---.     ", "  ({E}>{E})     ", " /(   )\\    ", "  `---´     "],
        ["            ", "  .---.     ", "  ({E}>{E})     ", " |(   )|    ", "  `---´     "],
        ["  .---.     ", "  ({E}>{E})     ", " /(   )\\    ", "  `---´     ", "   ~ ~      "],
    ]),
    ("ghost", "rare", "#c8c8e0", [
        ["            ", "   .----.   ", "  / {E}  {E} \\  ", "  |      |  ", "  ~`~``~`~  "],
        ["            ", "   .----.   ", "  / {E}  {E} \\  ", "  |      |  ", "  `~`~~`~`  "],
        ["    ~  ~    ", "   .----.   ", "  / {E}  {E} \\  ", "  |      |  ", "  ~~`~~`~~  "],
    ]),
    ("snail", "rare", "#b89060", [
        ["            ", " {E}    .--.  ", "  \\  ( @ )  ", "   \\_`--´   ", "  ~~~~~~~   "],
        ["            ", "  {E}   .--.  ", "  |  ( @ )  ", "   \\_`--´   ", "  ~~~~~~~   "],
        ["            ", " {E}    .--.  ", "  \\  ( @  ) ", "   \\_`--´   ", "   ~~~~~~   "],
    ]),
    ("cactus", "rare", "#7dbf8e", [
        ["            ", " n  ____  n ", " | |{E}  {E}| | ", " |_|    |_| ", "   |    |   "],
        ["            ", "    ____    ", " n |{E}  {E}| n ", " |_|    |_| ", "   |    |   "],
        [" n        n ", " |  ____  | ", " | |{E}  {E}| | ", " |_|    |_| ", "   |    |   "],
    ]),
    ("chonk", "rare", "#c4a484", [
        ["            ", "  /\\    /\\  ", " ( {E}    {E} ) ", " (   ..   ) ", "  `------´  "],
        ["            ", "  /\\    /|  ", " ( {E}    {E} ) ", " (   ..   ) ", "  `------´  "],
        ["            ", "  /\\    /\\  ", " ( {E}    {E} ) ", " (   ..   ) ", "  `------´~ "],
    ]),
    ("octopus", "epic", "#b89cf0", [
        ["            ", "   .----.   ", "  ( {E}  {E} )  ", "  (______)  ", "  /\\/\\/\\/\\  "],
        ["            ", "   .----.   ", "  ( {E}  {E} )  ", "  (______)  ", "  \\/\\/\\/\\/  "],
        ["     o      ", "   .----.   ", "  ( {E}  {E} )  ", "  (______)  ", "  /\\/\\/\\/\\  "],
    ]),
    ("jellyfish", "epic", "#a4d4e8", [
        ["            ", "  ╭━━━━━━╮  ", " ╭  {E}  {E}  ╮ ", "  ╰┬┬┬┬┬┬╯  ", "   ┆┆┆┆┆┆   "],
        ["            ", "  ╭━━━━━━╮  ", " ╭  {E}  {E}  ╮ ", "  ╰┬┬┬┬┬┬╯  ", "   ∫∫∫∫∫∫   "],
        ["            ", "  ╭━━━━━━╮  ", " ╭  {E}  {E}  ╮ ", "  ╰┬┬┬┬┬┬╯  ", "   ┆┆┆┆┆┆   "],
    ]),
    ("axolotl", "epic", "#f0a4d4", [
        ["            ", "}~(______)~{", "}~({E} .. {E})~{", "  ( .--. )  ", "  (_/  \\_)  "],
        ["            ", "~}(______){~", "~}({E} .. {E}){~", "  ( .--. )  ", "  (_/  \\_)  "],
        ["            ", "}~(______)~{", "}~({E} .. {E})~{", "  (  --  )  ", "  ~_/  \\_~  "],
    ]),
    ("robot", "epic", "#7cc7f0", [
        ["            ", "   .[||].   ", "  [ {E}  {E} ]  ", "  [ ==== ]  ", "  `------´  "],
        ["            ", "   .[||].   ", "  [ {E}  {E} ]  ", "  [ -==- ]  ", "  `------´  "],
        ["     *      ", "   .[||].   ", "  [ {E}  {E} ]  ", "  [ ==== ]  ", "  `------´  "],
    ]),
    ("dragon", "legendary", "#ff7a5c", [
        ["            ", "  /^\\  /^\\  ", " <  {E}  {E}  > ", " (   ~~   ) ", "  `-vvvv-´  "],
        ["            ", "  /^\\  /^\\  ", " <  {E}  {E}  > ", " (        ) ", "  `-vvvv-´  "],
        ["   ~    ~   ", "  /^\\  /^\\  ", " <  {E}  {E}  > ", " (   ~~   ) ", "  `-vvvv-´  "],
    ]),
    ("phoenix", "legendary", "#ff9544", [
        ["    ^^^^    ", "   /^v^\\    ", "  ( {E}  {E} )  ", "   \\___/    ", "   ^^^^^    "],
        ["   ^^^^^    ", "   /^v^\\    ", "  ( {E}  {E} )  ", "   \\___/    ", "  ^vvvvv^   "],
        ["    *  *    ", "   /^v^\\    ", "  ( {E}  {E} )  ", "   \\___/    ", "   ^^^^^    "],
    ]),
    ("fox", "legendary", "#f08c5c", [
        ["            ", "   /\\__/\\   ", "  ( {E}><{E} )  ", "   \\_vv_/   ", "   /    \\~  "],
        ["            ", "   /\\__/\\   ", "  ( {E}>>{E} )  ", "   \\_vv_/   ", "  ~/    \\   "],
        ["            ", "   /\\__/\\   ", "  ( {E}><{E} )  ", "   \\_..__/  ", "   /    \\~  "],
    ]),
    ("shiba", "legendary", "#e8a474", [
        ["            ", "  /\\____/\\  ", " (  {E}  {E}  ) ", " (   ww   ) ", "  `--uu--´  "],
        ["            ", "  /\\____/|  ", " (  {E}  {E}  ) ", " (   ww   ) ", "  `--uu--´  "],
        ["    *       ", "  /\\____/\\  ", " (  {E}  {E}  ) ", " (   ww   ) ", "  `--uu--´  "],
    ]),
    ("mochi", "legendary", "#fff0e8", [
        ["            ", "   .----.   ", "  ( {E} ω {E} ) ", "   `----´   ", "   ~~~~~~   "],
        ["            ", "  .------.  ", " ( {E}  ω  {E} )", " (        ) ", "   ~~~~~~   "],
        ["    ~~      ", "   .----.   ", "  ( {E} ω {E} ) ", "   `----´   ", "   ~~~~~~   "],
    ]),
    ("panda", "legendary", "#f5f5f5", [
        ["            ", " .--------. ", " ( o{E}  {E}o ) ", " (   ω    ) ", "  `------´  "],
        ["            ", " .--------. ", " ( O{E}  {E}O ) ", " (   o    ) ", "  `------´  "],
        ["     **     ", " .--------. ", " ( o{E}  {E}o ) ", " (   ω    ) ", "  `------´  "],
    ]),
    ("hamster", "legendary", "#f0c890", [
        ["            ", "  ((____))  ", " ( {E} ω {E} )  ", "  \\  ()  /  ", "   ¯¯¯¯¯¯   "],
        ["            ", "  ((====))  ", " ( {E} º {E} )  ", "  \\ (oo) /  ", "   ¯¯¯¯¯¯   "],
        ["    .       ", "  ((____))  ", " ( {E} ω {E} )  ", "  \\  ()  /  ", "   ¯¯¯¯¯¯   "],
    ]),
    ("bee", "legendary", "#f5d44c", [
        ["    ^^^^    ", " ( ====== ) ", " ( {E} ω {E} )  ", " ( ====== ) ", "   `wwww´   "],
        ["     vv     ", " ( ------ ) ", " ( {E} º {E} )  ", " ( ------ ) ", "   `wwww´   "],
        ["   ^^^^^^   ", " ( ====== ) ", " ( {E} ω {E} )  ", " ( ====== ) ", "   `wwww´   "],
    ]),
    ("otter", "legendary", "#a4906c", [
        ["            ", "   .---.    ", "  ( {E}ω{E} )   ", "   \\_*_/    ", "   /( )\\    "],
        ["            ", "   .---.    ", "  ( {E}ω{E} )   ", "   \\_★_/    ", "   /( )\\    "],
        ["     z      ", "   .---.    ", "  ( {E}-{E} )   ", "   \\_*_/    ", "   /( )\\    "],
    ]),
]

_BEHAVIOR = {
    "cat":    {"proactiveLevel": 1, "idleFrequency": "low",    "localLines": ["显然，可以。", "这段值得再看一眼。"]},
    "rabbit": {"proactiveLevel": 5, "idleFrequency": "high",   "localLines": ["啊！要我看看吗？", "哦哦哦我发现一点！"]},
    "robot":  {"proactiveLevel": 2, "idleFrequency": "normal", "localLines": ["[ACK] context ready.", "[BEEP] 需要输入。"]},
    "turtle": {"proactiveLevel": 1, "idleFrequency": "low",    "localLines": ["慢慢看，别急。", "老朽先记下此处。"]},
    "fox":    {"proactiveLevel": 4, "idleFrequency": "normal", "localLines": ["小狐嗅到玄机啦～", "要不要追一下这里？"]},
    "bee":    {"proactiveLevel": 4, "idleFrequency": "normal", "localLines": ["任务：需要我拆解吗？", "嗡，下一步很清楚。"]},
}
_BEHAVIOR_DEFAULT = {"proactiveLevel": 3, "idleFrequency": "normal", "localLines": ["要我看看这里吗？", "我在这儿。"]}


def _name(species_id: str) -> str:
    # Title-case for display ("Duck" / "Capybara") — owner can rename in admin.
    return species_id.capitalize()


def upgrade() -> None:
    rows = []
    for sort_idx, (species_id, rarity, color, frames) in enumerate(_FRAMES):
        trait, personality, description, stat_overrides = _PROFILES[species_id]
        stats = {**_RARITY_STAT_BASE[rarity], **stat_overrides}
        behavior = _BEHAVIOR.get(species_id, _BEHAVIOR_DEFAULT)
        # Frames stored as list-of-list-of-line-strings; the public API will
        # serialize them straight back to JSON so the frontend layout layer
        # treats them identically to the JS hardcode.
        rows.append({
            "id": species_id,
            "name": _name(species_id),
            "rarity": rarity,
            "color": color,
            "trait_zh": trait,
            "personality_zh": personality,
            "description_zh": description,
            "frames": json.dumps(frames),
            "behavior": json.dumps(behavior),
            "stats": json.dumps(stats),
            "visible": True,
            "sort_order": sort_idx,
        })

    # ON CONFLICT DO NOTHING keeps owner edits intact across re-runs and
    # makes the migration safe to re-apply on environments that already have
    # a partial seed.
    insert_sql = sa.text(
        """
        INSERT INTO pet_species (
            id, name, rarity, color,
            trait_zh, personality_zh, description_zh,
            frames, behavior, stats,
            visible, sort_order
        ) VALUES (
            :id, :name, :rarity, :color,
            :trait_zh, :personality_zh, :description_zh,
            CAST(:frames AS jsonb), CAST(:behavior AS jsonb), CAST(:stats AS jsonb),
            :visible, :sort_order
        ) ON CONFLICT (id) DO NOTHING
        """
    )
    for r in rows:
        op.execute(insert_sql.bindparams(**r))


def downgrade() -> None:
    # Only remove rows we seeded; preserve any owner-added species.
    ids = [species_id for species_id, *_ in _FRAMES]
    op.execute(
        sa.text("DELETE FROM pet_species WHERE id = ANY(:ids)").bindparams(
            sa.bindparam("ids", value=ids, type_=sa.ARRAY(sa.String))
        )
    )
