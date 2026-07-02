"""
Optional email delivery (the *Send a message / Gmail* step).

Disabled unless SMTP settings are supplied via environment variables, so the
pipeline never sends anything by accident. For Gmail use an App Password.

    JOBSCREENER_SMTP_HOST   (e.g. smtp.gmail.com)
    JOBSCREENER_SMTP_PORT   (e.g. 465)
    JOBSCREENER_SMTP_USER   (your address)
    JOBSCREENER_SMTP_PASS   (app password)
    JOBSCREENER_EMAIL_TO    (recipient; defaults to SMTP_USER)
"""
from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def email_configured() -> bool:
    return all(os.environ.get(k) for k in
               ("JOBSCREENER_SMTP_HOST", "JOBSCREENER_SMTP_USER", "JOBSCREENER_SMTP_PASS"))


def send_report(html_body: str, subject: str) -> None:
    if not email_configured():
        raise RuntimeError(
            "Email not configured. Set JOBSCREENER_SMTP_HOST/USER/PASS (and optionally "
            "PORT/EMAIL_TO) to enable delivery."
        )
    host = os.environ["JOBSCREENER_SMTP_HOST"]
    port = int(os.environ.get("JOBSCREENER_SMTP_PORT", "465"))
    user = os.environ["JOBSCREENER_SMTP_USER"]
    password = os.environ["JOBSCREENER_SMTP_PASS"]
    to_addr = os.environ.get("JOBSCREENER_EMAIL_TO", user)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL(host, port) as server:
        server.login(user, password)
        server.sendmail(user, [to_addr], msg.as_string())
