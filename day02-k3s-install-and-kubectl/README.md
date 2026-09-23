# Day 2 — Kubernetes Architecture & Installing Your First Cluster

Today has two halves: understanding what Kubernetes' moving parts actually are, and then standing up a real, working cluster on your own machine that every remaining day in this course runs against. Take your time on the install — a shaky cluster now costs you far more time later than getting it right today.

## Learning objectives
- Explain the control-plane / data-plane split and what each Kubernetes component does
- Choose and prepare an environment to run Kubernetes on, whatever OS you're starting from
- Install a single-node k3s cluster from scratch, including troubleshooting a failed install
- Configure `kubectl` and understand contexts/kubeconfig
- Run your Day 1 image on the cluster via imperative commands
- Read `kubectl get`/`describe`/`get events` output fluently
- Manage the k3s service itself (start/stop/restart/logs/uninstall)
- Master `kubectl` itself: output formats, dry-run/diff, patch types, ephemeral debug containers, `cp`, `proxy` vs. `port-forward`, contexts/namespace switching, and shell completion — the productivity layer every later day assumes you already have

## 1. Concepts

### 1.1 Architecture at a glance

```
 ┌───────────────────────── Control Plane ─────────────────────────┐
 │  kube-apiserver   ← the only component everything talks to       │
 │  etcd             ← cluster state, stored as key/value pairs      │
 │  kube-scheduler   ← decides which Node a new Pod runs on          │
 │  kube-controller-manager ← reconciliation loops (Deployments,     │
 │                            Nodes, etc. — "make actual = desired") │
 │  cloud-controller-manager ← cloud-provider integration (LBs,      │
 │                              volumes, Node lifecycle) — N/A here  │
 └────────────────────────────────────────────────────────────────┘
                              │  (watches/writes via API server)
 ┌──────────────────────────── Node ─────────────────────────────┐
 │  kubelet       ← talks to the API server, starts/stops          │
 │                  containers via the container runtime            │
 │  kube-proxy    ← programs iptables/ipvs rules for Services       │
 │  container runtime (containerd) ← actually runs containers       │
 └──────────────────────────────────────────────────────────────┘
```

Walking through each component and what actually breaks if it goes down:

- **kube-apiserver** — a stateless REST front end validating and persisting every object (Pods, Deployments, Services...) to etcd. It is the *only* component anything else talks to directly — `kubectl`, the scheduler, the kubelets, even other control-plane components all go through it. Nothing in Kubernetes has a back-channel around the API server. If it's down, you can't change cluster state, but already-running Pods keep running (the kubelet caches what it needs).
- **etcd** — a distributed, strongly-consistent key-value store holding the entire cluster's desired state. Every object you `kubectl apply` ends up as a key under `/registry/...` in etcd. Lose etcd with no backup and you lose your cluster's brain, even if every Node and container is still physically running.
- **kube-scheduler** — watches for Pods with no Node assigned (`spec.nodeName` empty) and picks one, based on resource requests, taints/tolerations (Day 10), affinity rules, and more. It only *assigns*; it never runs anything itself.
- **kube-controller-manager** — actually a bundle of independent control loops (the Deployment controller, ReplicaSet controller, Node controller, and dozens more) compiled into one binary for operational simplicity. Each loop follows the same pattern: watch the API server, compare desired vs. actual, act to close the gap, repeat forever.
- **kubelet** (runs on every Node) — the agent that actually makes Pods real. It watches the API server for Pods assigned to its Node, and drives the container runtime to pull images and start/stop/restart containers accordingly. It also reports Node and Pod status back up.
- **kube-proxy** (runs on every Node) — implements the Service abstraction (Day 5) by programming `iptables`/IPVS rules so Service ClusterIPs route to the right Pod IPs.
- **container runtime** (containerd in k3s's case) — the low-level component that actually creates namespaces/cgroups and starts a container process, one layer below what you did by hand with `docker` on Day 1. Kubernetes talks to it via the [Container Runtime Interface (CRI)](https://kubernetes.io/docs/concepts/architecture/cri/), which is *why* Kubernetes can support containerd, CRI-O, or others interchangeably.

Everything in Kubernetes is a **declarative reconciliation loop**: you write desired state (YAML) to etcd via the API server; a controller notices the gap between desired and actual state and drives the cluster toward desired state, continuously, forever. There is no "run this once" — controllers keep working even after you log off. Internalizing this one idea makes the rest of the course make sense.

### 1.2 Why k3s (and how it differs from "full" Kubernetes)

[k3s](https://docs.k3s.io/) is a [CNCF-certified](https://www.cncf.io/certification/software-conformance/) Kubernetes distribution built by Rancher/SUSE, shipped as a single ~70MB binary. It is not a stripped-down, API-incompatible toy — anything you learn against k3s transfers directly to EKS/GKE/AKS/kubeadm clusters, because it passes the same Kubernetes conformance test suite. What k3s changes for operational simplicity:

| | "Full" Kubernetes (kubeadm) | k3s |
|---|---|---|
| Datastore | etcd (separate process/cluster) | Embedded SQLite by default (single-node); can switch to etcd, MySQL, Postgres, or external etcd for HA |
| Control-plane components | Separate binaries/Pods | Compiled into one `k3s` binary/process |
| Container runtime | Installed separately (containerd/CRI-O) | Bundled containerd, no separate install |
| Networking (CNI), DNS, Ingress | You install Flannel/Calico/etc., CoreDNS, an Ingress controller yourself | Bundled: Flannel (CNI), CoreDNS, Traefik (Ingress), a local-path storage provisioner, and a basic ServiceLB |
| Typical install time | 30+ minutes, many steps | Under 60 seconds, one command |

For learning, this means you get a fully conformant cluster almost instantly, with sane defaults for every "day 2 add-on" you'd otherwise have to install by hand before you could do anything — you'll still learn what each of those add-ons does (Days 7, 11, 15, 18) because k3s doesn't hide them, it just pre-installs them.

### 1.3 kubectl & kubeconfig

[`kubectl`](https://kubernetes.io/docs/reference/kubectl/) is a thin client that reads `~/.kube/config` (a [**kubeconfig**](https://kubernetes.io/docs/concepts/configuration/organize-cluster-access-kubeconfig/) file) to know which API server to talk to, as which user/credentials, and calls that pairing a **context**. Every `kubectl` command is really just an HTTPS call to the [`kube-apiserver`](https://kubernetes.io/docs/concepts/overview/components/#kube-apiserver) — `kubectl` itself holds no cluster state and does no orchestration; it's a REST client with very good ergonomics.

### Official documentation
- [Kubernetes Components](https://kubernetes.io/docs/concepts/overview/components/)
- [The Kubernetes API](https://kubernetes.io/docs/concepts/overview/kubernetes-api/)
- [Nodes](https://kubernetes.io/docs/concepts/architecture/nodes/)
- [The Kubernetes Control Plane / Architecture overview](https://kubernetes.io/docs/concepts/architecture/)
- [Container Runtime Interface (CRI)](https://kubernetes.io/docs/concepts/architecture/cri/)
- [Install and Set Up kubectl](https://kubernetes.io/docs/tasks/tools/#kubectl)
- [Organizing Cluster Access with kubeconfig](https://kubernetes.io/docs/concepts/configuration/organize-cluster-access-kubeconfig/)
- [kubectl Cheat Sheet](https://kubernetes.io/docs/reference/kubectl/cheatsheet/)
- [k3s Documentation](https://docs.k3s.io/)
- [k3s Quick-Start Guide](https://docs.k3s.io/quick-start)
- [k3s: Private Registry Configuration](https://docs.k3s.io/installation/private-registry)
- [CNCF Software Conformance](https://www.cncf.io/certification/software-conformance/)

## 2. Choose your environment

You need a Linux machine (real or virtual) with **at least 2 vCPU, 4GB RAM, 20GB free disk**, outbound internet access, and `sudo`. Pick whichever of these matches what you have:

| You have... | Do this |
|---|---|
| A Linux machine already (bare metal, VM, cloud instance) — Ubuntu 22.04/24.04 assumed | Skip to **2.1** directly |
| A Windows PC | Install **WSL2** with an Ubuntu distro, then treat it as your Linux machine (`wsl --install -d Ubuntu-24.04` in an admin PowerShell, reboot, then continue at 2.1 *inside* the WSL Ubuntu shell) |
| A Mac (Intel or Apple Silicon) | Install [Multipass](https://multipass.run/) (`brew install multipass`), then `multipass launch --name k8s --cpus 2 --memory 4G --disk 20G 24.04`, then `multipass shell k8s` to get a Linux shell — continue at 2.1 inside it |
| Nothing local you want to touch / want full isolation | Spin up any cheap cloud VM (a $5-6/month Ubuntu 24.04 droplet/instance from any provider works fine) and SSH into it — continue at 2.1 |
| Only Docker Desktop, no spare VM at all | Use **k3d** instead (k3s running *inside* Docker containers on your existing machine) — see the **k3d alternative** box at the end of section 2.1. Every later day's commands are identical either way. |

> This course's commands assume a Debian/Ubuntu-family Linux shell (`apt`, `systemctl`). If you're on Fedora/RHEL/Rocky, swap `apt` for `dnf`; k3s's installer itself is distro-agnostic.

## 3. Hands-on lab

### 3.1 Check prerequisites

```bash
# CPU / memory / disk
nproc                       # want >= 2
free -h                     # want >= 4G total
df -h /                     # want >= 20G free

# k3s needs these kernel modules available (usually already loaded on modern kernels)
lsmod | grep -E 'br_netfilter|overlay' || echo "will be auto-loaded by k3s on most distros"

# Ports k3s needs open on this machine (loopback/private network is fine for a single node):
#   6443/tcp  - Kubernetes API server
#   10250/tcp - kubelet
#   8472/udp  - Flannel VXLAN (only matters once you add a second node, Day 19+)
sudo ss -tulnp | grep -E '6443|10250' || echo "nothing bound yet — expected before install"
```

### 3.2 Install k3s

```bash
curl -sfL https://get.k3s.io | sh -
```

This script downloads the `k3s` binary, installs it as a `systemd` service named `k3s`, and starts it immediately. Confirm it's actually up before moving on — **do not skip this check**:

```bash
sudo systemctl status k3s --no-pager      # want "active (running)"
sudo k3s kubectl get nodes                # want your node, STATUS Ready (may take ~30-60s)
```

> **Pinning a version:** for reproducibility (and because this course was written against a specific k3s release), you can pin the install: `curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION=v1.30.5+k3s1 sh -`. See the [k3s releases page](https://github.com/k3s-io/k3s/releases) for current versions.

### 3.3 Configure kubectl for your user (no `sudo` needed after this)

```bash
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $(id -u):$(id -g) ~/.kube/config
chmod 600 ~/.kube/config

# k3s installs its own kubectl at /usr/local/bin/kubectl; confirm it's on PATH
kubectl version
kubectl get nodes -o wide
kubectl get pods -A     # -A = --all-namespaces; see k3s's own system Pods
kubectl cluster-info
```

If `kubectl` isn't found, the installer places a symlink at `/usr/local/bin/kubectl` — confirm with `which kubectl` and that `/usr/local/bin` is on your `$PATH` (`echo $PATH`).

### 3.4 Managing the k3s service

You'll use these constantly across the course whenever something seems wrong at the cluster level (as opposed to inside a single Pod):

```bash
sudo systemctl status k3s          # is it running?
sudo systemctl restart k3s         # restart the whole control plane + kubelet
sudo journalctl -u k3s -f          # live-tail k3s's own logs — your first stop if `kubectl` can't connect at all
sudo systemctl stop k3s            # stop (Pods keep their last state, nothing new is scheduled)
sudo systemctl start k3s           # start again
```

### 3.5 Point k3s at your local registry from Day 1

This section assumes the registry container you started in [Day 1, section 2.6](../day01-containers-and-docker/README.md#26-run-a-local-registry-this-is-exactly-how-k3s-will-pull-your-images-later) is still running. If you're picking the course back up in a new shell session (or on a fresh VM) and it isn't, start it again first:

```bash
docker ps --filter name=registry   # empty output means it's not running
docker run -d -p 5000:5000 --restart=always --name registry registry:2   # only if the line above was empty
```

k3s's bundled containerd needs to know `localhost:5000` is an insecure (HTTP) registry before it will pull from it:

```bash
sudo mkdir -p /etc/rancher/k3s
cat <<'EOF' | sudo tee /etc/rancher/k3s/registries.yaml
mirrors:
  "localhost:5000":
    endpoint:
      - "http://localhost:5000"
EOF
sudo systemctl restart k3s
sudo systemctl status k3s --no-pager   # confirm it came back up after the restart
```

### 3.6 Run your first Pod imperatively

```bash
kubectl run hello --image=localhost:5000/hello-k8s:1.0.0 --port=8080
kubectl get pods -w      # ctrl-c once it's Running
kubectl describe pod hello
kubectl logs hello
kubectl port-forward pod/hello 8080:8080 &
curl localhost:8080/
kill %1
```

### 3.7 Explore the API without guessing

```bash
kubectl api-resources | head -20
kubectl explain pod.spec.containers
kubectl explain pod.spec.containers.resources --recursive
kubectl get pod hello -o yaml | less
```

### 3.8 Clean up

```bash
kubectl delete pod hello
```

### 3.9 Troubleshooting a failed install

| Symptom | Likely cause / fix |
|---|---|
| `sudo systemctl status k3s` shows `failed` | Run `sudo journalctl -u k3s -e --no-pager` and read the last 30-40 lines — the real error is almost always near the bottom |
| `Node` never reaches `Ready` | Check `sudo journalctl -u k3s -f` for CNI (Flannel) errors; confirm no other process already owns port `6443` (`sudo ss -tulnp \| grep 6443`) |
| `kubectl` hangs or times out | `~/.kube/config` server URL should be `https://127.0.0.1:6443` — confirm with `kubectl config view --minify`; also confirm `sudo systemctl status k3s` is actually active |
| `Permission denied` reading `/etc/rancher/k3s/k3s.yaml` | You skipped the `chown`/`chmod` in 3.3, or you're using a fresh shell where `~/.kube/config` wasn't picked up — check `echo $KUBECONFIG` is unset or points at the right file |
| Installed on a machine already running Docker's default bridge network `172.17.0.0/16` and something looks wrong with Pod networking | k3s's default Pod CIDR is `10.42.0.0/16` and Service CIDR `10.43.0.0/16` — a conflict is rare, but if you have unusual existing routes, install with `INSTALL_K3S_EXEC="--cluster-cidr=10.52.0.0/16 --service-cidr=10.53.0.0/16"` |

The table above covers install-specific failures. For everything you'll hit once Pods/Services enter the picture from Day 3 onward, see [Debugging Common Kubernetes Issues](../TROUBLESHOOTING.md) — every later day links back to it too.

### 3.10 Uninstalling / starting over

The installer places an uninstall script on the machine — this is the safe way to fully reset if you want to redo this lab from scratch:

```bash
sudo /usr/local/bin/k3s-uninstall.sh
# then simply re-run section 3.2 to reinstall
```

> **k3d alternative** (if you only have Docker and no spare VM): `k3d` runs k3s server/agent nodes as Docker containers on your existing machine — same k3s underneath, same `kubectl` experience, no VM required. Install with `curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash`, then `k3d cluster create zero2hero --api-port 6443 -p "30080-30090:30080-30090@server:0"` in place of section 3.2's `curl | sh`. `kubectl` config is written automatically by `k3d`; section 3.3 is not needed.
>
> **Registry caveat for k3d specifically:** section 3.5's approach does *not* work unchanged here. A k3d node is itself a Docker container with its own network namespace, so `localhost:5000` from inside a k3d node never reaches a plain `docker run -p 5000:5000 registry:2` container on your host — that command only worked for every other environment option because k3s there runs directly on the same host/VM as the registry. Instead, let k3d wire the registry into the cluster's own Docker network for you: recreate your cluster with `k3d cluster create zero2hero --api-port 6443 -p "30080-30090:30080-30090@server:0" --registry-create zero2hero-registry:0.0.0.0:5000` (check `k3d registry --help` if this exact flag has moved by the time you run it). This still exposes the registry at `localhost:5000` on your host for `docker push`, and every node can reach it too — skip section 3.5 entirely, since k3d already configured containerd's registry trust for you.

## 4. kubectl Mastery

Every remaining day in this course leans on `kubectl` constantly — this section is the one place that teaches the tool itself in depth, so later days can just *use* it. Work through each subsection's drill before moving on; none of it needs anything beyond the Pod you already created in section 3.6 (recreate it if you cleaned up: `kubectl run hello --image=localhost:5000/hello-k8s:1.0.0 --port=8080`).

### 4.1 Output formats — get exactly the data you need, scriptably

`-o wide`/`yaml`/`json` are the ones you've used so far. Three more matter far more once you start scripting against a cluster (CI pipelines, health-check scripts, the mini-operator you'll write by hand on Day 22):

- **`-o jsonpath='{...}'`** — extract one specific field, no parsing required downstream:
  ```bash
  kubectl get pod hello -o jsonpath='{.status.podIP}'; echo
  kubectl get pods -o jsonpath='{.items[*].metadata.name}'; echo
  kubectl get pod hello -o jsonpath='{.spec.containers[0].image}'; echo
  ```
- **`-o custom-columns=`** — a lightweight, readable table with exactly the columns you want, no jq/awk needed:
  ```bash
  kubectl get pods -o custom-columns='NAME:.metadata.name,IMAGE:.spec.containers[0].image,STATUS:.status.phase'
  ```
- **`--sort-by=`** — order any list by any field, e.g. find the most-restarted Pods cluster-wide:
  ```bash
  kubectl get pods -A --sort-by='.status.containerStatuses[0].restartCount'
  ```
- **`-o name`** — bare `kind/name` output, built for piping into another command:
  ```bash
  kubectl get pods -o name | xargs -I{} kubectl label {} inspected=true
  ```

### 4.2 Dry-run, diff, and patch — changing things safely

You've used `--dry-run=client -o yaml` since Day 3 to render a manifest without sending it. There's a second, stronger mode, and a way to preview a *real* change before it lands:

```bash
# --dry-run=client: render locally, no network call at all
kubectl run dry-test --image=nginx --dry-run=client -o yaml

# --dry-run=server: send it to the real API server (full admission chain, Day 17) but don't PERSIST it — catches schema/admission errors client-side dry-run can't see
kubectl run dry-test --image=nginx --dry-run=server -o yaml

# kubectl diff: compare a local file against live cluster state, using that same server-side dry-run under the hood
kubectl diff -f ../day03-pods/manifests/pod-basic.yaml
```

`kubectl patch` supports three distinct patch strategies — you've already used two of them in earlier days without the distinction being named:

| `--type` | Semantics | Where you've already used it |
|---|---|---|
| `strategic` (default) | Kubernetes-aware merge — understands list semantics per-field (e.g. merges `containers` by `name` instead of blindly replacing the array) | Default for every plain `kubectl patch` so far |
| `merge` (RFC 7396 JSON Merge Patch) | Simpler merge — replaces whole arrays wholesale, no Kubernetes-specific list awareness | Day 6 (`kubectl patch configmap ... --type merge`), Day 8 (`kubectl patch website ... --type merge`) |
| `json` (RFC 6902 JSON Patch) | Explicit `add`/`remove`/`replace` operations against exact paths — most precise, most verbose | Day 17 (`kubectl patch validatingadmissionpolicybinding --type=json ...`) |

```bash
kubectl patch pod hello --type merge -p '{"metadata":{"labels":{"patched":"true"}}}'
kubectl patch pod hello --type json -p '[{"op":"add","path":"/metadata/labels/via-json-patch","value":"true"}]'
kubectl get pod hello --show-labels
```

### 4.3 Ephemeral debug containers — `kubectl debug`

`kubectl exec` (used constantly since Day 3) only works if the target container **has a shell and debugging tools already installed** — many real-world production images (distroless, `scratch`-based) deliberately have neither, to shrink attack surface. [`kubectl debug`](https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/) solves this by attaching a **temporary, throwaway container** (an "ephemeral container") to an already-running Pod, sharing its process namespace, without modifying or restarting the original:

```bash
kubectl debug -it hello --image=busybox:1.36 --target=hello-k8s -- sh
# inside: ps aux    <- shows the ORIGINAL container's processes too, thanks to --target sharing its PID namespace
exit
```

The same command works at the **Node** level, when you need to inspect a Node's filesystem/tools directly without SSH access:
```bash
kubectl debug node/$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}') -it --image=busybox:1.36 -- chroot /host sh
exit
```

### 4.4 Copying files and reaching cluster-internal services

```bash
echo "hello from the host" > /tmp/from-host.txt
kubectl cp /tmp/from-host.txt hello:/tmp/from-host.txt
kubectl exec hello -- cat /tmp/from-host.txt
```

You've used `kubectl port-forward` throughout this day — it tunnels your local port directly to **one** Pod or Service port. [`kubectl proxy`](https://kubernetes.io/docs/tasks/access-application-cluster/access-cluster/#directly-accessing-the-rest-api) is different: it exposes the **entire Kubernetes API** on localhost, authenticated using your own kubeconfig credentials, letting you hit any resource's REST endpoint directly, including a generic Service-proxying subresource:

```bash
kubectl proxy --port=8001 &
curl http://localhost:8001/api/v1/namespaces/default/pods/hello
curl http://localhost:8001/api/v1/namespaces/default/services/hello-k8s-svc:80/proxy/   # if that Service exists from Day 5
kill %1
```
Use `port-forward` for "let me reach this one specific thing" (today's default everywhere in this course); use `proxy` for exploring or scripting against the raw API itself.

### 4.5 Contexts, namespaces, and multi-cluster productivity

You'll accumulate more `kubectl` contexts than you expect — this lab VM today, a second cluster tomorrow, a friend's cluster next week. Know these cold:

```bash
kubectl config get-contexts
kubectl config current-context
kubectl config use-context <name>                          # switch clusters entirely
kubectl config set-context --current --namespace=default    # stop typing `-n <ns>` on every single command
```

For real multi-cluster/multi-namespace work, the community tools [`kubectx` and `kubens`](https://github.com/ahmetb/kubectx) wrap exactly these two commands with fuzzy-search and a "switch back to previous" shortcut — extremely common in real engineers' daily workflow, worth installing once you're past this course's single-cluster labs.

### 4.6 Autocompletion and plugins

Tab-completion for resource names, not just subcommands, saves real time every single day:
```bash
echo 'source <(kubectl completion bash)' >> ~/.bashrc   # or: completion zsh >> ~/.zshrc
echo 'alias k=kubectl' >> ~/.bashrc
echo 'complete -o default -F __start_kubectl k' >> ~/.bashrc
source ~/.bashrc
```

[`krew`](https://krew.sigs.k8s.io/) is `kubectl`'s own plugin manager (itself installed as a `kubectl` plugin) — once installed, `kubectl plugin list` shows what's available and `kubectl krew install <name>` adds more. Two worth knowing about now, useful again in later days:
```bash
kubectl krew install ctx ns tree
kubectl ctx      # fuzzy context switcher (krew's version of kubectx)
kubectl tree deployment hello-k8s   # if you still have a Deployment around — visualizes the FULL ownership chain from Day 4 (Deployment -> ReplicaSet -> Pods) as a tree, in one command
```

### Official documentation (kubectl mastery)
- [kubectl Reference Docs](https://kubernetes.io/docs/reference/kubectl/)
- [JSONPath Support](https://kubernetes.io/docs/reference/kubectl/jsonpath/)
- [Kubectl Cheat Sheet](https://kubernetes.io/docs/reference/kubectl/cheatsheet/)
- [Update API Objects in Place Using kubectl patch](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/update-api-object-kubectl-patch/)
- [Debugging Running Pods (`kubectl debug`)](https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/)
- [Debugging Kubernetes Nodes with `kubectl debug`](https://kubernetes.io/docs/tasks/debug/debug-cluster/kubectl-node-debug/)
- [Accessing the Kubernetes API (`kubectl proxy`)](https://kubernetes.io/docs/tasks/access-application-cluster/access-cluster/#directly-accessing-the-rest-api)
- [Organizing Cluster Access with kubeconfig](https://kubernetes.io/docs/concepts/configuration/organize-cluster-access-kubeconfig/)
- [krew — kubectl plugin manager](https://krew.sigs.k8s.io/)

## 5. Key commands reference

| Command | Purpose |
|---|---|
| `kubectl get <resource> [-A\|-n ns] [-o wide\|yaml\|json\|jsonpath=...\|custom-columns=...]` | List resources, in whatever shape you need |
| `kubectl describe <resource> <name>` | Full details + recent Events — **your #1 debugging tool** |
| `kubectl logs [-f] <pod> [-c container] [--previous]` | Container logs |
| `kubectl exec -it <pod> [-c container] -- sh` | Shell into a container that already has one |
| `kubectl debug -it <pod> --image=<img> --target=<container> -- sh` | Attach a throwaway debug container, no shell required in the original |
| `kubectl apply -f <file.yaml>` | Declaratively create/update from YAML (used from Day 3 onward) |
| `kubectl diff -f <file.yaml>` | Preview what `apply` would change, before applying |
| `kubectl patch <resource> <name> --type {strategic\|merge\|json} -p '<patch>'` | Targeted, partial update |
| `kubectl delete -f <file.yaml>` | Delete what that file defines |
| `kubectl explain <resource>.<path>` | Offline field docs |
| `kubectl get events --sort-by=.lastTimestamp` | Cluster-wide recent events, chronological |
| `kubectl cp <src> <pod>:<dest>` | Copy files into/out of a container |
| `kubectl proxy --port=<port>` | Expose the full API locally, authenticated as you |
| `kubectl config {get-contexts\|use-context\|set-context --current --namespace=}` | Manage clusters/namespaces you switch between |
| `sudo systemctl {status\|restart\|stop\|start} k3s` | Manage the cluster service itself |
| `sudo journalctl -u k3s -f` | Live cluster-level logs (not Pod logs) |

Next: [Day 3 — Pods](../day03-pods/README.md)
