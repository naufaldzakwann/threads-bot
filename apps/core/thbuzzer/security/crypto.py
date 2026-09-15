"""AES-256-GCM + keyring/DPAPI (§18). AAD = kolom+id via HKDF. Tanpa backdoor."""
from __future__ import annotations

import base64
import os
import secrets

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

SERVICE = "THBuzzer"
KEY_NAME = "master-key-v1"


def _load_or_create_master_key() -> bytes:
    try:
        import keyring  # type: ignore

        raw = keyring.get_password(SERVICE, KEY_NAME)
        if raw:
            return base64.b64decode(raw)
        key = secrets.token_bytes(32)
        try:
            keyring.set_password(SERVICE, KEY_NAME, base64.b64encode(key).decode())
        except Exception:
            pass
        return key
    except Exception:
        # Fallback dev: env var (prod Windows memakai Credential Manager/DPAPI via keyring)
        env = os.environ.get("THBUZZER_MASTER_KEY")
        if env:
            return base64.b64decode(env)
        return secrets.token_bytes(32)


_MASTER = _load_or_create_master_key()


def _subkey(column: str, row_id: str) -> bytes:
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=f"{column}:{row_id}".encode())
    return hkdf.derive(_MASTER)


def encrypt(plaintext: str, column: str, row_id: str) -> str:
    """Return base64(nonce||ct). Plaintext '' -> ''."""
    if not plaintext:
        return ""
    aes = AESGCM(_subkey(column, row_id))
    nonce = secrets.token_bytes(12)
    ct = aes.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ct).decode()


def decrypt(blob: str, column: str, row_id: str) -> str:
    if not blob:
        return ""
    raw = base64.b64decode(blob)
    nonce, ct = raw[:12], raw[12:]
    aes = AESGCM(_subkey(column, row_id))
    try:
        return aes.decrypt(nonce, ct, None).decode("utf-8")
    except InvalidTag as e:
        raise ValueError("decrypt failed: wrong key/column/id") from e
