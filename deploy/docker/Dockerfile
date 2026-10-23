# syntax=docker/dockerfile:1
FROM node:25-bookworm-slim AS ui
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ODF_FILE_DIR=/data/odf/files
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 ca-certificates && rm -rf /var/lib/apt/lists/* && groupadd --gid 10001 odf && \
    useradd --uid 10001 --gid odf --no-create-home --shell /usr/sbin/nologin odf
WORKDIR /app
COPY impl /app/impl
RUN python -m pip install --upgrade pip && \
    python -m pip install /app/impl
COPY --from=ui /app/impl/odf/static /app/impl/odf/static
COPY scripts /app/scripts
COPY deploy/docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh && \
    mkdir -p /data/odf/files /backups && \
    chown -R odf:odf /app /data/odf /backups
USER odf
WORKDIR /app/impl
EXPOSE 18080 18082
HEALTHCHECK --interval=20s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:18080/readyz', timeout=3)"
ENTRYPOINT ["/app/entrypoint.sh"]
