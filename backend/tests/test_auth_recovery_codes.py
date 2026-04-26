import re

import pyotp
import pytest

from app.services.recovery_codes import generate_set, hash_code

EMAIL = "hi@wangyang.dev"
PASS = "changeme"
CODE_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{4}-[0-9A-HJKMNP-TV-Z]{4}$")  # Crockford ex I/L/O/U


def test_generate_set_shape():
    codes = generate_set()
    assert len(codes) == 8
    for c in codes:
        assert CODE_RE.match(c), c


def test_hash_code_is_64_hex():
    h = hash_code("ABCD-EFGH")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


@pytest.fixture
async def admin_token(client):
    r = await client.post("/api/admin/auth/login", json={"email": EMAIL, "password": PASS})
    return r.json()["access"]


@pytest.fixture
async def reset_2fa(client):
    yield
    from sqlalchemy import delete, update

    from app.db import AsyncSessionLocal
    from app.models import Account, TfaRecoveryCode
    async with AsyncSessionLocal() as s:
        await s.execute(delete(TfaRecoveryCode).where(TfaRecoveryCode.account_id == 1))
        await s.execute(
            update(Account).where(Account.id == 1).values(
                tfa_enabled=False, tfa_secret_encrypted=None
            )
        )
        await s.commit()


async def _enable_2fa(client, admin_token):
    r1 = await client.post(
        "/api/admin/account/2fa/setup",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    secret = r1.json()["secret"]
    code = pyotp.TOTP(secret).now()
    r2 = await client.post(
        "/api/admin/account/2fa/enable",
        json={"code": code},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    return secret, r2.json()["recovery_codes"]


async def test_enable_returns_recovery_codes(client, admin_token, reset_2fa):
    secret, codes = await _enable_2fa(client, admin_token)
    assert len(codes) == 8
    for c in codes:
        assert CODE_RE.match(c)


async def test_recovery_code_works_for_2fa_login(client, admin_token, reset_2fa):
    _, codes = await _enable_2fa(client, admin_token)
    r1 = await client.post("/api/admin/auth/login", json={"email": EMAIL, "password": PASS})
    challenge = r1.json()["challenge"]
    r2 = await client.post(
        "/api/admin/auth/2fa", json={"challenge": challenge, "code": codes[0]}
    )
    assert r2.status_code == 200, r2.text
    assert "access" in r2.json()


async def test_recovery_code_single_use(client, admin_token, reset_2fa):
    _, codes = await _enable_2fa(client, admin_token)
    # use first code
    r1 = await client.post("/api/admin/auth/login", json={"email": EMAIL, "password": PASS})
    chal1 = r1.json()["challenge"]
    await client.post("/api/admin/auth/2fa", json={"challenge": chal1, "code": codes[0]})
    # try to reuse same code
    r2 = await client.post("/api/admin/auth/login", json={"email": EMAIL, "password": PASS})
    chal2 = r2.json()["challenge"]
    r3 = await client.post(
        "/api/admin/auth/2fa", json={"challenge": chal2, "code": codes[0]}
    )
    assert r3.status_code == 401


async def test_recovery_codes_concurrent_use(client, admin_token, reset_2fa):
    """Two concurrent /auth/2fa calls with the SAME recovery code must
    have at most one succeed (DB-level single-use guarantee)."""
    import asyncio

    import pyotp

    # Set up 2FA and grab the codes
    r1 = await client.post(
        "/api/admin/account/2fa/setup",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    secret = r1.json()["secret"]
    code = pyotp.TOTP(secret).now()
    enable = await client.post(
        "/api/admin/account/2fa/enable",
        json={"code": code},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    rc = enable.json()["recovery_codes"][0]

    # Issue two challenges
    chal1 = (await client.post(
        "/api/admin/auth/login", json={"email": EMAIL, "password": PASS}
    )).json()["challenge"]
    chal2 = (await client.post(
        "/api/admin/auth/login", json={"email": EMAIL, "password": PASS}
    )).json()["challenge"]

    # Fire both /auth/2fa calls concurrently with the same recovery code
    results = await asyncio.gather(
        client.post("/api/admin/auth/2fa", json={"challenge": chal1, "code": rc}),
        client.post("/api/admin/auth/2fa", json={"challenge": chal2, "code": rc}),
        return_exceptions=False,
    )
    statuses = sorted([r.status_code for r in results])
    # Exactly one 200, the other 401
    assert statuses == [200, 401], f"Expected [200, 401], got {statuses}"


async def test_regenerate_replaces_all_codes(client, admin_token, reset_2fa):
    import pyotp
    secret, old_codes = await _enable_2fa(client, admin_token)
    fresh_totp = pyotp.TOTP(secret).now()
    r = await client.post(
        "/api/admin/account/2fa/recovery-codes/regenerate",
        json={"current_code": fresh_totp},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    new_codes = r.json()["recovery_codes"]
    assert len(new_codes) == 8
    assert set(new_codes).isdisjoint(set(old_codes))
    # old codes no longer work
    r2 = await client.post("/api/admin/auth/login", json={"email": EMAIL, "password": PASS})
    chal = r2.json()["challenge"]
    r3 = await client.post(
        "/api/admin/auth/2fa", json={"challenge": chal, "code": old_codes[0]}
    )
    assert r3.status_code == 401
