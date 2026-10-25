FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    SECRETS_DIR=/secrets
WORKDIR /opt/kilowatch
LABEL org.opencontainers.image.title="Kilowatch" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.licenses="GPL-3.0-or-later"
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10001 kilowatch \
    && useradd --uid 10001 --gid kilowatch --no-create-home --shell /usr/sbin/nologin kilowatch \
    && mkdir -p /data /secrets \
    && chown kilowatch:kilowatch /data /secrets \
    && chmod 700 /secrets
COPY --chown=kilowatch:kilowatch app ./app
COPY docker-entrypoint.sh /usr/local/bin/kilowatch-entrypoint
RUN chmod 755 /usr/local/bin/kilowatch-entrypoint
COPY LICENSE THIRD-PARTY.md ./
VOLUME ["/data", "/secrets"]
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3).read()"]
ENTRYPOINT ["kilowatch-entrypoint"]
CMD ["python", "-m", "uvicorn", "app.main:factory", "--factory", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--no-access-log"]
