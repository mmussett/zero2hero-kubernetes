# Day 20 — GitOps: Continuous, Git-Driven Deployment with ArgoCD & Flux

> **Prerequisite:** this lab deploys directly from **your own fork/push of this course repository** — see the top-level README's note on publishing to GitHub. Replace `REPO_URL_PLACEHOLDER` in every manifest below with your repo's real URL before applying. If you haven't pushed this repo anywhere yet, do that first; today's lab is exactly why the top-level README asked you to.

Day 19 taught you to package an application as a Helm chart and deploy it with `helm upgrade` — a human, running a command, from wherever they happen to be sitting. Today asks: what actually triggers that command in a real production team, at 2am, when nobody is at a keyboard? The answer, increasingly, is **GitOps**.

## Learning objectives
- Explain the difference between push-based deployment (CI running `kubectl`/`helm` against your cluster) and pull-based GitOps (a controller *inside* the cluster reconciling from Git)
- Install ArgoCD and deploy Day 19's own Helm chart from your own Git repository
- Observe drift detection and self-healing when someone bypasses Git and edits the cluster directly
- Perform a rollback via Git history, not a cluster-side command
- Install Flux and deploy the identical chart, comparing its decomposed controller architecture to ArgoCD's integrated model
- Decide, with real criteria, which tool (or neither) fits a given team

## 1. Concepts

### 1.1 Push vs. pull deployment

Every deployment mechanism you've used so far in this course — `kubectl apply`, `helm install`, even a CI pipeline running those commands — is **push-based**: something *outside* the cluster (you, or a CI runner) initiates a change and pushes it in, using credentials that grant it write access to the cluster. This has two real problems at scale: (1) CI systems accumulate broad, standing cluster credentials, a significant attack surface if that CI system is ever compromised; (2) nothing continuously verifies the cluster still matches what was intended — if someone runs a manual `kubectl edit` afterward, nothing notices or corrects it.

[**GitOps**](https://opengitops.dev/) flips this: a **controller running inside the cluster** continuously watches a Git repository and reconciles live cluster state toward whatever that repository declares — the same watch-compare-act reconciliation loop from Day 2's architecture diagram, now applied to your *entire application deployment*, not just one Kubernetes resource type. Nothing external ever needs direct cluster-write credentials at all — Git becomes the single source of truth, and the only "deployment" action a human takes is a `git commit`.

```
 PUSH (what you've done all course):        PULL (GitOps, today):

 You/CI ──kubectl/helm──▶ Cluster            You ──git push──▶ Git repo
   (needs cluster credentials)                                    │
                                                          polled/watched by
                                                                    ▼
                                              GitOps controller (IN cluster)
                                                     │  reconciles
                                                     ▼
                                                  Cluster
                                              (controller already has
                                               in-cluster credentials —
                                               nothing external needs any)
```

### 1.2 What this buys you, concretely

- **Audit trail for free** — every deployed change has a corresponding Git commit: who, when, why (commit message), and an exact diff. Compare to `kubectl apply` history, which Day 2/4 showed is at best a `rollout history` per-Deployment, with no unified cross-resource story.
- **Rollback = `git revert`** — reverting a commit and letting the controller reconcile is now your rollback mechanism, unifying "how do I roll back my whole app" into the same tool you already use for code.
- **Drift detection and self-healing** — if a change is made directly against the cluster (a manual `kubectl edit`, an incident-response hotfix someone forgot to also commit), the controller notices the live state no longer matches Git and can flag it (`OutOfSync`) or automatically revert it (`selfHeal`) — today's lab does both, deliberately, so you see the difference.
- **No standing external credentials** — the controller holds in-cluster credentials; your CI pipeline's job shrinks to "push code and manifests to Git," nothing more privileged than that.

### 1.3 ArgoCD's model: one integrated Application

[**ArgoCD**](https://argo-cd.readthedocs.io/) centers on one CRD, `Application`, declaring a Git repo + path + target cluster/namespace, with a full web UI visualizing every resource it manages, live sync status, and a diff view before you approve a change. It has native, first-class support for Helm charts, Kustomize overlays, and plain YAML — all through the same `Application` object, just pointed at a different kind of source path.

### 1.4 Flux's model: decomposed, composable controllers

[**Flux**](https://fluxcd.io/) (v2) splits the same job across independently-deployed, independently-scaled controllers: `source-controller` watches Git/Helm/OCI sources (via a `GitRepository` CRD, used today), `kustomize-controller` reconciles plain-manifest/Kustomize paths, and `helm-controller` reconciles Helm charts (via a `HelmRelease` CRD, also used today) sourced from whatever `source-controller` is watching. There's no built-in web UI in Flux core (a separate product, Flux's Weave GitOps UI, or Grafana dashboards, fill that gap) — Flux leans toward being driven by, and inspected through, `kubectl`/GitOps tooling rather than a dedicated console.

| | ArgoCD | Flux |
|---|---|---|
| Architecture | One integrated `Application` CRD + built-in UI | Decomposed controllers (`source`, `kustomize`, `helm`, `notification`...), each independently scalable |
| UI | Full-featured web UI included | None built-in (kubectl-driven; optional separate UI projects) |
| Helm support | Native, via `Application.spec.source.helm` | Native, via a separate `HelmRelease` CRD sourced from a `GitRepository`/`HelmRepository` |
| Multi-cluster | Strong built-in support (one ArgoCD managing many target clusters) | Supported, typically via separate Flux installs per cluster or cross-cluster source references |
| Typical fit | Teams wanting a visual, click-through interface and a single mental model for "the whole app" | Teams wanting minimal, composable, Unix-philosophy pieces they wire together, often preferring pure CLI/GitOps-native workflows |

### 1.5 GitOps doesn't replace Helm — it drives it

Today's lab deploys the **exact same Helm chart** from Day 19 through both tools — GitOps is not a competing packaging mechanism, it's the automation layer that decides *when* and *how* your existing chart gets applied. The chart itself doesn't change at all.

### Official documentation
- [OpenGitOps Principles](https://opengitops.dev/)
- [ArgoCD documentation](https://argo-cd.readthedocs.io/en/stable/)
- [ArgoCD: Application CRD reference](https://argo-cd.readthedocs.io/en/stable/operator-manual/application.yaml/)
- [ArgoCD: Automated Sync Policy](https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/)
- [Flux documentation](https://fluxcd.io/flux/)
- [Flux: GitRepository API reference](https://fluxcd.io/flux/components/source/gitrepositories/)
- [Flux: HelmRelease API reference](https://fluxcd.io/flux/components/helm/helmreleases/)
- [CNCF: GitOps Working Group](https://github.com/cncf/tag-app-delivery/tree/main/gitops-wg)

## 2. Hands-on lab

```bash
cd day20-gitops-with-argocd-and-flux/manifests
REPO_URL="https://github.com/<your-username>/zero2hero-kubernetes.git"   # <-- set this to your real repo

# 2.1 Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl wait --for=condition=Available -n argocd deployment/argocd-server --timeout=180s

# 2.2 Reach the UI and log in
kubectl port-forward -n argocd svc/argocd-server 8080:443 &
ARGO_PW=$(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d)
echo "ArgoCD UI: https://localhost:8080  user: admin  password: $ARGO_PW"

# 2.3 Deploy Day 19's chart via a manual-sync Application
sed "s#REPO_URL_PLACEHOLDER#${REPO_URL}#" argocd-application-hello-chart.yaml | kubectl apply -f -
kubectl get application hello-chart -n argocd -w   # status: OutOfSync (nothing has synced yet)

# In the UI (or via CLI): trigger a manual sync
argocd login localhost:8080 --username admin --password "$ARGO_PW" --insecure
argocd app sync hello-chart
kubectl get pods -n argocd-demo   # the chart's Deployment/Service, running -- deployed via Git, not `helm install`

# 2.4 Drift detection: bypass Git entirely
kubectl scale deployment argocd-demo-hello-chart -n argocd-demo --replicas=5
kubectl get application hello-chart -n argocd -o jsonpath='{.status.sync.status}'; echo
# OutOfSync -- ArgoCD noticed the live state no longer matches Git, WITHOUT auto-fixing it yet

# 2.5 Turn on automated sync + self-heal, then repeat the drift test
sed "s#REPO_URL_PLACEHOLDER#${REPO_URL}#" argocd-application-automated.yaml | kubectl apply -f -
kubectl scale deployment argocd-demo-hello-chart -n argocd-demo --replicas=5
sleep 15
kubectl get deployment argocd-demo-hello-chart -n argocd-demo -o jsonpath='{.spec.replicas}'; echo
# back to whatever Git/values.yaml declares -- selfHeal reverted your manual change automatically

# 2.6 Rollback via git revert
# On your machine (not the cluster): edit values.yaml's `greeting`, commit, push.
# Watch ArgoCD auto-sync the change within its poll interval, then:
#   git revert HEAD && git push
# Watch it auto-sync BACK -- this is your whole rollback mechanism, no cluster command involved.

# 2.7 Install Flux and deploy the SAME chart
curl -s https://fluxcd.io/install.sh | sudo bash
flux install
sed "s#REPO_URL_PLACEHOLDER#${REPO_URL}#" flux-helmrelease.yaml | kubectl apply -f -
kubectl get gitrepository,helmrelease -n flux-system -w   # wait for both Ready
kubectl get pods -n flux-demo   # the IDENTICAL chart, deployed by a completely different tool

# 2.8 Compare resource footprint and object model
kubectl top pod -n argocd
kubectl top pod -n flux-system
kubectl get applications.argoproj.io -n argocd
kubectl get gitrepositories,helmreleases -n flux-system

# 2.9 Clean up
kubectl delete -n argocd -f argocd-application-automated.yaml --ignore-not-found
kubectl delete namespace argocd-demo flux-demo
kubectl delete -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl delete namespace argocd
flux uninstall --namespace flux-system -s
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| ArgoCD `Application` stuck `Unknown`/`OutOfSync` forever, never even attempts a sync | `repoURL` still has the literal `REPO_URL_PLACEHOLDER` text, or points at a private repo with no credentials configured | Confirm the `sed` substitution actually ran; for a private repo, add credentials via `argocd repo add` first |
| `Application` reports a source/path error | `path` doesn't exist at that exact location/branch in your repo, or you haven't pushed your latest commits yet | `git log`/`git status` on your local clone; confirm the path exists on the branch/`targetRevision` the Application points at |
| Flux `GitRepository`/`HelmRelease` stuck `False`/not Ready | Same root causes as above (bad URL, wrong branch, chart path), or the interval just hasn't elapsed yet | `flux get sources git` / `flux get helmreleases` for the exact condition message; `flux reconcile source git <name>` to force an immediate retry |
| Manual `kubectl scale`/`kubectl edit` change keeps getting reverted | `selfHeal: true` is working exactly as designed (section 1.2) — that's the point of GitOps | Make the change in Git instead, and let the controller apply it |
| Rolled back via the ArgoCD UI/CLI, but the "bad" version came right back shortly after | Classic drift trap (Day 20 Exercise 4): `selfHeal` re-applied Git's still-newer content over your out-of-band rollback | Always prefer `git revert` + push over ArgoCD's own rollback feature when `selfHeal` is enabled |

See also: [Debugging Common Kubernetes Issues](../TROUBLESHOOTING.md).

## 3. Key commands reference

| Command | Purpose |
|---|---|
| `kubectl get application -n argocd` | List ArgoCD Applications and their Sync/Health status |
| `argocd app sync <name>` | Trigger a manual sync (CLI equivalent of the UI's Sync button) |
| `argocd app diff <name>` | Show what would change before syncing |
| `kubectl get gitrepository,helmrelease -n flux-system` | List Flux sources and releases, and their Ready status |
| `flux get sources git` / `flux get helmreleases` | Flux CLI equivalents with reconciliation detail |
| `flux reconcile source git <name>` | Force an immediate re-poll, without waiting for the interval |

Next: [Day 21 — Autoscaling & Advanced Rollouts](../day21-autoscaling-and-rollouts/README.md)
