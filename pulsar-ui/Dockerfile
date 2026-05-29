# Build context: workspace root (docker-compose.yml sets context: .)
#
# Two-layer cache strategy:
#   Layer 1 — reinstalled only when pyproject.toml / uv.lock changes
#   Layer 2 — reinstalled only when source code changes

FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# ── Layer 1: install dependencies ─────────────────────────────────────────────
# Copy workspace definition + lock file
COPY pyproject.toml uv.lock ./
COPY pulsar-agent/pyproject.toml ./pulsar-agent/
COPY pulsar-ui/pyproject.toml    ./pulsar-ui/

# Stub __init__.py so hatchling can build the editable packages
RUN mkdir -p pulsar-agent/src/pulsar_agent pulsar-ui/src/pulsar_ui \
 && touch pulsar-agent/src/pulsar_agent/__init__.py \
         pulsar-ui/src/pulsar_ui/__init__.py

RUN uv sync --no-dev

# ── Layer 2: copy source code ─────────────────────────────────────────────────
COPY pulsar-agent/src/ ./pulsar-agent/src/
COPY pulsar-ui/src/    ./pulsar-ui/src/

RUN uv sync --no-dev

# ── Runtime ───────────────────────────────────────────────────────────────────
EXPOSE 8501

# Required at runtime (from .env or docker-compose environment:):
#   CUBE_API_URL      — set to http://cube:4000/cubejs-api/v1 in compose
#   CUBE_API_TOKEN    — JWT signed from CUBEJS_API_SECRET
#   OPENROUTER_API_KEY

CMD ["uv", "run", "python", "-m", "pulsar_ui"]
