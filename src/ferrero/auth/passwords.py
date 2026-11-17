"""Password hashing with scrypt (Python's standard library: no extra dependency) and the rules for new passwords."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

N, R, P, KEY_BYTES = 2**14, 8, 1, 32   # 16 MB of memory per hash: slow to brute-force, quick enough to sign in
MIN_LENGTH, MAX_LENGTH = 10, 200


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=N, r=R, p=P, dklen=KEY_BYTES)
    return f"scrypt${N}${R}${P}${_b64(salt)}${_b64(key)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, key = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = _unb64(key)
        candidate = hashlib.scrypt(password.encode("utf-8"), salt=_unb64(salt), n=int(n), r=int(r), p=int(p),
                                   dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate, expected)


def password_problem(password: str, *, email: str = "", full_name: str = "") -> str | None:
    """Why a new password can't be used, or None."""
    if len(password) < MIN_LENGTH:
        return f"Use at least {MIN_LENGTH} characters."
    if len(password) > MAX_LENGTH:
        return f"Use at most {MAX_LENGTH} characters."
    lowered = password.casefold()
    parts = [email.split("@")[0].casefold(), *(w.casefold() for w in full_name.split() if len(w) >= 4)]
    if any(part and part in lowered for part in parts):
        return "Don't use your name or e-mail address in the password."
    if len(set(password)) < 5:
        return "Use a password with more variety: it repeats too few characters."
    return None
