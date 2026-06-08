FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml README.md uv.lock ./
COPY src/ ./src/

RUN uv sync --frozen --no-dev

# PORT is set by Railway platform automatically — don't override
# The CMD defaults to $PORT (from env) or 8001 locally
ENV LOG_LEVEL=INFO
ENV TRANSPORT=sse

# Use shell form so $PORT from Railway is respected (default 8001 locally)
CMD uv run clevertech-mcp-server --transport sse --host 0.0.0.0 --port ${PORT:-8001}
