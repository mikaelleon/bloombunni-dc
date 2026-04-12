"""Load bot token from the environment.

Everything else (channels, roles, payment text) is configured per server in Discord
with `/setup`, `/config`, etc., and stored in SQLite.
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


def _optional_int(name: str) -> int | None:
    v = _strip(name)
    if not v:
        return None
    try:
        return int(v)
    except ValueError:
        print(
            f"CONFIG WARNING: {name} must be a whole number; ignoring.",
            file=sys.stderr,
            flush=True,
        )
        return None


def _load() -> None:
    global BOT_TOKEN

    v = _strip("BOT_TOKEN")
    if not v:
        print(
            "CONFIG ERROR: BOT_TOKEN is missing or empty. Set it in .env or your host's environment.",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(1)
    BOT_TOKEN = v


_load()

# Optional: sync slash commands to this guild immediately (avoids long global propagation
# and CommandSignatureMismatch while testing). Right‑click server → Copy Server ID.
SYNC_GUILD_ID: int | None = _optional_int("SYNC_GUILD_ID")

DATABASE_PATH: Path = _BOT_DIR / "bot.db"
TOS_FILE: Path = _BOT_DIR / "tos.txt"
TEMPLATES_FILE: Path = _BOT_DIR / "templates.json"


def validate_config() -> None:
    """Idempotent check after load (e.g. in setup_hook)."""
    _ = BOT_TOKEN
    _ = SYNC_GUILD_ID
