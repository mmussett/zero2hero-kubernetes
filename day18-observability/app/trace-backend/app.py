import os
import random
import time

from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/")
def index():
    # Simulate variable-latency work so the trace waterfall (Jaeger UI) has
    # something interesting to show — a random 20-200ms span duration.
    work_ms = random.randint(20, 200)
    time.sleep(work_ms / 1000)
    return jsonify({"service": "trace-backend", "simulated_work_ms": work_ms})


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
