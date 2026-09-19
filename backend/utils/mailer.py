"""
Email verification / reset are SIMULATED per the brief: no SMTP is
configured. We log to outbox.log so the flow is inspectable, and the
signup/forgot-password routes also echo the raw token back in dev mode.
"""
import os
from datetime import datetime

OUTBOX_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "outbox.log")


def send_simulated_email(to: str, subject: str, body: str) -> None:
    line = f"[{datetime.utcnow().isoformat()}Z] TO: {to} | SUBJECT: {subject} | {body}\n"
    with open(OUTBOX_PATH, "a", encoding="utf-8") as f:
        f.write(line)
