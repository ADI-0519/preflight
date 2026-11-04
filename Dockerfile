# PreFlight as one container: the FastAPI service, the built web page and FFmpeg.
# Built by deploy/cloud-run.sh; see docs/deploy.md. The git-ignored ASA ruling pages and demo
# files are copied into data/raw/ by that script before the build and never enter Git.

FROM node:22.14-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM mwader/static-ffmpeg:7.1 AS ffmpeg

FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.10.8 /uv /usr/local/bin/uv
COPY --from=ffmpeg /ffmpeg /ffprobe /usr/local/bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1 UV_PYTHON_DOWNLOADS=never PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --extra api --no-install-project
COPY src ./src
RUN uv sync --locked --extra api

COPY prompts ./prompts
COPY results ./results
COPY eval/splits ./eval/splits
COPY data/snapshots ./data/snapshots
COPY data/raw/rulings ./data/raw/rulings
COPY data/raw/demo ./data/raw/demo
COPY --from=web /web/dist ./web/dist
# fail the build, not the first screening, when the ruling cache lacks a page the precedent list needs
RUN .venv/bin/python -c "from preflight.api.service import SNAPSHOTS; from preflight.check.precedents import load_precedents; load_precedents(SNAPSHOTS.rulings)"

RUN useradd --create-home --uid 10001 preflight \
    && mkdir -p data/raw/uploads data/work data/cache \
    && chown -R preflight data
USER preflight

# Cloud Run sets PORT and terminates HTTPS in front; proxy headers give the visitor's address and https scheme.
# One worker: jobs, sessions and sign-in codes live in this process.
CMD ["sh", "-c", "exec /app/.venv/bin/uvicorn preflight.api:create_app --factory --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --proxy-headers --forwarded-allow-ips='*' --no-access-log"]
