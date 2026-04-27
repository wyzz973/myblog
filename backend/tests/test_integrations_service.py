import pytest
from sqlalchemy import delete

from app.db import AsyncSessionLocal
from app.models import Integration
from app.services import integrations as svc


@pytest.fixture(autouse=True)
async def _reset_pool():
    """Dispose the engine pool before each test so asyncpg connections are
    not carried across test-local event loops."""
    from app import db as _db
    await _db.engine.dispose()
    yield
    await _db.engine.dispose()


@pytest.fixture(autouse=True)
async def cleanup():
    yield
    async with AsyncSessionLocal() as s:
        await s.execute(delete(Integration))
        await s.commit()


async def test_upsert_creates_new():
    async with AsyncSessionLocal() as s:
        row = await svc.upsert(s, name="github", username="me",
                               secret="ghp_xxxx", extra={"foo": "bar"})
        await s.commit()
        assert row.name == "github"
        assert row.username == "me"
        assert row.secret_encrypted != "ghp_xxxx"  # encrypted
        assert row.extra_json == {"foo": "bar"}


async def test_upsert_updates_existing():
    async with AsyncSessionLocal() as s:
        await svc.upsert(s, name="github", username="alice", secret="t1")
        row = await svc.upsert(s, name="github", username="bob", secret="t2")
        await s.commit()
        assert row.username == "bob"
        # only one row
        rows = (await s.execute(__import__("sqlalchemy").select(Integration))).scalars().all()
        assert len(rows) == 1


async def test_get_secret_decrypts_round_trip():
    async with AsyncSessionLocal() as s:
        await svc.upsert(s, name="github", username="me", secret="my-token-xyz")
        await s.commit()
    async with AsyncSessionLocal() as s:
        secret = await svc.get_secret(s, name="github")
        assert secret == "my-token-xyz"


async def test_get_secret_missing_returns_none():
    async with AsyncSessionLocal() as s:
        assert await svc.get_secret(s, name="github") is None


async def test_set_status():
    async with AsyncSessionLocal() as s:
        await svc.upsert(s, name="github", username="me", secret="t")
        await svc.set_status(s, name="github", status="ok", error=None)
        await s.commit()
    async with AsyncSessionLocal() as s:
        row = await svc.get(s, name="github")
        assert row.last_status == "ok"
        assert row.last_synced_at is not None


async def test_upsert_rotates_ciphertext_on_each_call():
    """secret_box uses a fresh nonce per encrypt; ciphertext should differ
    between two upsert calls even with the same plaintext secret. Documents
    that re-upserting is a key rotation, not a no-op."""
    async with AsyncSessionLocal() as s:
        row1 = await svc.upsert(s, name="github", username="me", secret="same-token")
        first_ct = row1.secret_encrypted
        await s.commit()
    async with AsyncSessionLocal() as s:
        row2 = await svc.upsert(s, name="github", username="me", secret="same-token")
        await s.commit()
        # Different ciphertext, same plaintext after decrypt.
        assert row2.secret_encrypted != first_ct
    async with AsyncSessionLocal() as s:
        assert await svc.get_secret(s, name="github") == "same-token"
