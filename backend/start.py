"""Uvicorn entry point for the Memship backend."""

import logging
import os

import uvicorn

from app.core.config import settings


def main() -> None:
    env = os.getenv("APP_ENV", "development")
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    log_level = settings.LOG_LEVEL
    reload = env == "development"

    # uvicorn's log_level only tunes its own loggers (uvicorn, uvicorn.access).
    # app.* loggers propagate to root, which needs its own level + handler.
    logging.basicConfig(level=log_level.upper())

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=False,
        log_level=log_level,
    )


if __name__ == "__main__":
    main()
