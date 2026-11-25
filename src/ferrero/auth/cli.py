"""``python -m ferrero.auth``: manage sign-in passwords and sessions.

    python -m ferrero.auth accounts                 everyone with an account: role, password state, access, last sign-in
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
    auth = Auth(settings, CaseModel(settings.csv_dir, settings.today, catalogue=settings.catalogue_path))
    if args.command == "accounts":
        for u in auth.directory():
            state = "active" if u["active"] else "DISABLED"
            print(f"{u['user_id']:<6} {u['email']:<34} {u['entra_group']:<15} {u['password']:<11} {state:<9} "
                  f"last sign-in {u['last_sign_in'] or 'never'}")
        if not settings.admin_password:
            print("\nFERRERO_PASSWORD is not set: the platform administrator can't sign in.")
        if not settings.demo_password:
            print("FERRERO_DEMO_PASSWORD is not set: other accounts sign in with a password of their own "
                  "(the administrator gives temporary ones on the Users page).")
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
