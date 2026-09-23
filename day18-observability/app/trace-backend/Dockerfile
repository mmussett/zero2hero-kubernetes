FROM python:3.12-slim
WORKDIR /app
RUN useradd --uid 10001 --create-home appuser
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    # opentelemetry-bootstrap inspects installed packages (here: Flask) and
    # installs the matching auto-instrumentation package for each one --
    # this is what makes tracing possible with ZERO application code changes.
    && opentelemetry-bootstrap -a install
COPY app.py .
USER 10001
ENV PORT=8080 \
    OTEL_SERVICE_NAME=trace-backend \
    OTEL_TRACES_EXPORTER=otlp \
    OTEL_METRICS_EXPORTER=none \
    OTEL_LOGS_EXPORTER=none \
    OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf \
    OTEL_PYTHON_LOG_CORRELATION=true
EXPOSE 8080
# opentelemetry-instrument wraps the process, patching instrumented
# libraries (Flask, requests) in-place at startup -- app.py itself never
# imports or calls anything OpenTelemetry-related directly.
CMD ["opentelemetry-instrument", "python", "app.py"]
