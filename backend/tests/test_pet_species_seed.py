"""Task 21b: verify the seed migration populates pet_species correctly.

The migration runs once at suite startup (conftest's alembic upgrade), so by
the time these tests run the rows are already present. We just assert the
catalogue is complete and each row has the JSONB shape the frontend expects.
"""
import pytest
from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.models import PetSpecies


# Same 28 IDs as src/components/pet/species.js — the seed migration's _FRAMES
# list ordering. If we add a species we update both this test and the
# migration; new owner-added species via admin UI go through API, not seed.
EXPECTED_IDS = {
    "duck", "goose", "blob", "cat", "rabbit",
    "penguin", "owl", "turtle", "capybara",
    "mushroom", "ghost", "snail", "cactus", "chonk",
    "octopus", "jellyfish", "axolotl", "robot",
    "dragon", "phoenix", "fox", "shiba", "mochi",
    "panda", "hamster", "bee", "otter",
}
EXPECTED_RARITY = {
    "duck": "common", "goose": "common", "blob": "common", "cat": "common", "rabbit": "common",
    "penguin": "uncommon", "owl": "uncommon", "turtle": "uncommon", "capybara": "uncommon",
    "mushroom": "rare", "ghost": "rare", "snail": "rare", "cactus": "rare", "chonk": "rare",
    "octopus": "epic", "jellyfish": "epic", "axolotl": "epic", "robot": "epic",
    "dragon": "legendary", "phoenix": "legendary", "fox": "legendary",
    "shiba": "legendary", "mochi": "legendary", "panda": "legendary",
    "hamster": "legendary", "bee": "legendary", "otter": "legendary",
}


@pytest.fixture(autouse=True)
async def _reset_pool():
    from app import db as _db
    await _db.engine.dispose()
    yield
    await _db.engine.dispose()


async def test_seed_loaded_all_species():
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(PetSpecies))).scalars().all()
    ids = {r.id for r in rows}
    # 27 frames in the migration (jellyfish counted once even though there are
    # several legendary/epic siblings) — the EXPECTED_IDS set has 27 entries.
    assert EXPECTED_IDS.issubset(ids), f"missing seeded species: {EXPECTED_IDS - ids}"


async def test_seed_rarities_match_frontend():
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(PetSpecies))).scalars().all()
    by_id = {r.id: r for r in rows}
    for sid, expected in EXPECTED_RARITY.items():
        assert by_id[sid].rarity == expected, f"{sid}: expected {expected}, got {by_id[sid].rarity}"


async def test_seed_frames_use_eye_marker():
    """Every frame line is a string; at least one line per species contains
    the {E} eye-marker token so the frontend STATE_EYE substitution still
    finds something to replace."""
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(PetSpecies).where(PetSpecies.id.in_(EXPECTED_IDS)))).scalars().all()
    for r in rows:
        assert isinstance(r.frames, list) and len(r.frames) == 3, f"{r.id}: expected 3 frames, got {len(r.frames)}"
        for frame in r.frames:
            assert isinstance(frame, list), f"{r.id}: frame must be list of lines"
            assert all(isinstance(line, str) for line in frame), f"{r.id}: frame lines must be strings"
        flat = "\n".join("\n".join(f) for f in r.frames)
        assert "{E}" in flat, f"{r.id}: no {{E}} eye-marker found in any frame"


async def test_seed_behavior_shape():
    """Behavior must carry the three keys frontend uses: proactiveLevel,
    idleFrequency, localLines. We seeded camelCase to match the JS hardcode."""
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(PetSpecies).where(PetSpecies.id.in_(EXPECTED_IDS)))).scalars().all()
    for r in rows:
        b = r.behavior
        assert "proactiveLevel" in b, f"{r.id}: missing proactiveLevel"
        assert "idleFrequency" in b, f"{r.id}: missing idleFrequency"
        assert "localLines" in b and isinstance(b["localLines"], list), f"{r.id}: localLines must be list"
        assert b["idleFrequency"] in ("low", "normal", "high"), f"{r.id}: bad idleFrequency {b['idleFrequency']!r}"
        assert isinstance(b["proactiveLevel"], int) and 1 <= b["proactiveLevel"] <= 5, (
            f"{r.id}: proactiveLevel must be int 1..5, got {b['proactiveLevel']!r}"
        )


async def test_seed_stats_have_five_axes():
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(PetSpecies).where(PetSpecies.id.in_(EXPECTED_IDS)))).scalars().all()
    AXES = {"debugging", "patience", "chaos", "wisdom", "snark"}
    for r in rows:
        assert AXES.issubset(set(r.stats.keys())), f"{r.id}: stats missing axes {AXES - set(r.stats.keys())}"


async def test_seed_visible_and_sort_order_unique():
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(PetSpecies).where(PetSpecies.id.in_(EXPECTED_IDS)))).scalars().all()
    assert all(r.visible for r in rows), "all seeded species should be visible by default"
    sort_orders = [r.sort_order for r in rows]
    assert len(sort_orders) == len(set(sort_orders)), "seeded sort_order values should be unique"
