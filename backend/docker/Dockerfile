FROM python:3.12-slim

WORKDIR /app

# System dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends postgresql-client && \
    rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy VERSION from repo root (build context is backend/)
# VERSION is mounted as volume in dev, copied in production builds
ARG APP_VERSION=0.0.1
RUN echo "$APP_VERSION" > /app/VERSION

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
