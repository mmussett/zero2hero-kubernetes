---
---
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

## 3. Docker CLI Reference

The lab above used a handful of commands. This section is a comprehensive tour of the Docker CLI, organized by category — skim it now, then come back to it as a reference whenever you need a flag you've forgotten. Every command works identically with Podman/`nerdctl` (substitute the binary name).

### 3.1 Image management

An image is built once and reused everywhere — these commands create, inspect, and move images around.

```bash
docker build -t hello-k8s:1.0.0 .              # build from Dockerfile in current dir
docker build -t hello-k8s:1.0.0 -f Dockerfile.naive .   # build from a specific file
docker images                                  # list local images
docker image ls --filter "dangling=true"       # list untagged/orphaned layers
docker tag hello-k8s:1.0.0 localhost:5000/hello-k8s:1.0.0   # add an additional name/tag
docker pull nginx:1.27                         # download an image without running it
docker push localhost:5000/hello-k8s:1.0.0     # upload to a registry
docker rmi hello-k8s:1.0.0                     # delete a local image
docker save hello-k8s:1.0.0 -o hello-k8s.tar   # export an image to a tarball (no registry needed)
docker load -i hello-k8s.tar                   # import an image from a tarball
docker history hello-k8s:1.0.0                 # show each layer and its size
docker image inspect hello-k8s:1.0.0           # full JSON metadata for an image
```

| Command | Purpose |
|---|---|
| `docker build -t <name>:<tag> [-f <file>] <context>` | Build an image; `<context>` is the directory sent to the daemon (everything not excluded by `.dockerignore`) |
| `docker images` / `docker image ls` | List local images |
| `docker tag <src> <dst>` | Give an existing image an additional name — doesn't copy data, just adds a reference |
| `docker pull <image>[:<tag>]` | Download an image without creating a container |
| `docker push <image>[:<tag>]` | Upload an image to a registry |
| `docker rmi <image>` | Remove a local image (fails if a container still references it) |
| `docker save -o <file>.tar <image>` / `docker load -i <file>.tar` | Export/import an image as a portable tarball, bypassing any registry |
| `docker history <image>` | Show every layer and its size, oldest first |
| `docker image inspect <image>` | Full JSON metadata: layers, env, entrypoint, exposed ports, size |

### 3.2 Container lifecycle

A container is a running (or stopped) instance of an image. These commands control that instance's lifecycle from creation to removal.

```bash
docker run -d -p 8080:8080 --name hello-k8s hello-k8s:1.0.0   # create + start, detached
docker run --rm -it ubuntu:24.04 bash          # create + start, interactive, auto-remove on exit
docker start hello-k8s                         # start a stopped container
docker stop hello-k8s                          # graceful stop (SIGTERM, then SIGKILL after a timeout)
docker restart hello-k8s                       # stop then start
docker pause hello-k8s                         # freeze all processes in the container (cgroup freezer)
docker unpause hello-k8s                       # resume a paused container
docker kill hello-k8s                          # immediate SIGKILL, no graceful shutdown
docker rm hello-k8s                            # delete a stopped container
docker rm -f hello-k8s                         # stop (SIGKILL) and delete in one step
docker rename hello-k8s hello-k8s-old          # rename a container without recreating it
docker cp hello-k8s:/app/config.json .         # copy a file out of a container's filesystem
```

| Command | Purpose |
|---|---|
| `docker run [flags] <image> [cmd]` | Create and start a new container. See §3.3 for the most useful flags |
| `docker start` / `docker stop` / `docker restart <container>` | Start a stopped container / gracefully stop / restart a running one |
| `docker pause` / `docker unpause <container>` | Freeze/resume all processes without stopping the container |
| `docker kill <container>` | Send `SIGKILL` immediately — skips graceful shutdown, use `stop` normally |
| `docker rm [-f] <container>` | Remove a container; `-f` also stops it first if running |
| `docker rename <old> <new>` | Rename a container in place |
| `docker cp <container>:<path> <host-path>` | Copy files between a container and the host, in either direction |

**`docker run` flags worth knowing:**

| Flag | Effect |
|---|---|
| `-d`, `--detach` | Run in the background, print the container ID, return control to your shell |
| `-it` | `-i` keeps stdin open, `-t` allocates a pseudo-TTY — combine for an interactive shell |
| `--rm` | Automatically remove the container when it exits — ideal for one-off/throwaway runs |
| `--name <name>` | Give the container a stable name instead of a random one |
| `-p <host>:<container>` | Publish a container port to a specific host port |
| `-P` | Publish **all** `EXPOSE`d ports to random high host ports |
| `-e KEY=value` | Set an environment variable (repeatable) |
| `--env-file <file>` | Load many environment variables from a file at once |
| `-v <host-path>:<container-path>` | Bind-mount a host directory/file into the container (see §3.5) |
| `--network <name>` | Attach to a specific Docker network instead of the default bridge |
| `--memory=<n>`, `--cpus=<n>` | Hard resource caps enforced via cgroups — the direct ancestor of Kubernetes `resources.limits` |
| `--restart=<policy>` | `no` (default) / `on-failure[:max-retries]` / `always` / `unless-stopped` |
| `--entrypoint <cmd>` | Override the image's `ENTRYPOINT` for this one run |

### 3.3 Inspecting & debugging running containers

The exact muscle memory you'll reuse constantly once Pods replace containers as the unit you're debugging.

```bash
docker ps                                      # running containers
docker ps -a                                   # running + stopped containers
docker logs hello-k8s                          # all logs since the container started
docker logs -f --tail 50 hello-k8s             # follow, starting from the last 50 lines
docker exec -it hello-k8s sh                   # open a shell inside a running container
docker exec hello-k8s env                      # run a one-off command inside it, no shell needed
docker attach hello-k8s                        # attach to the container's own PID 1 stdin/stdout (rarely what you want — prefer exec)
docker top hello-k8s                           # processes running inside the container, from the host's view
docker stats hello-k8s                         # live CPU/memory/network usage, like `top` for containers
docker diff hello-k8s                          # files added/changed/deleted vs. the image's original layers
docker port hello-k8s                          # show the container's published port mappings
docker inspect hello-k8s                       # full JSON: config, mounts, network settings, state, exit code
```

| Command | Purpose |
|---|---|
| `docker ps [-a]` | List running containers (`-a` includes stopped ones) |
| `docker logs [-f] [--tail N] <container>` | View stdout/stderr; `-f` follows live, `--tail` limits history |
| `docker exec [-it] <container> <cmd>` | Run a new process inside an already-running container — your primary debugging tool |
| `docker attach <container>` | Attach to the container's original foreground process — exiting can stop the container; `exec` is almost always safer |
| `docker top <container>` | List the container's processes from the host's process table |
| `docker stats [container...]` | Live resource usage stream; omit the name to see every container |
| `docker diff <container>` | Filesystem changes (`A`dded/`C`hanged/`D`eleted) relative to the image |
| `docker port <container>` | Show which host ports map to which container ports |
| `docker inspect <container>` | Full JSON state — exit code, env, mounts, IP address, restart count |

### 3.4 Networking

By default, `docker run` attaches a container to the `bridge` network, giving it a private IP and NAT'd access to the outside world; `-p` punches a hole through that NAT for inbound traffic.

```bash
docker network ls                              # list networks (bridge, host, none, plus any you create)
docker network create app-net                  # create an isolated user-defined bridge network
docker run -d --network app-net --name db postgres:16
docker run -d --network app-net --name api hello-k8s:1.0.0   # 'api' can reach 'db' by container name — DNS is automatic
docker network inspect app-net                 # see attached containers and their IPs
docker network connect app-net hello-k8s       # attach an already-running container to another network
docker network disconnect app-net hello-k8s    # detach it
docker network rm app-net                      # delete a network (must have no attached containers)
```

| Command | Purpose |
|---|---|
| `docker network ls` | List all networks on this host |
| `docker network create <name>` | Create a user-defined bridge network — containers on it resolve each other by container name via built-in DNS (the default `bridge` network does **not** offer this) |
| `docker network inspect <name>` | Show subnet, gateway, and attached containers |
| `docker network connect` / `disconnect <net> <container>` | Attach/detach a running container to/from a network without recreating it |
| `docker network rm <name>` | Delete a network |
| `--network host` (on `docker run`) | Skip network isolation entirely — the container shares the host's network namespace directly (no `-p` needed, but no port isolation either) |
| `--network none` (on `docker run`) | No networking at all beyond loopback |

This container-name-based DNS resolution on a user-defined network is the direct conceptual ancestor of Kubernetes [Service discovery](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/) (Day 5/15) — `api` reaching `db` by name here is the same idea as a Pod reaching `my-svc.my-namespace.svc.cluster.local` later.

### 3.5 Volumes & bind mounts

Containers are ephemeral by design — anything written to a container's writable layer is lost when it's removed. Volumes and bind mounts give data a lifetime independent of any one container, the same problem [PersistentVolumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/) solve in Kubernetes (Day 7).

```bash
docker volume create app-data                  # create a named, Docker-managed volume
docker run -d -v app-data:/var/lib/data --name db postgres:16   # named volume — Docker owns where it lives on disk
docker run -d -v "$(pwd)/config":/app/config:ro --name api hello-k8s:1.0.0   # bind mount — you own the host path, ':ro' = read-only
docker volume ls                               # list volumes
docker volume inspect app-data                 # see the volume's actual location on the host
docker volume rm app-data                      # delete a volume (must not be in use)
docker volume prune                            # delete every volume not referenced by any container
```

| Concept | Use it when... |
|---|---|
| **Named volume** (`-v app-data:/path`) | You just need durable storage and don't care exactly where it lives on the host — Docker manages the location. Preferred for databases and app state. |
| **Bind mount** (`-v $(pwd)/x:/path`) | You need a *specific* host path visible inside the container — config files, source code for live-reload during development, host device access. |
| **`--mount`** (verbose alternative to `-v`) | Same capabilities as `-v` but explicit key=value syntax (`--mount type=bind,source=...,target=...,readonly`) — clearer in scripts, harder to typo silently |

| Command | Purpose |
|---|---|
| `docker volume create <name>` | Create a named volume |
| `docker volume ls` / `docker volume inspect <name>` | List volumes / show a volume's host path and metadata |
| `docker volume rm <name>` | Delete a volume |
| `docker volume prune` | Delete all volumes not currently used by any container — **destructive**, confirm what's unused first |

### 3.6 Build options in depth

```bash
docker build --build-arg APP_VERSION=2.0.0 -t hello-k8s:2.0.0 .   # pass a build-time variable (needs ARG in the Dockerfile)
docker build --no-cache -t hello-k8s:1.0.0 .    # ignore layer cache entirely — rebuild from scratch
docker build --target builder -t hello-k8s:builder .   # stop at a specific stage of a multi-stage build
docker build --platform linux/arm64 -t hello-k8s:1.0.0 .   # cross-build for a different CPU architecture
```

| Flag | Purpose |
|---|---|
| `--build-arg KEY=value` | Pass a value into the build available via a Dockerfile `ARG` instruction — unlike `ENV`, not present in the final image unless explicitly re-exported |
| `--no-cache` | Rebuild every layer from scratch, ignoring the layer cache — use when you suspect a stale cached layer is hiding a real change |
| `--target <stage-name>` | Build only up to a named stage in a multi-stage Dockerfile — useful for building just the `builder` stage to debug it in isolation |
| `--platform <os/arch>` | Build for an architecture other than the host's (requires QEMU emulation or a remote builder) — relevant the moment your cluster's nodes aren't all the same CPU architecture |
| `.dockerignore` (file, not a flag) | Excludes files/directories from the build context, the same way `.gitignore` excludes files from git — keeps `.git/`, `node_modules/`, and secrets out of the image and speeds up every build |

### 3.7 Cleanup & disk management

Images, stopped containers, unused networks, and dangling volumes all consume disk silently. These are the commands to reclaim it.

```bash
docker system df                               # disk usage summary by category
docker container prune                         # delete all stopped containers
docker image prune                             # delete dangling (untagged) images only
docker image prune -a                          # delete ALL images not used by a running container
docker volume prune                            # delete all unused volumes
docker network prune                           # delete all unused user-defined networks
docker system prune -a --volumes               # nuke everything unused in one command — containers, images, networks, and volumes
```

| Command | Purpose |
|---|---|
| `docker system df` | Summarize disk usage: images, containers, local volumes, build cache |
| `docker container prune` | Remove all stopped containers |
| `docker image prune [-a]` | Remove dangling images; `-a` also removes any image not referenced by a running container |
| `docker volume prune` | Remove volumes not attached to any container — **check `docker volume ls` first**, this is irreversible |
| `docker network prune` | Remove unused user-defined networks |
| `docker system prune -a --volumes` | The broadest cleanup: everything unused, in one command — use sparingly and never on a host with data you haven't backed up |

### 3.8 Registry & authentication

```bash
docker login                                   # authenticate to Docker Hub interactively
docker login localhost:5000                    # authenticate to a private/self-hosted registry
docker login ghcr.io -u <user> --password-stdin < token.txt   # non-interactive, for scripts/CI
docker logout                                  # clear stored credentials for the default registry
docker search nginx                            # search Docker Hub from the CLI (Hub only, not private registries)
```

An image name encodes its registry: `localhost:5000/hello-k8s:1.0.0` pulls from your local registry, `ghcr.io/org/hello-k8s:1.0.0` from GitHub Container Registry, and a bare `nginx:1.27` (no registry host) defaults to Docker Hub. Kubernetes' `imagePullSecrets` (introduced Day 6) is the cluster-side equivalent of the credentials `docker login` stores locally — a Pod needs its own explicit credential reference because it isn't running on your authenticated workstation.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `permission denied while trying to connect to the Docker daemon socket` | Your user isn't in the `docker` group yet, or the group membership hasn't taken effect in this shell | Re-run section 2.1's `usermod -aG docker $USER` then `newgrp docker`, or fully log out/in |
| `Cannot connect to the Docker daemon` | The Docker service itself isn't running | `sudo systemctl status docker`; `sudo systemctl start docker` if it's not active |
| `docker: Error response from daemon: driver failed programming external connectivity ... port is already allocated` | Something else already owns that host port | `docker ps` to find and stop the conflicting container, or pick a different host port in `-p` |
| Rebuilt the image but the app still behaves like the old code | You edited `app.py` but forgot to `docker build` again, or you're running a stale container from before the rebuild | `docker build` then `docker stop`/`docker rm` the old container before `docker run`-ing the new image |
| `docker push` to `localhost:5000` fails with a TLS/certificate error | The registry container serves plain HTTP, and your Docker daemon expects HTTPS by default for non-`localhost` hosts | Confirm you're pushing to literally `localhost:5000` (not a hostname/IP) — Docker trusts plain HTTP automatically only for `localhost` |

See also: [Debugging Common Kubernetes Issues](../TROUBLESHOOTING.md) for anything beyond today's plain-Docker scope.

## 4. Key commands reference

The essentials from today, condensed to a single cheat sheet — see §3 above for the full categorized reference.

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
