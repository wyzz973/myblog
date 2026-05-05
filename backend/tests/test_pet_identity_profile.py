from datetime import UTC, datetime

from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.models import PetVisitorProfile
from app.services import pet_identity, pet_profiles


def test_pet_vid_cookie_roundtrip_and_tamper_rejection():
    value = pet_identity.sign_vid("abc123")
    assert pet_identity.verify_vid(value) == "abc123"
    assert pet_identity.verify_vid(value + "tampered") is None
    assert pet_identity.verify_vid("abc123|bad") is None


def test_visitor_hash_comes_from_vid_not_ip():
    signed = pet_identity.sign_vid("visitor-token")
    by_cookie = pet_identity.visitor_hash_from_parts(
        signed_vid=signed,
        ip="1.2.3.4",
    )
    by_other_ip = pet_identity.visitor_hash_from_parts(
        signed_vid=signed,
        ip="9.9.9.9",
    )
    by_ip = pet_identity.visitor_hash_from_parts(signed_vid=None, ip="1.2.3.4")
    assert by_cookie == by_other_ip
    assert by_cookie != by_ip
    assert len(by_cookie) == 16


async def test_pet_profile_touch_and_interaction_update():
    async with AsyncSessionLocal() as s:
        profile = await pet_profiles.touch(
            s,
            visitor_hash="profiletest00001",
            species="cat",
            locale="zh-CN",
        )
        assert profile.visitor_hash == "profiletest00001"
        await pet_profiles.record_interaction(
            s,
            visitor_hash="profiletest00001",
            species="cat",
            mode="free_chat",
            post_id="pet-test",
            tag="devtools",
            message="这段代码是什么意思？",
            locale="zh-CN",
            now=datetime.now(UTC),
        )
        await s.commit()

    async with AsyncSessionLocal() as s:
        row = (
            await s.execute(
                select(PetVisitorProfile).where(
                    PetVisitorProfile.visitor_hash == "profiletest00001"
                )
            )
        ).scalar_one()
        assert row.interaction_count == 1
        assert row.preferred_language == "zh"
        assert row.interest_tags == ["devtools"]
        assert row.recent_post_ids == ["pet-test"]
        assert "代码" in (row.style_summary or "")
        await s.delete(row)
        await s.commit()
