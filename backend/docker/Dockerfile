FROM python:3.12-slim

WORKDIR /app

# System dependencies (postgresql-client + WeasyPrint libs)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        postgresql-client \
        libcairo2 libpango-1.0-0 libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 libffi-dev shared-mime-info && \
    rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Version comes from the git tag at build time (there is no VERSION file). CI passes
# --build-arg APP_VERSION=<tag>; the app reads it from the environment at runtime.
ARG APP_VERSION=0.0.0
ENV APP_VERSION=$APP_VERSION

# Copy dependency files first (layer caching)
COPY pyproject.toml ./

# Install dependencies
RUN uv sync --no-dev --no-install-project

# Copy application code
COPY . .

# Copy scripts
COPY docker/entrypoint.sh /entrypoint.sh
COPY docker/wait-for-postgres.sh /wait-for-postgres.sh
RUN chmod +x /entrypoint.sh /wait-for-postgres.sh

# Activate the virtualenv on PATH instead of going through `uv run`.
#
# `uv run` re-verifies the environment on every start and needs write access to
# /app/.venv, which forces the container to run as the user that built it — root.
# Putting the venv on PATH means NOTHING under /app is written at runtime, so the
# container runs under any uid. That is what lets Compose pass the host user's
# uid/gid through, which in turn keeps bind-mounted uploads readable on the host.
#
# Consequence: use `python`, `celery` and `alembic` directly in commands and in
# `docker compose exec` — not `uv run <cmd>`, which will fail as a non-root user.
# PYTHONPATH is required, not decoration: dependencies are installed with
# `--no-install-project`, so the `app` package itself is not in the venv. `uv run`
# used to paper over that by injecting the project root into sys.path. Console
# scripts (alembic, celery) get sys.path[0] = /app/.venv/bin instead, so without
# this they fail with "No module named 'app'".
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1

# Storage is normally a bind mount from the host; create it anyway so a bare
# `docker run` with no mount still starts. The app writes subdirectories here.
#
# /var/lib/celery holds celery beat's schedule database. It has to exist in the
# image, owned by the runtime user: Docker creates a mountpoint that is missing
# from the image as root:root, which is exactly the permission error this
# directory is here to avoid. /app itself stays root-owned, so beat cannot fall
# back to the working directory.
RUN groupadd -g 1001 memship \
    && useradd -u 1001 -g 1001 -m -d /home/memship memship \
    && mkdir -p /app/storage /var/lib/celery \
    && chown -R 1001:1001 /app/storage /var/lib/celery

# Default to non-root. Compose overrides this with the host user's ids so files
# written to the bind mount belong to the operator rather than to uid 1001.
USER 1001:1001

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "start.py"]
