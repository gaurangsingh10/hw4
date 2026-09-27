"""Password hashing and signed session cookies for Campus Customs.

Passwords are never stored or logged in plain text. We store only a salted,
slow PBKDF2-HMAC-SHA256 hash:

    pbkdf2_sha256$<iterations>$<salt hex>$<hash hex>      (current format)
    pbkdf2_sha256$<salt>$<hash hex>                       (legacy seed format, 120k iterations)

Legacy hashes still verify, and are upgraded to the current format on the next
successful login.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 600_000  # OWASP's recommended minimum for PBKDF2-HMAC-SHA256
LEGACY_ITERATIONS = 120_000  # what the seed database was hashed with
SALT_BYTES = 16

SESSION_COOKIE = "cc_session"
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60

SECRET_KEY_PATH = Path(__file__).resolve().parent / ".secret_key"


# ---------- Passwords ----------

def _pbkdf2(password: str, salt: bytes, iterations: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations).hex()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(SALT_BYTES)
    return f"{ALGORITHM}${ITERATIONS}${salt.hex()}${_pbkdf2(password, salt, ITERATIONS)}"


def verify_password(password: str, stored: str) -> bool:
    parts = stored.split("$")
    if parts[0] != ALGORITHM:
        return False
    if len(parts) == 4:
        _, iterations, salt_hex, expected = parts
        actual = _pbkdf2(password, bytes.fromhex(salt_hex), int(iterations))
    elif len(parts) == 3:
        _, salt, expected = parts
        actual = _pbkdf2(password, salt.encode(), LEGACY_ITERATIONS)
    else:
        return False
    return hmac.compare_digest(actual, expected)


def needs_rehash(stored: str) -> bool:
    parts = stored.split("$")
    return len(parts) != 4 or int(parts[1]) < ITERATIONS


# Used when an email is not found, so failed logins take the same time either
# way and attackers can't probe which emails have accounts.
DUMMY_HASH = hash_password(secrets.token_hex(16))


# ---------- Sessions ----------

def _load_secret_key() -> bytes:
    env = os.environ.get("CAMPUS_CUSTOMS_SECRET_KEY")
    if env:
        return env.encode()
    if not SECRET_KEY_PATH.exists():
        SECRET_KEY_PATH.write_text(secrets.token_hex(32))
        SECRET_KEY_PATH.chmod(0o600)
    return SECRET_KEY_PATH.read_text().strip().encode()


SECRET_KEY = _load_secret_key()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def create_session_token(user_id: int) -> str:
    payload = _b64(json.dumps({"uid": user_id, "exp": int(time.time()) + SESSION_TTL_SECONDS}).encode())
    sig = _b64(hmac.new(SECRET_KEY, payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def read_session_token(token: str | None) -> int | None:
    """Return the user id if the token is authentic and unexpired, else None."""
    if not token or "." not in token:
        return None
    payload, sig = token.rsplit(".", 1)
    expected = _b64(hmac.new(SECRET_KEY, payload.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        data = json.loads(_unb64(payload))
    except ValueError:
        return None
    if data.get("exp", 0) < time.time():
        return None
    return data.get("uid")


# ---------- Brute-force throttling ----------

MAX_FAILURES = 5
LOCKOUT_SECONDS = 15 * 60
_failures: dict[str, list[float]] = {}


def is_locked_out(key: str) -> bool:
    now = time.time()
    recent = [t for t in _failures.get(key, []) if now - t < LOCKOUT_SECONDS]
    _failures[key] = recent
    return len(recent) >= MAX_FAILURES


def record_failure(key: str) -> None:
    _failures.setdefault(key, []).append(time.time())


def clear_failures(key: str) -> None:
    _failures.pop(key, None)
