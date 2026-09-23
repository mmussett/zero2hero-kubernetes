# Day 1 — Linux Containers & Docker Fundamentals

Kubernetes orchestrates containers. Before you can reason about Pods, you need to have personally built an image, watched it run, and broken it. Today has no Kubernetes at all — that starts tomorrow.

## Learning objectives

By the end of today you can:
- Explain what a container actually is (namespaces + cgroups + a filesystem layer) vs. a VM
- Write a `Dockerfile`, build an image, and run a container from it
- Inspect a running container's logs, filesystem, and process list
- Explain image layers and why multi-stage builds and small base images matter
- Push/pull images via a local registry (the same mechanism k3s uses)

## 1. Concepts

**A container is not a lightweight VM.** It's a normal Linux process that the kernel has restricted using:
- **Namespaces** — give the process its own view of PIDs, network interfaces, mount points, hostname, and users. It *looks* isolated.
- **cgroups (control groups)** — cap how much CPU/memory/IO the process can consume. This is exactly what Kubernetes `resources.limits` configure later.
- **A union filesystem** — an image is a stack of read-only layers; a running container adds one thin writable layer on top. Layers are content-addressed and cached, which is why rebuilding an image after a one-line code change is fast.

**An image is not a container.** An image is the inert, versioned tarball-of-layers plus metadata (entrypoint, env, exposed ports). A container is a running (or stopped) *instance* of an image — same relationship as a class and an object.

A [**multi-stage build**](https://docs.docker.com/build/building/multi-stage/) uses multiple `FROM` lines in one Dockerfile — an early stage installs compilers/build tools and produces an artifact, a later stage starts fresh from a minimal base image and copies in just that artifact. The build tools and their layers never make it into the final image, only the compiled output does — this is why the sample app's Dockerfile (section 2.3) has a `builder` stage and a separate runtime stage, and why the final image is far smaller than the one that built it.

**Why this matters for Kubernetes:** a [Pod](https://kubernetes.io/docs/concepts/workloads/pods/) is fundamentally "run this container image, with these namespaces/cgroups settings, on some node." Everything Kubernetes adds on top — scheduling, restarts, networking, scaling — is orchestration *around* the primitive you're about to use directly.

### Official documentation
- [Kubernetes: Containers overview](https://kubernetes.io/docs/concepts/containers/)
- [Kubernetes: Images](https://kubernetes.io/docs/concepts/containers/images/)
- [Docker: What is a container?](https://docs.docker.com/get-started/docker-overview/)
- [Dockerfile reference](https://docs.docker.com/reference/dockerfile/)
- [Docker: Multi-stage builds](https://docs.docker.com/build/building/multi-stage/)
- [OCI Image Format Specification](https://github.com/opencontainers/image-spec)

## 2. Hands-on lab

### 2.1 Install Docker (Ubuntu/Debian)

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker   # or log out/in
docker version
```

> Already have Docker, Podman, or `nerdctl`? Any OCI-compatible builder works for this whole course; swap `docker` for your tool of choice.

### 2.2 Run your first container

```bash
docker run --rm hello-world
docker run --rm -it ubuntu:24.04 bash
# inside the container:
ps aux        # notice PID 1 is bash, not your host's init
hostname      # a random hex id — its own UTS namespace
exit
```

### 2.3 Build the sample app

This repo's `app/` folder contains a tiny Flask API. Build and run it:

```bash
cd app
docker build -t hello-k8s:1.0.0 .
docker run --rm -d -p 8080:8080 --name hello-k8s hello-k8s:1.0.0
curl localhost:8080/
curl localhost:8080/healthz
```

### 2.4 Inspect it like you'll later inspect a Pod

```bash
docker ps
docker logs hello-k8s
docker exec -it hello-k8s /bin/sh -c "id; ls /app"
docker inspect hello-k8s | jq '.[0].State, .[0].Config.Env'
docker stop hello-k8s
```

### 2.5 Understand layers

```bash
docker history hello-k8s:1.0.0
docker image inspect hello-k8s:1.0.0 --format '{{.Size}}'
```

Change one line in `app.py`, rebuild, and re-run `docker history`. Notice only the layers *after* the `COPY app.py .` instruction rebuild — everything above the change is reused from cache. This is why Dockerfiles put rarely-changing instructions (installing dependencies) *before* frequently-changing ones (copying source code).

### 2.6 Run a local registry (this is exactly how k3s will pull your images later)

```bash
docker run -d -p 5000:5000 --restart=always --name registry registry:2
docker tag hello-k8s:1.0.0 localhost:5000/hello-k8s:1.0.0
docker push localhost:5000/hello-k8s:1.0.0
docker rmi hello-k8s:1.0.0 localhost:5000/hello-k8s:1.0.0
docker pull localhost:5000/hello-k8s:1.0.0
```

You now have a private registry running on your machine — Day 2's k3s cluster will pull from it directly.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `permission denied while trying to connect to the Docker daemon socket` | Your user isn't in the `docker` group yet, or the group membership hasn't taken effect in this shell | Re-run section 2.1's `usermod -aG docker $USER` then `newgrp docker`, or fully log out/in |
| `Cannot connect to the Docker daemon` | The Docker service itself isn't running | `sudo systemctl status docker`; `sudo systemctl start docker` if it's not active |
| `docker: Error response from daemon: driver failed programming external connectivity ... port is already allocated` | Something else already owns that host port | `docker ps` to find and stop the conflicting container, or pick a different host port in `-p` |
| Rebuilt the image but the app still behaves like the old code | You edited `app.py` but forgot to `docker build` again, or you're running a stale container from before the rebuild | `docker build` then `docker stop`/`docker rm` the old container before `docker run`-ing the new image |
| `docker push` to `localhost:5000` fails with a TLS/certificate error | The registry container serves plain HTTP, and your Docker daemon expects HTTPS by default for non-`localhost` hosts | Confirm you're pushing to literally `localhost:5000` (not a hostname/IP) — Docker trusts plain HTTP automatically only for `localhost` |

See also: [Debugging Common Kubernetes Issues](../TROUBLESHOOTING.md) for anything beyond today's plain-Docker scope.

## 3. Key commands reference

| Command | Purpose |
|---|---|
| `docker build -t <name>:<tag> .` | Build an image from a Dockerfile |
| `docker run -d -p <host>:<container> <image>` | Run detached, with port mapping |
| `docker ps` / `docker ps -a` | List running / all containers |
| `docker logs -f <container>` | Stream logs |
| `docker exec -it <container> sh` | Shell into a running container |
| `docker inspect <container\|image>` | Full JSON metadata |
| `docker history <image>` | Show layers and their sizes |
| `docker system df` | Disk usage by images/containers/volumes |

Next: [Day 2 — Kubernetes architecture & installing k3s](../day02-k3s-install-and-kubectl/README.md)
