"""E-mail copies of notifications (optional). Off unless FERRERO_SMTP_HOST is set; notifications always appear in the app.

Each check sends one message per recipient listing their new reminders, with links back to the case when
FERRERO_PUBLIC_URL is set. FERRERO_NOTIFY_EMAIL_TO sends every message to one mailbox instead of the case owners'
(for a demonstration or a test: the users' own addresses may not receive mail).
"""
from __future__ import annotations

import os
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any


@dataclass(frozen=True)
class MailSettings:
    host: str
    port: int
    sender: str
    username: str | None = None
    password: str | None = None
    security: str = "starttls"      # starttls | ssl | none
    redirect_to: str | None = None
    public_url: str | None = None

    @classmethod
    def from_env(cls) -> MailSettings | None:
        env = os.environ.get
        host = env("FERRERO_SMTP_HOST")
        if not host:
            return None
        security = (env("FERRERO_SMTP_SECURITY") or "starttls").lower()
        if security not in ("starttls", "ssl", "none"):
            raise ValueError("FERRERO_SMTP_SECURITY must be starttls, ssl or none")
        default_port = {"ssl": 465, "starttls": 587, "none": 25}[security]
        username = env("FERRERO_SMTP_USERNAME") or None
        return cls(host=host, port=int(env("FERRERO_SMTP_PORT") or default_port),
                   sender=env("FERRERO_SMTP_FROM") or username or "ferrero@localhost", username=username,
                   password=env("FERRERO_SMTP_PASSWORD") or None, security=security,
                   redirect_to=env("FERRERO_NOTIFY_EMAIL_TO") or None,
                   public_url=(env("FERRERO_PUBLIC_URL") or "").rstrip("/") or None)


class Mailer:
    def __init__(self, settings: MailSettings):
        self.settings = settings

    @classmethod
    def from_env(cls) -> Mailer | None:
        found = MailSettings.from_env()
        return cls(found) if found else None

    def send(self, to: str, subject: str, text: str) -> None:
        s = self.settings
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = s.sender, to, subject
        msg.set_content(text)
        smtp_cls: Any = smtplib.SMTP_SSL if s.security == "ssl" else smtplib.SMTP
        kwargs = {"context": ssl.create_default_context()} if s.security == "ssl" else {}
        with smtp_cls(s.host, s.port, timeout=20, **kwargs) as smtp:
            if s.security == "starttls":
                smtp.starttls(context=ssl.create_default_context())
            if s.username:
                smtp.login(s.username, s.password or "")
            smtp.send_message(msg)


def compose(name: str, items: list[dict[str, Any]], public_url: str | None) -> tuple[str, str]:
    """Subject and plain-text body of one recipient's reminder message."""
    subject = f"Ferrero: {items[0]['title']} ({items[0]['case_id']})" if len(items) == 1 else \
        f"Ferrero: {len(items)} case reminders"
    lines = [f"Hello {name.split(' ')[0]},", "", "Ferrero case intelligence has new reminders for you:", ""]
    for n in items:
        lines.append(f"- {n['title']}")
        lines.append(f"  {n['body']}")
        if public_url:
            lines.append(f"  {public_url}{n['link']}")
        lines.append("")
    lines.append("You also see these under the bell in Ferrero.")
    return subject, "\n".join(lines)
