import pyotp

from app.services.totp import generate_secret, otpauth_uri, qr_svg, verify


def test_generate_secret_format():
    secret = generate_secret()
    assert len(secret) == 32
    # base32 alphabet: A-Z 2-7
    assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" for c in secret)


def test_otpauth_uri_includes_email_and_issuer():
    uri = otpauth_uri(secret="ABC234", email="hi@wangyang.dev")
    assert uri.startswith("otpauth://totp/")
    assert "hi%40wangyang.dev" in uri or "hi@wangyang.dev" in uri
    assert "secret=ABC234" in uri
    assert "issuer=" in uri


def test_qr_svg_returns_svg_string():
    svg = qr_svg("otpauth://totp/test?secret=ABC&issuer=test")
    assert svg.startswith("<?xml") or svg.startswith("<svg")
    assert "</svg>" in svg


def test_verify_accepts_current_code():
    secret = generate_secret()
    code = pyotp.TOTP(secret).now()
    assert verify(secret, code) is True


def test_verify_rejects_wrong_code():
    secret = generate_secret()
    assert verify(secret, "000000") is False


import pytest

EMAIL = "hi@wangyang.dev"
PASS = "changeme"


@pytest.fixture
async def admin_token(client):
    r = await client.post("/api/admin/auth/login", json={"email": EMAIL, "password": PASS})
    assert r.status_code == 200
    return r.json()["access"]


@pytest.fixture
async def reset_2fa(client, admin_token):
    """Cleanup: disable 2fa after each test that touched it."""
    yield
    from sqlalchemy import update
    from app.db import AsyncSessionLocal
    from app.models import Account
    async with AsyncSessionLocal() as s:
        await s.execute(
            update(Account).where(Account.id == 1).values(
                tfa_enabled=False, tfa_secret_encrypted=None
            )
        )
        await s.commit()


async def test_setup_returns_secret_and_qr(client, admin_token, reset_2fa):
    r = await client.post(
        "/api/admin/account/2fa/setup",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["secret"]) == 32
    assert body["otpauth_uri"].startswith("otpauth://totp/")
    assert "<svg" in body["qr_svg"] or body["qr_svg"].startswith("<?xml")


async def test_enable_with_correct_code_flips_flag(client, admin_token, reset_2fa):
    import pyotp
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
    assert r2.status_code == 200, r2.text
    # session endpoint should now report tfa_enabled
    r3 = await client.get(
        "/api/admin/session", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert r3.json()["tfa_enabled"] is True


async def test_enable_with_wrong_code_400(client, admin_token, reset_2fa):
    await client.post(
        "/api/admin/account/2fa/setup",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    r = await client.post(
        "/api/admin/account/2fa/enable",
        json={"code": "000000"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 400


async def test_disable_with_correct_code(client, admin_token, reset_2fa):
    import pyotp
    setup = await client.post(
        "/api/admin/account/2fa/setup",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    secret = setup.json()["secret"]
    code = pyotp.TOTP(secret).now()
    await client.post(
        "/api/admin/account/2fa/enable",
        json={"code": code},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    code2 = pyotp.TOTP(secret).now()
    r = await client.request(
        "DELETE",
        "/api/admin/account/2fa",
        json={"current_code": code2},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 204
