import os
import socket

import requests
from flask import Flask, Response

app = Flask(__name__)

BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend")


@app.route("/")
def index():
    try:
        resp = requests.get(f"{BACKEND_URL}/", timeout=2)
        resp.raise_for_status()
        data = resp.json()
        hits = data["hits"]
        backend_host = data["backend_host"]
        backend_status = "reachable"
    except requests.RequestException:
        hits = "?"
        backend_host = "?"
        backend_status = "UNREACHABLE"

    html = f"""
    <html>
      <head><title>Zero to Hero Capstone</title></head>
      <body style="font-family: sans-serif; margin: 3rem;">
        <h1>Zero to Hero for Kubernetes — Capstone</h1>
        <p><b>Frontend Pod:</b> {socket.gethostname()}</p>
        <p><b>Backend status:</b> {backend_status}</p>
        <p><b>Backend Pod:</b> {backend_host}</p>
        <p><b>Total hits (via Redis):</b> {hits}</p>
      </body>
    </html>
    """
    return Response(html, mimetype="text/html")


@app.route("/healthz")
def healthz():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
