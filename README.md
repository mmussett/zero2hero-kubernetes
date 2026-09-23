# Zero to Hero for Kubernetes

![Kubernetes](https://img.shields.io/badge/Kubernetes-1.30%2B-326CE5?logo=kubernetes&logoColor=white)
![k3s](https://img.shields.io/badge/Distribution-k3s-FFC61E?logo=k3s&logoColor=white)
![Duration](https://img.shields.io/badge/Duration-23%20days-success)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)

A 23-day, hands-on Kubernetes course that takes you from **never having run a container** to being able to design, deploy, secure, and operate production-grade workloads on Kubernetes — and pass a CKA-style practical exam.

## Introduction

**Zero to Hero for Kubernetes** is a self-paced, project-based path from absolute beginner to confident, production-minded Kubernetes practitioner — in twenty-three focused days, on infrastructure you fully control.

No prior Kubernetes knowledge is assumed, and no prior *container* knowledge is assumed either — Day 1 starts one level below Kubernetes, with plain Docker, and only introduces a cluster once you've built and run an image with your own hands. From there, every subsequent day adds exactly one coherent slice of the platform — workloads, storage, networking (including a deliberately deep two-day dive into Ingress Controllers and the Gateway API, across the most widely-adopted open-source options), security, observability, packaging (Helm, plus a GitOps day putting it into continuous, git-driven practice), autoscaling, extensibility — building toward a Day 23 capstone where you deploy, secure, scale, and deliberately break a real multi-tier application, then diagnose it back to health using nothing but the skills from the previous twenty-two days.

This course is built around a few deliberate principles:

- **Everything runs locally and for free.** A single small VM running [k3s](https://docs.k3s.io/) is the only infrastructure required, for all twenty-three days (with a temporary RAM bump recommended for the two heaviest days, called out where they occur). No cloud account, no billing, no waiting on shared resources.
- **Every lesson is hands-on first.** Concepts are taught, then immediately exercised against a real running cluster — never diagrams alone.
- **Every exercise has a worked answer.** You're expected to attempt each exercise yourself before reading `SOLUTIONS.md`, but you're never left stuck without a path forward.
- **Every concept links to primary sources.** Each day's `README.md` ends with an **Official documentation** section pointing at the exact upstream Kubernetes (or k3s, Helm, Traefik...) docs pages covering that day's material — so you build the habit of reading primary sources, the same habit you'll rely on once this course is finished and the docs are all you have.
- **Nothing is hidden behind magic.** Where a real tool would normally be a black box (an Operator, a Helm chart, an Ingress controller), this course either builds a minimal version of it yourself or explains exactly what it's doing underneath, so intuition survives contact with unfamiliar tools later.

Who this is for: engineers who can already use a terminal and are comfortable editing YAML, coming from any background — application development, ops, infrastructure, or a computer science program — who want a structured, complete path through Kubernetes rather than a scattered collection of tutorials.

## Table of Contents

- [Introduction](#introduction)
- [How This Course Works](#how-this-course-works)
- [Environment Assumptions](#environment-assumptions)
- [Syllabus](#syllabus)
  - **Phase 1 — Foundations:** [Day 1](day01-containers-and-docker/README.md) · [Day 2](day02-k3s-install-and-kubectl/README.md) · [Day 3](day03-pods/README.md) · [Day 4](day04-deployments-replicasets/README.md) · [Day 5](day05-services-and-networking/README.md)
  - **Phase 2 — Workloads, Config & Storage:** [Day 6](day06-configmaps-and-secrets/README.md) · [Day 7](day07-storage-and-volumes/README.md) · [Day 8](day08-statefulsets/README.md) · [Day 9](day09-daemonsets-jobs-cronjobs/README.md) · [Day 10](day10-namespaces-and-resource-management/README.md)
  - **Phase 3 — Networking:** [Day 11](day11-ingress/README.md) · [Day 12](day12-ingress-controllers-in-depth/README.md) · [Day 13](day13-gateway-api/README.md) · [Day 14](day14-network-policies/README.md) · [Day 15](day15-dns-and-service-discovery/README.md)
  - **Phase 4 — Security:** [Day 16](day16-rbac-and-service-accounts/README.md) · [Day 17](day17-pod-security-and-admission/README.md)
  - **Phase 5 — Observability:** [Day 18](day18-observability/README.md)
  - **Phase 6 — Package Management:** [Day 19](day19-helm/README.md) · [Day 20](day20-gitops-with-argocd-and-flux/README.md)
  - **Phase 7 — Scaling & Extensibility:** [Day 21](day21-autoscaling-and-rollouts/README.md) · [Day 22](day22-crds-operators-and-kustomize/README.md)
  - **Phase 8 — Capstone:** [Day 23](day23-capstone-project/README.md)
- [Quick Start](#quick-start)
- [Debugging Common Kubernetes Issues](TROUBLESHOOTING.md)
- [Getting Help When Stuck](#getting-help-when-stuck)
- [Documentation Conventions](#documentation-conventions)
- [Reference Material](#reference-material)
- [License](#license)
- [Contributing](#contributing)

## How this course works

Every day lives in its own folder: `dayNN-topic/`. Each folder contains:

| File | Purpose |
|---|---|
| `README.md` | Concepts for the day + a step-by-step hands-on lab |
| `EXERCISES.md` | 3-6 tasks to complete on your own |
| `SOLUTIONS.md` | Full worked answers, including commands and YAML |
| `manifests/` | YAML you `kubectl apply` during the lab/exercises |
| `app/` (some days) | Sample application source + `Dockerfile` |

**Rules for using it:**
1. Do the lab in `README.md` first — type the commands yourself, don't copy-paste blindly.
2. Attempt every exercise in `EXERCISES.md` *before* opening `SOLUTIONS.md`.
3. Every exercise is designed to run on the cluster you build on Day 2. Nothing later requires a cloud account.
4. Budget 1.5–3 hours per day. Days 12-13 (Ingress Controllers/Gateway API), Day 18 (Observability), and Days 20-23 (GitOps onward) run longer — Day 18 specifically needs 3-4 hours and 8GB RAM; it says so at the top of its own README.

## Environment assumptions

- A Linux machine (bare metal, VM, or WSL2) with at least **2 vCPU / 4GB RAM / 20GB disk**, `sudo` access, and outbound internet access. Ubuntu 22.04/24.04 is used in all examples; commands are noted where another distro differs. Bump to **4 vCPU / 8GB RAM** for Day 18 specifically (called out again in that day's own README).
- Single-node **k3s** cluster for Days 1-19. Days 20-23 optionally extend to a 3-node k3s cluster (instructions included, but a single node still works for every exercise).
- `docker` (or `nerdctl`/`podman` — noted where it matters) for building images locally in Days 1 and onward.
- No paid cloud services required anywhere in the course.

## Syllabus

### Phase 1 — Foundations
| Day | Topic |
|---|---|
| [01](day01-containers-and-docker/README.md) | Linux containers & Docker fundamentals — build and run your first image |
| [02](day02-k3s-install-and-kubectl/README.md) | Kubernetes architecture, installing a k3s cluster, and `kubectl` mastery (output formats, patch types, `debug`, `proxy`, contexts) |
| [03](day03-pods/README.md) | Pods — the atomic unit of Kubernetes |
| [04](day04-deployments-replicasets/README.md) | ReplicaSets, Deployments, rolling updates & rollbacks |
| [05](day05-services-and-networking/README.md) | Services, ClusterIP/NodePort/LoadBalancer, kube-proxy |

### Phase 2 — Workloads, Config & Storage
| Day | Topic |
|---|---|
| [06](day06-configmaps-and-secrets/README.md) | ConfigMaps & Secrets |
| [07](day07-storage-and-volumes/README.md) | Volumes, PersistentVolumes, PersistentVolumeClaims, StorageClasses |
| [08](day08-statefulsets/README.md) | StatefulSets & stable network identity |
| [09](day09-daemonsets-jobs-cronjobs/README.md) | DaemonSets, Jobs, CronJobs |
| [10](day10-namespaces-and-resource-management/README.md) | Namespaces, ResourceQuotas, LimitRanges, requests/limits |

### Phase 3 — Networking
| Day | Topic |
|---|---|
| [11](day11-ingress/README.md) | Ingress resources & your first controller (Traefik) |
| [12](day12-ingress-controllers-in-depth/README.md) | Ingress Controllers in depth: NGINX Ingress Controller & Kong Ingress Controller, compared head-to-head against Traefik |
| [13](day13-gateway-api/README.md) | Ingress Gateways: the Gateway API, with NGINX Gateway Fabric, Kong Gateway Operator & Envoy Gateway |
| [14](day14-network-policies/README.md) | NetworkPolicies — segmenting pod-to-pod traffic |
| [15](day15-dns-and-service-discovery/README.md) | CoreDNS & service discovery internals |

### Phase 4 — Security
| Day | Topic |
|---|---|
| [16](day16-rbac-and-service-accounts/README.md) | RBAC, ServiceAccounts, SecurityContexts |
| [17](day17-pod-security-and-admission/README.md) | Pod Security Standards, admission control, image supply-chain basics |

### Phase 5 — Observability
| Day | Topic |
|---|---|
| [18](day18-observability/README.md) | Metrics (Prometheus/Grafana), distributed tracing (Jaeger/OpenTelemetry), and centralized logging — node-agent (Loki, EFK/Filebeat) & sidecar (Fluent Bit, Fluentd) patterns compared |

### Phase 6 — Package Management
| Day | Topic |
|---|---|
| [19](day19-helm/README.md) | Helm — templating, packaging, releases |
| [20](day20-gitops-with-argocd-and-flux/README.md) | GitOps: continuous, git-driven deployment with ArgoCD (and a Flux comparison) |

### Phase 7 — Scaling & Extensibility
| Day | Topic |
|---|---|
| [21](day21-autoscaling-and-rollouts/README.md) | HPA, VPA concepts, Cluster Autoscaler concepts, advanced rollout strategies |
| [22](day22-crds-operators-and-kustomize/README.md) | Custom Resources, Operators, Kustomize |

### Phase 8 — Capstone
| Day | Topic |
|---|---|
| [23](day23-capstone-project/README.md) | Capstone: deploy, secure, scale, and troubleshoot a full multi-tier app end-to-end |

## Quick start

```bash
git clone <this-repo>
cd zero2hero-kubernetes/day01-containers-and-docker
cat README.md
```

## Getting help when stuck

- **[Debugging Common Kubernetes Issues](TROUBLESHOOTING.md)** — start here. A standalone field guide collating every well-known beginner failure mode (`ImagePullBackOff`, `CrashLoopBackOff`, `Pending` Pods, `Forbidden`, DNS failures, storage stuck-`Pending`, and more) with how to diagnose and fix each one, plus the general debugging method (`describe` → `logs` → `get events`) that solves most problems before you even reach a specific entry.
- Every day's own `README.md` also has a **Troubleshooting** section for issues specific to that day's topic, cross-linked to the addendum above for anything cross-cutting.
- `kubectl explain <resource>[.<field>]` — official field-level docs from your CLI, no internet needed.
- `kubectl get events --sort-by=.lastTimestamp` — the single most useful troubleshooting command in this course. Use it constantly.
- Every lab is idempotent: if you break your cluster, `k3s-uninstall.sh` (Day 2) and reinstall takes under 2 minutes.
- [kubernetes.io/docs](https://kubernetes.io/docs/home/) — the canonical reference. Every day's README links the specific pages relevant to that day under **Official documentation**.

## Documentation conventions

- Each day's `README.md` ends its **Concepts** section with an **Official documentation** list — read those links, don't just skim past them. This course teaches you to navigate the upstream docs, because that's what you'll do on the job.
- `kubectl explain` is referenced constantly instead of pasting full API schemas — it's always in sync with your cluster's exact version, which the written docs may not be.
- Command blocks are copy-paste safe top-to-bottom within a lab section; running them out of order may require re-running an earlier step.

## Reference material

- [Kubernetes Documentation](https://kubernetes.io/docs/home/)
- [Kubernetes API Reference](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.30/)
- [kubectl Reference Docs](https://kubernetes.io/docs/reference/kubectl/)
- [k3s Documentation](https://docs.k3s.io/)
- [CNCF Curriculum (CKA/CKAD exam domains)](https://github.com/cncf/curriculum)

## License

Released under the [MIT License](LICENSE). Course content, sample apps, and manifests are free to use, adapt, and redistribute for teaching or learning.

## Contributing

Found an error or an outdated command? Open an issue or a pull request — corrections against a real cluster run are especially welcome.
