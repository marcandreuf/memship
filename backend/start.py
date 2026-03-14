"""Uvicorn entry point for the Memship backend."""

import os

import uvicorn


def main() -> None:
    env = os.getenv("APP_ENV", "development")
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = env == "development"

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    main()
