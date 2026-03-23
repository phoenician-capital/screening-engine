"""
SMTP email sender — used for daily digest emails.
Uses stdlib smtplib, runs in a thread pool to stay non-blocking.
"""
from __future__ import annotations

import logging
import smtplib
from concurrent.futures import ThreadPoolExecutor
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.config.settings import settings

logger = logging.getLogger(__name__)


def _send_blocking(subject: str, body_html: str, to: str, from_: str) -> bool:
    cfg = settings.email
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_
    msg["To"] = to
    msg.attach(MIMEText(body_html, "html"))
    try:
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.login(cfg.smtp_user, cfg.smtp_password)
            server.sendmail(from_, [to], msg.as_string())
        logger.info("Digest email sent to %s", to)
        return True
    except Exception as e:
        logger.error("Failed to send digest email: %s", e)
        return False


async def send_digest_email(
    subject: str,
    body_html: str,
    to: str | None = None,
    from_: str | None = None,
) -> bool:
    cfg = settings.email
    if not cfg.configured:
        logger.warning("SMTP not configured — skipping digest email (set SMTP_PASSWORD)")
        return False

    recipient = to or cfg.digest_recipient
    sender = from_ or cfg.from_address

    loop_executor = ThreadPoolExecutor(max_workers=1)
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        loop_executor,
        _send_blocking,
        subject, body_html, recipient, sender,
    )
