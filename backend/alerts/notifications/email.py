"""Email dispatch via Gmail SMTP using an App Password.

Ports the email payload structure from the n8n workflows. Sends multipart
HTML + plain-text from the address `FinMate <GMAIL_USER>` over Gmail's
SSL submission port (465).

Requires two env vars set in `.env` / Cloud Run environment:
    GMAIL_USER          your Gmail address
    GMAIL_APP_PASSWORD  16-char App Password from
                        https://myaccount.google.com/apppasswords
                        (NOT the account password — that doesn't work)
"""
from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
SENDER_NAME = "FinMate"


# Recipient allowlist. Gmail's SMTP relay can be flaky to non-Gmail
# providers for new "free" accounts (deliverability throttling). For
# now we only attempt sends to @gmail.com — anyone else returns
# SKIPPED so the AlertLog row reflects why no mail went out.
# Override via env once domain reputation is established.
ALLOWED_RECIPIENT_DOMAINS = tuple(
    d.strip().lower()
    for d in os.environ.get("EMAIL_ALLOWED_DOMAINS", "gmail.com").split(",")
    if d.strip()
)


def send_email(to_address: str, subject: str, html: str, plain: str) -> dict:
    """Send a multipart email. Returns
        {"status": "SENT"}                    on success
        {"status": "SKIPPED", "reason": ...}  recipient outside allowlist
        {"status": "FAILED", "error": "..."}  on any failure
    Caller writes the AlertLog row from this return value."""
    addr_lc = (to_address or "").lower().strip()
    if not addr_lc or "@" not in addr_lc:
        return {"status": "FAILED", "error": "invalid recipient address"}
    domain = addr_lc.rsplit("@", 1)[1]
    if domain not in ALLOWED_RECIPIENT_DOMAINS:
        return {
            "status": "SKIPPED",
            "reason": f"recipient domain '{domain}' not in allowlist",
        }
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_pw = os.environ.get("GMAIL_APP_PASSWORD")
    if not gmail_user or not gmail_pw:
        return {
            "status": "FAILED",
            "error": "GMAIL_USER / GMAIL_APP_PASSWORD missing in environment",
        }

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{SENDER_NAME} <{gmail_user}>"
    msg["To"] = to_address
    msg.set_content(plain)
    msg.add_alternative(html, subtype="html")

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx, timeout=20) as s:
            s.login(gmail_user, gmail_pw)
            s.send_message(msg)
        return {"status": "SENT"}
    except smtplib.SMTPAuthenticationError as e:
        logger.error("Gmail auth failed: %s", e)
        return {
            "status": "FAILED",
            "error": f"AUTH: {e.smtp_error.decode(errors='ignore')}",
        }
    except Exception as e:
        logger.exception("Gmail send failed for %s", to_address)
        return {"status": "FAILED", "error": str(e)}
