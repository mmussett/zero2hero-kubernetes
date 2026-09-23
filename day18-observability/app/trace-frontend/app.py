import os

import requests
from flask import Flask, jsonify

app = Flask(__name__)

BACKEND_URL = os.environ.get("BACKEND_URL", "http://trace-backend")


@app.route("/")
def index():
    # The requests call below is auto-instrumented: OpenTelemetry patches
    # the `requests` library to (a) create a child span for this outbound
    # call, and (b) inject a "traceparent" HTTP header carrying the trace
    # context -- which trace-backend's own Flask auto-instrumentation then
    # picks up automatically, joining both spans into ONE trace. No code
    # here does this manually.
    resp = requests.get(f"{BACKEND_URL}/", timeout=5)
    return jsonify({"service": "trace-frontend", "backend_response": resp.json()})


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
