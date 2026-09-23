# Day 19 — Helm: Templating, Packaging & Release Management

You used Helm as a black box yesterday to install Prometheus and Loki. Today you learn what actually happened, and build your own chart.

## Learning objectives
- Explain what problem Helm solves beyond plain `kubectl apply -f`
- Understand a chart's structure: `Chart.yaml`, `values.yaml`, `templates/`
- Use Go templating, `values.yaml` overrides, and built-in objects (`.Release`, `.Chart`, `.Values`)
- Install, upgrade, roll back, and uninstall a release
- Use `helm template`/`--dry-run` to debug rendering before anything touches the cluster

## 1. Concepts

### 1.1 What Helm adds on top of raw manifests

Every earlier day in this course used `kubectl apply -f some-directory/`. That works, but breaks down at real-world scale:
- **No templating** — deploying the "same app" to dev/staging/prod with different replica counts, image tags, or resource limits means either hand-maintaining near-duplicate YAML files, or building your own templating from scratch.
- **No release tracking** — `kubectl` has no built-in concept of "this set of 15 objects together constitute one versioned application install" — no easy rollback of the *whole bundle* to how it looked before your last change (recall Day 4's rollback was per-Deployment, not per-application).
- **No dependency management** — installing something like `kube-prometheus-stack` (Day 18) by hand means manually authoring dozens of correctly-ordered, correctly-parameterized manifests yourself.

[**Helm**](https://helm.sh/) is Kubernetes's de-facto package manager, solving all three: a **chart** is a templated bundle of manifests plus metadata; a **release** is one named, versioned instance of a chart installed into a cluster; `helm upgrade`/`helm rollback` manage a release's full history as one unit, the same way Day 4's Deployment rollback worked for a single workload.

### 1.2 [Chart anatomy](https://helm.sh/docs/topics/charts/#the-chart-file-structure)

```
hello-chart/
├── Chart.yaml         # name, version, appVersion — chart metadata
├── values.yaml         # DEFAULT configuration values, overridable at install time
├── .helmignore          # like .dockerignore/.gitignore, for `helm package`
└── templates/
    ├── _helpers.tpl      # reusable named template snippets (helper functions)
    ├── deployment.yaml    # a normal Kubernetes manifest, with {{ }} template expressions
    ├── service.yaml
    ├── ingress.yaml        # wrapped in {{- if .Values.ingress.enabled }} — conditionally rendered
    ├── hpa.yaml
    └── NOTES.txt             # printed to the user after install/upgrade
```

Every file under `templates/` is processed through [Go's `text/template`](https://pkg.go.dev/text/template) engine (plus the [Sprig](http://masterminds.github.io/sprig/) function library Helm adds) **before** being sent to the API server — `helm template`/`helm install` render pure YAML at the end; the API server never sees a single `{{ }}` expression.

### 1.3 Key templating concepts

- [**Built-in objects**](https://helm.sh/docs/chart_template_guide/builtin_objects/): `.Values` (everything from `values.yaml`, overridable), `.Release` (`.Release.Name`, `.Release.Namespace`, `.Release.IsUpgrade`), `.Chart` (`.Chart.Name`, `.Chart.Version`, `.Chart.AppVersion`).
- [**Named templates**](https://helm.sh/docs/chart_template_guide/named_templates/) (`_helpers.tpl`): reusable snippets defined once with `{{- define "name" -}}...{{- end }}` and invoked elsewhere with `{{ include "name" . }}` — this course's chart uses one to generate a consistent, collision-avoiding resource name and a shared label block, so every template doesn't repeat that logic.
- **Conditionals**: `{{- if .Values.ingress.enabled }} ... {{- end }}` — entire resources (like `ingress.yaml`/`hpa.yaml` in this chart) can be included or omitted based on a value, avoiding maintaining two nearly-identical chart variants.
- **`toYaml` / `nindent`**: `{{- toYaml .Values.resources | nindent 12 }}` dumps an arbitrary nested value from `values.yaml` (like the whole `resources` block) directly into the template at the correct indentation — far cleaner than hand-templating every nested field individually.

### 1.4 Value layering — later sources win

```
chart's values.yaml (defaults)
        │  overridden by
        ▼
-f custom-values.yaml (one or more, applied left to right)
        │  overridden by
        ▼
--set key=value (highest precedence, applied last)
```

This layering is exactly why `values-prod.yaml` in this lab only needs to list the handful of keys that differ from the chart's defaults — every key it doesn't mention falls through to `values.yaml` unchanged.

### 1.5 Releases: install, upgrade, rollback — familiar from Day 4

`helm install` creates a named release and stores its exact rendered manifest + values as a Secret in-cluster (this is *how* Helm tracks history — nothing external). `helm upgrade` re-renders with new values/chart version and applies the diff, recording a new revision. `helm rollback <release> <revision>` reverts to any prior revision's exact rendered state — the whole-application analogue of Day 4's `kubectl rollout undo`.

### Official documentation
- [Helm documentation](https://helm.sh/docs/)
- [Chart Template Guide](https://helm.sh/docs/chart_template_guide/getting_started/)
- [Built-in Objects](https://helm.sh/docs/chart_template_guide/builtin_objects/)
- [Values Files](https://helm.sh/docs/chart_template_guide/values_files/)
- [Named Templates](https://helm.sh/docs/chart_template_guide/named_templates/)
- [Helm Commands Reference](https://helm.sh/docs/helm/helm/)
- [Sprig Function Documentation](http://masterminds.github.io/sprig/)
- [Artifact Hub (public chart registry)](https://artifacthub.io/)

## 2. Hands-on lab

```bash
cd day19-helm/chart

# 2.1 Render locally first — no cluster interaction at all
helm template hello-chart/ | less
helm template hello-chart/ --set replicaCount=5 --set greeting="Overridden!" | grep -A2 GREETING

# 2.2 Lint and dry-run against the real API server (validates, doesn't persist)
helm lint hello-chart/
helm install hello-release hello-chart/ --dry-run --debug | head -40

# 2.3 Real install
helm install hello-release hello-chart/
helm list
kubectl get deployment,svc -l app.kubernetes.io/instance=hello-release
kubectl port-forward svc/hello-release-hello-chart 8080:80 &
curl localhost:8080/
kill %1

# 2.4 Upgrade with different values
helm upgrade hello-release hello-chart/ --set replicaCount=4 --set greeting="Upgraded!"
kubectl get pods -l app.kubernetes.io/instance=hello-release
helm history hello-release

# 2.5 Use a values file for a whole environment's worth of overrides
helm upgrade hello-release hello-chart/ -f values-prod.yaml
kubectl get deployment hello-release-hello-chart -o jsonpath='{.spec.replicas}'; echo   # 4, per values-prod.yaml

# 2.6 Roll back
helm rollback hello-release 1
helm history hello-release
kubectl get deployment hello-release-hello-chart -o jsonpath='{.spec.replicas}'; echo   # back to values.yaml's default: 2

# 2.7 Inspect what Helm actually stores for release tracking
kubectl get secrets -l owner=helm

# 2.8 Uninstall
helm uninstall hello-release
kubectl get all -l app.kubernetes.io/instance=hello-release   # nothing left
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `helm install` fails with `rendered manifests contain a resource that already exists` | Another release (or a plain `kubectl apply`) already created an object with the identical name, and Helm doesn't own it | Use unique names per release (the `fullname` helper pattern), or `kubectl delete` the conflicting object if it's genuinely orphaned |
| A value change via `--set` seems to do nothing | Typo'd the path (case-sensitive, and Helm silently renders a missing key as empty rather than erroring — Day 19 Exercise 2) | `helm template` with the same `--set`/`-f` and grep the rendered output for the field you expect to see |
| `helm upgrade` succeeds, but nothing in the cluster actually changed | Rendered output was byte-identical to before (a no-op change), or you upgraded the wrong release/namespace | `helm get manifest <release>` before and after to diff directly |
| Release stuck in `pending-install` or `pending-upgrade` | A previous install/upgrade was interrupted mid-flight (network blip, Ctrl-C) | `helm rollback <release> <last-good-revision>`, or `helm uninstall` and reinstall cleanly if there's no good revision to return to |
| `helm template`/`helm install` errors on a Kubernetes API field that doesn't exist | Chart written against a different Kubernetes API version than your cluster runs (e.g. an old `apiVersion` for `Ingress`) | Check `kubectl api-versions` against what the chart's templates expect; update the template's `apiVersion` if needed |

See also: [Debugging Common Kubernetes Issues](../TROUBLESHOOTING.md).

## 3. Key commands reference

| Command | Purpose |
|---|---|
| `helm template <chart>` | Render locally, no cluster contact — your first debugging step, always |
| `helm lint <chart>` | Static-check a chart for common mistakes |
| `helm install <release> <chart> [-f values.yaml] [--set k=v]` | Install |
| `helm upgrade <release> <chart> [...]` | Update an existing release |
| `helm upgrade --install <release> <chart>` | Install if absent, upgrade if present — the common CI/CD idiom |
| `helm rollback <release> <revision>` | Revert to a prior revision |
| `helm history <release>` | List revisions |
| `helm list [-A]` | List installed releases |
| `helm uninstall <release>` | Remove a release and everything it created |

Next: [Day 20 — GitOps with ArgoCD & Flux](../day20-gitops-with-argocd-and-flux/README.md)
