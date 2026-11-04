FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/tmp/khammam-attendance-data \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && python -m playwright install --with-deps chromium \
    && useradd --system --uid 10001 --create-home appuser \
    && mkdir -p /tmp/khammam-attendance-data \
    && chown -R appuser:appuser /app /tmp/khammam-attendance-data /ms-playwright

COPY --chown=appuser:appuser app.py ./app.py
COPY --chown=appuser:appuser UI/ ./UI/
COPY --chown=appuser:appuser DSR/ ./DSR/
COPY --chown=appuser:appuser DCB/ ./DCB/
COPY --chown=appuser:appuser GPBalance/ ./GPBalance/
COPY --chown=appuser:appuser shared/ ./shared/

USER 10001
EXPOSE 8080

CMD ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
