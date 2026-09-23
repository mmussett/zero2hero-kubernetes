---
---
# Day 1 — Exercises

Attempt each exercise yourself before checking `SOLUTIONS.md`.

## Exercise 1 — Customize via environment variables
Run a second container from `hello-k8s:1.0.0` on host port `8081`, overriding `GREETING` to `"Zero to Hero!"` and `APP_VERSION` to `2.0.0`. Confirm via `curl` that both values appear in the JSON response.

[→ solution](SOLUTIONS.md#exercise-1)

## Exercise 2 — Multi-stage build size comparison
Build a second Dockerfile, `Dockerfile.naive`, that does **not** use a multi-stage build (single `FROM python:3.12-slim` stage that installs requirements directly with `pip install -r requirements.txt` and copies the source). Compare `docker image inspect --format '{{.Size}}'` between `hello-k8s:1.0.0` (multi-stage) and your naive build. Explain in one sentence why they differ (or don't).

[→ solution](SOLUTIONS.md#exercise-2)

## Exercise 3 — Break and diagnose a container
Run `docker run -d --name broken hello-k8s:1.0.0 python bad.py` (a script that doesn't exist). Use only `docker ps -a`, `docker logs`, and `docker inspect` to determine and write down the container's exit code and what it means.

[→ solution](SOLUTIONS.md#exercise-3)

## Exercise 4 — Resource limits
Run a container with a hard memory cap: `docker run -d --memory=50m --name memtest polinux/stress stress --vm 1 --vm-bytes 150M --vm-hang 0`. Observe what happens with `docker inspect memtest --format '{{.State.OOMKilled}}'`. Explain how this maps to something you'll configure in Kubernetes later in the course.

[→ solution](SOLUTIONS.md#exercise-4)

## Exercise 5 — Registry round-trip
Tag `hello-k8s:1.0.0` as `localhost:5000/hello-k8s:latest`, push it, delete *all* local copies of the image (`docker rmi`), then pull it back from `localhost:5000` and run it successfully on port `8082`.

[→ solution](SOLUTIONS.md#exercise-5)

## Exercise 6 (stretch) — Non-root enforcement
Modify `app/Dockerfile` to intentionally run as root (remove the `USER 10001` line), rebuild as `hello-k8s:root`, then run `docker exec hello-k8s-root id` and compare output to the original. Which one would you feel safer running in a shared cluster, and why?

[→ solution](SOLUTIONS.md#exercise-6)
