FROM mcr.microsoft.com/playwright/python:v1.50.0-noble

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    DATA_DIR=/tmp/epanchayat-attendance-data \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && useradd --system --uid 10001 --create-home appuser \
    && mkdir -p /tmp/epanchayat-attendance-data \
    && chown -R appuser:appuser /app /tmp/epanchayat-attendance-data

COPY --chown=appuser:appuser *.py ./
COPY --chown=appuser:appuser core/ ./core/
COPY --chown=appuser:appuser portal/ ./portal/
COPY --chown=appuser:appuser templates/ ./templates/
COPY --chown=appuser:appuser dsr/ ./dsr/
COPY --chown=appuser:appuser dcb/ ./dcb/
COPY --chown=appuser:appuser gp_balance/ ./gp_balance/
COPY --chown=appuser:appuser mas/ ./mas/
COPY --chown=appuser:appuser tools/ ./tools/
COPY --chown=appuser:appuser static/ ./static/
COPY --chown=appuser:appuser scripts/ ./scripts/

USER 10001
EXPOSE 8050

CMD ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-8050} --workers 1 --proxy-headers"]
