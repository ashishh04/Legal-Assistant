"""Sign-in: who may sign in, with which password, and the sessions that follow.

Accounts are the people in the user directory (dim_user), with their e-mail address as the sign-in name (the user id,
e.g. U-08, works too). A person's password is their own once they have set one; until then the starting password
FERRERO_DEMO_PASSWORD applies, if set. With neither, that account can't sign in: there is no built-in default password.

A session is a random token in an HttpOnly cookie; only its SHA-256 is stored. It ends after FERRERO_SESSION_HOURS
without activity (FERRERO_SESSION_REMEMBER_DAYS with "keep me signed in"), on sign-out, or when the password changes.
Repeated failures lock a sign-in name for 15 minutes; the same message answers a wrong password and an unknown name.
"""
from __future__ import annotations

import csv
import hashlib
import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from functools import cached_property
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..casemodel import CaseModel
from ..config import Settings
from ..security import Principal
from .passwords import hash_password, password_problem, verify_password
from .store import AuthStore

WINDOW_S = 15 * 60          # failures counted over this window ...
MAX_FAILURES_PER_LOGIN = 5  # ... lock a sign-in name after this many
MAX_FAILURES_PER_IP = 25    # ... and a client address after this many
TOUCH_EVERY_S = 300         # how often an active session's expiry is pushed back
WRONG = "The e-mail address or password is incorrect."


class AuthError(Exception):
    def __init__(self, message: str, status: int = 400, code: str | None = None):
        super().__init__(message)
        self.message, self.status, self.code = message, status, code


@dataclass(frozen=True)
class Account:
    user_id: str
    full_name: str
    job_title: str
    entra_group: str
    email: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="seconds")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def load_accounts(path: Path) -> dict[str, Account]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {r["user_id"]: Account(r["user_id"], r["full_name"], r["job_title"], r["entra_group"], r.get("email") or "")
                for r in csv.DictReader(f)}


class Auth:
    def __init__(self, settings: Settings, model: CaseModel):
        self.settings, self.model = settings, model
        self.store = AuthStore(settings.records_dir / "auth.sqlite")
        self.accounts = load_accounts(settings.csv_dir / "dim_user.csv")
        self._by_email = {a.email.casefold(): a for a in self.accounts.values() if a.email}
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    @cached_property
    def _starting(self) -> str | None:
        """The starting password, hashed: checked like any stored one, so timing doesn't tell which applies."""
        return hash_password(self.settings.demo_password) if self.settings.demo_password else None

    @cached_property
    def _dummy(self) -> str:
        """Checked against for unknown names: the same work, and the same answer, as a wrong password."""
        return hash_password(secrets.token_urlsafe(16))

    # ---------- accounts ----------
    def find(self, login: str) -> Account | None:
        login = (login or "").strip()
        return self.accounts.get(login.upper()) or self._by_email.get(login.casefold())

    def _stored_hash(self, user_id: str) -> str | None:
        with self.store.connect() as conn:
            row = conn.execute("SELECT password_hash FROM credentials WHERE user_id = ?", (user_id,)).fetchone()
        return row["password_hash"] if row else None

    def has_own_password(self, user_id: str) -> bool:
        return self._stored_hash(user_id) is not None

    @property
    def configured(self) -> bool:
        """Whether anyone can sign in at all (a starting password, or someone's own)."""
        if self.settings.demo_password:
            return True
        with self.store.connect() as conn:
            return conn.execute("SELECT 1 FROM credentials LIMIT 1").fetchone() is not None

    def public_accounts(self) -> list[dict[str, str]]:
        """The accounts the sign-in page may list (FERRERO_LOGIN_SHOW_ACCOUNTS), without any password information."""
        return [{"user_id": a.user_id, "full_name": a.full_name, "job_title": a.job_title, "entra_group": a.entra_group,
                 "email": a.email} for a in self.accounts.values()]

    def profile(self, principal: Principal) -> dict[str, Any]:
        a = self.accounts.get(principal.user_id)
        return {"email": a.email if a else "", "own_password": self.has_own_password(principal.user_id)}

    # ---------- throttling ----------
    def _recent(self, key: str, now: float) -> deque[float]:
        q = self._failures[key]
        while q and q[0] < now - WINDOW_S:
            q.popleft()
        return q

    def _locked(self, login: str, ip: str | None) -> bool:
        now = time.monotonic()
        with self._lock:
            return (len(self._recent(f"login:{login.casefold()}", now)) >= MAX_FAILURES_PER_LOGIN
                    or bool(ip) and len(self._recent(f"ip:{ip}", now)) >= MAX_FAILURES_PER_IP)

    def _fail(self, login: str, ip: str | None) -> None:
        now = time.monotonic()
        with self._lock:
            self._recent(f"login:{login.casefold()}", now).append(now)
            if ip:
                self._recent(f"ip:{ip}", now).append(now)

    def _log(self, login: str, account: Account | None, ip: str | None, ok: bool, reason: str | None) -> None:
        with self.store.connect() as conn:
            conn.execute("INSERT INTO sign_ins (at, user_id, login, ip, ok, reason) VALUES (?, ?, ?, ?, ?, ?)",
                         (_iso(_now()), account.user_id if account else None, login[:200], ip, int(ok), reason))

    # ---------- signing in and out ----------
    def _password_ok(self, account: Account | None, password: str) -> bool:
        stored = self._stored_hash(account.user_id) if account else None
        target = stored or (self._starting if account else None)
        if target is None:
            verify_password(password, self._dummy)  # same work either way
            return False
        return verify_password(password, target)

    def login(self, login: str, password: str, *, ip: str | None = None, user_agent: str | None = None,
              remember: bool = False) -> tuple[str, Principal, int | None]:
        """Check the password and open a session: (token, principal, cookie max-age or None for a browser session)."""
        login = (login or "").strip()
        if not login or not password:
            raise AuthError("Enter your e-mail address and password.", 400, "missing")
        if self._locked(login, ip):
            self._log(login, self.find(login), ip, False, "locked")
            raise AuthError("Too many unsuccessful attempts. Please wait 15 minutes and try again.", 429, "locked")
        account = self.find(login)
        if not self._password_ok(account, password):
            self._fail(login, ip)
            self._log(login, account, ip, False, "wrong password" if account else "unknown name")
            raise AuthError(WRONG, 401, "bad_credentials")
        principal = self.model.principal(account.user_id) if account else None
        if principal is None or not principal.role.case_groups:
            self._log(login, account, ip, False, "no access")
            raise AuthError("This account does not have access to Ferrero. Please contact Legal Operations.", 403, "no_access")
        with self._lock:
            self._failures.pop(f"login:{login.casefold()}", None)
        token = secrets.token_urlsafe(32)
        now = _now()
        idle = self._idle(remember)
        with self.store.connect() as conn:
            conn.execute("DELETE FROM sessions WHERE expires_at < ?", (_iso(now),))  # tidy up
            conn.execute("INSERT INTO sessions (token_hash, user_id, created_at, last_seen_at, expires_at, persistent, ip, "
                         "user_agent) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                         (_token_hash(token), account.user_id, _iso(now), _iso(now), _iso(now + idle), int(remember), ip,
                          (user_agent or "")[:300]))
        self._log(login, account, ip, True, None)
        return token, principal, int(idle.total_seconds()) if remember else None

    def _idle(self, persistent: bool) -> timedelta:
        return (timedelta(days=self.settings.session_remember_days) if persistent
                else timedelta(hours=self.settings.session_hours))

    def session(self, token: str | None) -> Principal | None:
        """The signed-in principal for a session token, or None (unknown, expired). Activity extends the session."""
        if not token or len(token) > 200:
            return None
        key, now = _token_hash(token), _now()
        with self.store.connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE token_hash = ?", (key,)).fetchone()
            if row is None:
                return None
            if row["expires_at"] < _iso(now):
                conn.execute("DELETE FROM sessions WHERE token_hash = ?", (key,))
                return None
            if datetime.fromisoformat(row["last_seen_at"]) < now - timedelta(seconds=TOUCH_EVERY_S):
                conn.execute("UPDATE sessions SET last_seen_at = ?, expires_at = ? WHERE token_hash = ?",
                             (_iso(now), _iso(now + self._idle(bool(row["persistent"]))), key))
        return self.model.principal(row["user_id"])

    def logout(self, token: str | None) -> None:
        if token:
            with self.store.connect() as conn:
                conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))

    # ---------- passwords ----------
    def change_password(self, principal: Principal, current: str, new: str, keep_token: str | None) -> None:
        """Set the user's own password; their other sessions end (the current one stays)."""
        account = self.accounts.get(principal.user_id)
        if account is None or not self._password_ok(account, current or ""):
            raise AuthError("Your current password is incorrect.", 400, "bad_current")
        problem = password_problem(new or "", email=account.email, full_name=account.full_name)
        if problem:
            raise AuthError(problem, 400, "weak_password")
        if new == current:
            raise AuthError("Choose a password different from the current one.", 400, "same_password")
        self.set_password(account.user_id, new, keep_token=keep_token)

    def set_password(self, user_id: str, password: str, keep_token: str | None = None) -> None:
        with self.store.connect() as conn:
            conn.execute("INSERT INTO credentials (user_id, password_hash, set_at) VALUES (?, ?, ?) "
                         "ON CONFLICT(user_id) DO UPDATE SET password_hash = excluded.password_hash, set_at = excluded.set_at",
                         (user_id, hash_password(password), _iso(_now())))
            conn.execute("DELETE FROM sessions WHERE user_id = ? AND token_hash <> ?",
                         (user_id, _token_hash(keep_token) if keep_token else ""))

    def clear_password(self, user_id: str) -> bool:
        """Back to the starting password (FERRERO_DEMO_PASSWORD); ends the user's sessions."""
        with self.store.connect() as conn:
            gone = conn.execute("DELETE FROM credentials WHERE user_id = ?", (user_id,)).rowcount
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        return bool(gone)

    def end_sessions(self, user_id: str | None = None) -> int:
        with self.store.connect() as conn:
            if user_id:
                return conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,)).rowcount
            return conn.execute("DELETE FROM sessions").rowcount
