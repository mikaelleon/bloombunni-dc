"""Minimal Flask server on a daemon thread for Render keep-alive."""

from __future__ import annotations

import logging
import os
import threading

from flask import Flask

log = logging.getLogger("bot.keep_alive")

app = Flask(__name__)


@app.route("/")
def index() -> str:
    return "Bot is alive."


def _http_port() -> int:
    """Bind to Render's PORT. Empty or invalid PORT must not crash (int('') raises ValueError)."""
    raw = os.environ.get("PORT")
    if raw is None or not str(raw).strip():
        return 8080
    try:
        port = int(str(raw).strip())
    except ValueError:
        return 8080
    if 1 <= port <= 65535:
        return port
    return 8080


def keep_alive() -> None:
    port = _http_port()
    # Makes Render logs readable: must match $PORT (e.g. 10000) after network config restarts.
    log.info("Flask keep-alive binding on 0.0.0.0:%s (PORT env: %r)", port, os.environ.get("PORT"))
    threading.Thread(
        target=app.run,
        kwargs={"host": "0.0.0.0", "port": port, "threaded": True},
        daemon=True,
    ).start()
