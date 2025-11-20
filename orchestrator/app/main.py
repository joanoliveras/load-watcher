from __future__ import annotations

import logging
import sys

from app.config import Settings
from app.orchestrator import run


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def main() -> None:
    settings = Settings()
    configure_logging(settings.log_level)
    logging.getLogger(__name__).info("Loaded orchestrator settings: %s", settings.model_dump())
    run(settings)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # pragma: no cover - top-level safeguard
        logging.exception("Orchestrator terminated due to an unhandled exception.")
        sys.exit(1)

