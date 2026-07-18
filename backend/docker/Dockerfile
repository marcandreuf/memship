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

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uv", "run", "python", "start.py"]
