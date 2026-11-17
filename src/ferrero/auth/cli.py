"""``python -m ferrero.auth``: manage sign-in passwords and sessions.

    python -m ferrero.auth accounts                 who can sign in, with which password, and their last sign-in
    python -m ferrero.auth set-password U-08        set someone's own password (asked for twice, not echoed)
    python -m ferrero.auth reset U-08               back to the starting password (FERRERO_DEMO_PASSWORD)
    python -m ferrero.auth sign-out [U-08]          end the sessions of one user, or of everyone
"""
from __future__ import annotations

import argparse
import getpass
import sys

from ..casemodel import CaseModel
from ..config import get_settings
from .passwords import password_problem
from .service import Auth


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ferrero-auth", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("accounts", help="list the accounts")
    sp = sub.add_parser("set-password", help="set a user's own password")
    sp.add_argument("user", help="user id (U-08) or e-mail address")
    rp = sub.add_parser("reset", help="remove a user's own password (the starting password applies again)")
    rp.add_argument("user")
    so = sub.add_parser("sign-out", help="end sessions")
    so.add_argument("user", nargs="?", help="only this user (default: everyone)")
    args = parser.parse_args(argv)

    settings = get_settings()
    auth = Auth(settings, CaseModel(settings.csv_dir, settings.demo_today, catalogue=settings.catalogue_path))
    if args.command == "accounts":
        with auth.store.connect() as conn:
            last = {r["user_id"]: r["at"] for r in conn.execute(
                "SELECT user_id, MAX(at) AS at FROM sign_ins WHERE ok = 1 GROUP BY user_id")}
        for a in auth.accounts.values():
            password = "own password" if auth.has_own_password(a.user_id) else (
                "starting password" if settings.demo_password else "no password: can't sign in")
            print(f"{a.user_id}  {a.email:<34} {a.entra_group:<12} {password:<28} last sign-in {last.get(a.user_id, 'never')}")
        if not settings.demo_password:
            print("\nFERRERO_DEMO_PASSWORD is not set: only accounts with their own password can sign in.")
        return 0

    account = auth.find(getattr(args, "user", "") or "") if getattr(args, "user", None) else None
    if getattr(args, "user", None) and account is None:
        print(f"No account {args.user}.", file=sys.stderr)
        return 1
    if args.command == "set-password":
        first = getpass.getpass(f"New password for {account.full_name} ({account.email}): ")
        if getpass.getpass("Again: ") != first:
            print("The two entries differ; nothing changed.", file=sys.stderr)
            return 1
        problem = password_problem(first, email=account.email, full_name=account.full_name)
        if problem:
            print(problem, file=sys.stderr)
            return 1
        auth.set_password(account.user_id, first)
        print(f"Password set for {account.full_name}; their other sessions have ended.")
        return 0
    if args.command == "reset":
        print(f"{account.full_name}: " + ("back to the starting password." if auth.clear_password(account.user_id)
                                          else "had no own password; sessions ended."))
        return 0
    ended = auth.end_sessions(account.user_id if account else None)
    print(f"{ended} session(s) ended.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
