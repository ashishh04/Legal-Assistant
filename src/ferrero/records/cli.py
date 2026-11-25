"""``python -m ferrero.records``: check deadlines and send reminders, verify the audit trail and the evidence files.

    python -m ferrero.records reminders [--date YYYY-MM-DD] [--email]   create the reminders due (e-mail them too)
    python -m ferrero.records verify                                    audit chain + every evidence file's fingerprint
    python -m ferrero.records status                                    what the store holds

The web app checks deadlines by itself (at start, every FERRERO_REMINDER_MINUTES and after each change); use
`reminders` from a scheduler when the app isn't running all the time.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from ..casemodel import CaseModel
from ..config import get_settings
from .mailer import Mailer
from .service import CaseRecords


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ferrero-records", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    rem = sub.add_parser("reminders", help="create the reminders due today")
    rem.add_argument("--date", type=date.fromisoformat, help="check as of this date instead of today")
    rem.add_argument("--email", action="store_true", help="also e-mail them (needs FERRERO_SMTP_HOST)")
    sub.add_parser("verify", help="check the audit chain and every evidence file")
    sub.add_parser("status", help="counts of what the store holds")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    settings = get_settings()
    model = CaseModel(settings.csv_dir, settings.today, catalogue=settings.catalogue_path)
    records = CaseRecords(settings, model, mailer=Mailer.from_env())
    if args.command == "reminders":
        created = records.run_reminders(args.date)
        print(f"{created} new notifications as of {(args.date or model.today).isoformat()}")
        if args.email:
            if records.mailer is None:
                print("E-mail is off: set FERRERO_SMTP_HOST (see .env.example).")
                return 1
            print(f"{records.deliver_email()} notifications e-mailed")
        return 0
    if args.command == "verify":
        found = records.verify()
        audit = found["audit"]
        print(f"Audit trail: {'intact' if audit['ok'] else 'BROKEN'} ({audit['entries']} entries checked)"
              + ("" if audit["ok"] else f" - {audit['first_bad']}: {audit['problem']}"))
        print(f"Evidence files: {found['evidence_checked'] - len(found['evidence_problems'])} of "
              f"{found['evidence_checked']} match their fingerprints"
              + (f"; problems: {', '.join(found['evidence_problems'])}" if found["evidence_problems"] else ""))
        return 0 if audit["ok"] and not found["evidence_problems"] else 1
    with records.store.read() as conn:
        for table, label in (("case_fields", "changed case fields"), ("evidence", "evidence items"),
                             ("follow_ups", "follow-ups"), ("notifications", "notifications"),
                             ("audit_log", "audit entries")):
            print(f"{conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]:>6}  {label}")
    print(f"Store: {settings.records_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
