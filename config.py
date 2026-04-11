"""Load and validate environment configuration."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

_BOT_DIR = Path(__file__).resolve().parent
load_dotenv(_BOT_DIR / ".env")

# On Render, set variables in the dashboard — .env is not committed.


def _strip(name: str) -> str | None:
    v = os.getenv(name)
    if v is None or not str(v).strip():
        return None
    return str(v).strip()


def _load() -> None:
    """Populate module-level constants or exit with a clear message (for Render logs)."""
    missing: list[str] = []
    bad_int: list[str] = []

    def req_str(key: str) -> str:
        v = _strip(key)
        if v is None:
            missing.append(key)
            return ""
        return v

    def req_int(key: str) -> int:
        v = _strip(key)
        if v is None:
            missing.append(key)
            return 0
        try:
            return int(v)
        except ValueError:
            bad_int.append(key)
            return 0

    global BOT_TOKEN, GUILD_ID, STAFF_ROLE_ID, TOS_AGREED_ROLE_ID
    global COMMISSIONS_OPEN_ROLE_ID, PLEASE_VOUCH_ROLE_ID, TICKET_CATEGORY_ID
    global NOTED_CATEGORY_ID, PROCESSING_CATEGORY_ID, DONE_CATEGORY_ID
    global QUEUE_CHANNEL_ID, SHOP_STATUS_CHANNEL_ID, TRANSCRIPT_CHANNEL_ID
    global VOUCHES_CHANNEL_ID, ORDER_NOTIFS_CHANNEL_ID, START_HERE_CHANNEL_ID
    global TOS_CHANNEL_ID, PAYMENT_CHANNEL_ID, WARN_LOG_CHANNEL_ID
    global GCASH_DETAILS, PAYPAL_LINK, KOFI_LINK, GCASH_QR_URL, PAYPAL_QR_URL

    BOT_TOKEN = req_str("BOT_TOKEN")
    GUILD_ID = req_int("GUILD_ID")
    STAFF_ROLE_ID = req_int("STAFF_ROLE_ID")
    TOS_AGREED_ROLE_ID = req_int("TOS_AGREED_ROLE_ID")
    COMMISSIONS_OPEN_ROLE_ID = req_int("COMMISSIONS_OPEN_ROLE_ID")
    PLEASE_VOUCH_ROLE_ID = req_int("PLEASE_VOUCH_ROLE_ID")
    TICKET_CATEGORY_ID = req_int("TICKET_CATEGORY_ID")
    NOTED_CATEGORY_ID = req_int("NOTED_CATEGORY_ID")
    PROCESSING_CATEGORY_ID = req_int("PROCESSING_CATEGORY_ID")
    DONE_CATEGORY_ID = req_int("DONE_CATEGORY_ID")
    QUEUE_CHANNEL_ID = req_int("QUEUE_CHANNEL_ID")
    SHOP_STATUS_CHANNEL_ID = req_int("SHOP_STATUS_CHANNEL_ID")
    TRANSCRIPT_CHANNEL_ID = req_int("TRANSCRIPT_CHANNEL_ID")
    VOUCHES_CHANNEL_ID = req_int("VOUCHES_CHANNEL_ID")
    ORDER_NOTIFS_CHANNEL_ID = req_int("ORDER_NOTIFS_CHANNEL_ID")
    START_HERE_CHANNEL_ID = req_int("START_HERE_CHANNEL_ID")
    TOS_CHANNEL_ID = req_int("TOS_CHANNEL_ID")
    PAYMENT_CHANNEL_ID = req_int("PAYMENT_CHANNEL_ID")
    WARN_LOG_CHANNEL_ID = req_int("WARN_LOG_CHANNEL_ID")
    GCASH_DETAILS = req_str("GCASH_DETAILS")
    PAYPAL_LINK = req_str("PAYPAL_LINK")
    KOFI_LINK = req_str("KOFI_LINK")
    GCASH_QR_URL = req_str("GCASH_QR_URL")
    PAYPAL_QR_URL = req_str("PAYPAL_QR_URL")

    if missing or bad_int:
        lines = [
            "CONFIG ERROR: Fix environment variables in Render (Environment tab) or .env locally.",
            "Copy names from .env.example and paste values (no quotes needed).",
            "",
        ]
        if missing:
            lines.append("Missing or empty:")
            lines.extend(f"  - {m}" for m in missing)
        if bad_int:
            lines.append("Not valid integers (use digits only, e.g. 123456789012345678):")
            lines.extend(f"  - {b}" for b in bad_int)
        print("\n".join(lines), file=sys.stderr, flush=True)
        raise SystemExit(1)


_load()

DATABASE_PATH: Path = _BOT_DIR / "bot.db"
TOS_FILE: Path = _BOT_DIR / "tos.txt"
TEMPLATES_FILE: Path = _BOT_DIR / "templates.json"


def validate_config() -> None:
    """Idempotent check after load (e.g. in setup_hook)."""
    _ = BOT_TOKEN and GUILD_ID
