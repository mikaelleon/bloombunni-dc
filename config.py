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


def _path_writable(path: Path) -> bool:
    parent = path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
        with parent.joinpath(".mika_write_test").open("w", encoding="utf-8") as f:
            f.write("ok")
        parent.joinpath(".mika_write_test").unlink(missing_ok=True)
        return True
    except Exception:
        return False


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
BOT_OWNER_ID: int | None = _optional_int("BOT_OWNER_ID")
ERROR_ALERT_CHANNEL_ID: int | None = _optional_int("ERROR_ALERT_CHANNEL_ID")

DATABASE_PATH: Path = _BOT_DIR / "bot.db"
TOS_FILE: Path = _BOT_DIR / "tos.txt"
TEMPLATES_FILE: Path = _BOT_DIR / "templates.json"


def validate_config() -> None:
    """Idempotent full config validation (e.g. in setup_hook)."""
    errors: list[str] = []

    if not BOT_TOKEN or not str(BOT_TOKEN).strip():
        errors.append("BOT_TOKEN is missing or empty.")

    if SYNC_GUILD_ID is not None and SYNC_GUILD_ID <= 0:
        errors.append("SYNC_GUILD_ID must be a positive integer.")
    if BOT_OWNER_ID is not None and BOT_OWNER_ID <= 0:
        errors.append("BOT_OWNER_ID must be a positive integer.")
    if ERROR_ALERT_CHANNEL_ID is not None and ERROR_ALERT_CHANNEL_ID <= 0:
        errors.append("ERROR_ALERT_CHANNEL_ID must be a positive integer.")

    if not _path_writable(DATABASE_PATH):
        errors.append(f"DATABASE_PATH parent is not writable: {DATABASE_PATH.parent}")

    if errors:
        print("CONFIG ERROR: startup validation failed.", file=sys.stderr, flush=True)
        for e in errors:
            print(f" - {e}", file=sys.stderr, flush=True)
        raise SystemExit(1)
