"""TOTP wrapper around pyotp + SVG QR via segno."""
from __future__ import annotations

import io

import pyotp
import segno

ISSUER = "wangyang.dev"


def generate_secret() -> str:
    """Returns a 32-char base32 string."""
    return pyotp.random_base32(length=32)


def otpauth_uri(*, secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=ISSUER)


def qr_svg(uri: str) -> str:
    qr = segno.make(uri, micro=False)
    buf = io.BytesIO()
    qr.save(buf, kind="svg", scale=4, dark="black", light=None)
    return buf.getvalue().decode("utf-8")


def verify(secret: str, code: str) -> bool:
    """±1 30-second step window (pyotp default valid_window=1)."""
    return bool(pyotp.TOTP(secret).verify(code, valid_window=1))
