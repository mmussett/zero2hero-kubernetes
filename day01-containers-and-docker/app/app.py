import os
import socket
from datetime import datetime, timezone

from flask import Flask, jsonify

app = Flask(__name__)

# Simple in-memory counter to demonstrate that state is lost on restart
# (used later in the course to explain Pod ephemerality).
request_count = 0


@app.route("/")
def index():
    global request_count
    request_count += 1
    return jsonify(
        {
            "message": os.environ.get("GREETING", "Hello from a container!"),
            "hostname": socket.gethostname(),
            "app_version": os.environ.get("APP_VERSION", "dev"),
            "request_count": request_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
