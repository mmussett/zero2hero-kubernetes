---
---
# Day 1 — Solutions

## Exercise 1
```bash
docker run --rm -d -p 8081:8080 \
  -e GREETING="Zero to Hero!" \
  -e APP_VERSION=2.0.0 \
  --name hello-k8s-v2 hello-k8s:1.0.0
curl localhost:8081/
```
The JSON response's `message` and `app_version` fields reflect the overridden env vars — the image is unchanged; only the container's environment differs. This is the exact mechanism `env:` in a Pod spec uses later.

## Exercise 2
```dockerfile
# Dockerfile.naive
FROM python:3.12-slim
WORKDIR /app
RUN useradd --uid 10001 --create-home appuser
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
USER 10001
ENV PORT=8080 APP_VERSION=1.0.0
EXPOSE 8080
CMD ["python", "app.py"]
```
```bash
docker build -f Dockerfile.naive -t hello-k8s:naive .
docker image inspect hello-k8s:1.0.0 --format '{{.Size}}'
docker image inspect hello-k8s:naive --format '{{.Size}}'
```
**Explanation:** for this specific Flask app the sizes are close, because `pip`'s build cache/wheel cache is the main difference eliminated by the multi-stage copy — `pip` itself and its cache never land in the final image with the multi-stage approach. The gap becomes dramatic when the build stage needs compilers (`gcc`, `build-essential`) for packages with native extensions: multi-stage discards the entire toolchain, naive keeps it in the final image (often hundreds of MB).

## Exercise 3
```bash
docker run -d --name broken hello-k8s:1.0.0 python bad.py
docker ps -a --filter name=broken
docker logs broken
docker inspect broken --format '{{.State.ExitCode}} {{.State.Error}}'
```
Expected: exit code `2`, and `docker logs` shows a Python traceback: `can't open file '/app/bad.py': [Errno 2] No such file or directory`. Exit code 2 here comes from the Python interpreter itself (not a Kubernetes-specific meaning) — but the *pattern* of "check `docker ps -a` for exit code, then `logs` for the reason" is identical to `kubectl get pod` + `kubectl logs` you'll use for the rest of the course.

## Exercise 4
```bash
docker run -d --memory=50m --name memtest polinux/stress \
  stress --vm 1 --vm-bytes 150M --vm-hang 0
sleep 5
docker inspect memtest --format '{{.State.OOMKilled}}'   # true
docker inspect memtest --format '{{.State.ExitCode}}'    # 137 (128 + SIGKILL/9)
```
The kernel's OOM killer terminates the process once it exceeds the cgroup memory limit. This is *identical* to what happens when a Pod exceeds `resources.limits.memory` in Kubernetes — you'll see the same `OOMKilled` reason and exit code `137` in `kubectl describe pod` starting Day 4.

## Exercise 5
```bash
docker tag hello-k8s:1.0.0 localhost:5000/hello-k8s:latest
docker push localhost:5000/hello-k8s:latest
docker rmi hello-k8s:1.0.0 localhost:5000/hello-k8s:latest
docker images | grep hello-k8s   # empty
docker pull localhost:5000/hello-k8s:latest
docker run --rm -d -p 8082:8080 --name hello-k8s-reg localhost:5000/hello-k8s:latest
curl localhost:8082/
```

## Exercise 6
```dockerfile
# hello-k8s:root — same as app/Dockerfile but without `USER 10001`
```
```bash
docker build -t hello-k8s:root .
docker run --rm -d -p 8083:8080 --name hello-k8s-root hello-k8s:root
docker exec hello-k8s-root id
# uid=0(root) gid=0(root) groups=0(root)   <- vs uid=10001 for the original
```
The non-root version is safer: if an attacker achieves code execution inside the container (e.g. via a dependency vulnerability), root-in-container plus a container-runtime escape or `hostPath` misconfiguration can lead to root-on-host. Running as a non-root UID removes that entire escalation path even if the process is compromised. Kubernetes's Pod Security Standards (Day 17) can enforce this cluster-wide with `runAsNonRoot: true`.
