# The FastAPI service.
#
# Build context is `backend/`, so every path below is relative to it.

FROM python:3.13-slim

# PYTHONUNBUFFERED matters more here than usual: the structured logger writes
# one JSON object per line to stdout, and a buffered stream would hold those
# lines back until the buffer filled -- which reads as an app that stopped
# logging rather than one that is merely quiet.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Copied on its own, ahead of the source, so the dependency layer is cached:
# editing a route must not reinstall pandas and numpy, which yfinance pulls in
# and which dominate the build.
COPY requirements.txt .
RUN pip install -r requirements.txt

# app/ is the service. The other three are here for the one-time setup
# commands -- migrate.py reads migrations/, ingest_kb.py reads data/kb/, and
# seed_data.py needs both scripts/ and app/.
COPY app/ ./app/
COPY migrations/ ./migrations/
COPY scripts/ ./scripts/
COPY data/ ./data/

# Nothing writes to the filesystem at runtime, so the process does not need to
# own anything it runs as root to reach.
RUN useradd --create-home --uid 1000 appuser
USER appuser

EXPOSE 8000

# Shell form, deliberately: the exec form does not expand ${PORT}, and Railway
# and Cloud Run both inject the port to bind rather than letting the app pick
# one. --host 0.0.0.0 is equally required -- uvicorn's default binds loopback,
# which inside a container means nothing outside it can ever connect.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
