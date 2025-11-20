from __future__ import annotations

import os

import uvicorn

from app.api import app


def run() -> None:
    host = "0.0.0.0"
    port = 8080
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run()
