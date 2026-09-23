FROM python:3.12-slim
WORKDIR /app
RUN useradd --uid 10001 --create-home appuser
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && opentelemetry-bootstrap -a install
COPY app.py .
USER 10001
ENV PORT=8080 \
    OTEL_SERVICE_NAME=trace-frontend \
    OTEL_TRACES_EXPORTER=otlp \
    OTEL_METRICS_EXPORTER=none \
    OTEL_LOGS_EXPORTER=none \
    OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf \
    OTEL_PYTHON_LOG_CORRELATION=true
EXPOSE 8080
CMD ["opentelemetry-instrument", "python", "app.py"]
