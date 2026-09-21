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

    # Reload in development only, and only on the application package: the
    # default watches the working directory, which in the container includes
    # the uploads volume, so every stored file would restart the API. Was
    # `reload=False` for a while (#262) — the dev stack promised hot reload
    # and silently served stale code until the container was restarted.
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
        reload_dirs=["app"] if reload else None,
        log_level=log_level,
    )


if __name__ == "__main__":
    main()
