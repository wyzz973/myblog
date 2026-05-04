from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.models import PetMessage, PetUsageEvent, PetVisitorProfile


async def test_forget_me_clears_current_visitor_profile_context_and_cookies(client, redis):
    # Establish cookies/profile via config + one summon.
    await client.get("/api/pet/config")
    await client.post("/api/pet/summon", json={"message": "hello"})

    async with AsyncSessionLocal() as s:
        profile = (
            await s.execute(select(PetVisitorProfile).order_by(PetVisitorProfile.last_seen_at.desc()))
        ).scalars().first()
        assert profile is not None
        visitor_hash = profile.visitor_hash
    await redis.lpush(f"pet:ctx:{visitor_hash}", '{"role":"user","content":"hello"}')

    r = await client.post("/api/pet/forget")
    assert r.status_code == 200
    assert r.json()["forgotten"] is True
    assert await redis.exists(f"pet:ctx:{visitor_hash}") == 0

    async with AsyncSessionLocal() as s:
        assert (
            await s.execute(
                select(PetVisitorProfile).where(PetVisitorProfile.visitor_hash == visitor_hash)
            )
        ).scalar_one_or_none() is None
        messages = (await s.execute(select(PetMessage))).scalars().all()
        usage = (await s.execute(select(PetUsageEvent))).scalars().all()
        for row in messages:
            await s.delete(row)
        for row in usage:
            await s.delete(row)
        await s.commit()
