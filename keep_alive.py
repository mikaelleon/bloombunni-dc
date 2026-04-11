"""Minimal Flask server on a daemon thread for Render keep-alive."""

from __future__ import annotations

import os
import threading

from flask import Flask

app = Flask(__name__)


@app.route("/")
def index() -> str:
    return "Bot is alive."


def _http_port() -> int:
    # Render (and many hosts) set PORT; the public URL must hit this port or you get 502.
    return int(os.environ.get("PORT", "8080"))


def keep_alive() -> None:
    threading.Thread(
        target=app.run,
        kwargs={"host": "0.0.0.0", "port": _http_port(), "threaded": True},
        daemon=True,
    ).start()
