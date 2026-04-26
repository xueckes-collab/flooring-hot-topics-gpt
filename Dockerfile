FROM python:3.12-slim

WORKDIR /app

# System deps (none beyond the base image needed for our stack)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt /app/
RUN pip install -r requirements.txt

COPY . /app

# SQLite + exports live on a persistent volume in production.
# Railway/Render mount a volume at /data — set DATABASE_PATH=/data/byok.db
# and EXPORT_DIR=/data/exports in their dashboard.
RUN mkdir -p /data /app/exports && chmod 777 /data /app/exports

EXPOSE 8000

# Railway sets $PORT, Render sets $PORT, Fly sets $PORT — uvicorn picks it up.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
