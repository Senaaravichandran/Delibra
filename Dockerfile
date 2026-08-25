FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VERDICTFORGE_ENVIRONMENT=production \
    VERDICTFORGE_DATABASE_PATH=/app/data/verdictforge.db

WORKDIR /app

RUN addgroup --system verdictforge && adduser --system --ingroup verdictforge verdictforge

COPY requirements.txt ./
RUN python -m pip install --upgrade pip && python -m pip install -r requirements.txt

COPY pyproject.toml LICENSE README.md app.py ./
COPY verdictforge ./verdictforge
RUN mkdir -p /app/data && chown -R verdictforge:verdictforge /app

USER verdictforge
EXPOSE 8000
VOLUME ["/app/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3)"

CMD ["uvicorn", "verdictforge.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers"]

