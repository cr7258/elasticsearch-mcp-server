# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Builder: install dependencies into a virtual environment using uv
# ---------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.10-bookworm-slim AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install dependencies first to leverage layer caching
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-project

# Copy source and install the project itself
COPY src/ /app/src/
COPY pyproject.toml uv.lock LICENSE README.md /app/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# ---------------------------------------------------------------------------
# Runtime: minimal image without uv
# ---------------------------------------------------------------------------
FROM python:3.10-slim-bookworm

WORKDIR /app

RUN groupadd -r appuser && useradd --no-log-init -r -g appuser -u 1000 appuser

# Copy the pre-built virtual environment and source
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appuser /app/src /app/src

# Copy and configure entrypoint
COPY --chown=appuser:appuser docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Default: disable SSL verification for self-signed certs (override in production)
    VERIFY_CERTS=false

USER appuser

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000"]
