"""Sign-in: who may sign in, with which password, and the sessions that follow; and the platform administrator.

Accounts are the people in the user directory: the pack's dim_user, the platform administrator, and the people the
administrator adds. The e-mail address is the sign-in name (the user id, e.g. U-08, works too).

Passwords:
- the administrator (FERRERO_ADMIN_EMAIL, admin@ferrero.com by default) signs in with FERRERO_PASSWORD, which is set in
  the server's configuration and nowhere else;
- anyone else with a password of their own uses it: one they set, or a temporary one the administrator gave them
  (they are asked to change it);
- otherwise the starting password FERRERO_DEMO_PASSWORD applies, if set. With none of these the account can't sign in:
  there is no built-in default password.

The administrator manages users (adds people, disables accounts, sets temporary passwords) and can switch into another
user's view of the portal. The session then acts as that user, with exactly that user's access, and every change it
makes is recorded as "<administrator> as <user>". Every administrative action is logged (admin_log).

A session is a random token in an HttpOnly cookie; only its SHA-256 is stored. It ends after FERRERO_SESSION_HOURS
without activity (FERRERO_SESSION_REMEMBER_DAYS with "keep me signed in"), on sign-out, when the password changes, or
when the account is disabled. Repeated failures lock a sign-in name for 15 minutes; the same message answers a wrong
password and an unknown name.
"""
from __future__ import annotations

import csv
import hashlib
import re
import secrets
import sqlite3
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from functools import cached_property
from pathlib import Path
from typing import Any

from ..casemodel import CaseModel
from ..config import Settings
from ..security import ADMIN_GROUP, ASSIGNABLE_GROUPS, Principal, role_for_group
from .passwords import hash_password, password_problem, verify_password
from .store import AuthStore

WINDOW_S = 15 * 60          # failures counted over this window ...
MAX_FAILURES_PER_LOGIN = 5  # ... lock a sign-in name after this many
MAX_FAILURES_PER_IP = 25    # ... and a client address after this many
TOUCH_EVERY_S = 300         # how often an active session's expiry is pushed back
WRONG = "The e-mail address or password is incorrect."
ADMIN_ID = "U-00"
EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
USER_ID = re.compile(r"U-(\d{2,3})")
TEAMS = {"Legal-UAE": "IP", "Legal-KSA": "Litigation", "Legal-MENA": "Litigation", "Legal-Ops": "Legal Operations",
         "Leadership": "Leadership", "Procurement": "Procurement"}


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
    team: str = ""
    country: str = ""
    source: str = "directory"   # directory (the pack's dim_user) | added (by the administrator) | administrator


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="seconds")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _text(value: Any, label: str, limit: int, *, required: bool = False) -> str:
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise AuthError(f"{label} is required.", 400, "invalid")
        return ""
    if not isinstance(value, str):
        raise AuthError(f"{label} must be text.", 400, "invalid")
    value = " ".join(value.split())
    if len(value) > limit:
        raise AuthError(f"{label} is limited to {limit} characters.", 400, "invalid")
    return value


def load_accounts(path: Path) -> dict[str, Account]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {r["user_id"]: Account(r["user_id"], r["full_name"], r["job_title"], r["entra_group"], r.get("email") or "",
                                      r.get("team") or "", r.get("country") or "")
                for r in csv.DictReader(f)}


class Auth:
    def __init__(self, settings: Settings, model: CaseModel):
        self.settings, self.model = settings, model
        self.store = AuthStore(settings.records_dir / "auth.sqlite")
        self._pack = load_accounts(settings.csv_dir / "dim_user.csv")
        self.admin = Account(ADMIN_ID, "Platform Administrator", "Platform administrator", ADMIN_GROUP,
                             settings.admin_email, "Administration", "UAE", "administrator")
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self.reload_directory()

    # ---------- the directory: the pack's people, the administrator, and the people added ----------
    def reload_directory(self) -> None:
        with self.store.connect() as conn:
            added = [dict(r) for r in conn.execute("SELECT * FROM directory_users ORDER BY user_id")]
            disabled = {r["user_id"] for r in conn.execute("SELECT user_id FROM disabled_users")} - {ADMIN_ID}
        accounts: dict[str, Account] = {**self._pack, ADMIN_ID: self.admin}
        for r in added:
            accounts[r["user_id"]] = Account(r["user_id"], r["full_name"], r["job_title"], r["entra_group"], r["email"],
                                             r["team"], r["country"], "added")
        with self._lock:
            self.accounts = accounts
            self._by_email = {a.email.casefold(): a for a in accounts.values() if a.email}
            self.disabled = frozenset(disabled)
        extra = [self.admin] + [accounts[r["user_id"]] for r in added]
        self.model.set_directory([{"user_id": a.user_id, "full_name": a.full_name, "job_title": a.job_title, "team": a.team,
                                   "country": a.country, "entra_group": a.entra_group, "email": a.email} for a in extra],
                                 self.disabled)

    @cached_property
    def _starting(self) -> str | None:
        """The starting password, hashed: checked like any stored one, so timing doesn't tell which applies."""
        return hash_password(self.settings.demo_password) if self.settings.demo_password else None

    @cached_property
    def _admin_hash(self) -> str | None:
        return hash_password(self.settings.admin_password) if self.settings.admin_password else None

    @cached_property
    def _dummy(self) -> str:
        """Checked against for unknown names: the same work, and the same answer, as a wrong password."""
        return hash_password(secrets.token_urlsafe(16))

    def find(self, login: str) -> Account | None:
        login = (login or "").strip()
        return self.accounts.get(login.upper()) or self._by_email.get(login.casefold())

    def _credential(self, user_id: str) -> sqlite3.Row | None:
        with self.store.connect() as conn:
            return conn.execute("SELECT password_hash, temporary FROM credentials WHERE user_id = ?", (user_id,)).fetchone()

    def has_own_password(self, user_id: str) -> bool:
        """A password of the user's own choosing (the administrator's is set in the configuration)."""
        if user_id == ADMIN_ID:
            return True
        row = self._credential(user_id)
        return row is not None and not row["temporary"]

    @property
    def configured(self) -> bool:
        """Whether anyone can sign in at all (the administrator, a starting password, or someone's own)."""
        if self.settings.demo_password or self.settings.admin_password:
            return True
        with self.store.connect() as conn:
            return conn.execute("SELECT 1 FROM credentials LIMIT 1").fetchone() is not None

    def public_accounts(self) -> list[dict[str, str]]:
        """The accounts the sign-in page may list (FERRERO_LOGIN_SHOW_ACCOUNTS), without any password information."""
        return [{"user_id": a.user_id, "full_name": a.full_name, "job_title": a.job_title, "entra_group": a.entra_group,
                 "email": a.email} for a in self.accounts.values() if a.user_id not in self.disabled]

    def profile(self, principal: Principal) -> dict[str, Any]:
        a = self.accounts.get(principal.user_id)
        return {"email": a.email if a else "",
                # after a switch the view is someone else's: their password is not the administrator's business here
                "own_password": bool(principal.acting_by) or self.has_own_password(principal.user_id),
                "is_admin": principal.is_admin,
                "acting_by": {"user_id": principal.acting_by, "full_name": principal.acting_by_name}
                if principal.acting_by else None}

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
        if account is not None and account.user_id == ADMIN_ID:
            target = self._admin_hash
        else:
            row = self._credential(account.user_id) if account else None
            target = row["password_hash"] if row else (self._starting if account else None)
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
        if account.user_id in self.disabled:
            self._log(login, account, ip, False, "disabled")
            raise AuthError("This account has been disabled. Please contact your administrator.", 403, "disabled")
        principal = self.model.principal(account.user_id)
        if principal is None or not principal.role.case_groups:
            self._log(login, account, ip, False, "no access")
            raise AuthError("This account does not have access to Ferrero. Please contact your administrator.", 403,
                            "no_access")
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

    def _session_row(self, token: str | None) -> sqlite3.Row | None:
        """A live session's row (unknown or expired: None). Activity extends the session."""
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
        return row

    def own_principal(self, token: str | None) -> Principal | None:
        """Who signed in with this session, ignoring a switch into another user's view."""
        row = self._session_row(token)
        return self.model.principal(row["user_id"]) if row else None  # None for a disabled account

    def session(self, token: str | None) -> Principal | None:
        """The principal a request acts as: the signed-in user, or the user the administrator switched into."""
        row = self._session_row(token)
        if row is None:
            return None
        own = self.model.principal(row["user_id"])
        if own is None:
            return None
        if row["acting_as"] and own.is_admin:
            target = self.model.principal(row["acting_as"])
            if target is not None and not target.is_admin:
                return replace(target, acting_by=own.user_id, acting_by_name=own.full_name)
            with self.store.connect() as conn:  # that account was disabled meanwhile: back to the administrator
                conn.execute("UPDATE sessions SET acting_as = NULL WHERE token_hash = ?", (_token_hash(token),))
        return own

    def logout(self, token: str | None) -> None:
        if token:
            with self.store.connect() as conn:
                conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))

    # ---------- switching into another user's view (administrator) ----------
    def _need_admin(self, principal: Principal | None) -> Principal:
        if principal is None or not principal.is_admin or principal.acting_by:
            raise AuthError("This is for the platform administrator.", 403, "not_admin")
        return principal

    def switch(self, token: str | None, user_id: str) -> Principal:
        admin = self._need_admin(self.own_principal(token))
        account = self.find(user_id or "")
        if account is None:
            raise AuthError(f"There is no user {user_id}.", 404, "unknown_user")
        if account.user_id == ADMIN_ID:
            raise AuthError("Choose another user: this is your own account.", 400, "self")
        if account.user_id in self.disabled:
            raise AuthError(f"{account.full_name}'s account is disabled. Enable it first.", 409, "disabled")
        target = self.model.principal(account.user_id)
        if target is None or not target.role.case_groups:
            raise AuthError(f"{account.full_name} has no access to Ferrero.", 409, "no_access")
        with self.store.connect() as conn:
            conn.execute("UPDATE sessions SET acting_as = ? WHERE token_hash = ?", (account.user_id, _token_hash(token or "")))
            self._admin_log(conn, admin.user_id, "switch", account.user_id, f"Switched into {account.full_name}'s view")
        return replace(target, acting_by=admin.user_id, acting_by_name=admin.full_name)

    def switch_back(self, token: str | None) -> Principal:
        row = self._session_row(token)
        admin = self.model.principal(row["user_id"]) if row else None
        if admin is None or not admin.is_admin:
            raise AuthError("This is for the platform administrator.", 403, "not_admin")
        with self.store.connect() as conn:
            conn.execute("UPDATE sessions SET acting_as = NULL WHERE token_hash = ?", (_token_hash(token or ""),))
            if row["acting_as"]:
                self._admin_log(conn, admin.user_id, "switch.back", row["acting_as"], "Returned to the administrator")
        return admin

    # ---------- users (administrator) ----------
    @staticmethod
    def _admin_log(conn: sqlite3.Connection, admin_id: str, action: str, user_id: str | None, detail: str | None) -> None:
        conn.execute("INSERT INTO admin_log (at, admin_id, action, user_id, detail) VALUES (?, ?, ?, ?, ?)",
                     (_iso(_now()), admin_id, action, user_id, detail))

    def countries(self) -> list[str]:
        return sorted({c["country"] for c in self.model.base_cases()} | {"UAE"})

    def directory(self) -> list[dict[str, Any]]:
        """Every account with its access, password state and last sign-in (no password information beyond that)."""
        with self.store.connect() as conn:
            last = {r["user_id"]: r["at"] for r in conn.execute(
                "SELECT user_id, MAX(at) AS at FROM sign_ins WHERE ok = 1 AND user_id IS NOT NULL GROUP BY user_id")}
            creds = {r["user_id"]: r["temporary"] for r in conn.execute("SELECT user_id, temporary FROM credentials")}
        out = []
        for a in sorted(self.accounts.values(), key=lambda a: (a.user_id != ADMIN_ID, a.source == "added", a.user_id)):
            if a.user_id == ADMIN_ID:
                password = "configured" if self.settings.admin_password else "not set"
            elif a.user_id in creds:
                password = "temporary" if creds[a.user_id] else "own"
            else:
                password = "starting" if self.settings.demo_password else "not set"
            out.append({"user_id": a.user_id, "full_name": a.full_name, "job_title": a.job_title, "team": a.team,
                        "country": a.country, "entra_group": a.entra_group, "email": a.email, "source": a.source,
                        "active": a.user_id not in self.disabled, "password": password,
                        "access": role_for_group(a.entra_group).description, "last_sign_in": last.get(a.user_id)})
        return out

    def list_users(self, principal: Principal) -> dict[str, Any]:
        self._need_admin(principal)
        return {"users": self.directory(), "countries": self.countries(), "starting_password": bool(self.settings.demo_password),
                "roles": [{"group": g, "description": role_for_group(g).description} for g in ASSIGNABLE_GROUPS]}

    def _entry(self, user_id: str) -> dict[str, Any]:
        return next(u for u in self.directory() if u["user_id"] == user_id)

    def _clean_profile(self, data: dict[str, Any], *, partial: bool = False) -> dict[str, str]:
        out: dict[str, str] = {}
        if not partial or "full_name" in data:
            out["full_name"] = _text(data.get("full_name"), "The name", 120, required=True)
        if not partial or "job_title" in data:
            out["job_title"] = _text(data.get("job_title"), "The job title", 120, required=True)
        if not partial or "entra_group" in data:
            if data.get("entra_group") not in ASSIGNABLE_GROUPS:
                raise AuthError("Choose the user's role.", 400, "invalid")
            out["entra_group"] = data["entra_group"]
            out["team"] = TEAMS[out["entra_group"]]
        if not partial or "country" in data:
            if data.get("country") not in self.countries():
                raise AuthError("Choose the user's country.", 400, "invalid")
            out["country"] = data["country"]
        return out

    def add_user(self, principal: Principal, data: dict[str, Any]) -> dict[str, Any]:
        """A new person, with a temporary password they are asked to change when they first sign in."""
        admin = self._need_admin(principal)
        profile = self._clean_profile(data)
        email = (data.get("email") or "").strip().lower()
        if len(email) > 200 or not EMAIL.fullmatch(email):
            raise AuthError("Enter a valid work e-mail address.", 400, "invalid")
        if email.casefold() in self._by_email:
            raise AuthError(f"There is already an account for {email}.", 409, "exists")
        password = data.get("password") or ""
        problem = password_problem(password, email=email, full_name=profile["full_name"])
        if problem:
            raise AuthError(problem, 400, "weak_password")
        now = _iso(_now())
        with self.store.connect() as conn:
            taken = set(self.accounts) | {r["user_id"] for r in conn.execute("SELECT user_id FROM directory_users")}
            number = max((int(m.group(1)) for t in taken if (m := USER_ID.fullmatch(t))), default=0) + 1
            user_id = f"U-{number:02d}"
            conn.execute("INSERT INTO directory_users (user_id, full_name, job_title, team, country, entra_group, email, "
                         "created_by, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (user_id, profile["full_name"], profile["job_title"], profile["team"], profile["country"],
                          profile["entra_group"], email, admin.user_id, now, now))
            conn.execute("INSERT INTO credentials (user_id, password_hash, set_at, temporary) VALUES (?, ?, ?, 1)",
                         (user_id, hash_password(password), now))
            self._admin_log(conn, admin.user_id, "user.added", user_id,
                            f"{profile['full_name']} <{email}>, {profile['entra_group']}, {profile['country']}")
        self.reload_directory()
        return self._entry(user_id)

    def update_user(self, principal: Principal, user_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        """Change an added person's details or role, or turn anyone's access off and on."""
        admin = self._need_admin(principal)
        account = self.accounts.get((user_id or "").upper())
        if account is None:
            raise AuthError(f"There is no user {user_id}.", 404, "unknown_user")
        if account.user_id == ADMIN_ID:
            raise AuthError("The administrator's account is set in the server configuration.", 409, "managed")
        if not isinstance(changes, dict) or not changes:
            raise AuthError("Nothing to change.", 400, "invalid")
        details = {k: v for k, v in changes.items() if k != "active"}
        if details and account.source != "added":
            raise AuthError(f"{account.full_name} comes from the company directory: only their access can be turned on "
                            "or off here.", 409, "directory")
        unknown = sorted(set(details) - {"full_name", "job_title", "entra_group", "country"})
        if unknown:
            raise AuthError(f"These details can't be changed: {', '.join(unknown)}.", 400, "invalid")
        profile = self._clean_profile(details, partial=True) if details else {}
        now = _iso(_now())
        with self.store.connect() as conn:
            if profile:
                sets = ", ".join(f"{k} = ?" for k in profile)  # names from _clean_profile only
                conn.execute(f"UPDATE directory_users SET {sets}, updated_at = ? WHERE user_id = ?",
                             [*profile.values(), now, account.user_id])
                self._admin_log(conn, admin.user_id, "user.updated", account.user_id,
                                "; ".join(f"{k}: {v}" for k, v in profile.items()))
            if "active" in changes:
                if not isinstance(changes["active"], bool):
                    raise AuthError("Access must be on or off.", 400, "invalid")
                if not changes["active"] and account.user_id not in self.disabled:
                    conn.execute("INSERT OR IGNORE INTO disabled_users (user_id, disabled_by, disabled_at) VALUES (?, ?, ?)",
                                 (account.user_id, admin.user_id, now))
                    conn.execute("DELETE FROM sessions WHERE user_id = ?", (account.user_id,))
                    conn.execute("UPDATE sessions SET acting_as = NULL WHERE acting_as = ?", (account.user_id,))
                    self._admin_log(conn, admin.user_id, "user.disabled", account.user_id, None)
                elif changes["active"] and account.user_id in self.disabled:
                    conn.execute("DELETE FROM disabled_users WHERE user_id = ?", (account.user_id,))
                    self._admin_log(conn, admin.user_id, "user.enabled", account.user_id, None)
        self.reload_directory()
        return self._entry(account.user_id)

    def set_temporary_password(self, principal: Principal, user_id: str, password: str) -> dict[str, Any]:
        """Give someone a temporary password (for example a new joiner, or a forgotten password); their sessions end."""
        admin = self._need_admin(principal)
        account = self.accounts.get((user_id or "").upper())
        if account is None:
            raise AuthError(f"There is no user {user_id}.", 404, "unknown_user")
        if account.user_id == ADMIN_ID:
            raise AuthError("The administrator's password is set in the server configuration.", 409, "managed")
        problem = password_problem(password or "", email=account.email, full_name=account.full_name)
        if problem:
            raise AuthError(problem, 400, "weak_password")
        self.set_password(account.user_id, password, temporary=True)
        with self.store.connect() as conn:
            self._admin_log(conn, admin.user_id, "password.set", account.user_id, "Temporary password set")
        return self._entry(account.user_id)

    # ---------- passwords ----------
    def change_password(self, principal: Principal, current: str, new: str, keep_token: str | None) -> None:
        """Set the user's own password; their other sessions end (the current one stays)."""
        if principal.acting_by:
            raise AuthError("Return to your own account to change a password.", 400, "acting")
        if principal.user_id == ADMIN_ID:
            raise AuthError("The administrator's password is set in the server configuration.", 400, "managed")
        account = self.accounts.get(principal.user_id)
        if account is None or not self._password_ok(account, current or ""):
            raise AuthError("Your current password is incorrect.", 400, "bad_current")
        problem = password_problem(new or "", email=account.email, full_name=account.full_name)
        if problem:
            raise AuthError(problem, 400, "weak_password")
        if new == current:
            raise AuthError("Choose a password different from the current one.", 400, "same_password")
        self.set_password(account.user_id, new, keep_token=keep_token)

    def set_password(self, user_id: str, password: str, keep_token: str | None = None, temporary: bool = False) -> None:
        with self.store.connect() as conn:
            conn.execute("INSERT INTO credentials (user_id, password_hash, set_at, temporary) VALUES (?, ?, ?, ?) "
                         "ON CONFLICT(user_id) DO UPDATE SET password_hash = excluded.password_hash, set_at = excluded.set_at, "
                         "temporary = excluded.temporary",
                         (user_id, hash_password(password), _iso(_now()), int(temporary)))
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
