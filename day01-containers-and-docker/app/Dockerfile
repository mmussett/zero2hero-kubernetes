# --- build stage ---
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --target=/app/deps -r requirements.txt

# --- runtime stage ---
FROM python:3.12-slim
WORKDIR /app

# Run as a non-root user (Day 15 revisits why this matters for Pod Security)
RUN useradd --uid 10001 --create-home appuser
COPY --from=builder /app/deps /usr/local/lib/python3.12/site-packages
COPY app.py .
USER 10001

ENV PORT=8080 \
    APP_VERSION=1.0.0
EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=2s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz')" || exit 1

CMD ["python", "app.py"]
