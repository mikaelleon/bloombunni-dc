"""Minimal Flask server on a daemon thread for Render keep-alive."""

from __future__ import annotations

import threading

from flask import Flask

app = Flask(__name__)


@app.route("/")
def index() -> str:
    return "Bot is alive."


def keep_alive() -> None:
    threading.Thread(
        target=app.run,
        kwargs={"host": "0.0.0.0", "port": 8080},
        daemon=True,
    ).start()
