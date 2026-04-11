"""Load and validate environment configuration."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

_BOT_DIR = Path(__file__).resolve().parent


def _req(name: str) -> str:
    v = os.getenv(name)
    if v is None or str(v).strip() == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return str(v).strip()


def _req_int(name: str) -> int:
    return int(_req(name))


BOT_TOKEN: str = _req("BOT_TOKEN")
GUILD_ID: int = _req_int("GUILD_ID")
STAFF_ROLE_ID: int = _req_int("STAFF_ROLE_ID")
TOS_AGREED_ROLE_ID: int = _req_int("TOS_AGREED_ROLE_ID")
COMMISSIONS_OPEN_ROLE_ID: int = _req_int("COMMISSIONS_OPEN_ROLE_ID")
PLEASE_VOUCH_ROLE_ID: int = _req_int("PLEASE_VOUCH_ROLE_ID")
TICKET_CATEGORY_ID: int = _req_int("TICKET_CATEGORY_ID")
NOTED_CATEGORY_ID: int = _req_int("NOTED_CATEGORY_ID")
PROCESSING_CATEGORY_ID: int = _req_int("PROCESSING_CATEGORY_ID")
DONE_CATEGORY_ID: int = _req_int("DONE_CATEGORY_ID")
QUEUE_CHANNEL_ID: int = _req_int("QUEUE_CHANNEL_ID")
SHOP_STATUS_CHANNEL_ID: int = _req_int("SHOP_STATUS_CHANNEL_ID")
TRANSCRIPT_CHANNEL_ID: int = _req_int("TRANSCRIPT_CHANNEL_ID")
VOUCHES_CHANNEL_ID: int = _req_int("VOUCHES_CHANNEL_ID")
ORDER_NOTIFS_CHANNEL_ID: int = _req_int("ORDER_NOTIFS_CHANNEL_ID")
START_HERE_CHANNEL_ID: int = _req_int("START_HERE_CHANNEL_ID")
TOS_CHANNEL_ID: int = _req_int("TOS_CHANNEL_ID")
PAYMENT_CHANNEL_ID: int = _req_int("PAYMENT_CHANNEL_ID")
WARN_LOG_CHANNEL_ID: int = _req_int("WARN_LOG_CHANNEL_ID")
GCASH_DETAILS: str = _req("GCASH_DETAILS")
PAYPAL_LINK: str = _req("PAYPAL_LINK")
KOFI_LINK: str = _req("KOFI_LINK")
GCASH_QR_URL: str = _req("GCASH_QR_URL")
PAYPAL_QR_URL: str = _req("PAYPAL_QR_URL")

DATABASE_PATH: Path = _BOT_DIR / "bot.db"
TOS_FILE: Path = _BOT_DIR / "tos.txt"
TEMPLATES_FILE: Path = _BOT_DIR / "templates.json"


def validate_config() -> None:
    """Re-validate that all required variables are set (call at startup)."""
    _ = BOT_TOKEN
    _ = GUILD_ID
    _ = STAFF_ROLE_ID
    _ = TOS_AGREED_ROLE_ID
    _ = COMMISSIONS_OPEN_ROLE_ID
    _ = PLEASE_VOUCH_ROLE_ID
    _ = TICKET_CATEGORY_ID
    _ = NOTED_CATEGORY_ID
    _ = PROCESSING_CATEGORY_ID
    _ = DONE_CATEGORY_ID
    _ = QUEUE_CHANNEL_ID
    _ = SHOP_STATUS_CHANNEL_ID
    _ = TRANSCRIPT_CHANNEL_ID
    _ = VOUCHES_CHANNEL_ID
    _ = ORDER_NOTIFS_CHANNEL_ID
    _ = START_HERE_CHANNEL_ID
    _ = TOS_CHANNEL_ID
    _ = PAYMENT_CHANNEL_ID
    _ = WARN_LOG_CHANNEL_ID
    _ = GCASH_DETAILS
    _ = PAYPAL_LINK
    _ = KOFI_LINK
    _ = GCASH_QR_URL
    _ = PAYPAL_QR_URL
