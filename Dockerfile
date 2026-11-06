FROM mcr.microsoft.com/playwright/python:v1.50.0-noble

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
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
COPY --chown=appuser:appuser automate_epts/ ./automate_epts/
COPY --chown=appuser:appuser GPBALNCE/ ./GPBALNCE/

USER 10001
EXPOSE 8080

CMD ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --proxy-headers"]
