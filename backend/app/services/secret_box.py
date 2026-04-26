"""AES-GCM symmetric encryption for at-rest secrets (e.g. TOTP secret).

Key is derived from `settings.secrets_key` via SHA-256 → 32 bytes.
Output format (base64-encoded for DB string storage):

    nonce(12) || ciphertext+tag

`encrypt` and `decrypt` operate on Python str <-> str. Use this module ONLY
for short server-side secrets that need symmetric retrieval; never for user
passwords (use argon2 there).
"""
from __future__ import annotations

import base64
import hashlib
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings


class SecretBoxError(Exception):
    pass


def _key() -> bytes:
    raw = get_settings().secrets_key.get_secret_value().encode()
    return hashlib.sha256(raw).digest()


def encrypt(plaintext: str) -> str:
    nonce = os.urandom(12)
    box = AESGCM(_key())
    ct = box.encrypt(nonce, plaintext.encode(), associated_data=None)
    return base64.urlsafe_b64encode(nonce + ct).decode()


def decrypt(blob: str) -> str:
    try:
        raw = base64.urlsafe_b64decode(blob.encode())
    except Exception as e:
        raise SecretBoxError("invalid encoding") from e
    if len(raw) < 13:
        raise SecretBoxError("blob too short")
    nonce, ct = raw[:12], raw[12:]
    box = AESGCM(_key())
    try:
        return box.decrypt(nonce, ct, associated_data=None).decode()
    except InvalidTag as e:
        raise SecretBoxError("authentication failed") from e
