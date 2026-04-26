import pytest

from app.services.secret_box import SecretBoxError, decrypt, encrypt


def test_round_trip():
    blob = encrypt("totp-secret-XYZ")
    assert isinstance(blob, str)         # base64 string for DB storage
    assert blob != "totp-secret-XYZ"
    assert decrypt(blob) == "totp-secret-XYZ"


def test_tampered_ciphertext_raises():
    blob = encrypt("hello")
    # flip a byte in the middle
    flipped = blob[:8] + ("A" if blob[8] != "A" else "B") + blob[9:]
    with pytest.raises(SecretBoxError):
        decrypt(flipped)


def test_distinct_ciphertexts_for_same_plaintext():
    a = encrypt("same")
    b = encrypt("same")
    assert a != b                        # nonce randomised
    assert decrypt(a) == decrypt(b) == "same"


def test_encrypted_blob_fits_in_db_column():
    """A 32-char base32 TOTP secret encrypts to a blob ≤ 256 chars (the column width)."""
    secret = "A" * 32
    blob = encrypt(secret)
    assert len(blob) <= 256
