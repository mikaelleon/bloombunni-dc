"""Load bot token from the environment.

Everything else (channels, roles, payment text) is configured per server in Discord
with `/serverconfig` and stored in SQLite.
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

DATABASE_PATH: Path = _BOT_DIR / "bot.db"
TOS_FILE: Path = _BOT_DIR / "tos.txt"
TEMPLATES_FILE: Path = _BOT_DIR / "templates.json"


def validate_config() -> None:
    """Idempotent check after load (e.g. in setup_hook)."""
    _ = BOT_TOKEN
