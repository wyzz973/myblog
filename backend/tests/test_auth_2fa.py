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
