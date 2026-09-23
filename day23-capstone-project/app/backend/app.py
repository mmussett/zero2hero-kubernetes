import os
import socket

import redis
from flask import Flask, jsonify

app = Flask(__name__)

r = redis.Redis(
    host=os.environ.get("REDIS_HOST", "redis"),
    port=int(os.environ.get("REDIS_PORT", "6379")),
    socket_connect_timeout=2,
    socket_timeout=2,
)


@app.route("/")
def index():
    hits = r.incr("hits")
    return jsonify(
        {
            "hits": hits,
            "backend_host": socket.gethostname(),
        }
    )


@app.route("/healthz")
def healthz():
    try:
        r.ping()
        return jsonify({"status": "ok", "redis": "reachable"}), 200
    except redis.exceptions.RedisError:
        return jsonify({"status": "degraded", "redis": "unreachable"}), 503


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
