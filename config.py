"""Load and validate environment configuration (secrets + payment copy only).

Channel and role IDs are configured per server with `/serverconfig`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

_BOT_DIR = Path(__file__).resolve().parent
load_dotenv(_BOT_DIR / ".env")


def _strip(name: str) -> str | None:
    v = os.getenv(name)
    if v is None or not str(v).strip():
        return None
    return str(v).strip()


def _load() -> None:
    missing: list[str] = []
    bad_int: list[str] = []

    def req_str(key: str) -> str:
        v = _strip(key)
        if v is None:
            missing.append(key)
            return ""
        return v

    def opt_int(key: str) -> int:
        v = _strip(key)
        if v is None:
            return 0
        try:
            return int(v)
        except ValueError:
            bad_int.append(key)
            return 0

    global BOT_TOKEN, GUILD_ID, GCASH_DETAILS, PAYPAL_LINK, KOFI_LINK, GCASH_QR_URL, PAYPAL_QR_URL

    BOT_TOKEN = req_str("BOT_TOKEN")
    GUILD_ID = opt_int("GUILD_ID")
    GCASH_DETAILS = req_str("GCASH_DETAILS")
    PAYPAL_LINK = req_str("PAYPAL_LINK")
    KOFI_LINK = req_str("KOFI_LINK")
    GCASH_QR_URL = req_str("GCASH_QR_URL")
    PAYPAL_QR_URL = req_str("PAYPAL_QR_URL")

    if missing or bad_int:
        lines = [
            "CONFIG ERROR: Set required environment variables (Render dashboard or .env).",
            "",
        ]
        if missing:
            lines.append("Missing or empty:")
            lines.extend(f"  - {m}" for m in missing)
        if bad_int:
            lines.append("Not valid integers:")
            lines.extend(f"  - {b}" for b in bad_int)
        print("\n".join(lines), file=sys.stderr, flush=True)
        raise SystemExit(1)


_load()

DATABASE_PATH: Path = _BOT_DIR / "bot.db"
TOS_FILE: Path = _BOT_DIR / "tos.txt"
TEMPLATES_FILE: Path = _BOT_DIR / "templates.json"


def validate_config() -> None:
    """Idempotent check after load (e.g. in setup_hook)."""
    _ = BOT_TOKEN
