# Day 19 — Solutions

## Exercise 1
```yaml
# values.yaml addition
replicaMinReadySeconds: 0
```
```yaml
# deployment.yaml addition, under spec:
spec:
  minReadySeconds: {{ .Values.replicaMinReadySeconds }}
  {{- if not .Values.autoscaling.enabled }}
  replicas: {{ .Values.replicaCount }}
  {{- end }}
```
```bash
helm template hello-chart/ --set replicaMinReadySeconds=10 | grep minReadySeconds
helm upgrade hello-release hello-chart/ --set replicaMinReadySeconds=10
kubectl get deployment hello-release-hello-chart -o jsonpath='{.spec.minReadySeconds}'; echo   # 10
```

## Exercise 2
```bash
helm template hello-chart/ | grep -A3 "kind: Service"
```
It **renders without erroring** — Go templates silently produce an **empty string** for a reference to a map key that doesn't exist (`.Values.service.Port` vs. the real `.Values.service.port`), so the output YAML ends up with `port: ` and `targetPort: ` (or similar) with no value at all — a schema validation failure only shows up later, when `kubectl apply`/`helm install` actually sends this malformed Service to the API server, which rejects it (`port` is a required integer field). `helm lint` does **not** catch this because linting checks chart *structure and conventions* (required files present, `Chart.yaml` well-formed, some best-practice rules) — it does not execute a full schema validation of every possible rendered output against the Kubernetes API schema, and it definitely doesn't know that `Port` (capital P) isn't a key you meant to reference. This is exactly why `helm template` (or `--dry-run --debug` against a real API server, which *does* validate schema) is a mandatory step before any real install, not just `lint` alone.
```bash
# fix: {{ .Values.service.port }}
```

## Exercise 3
```bash
helm install hello-release-2 hello-chart/ --set ingress.enabled=true --set ingress.host=hello2.zero2hero.local
kubectl get ingress
# only "hello-release-2-hello-chart" listed
echo "127.0.0.1 hello2.zero2hero.local" | sudo tee -a /etc/hosts
curl http://hello2.zero2hero.local/
```
`hello-release` never created an Ingress object at all — the `{{- if .Values.ingress.enabled }}` guard in `templates/ingress.yaml` means that when the value is `false` (the chart default), the **entire file renders as empty output**, and Helm/`kubectl` simply never sees an Ingress resource for that release — this is the standard pattern for optional chart features.

## Exercise 4
```bash
helm get manifest hello-release > /tmp/before.yaml
helm upgrade hello-release hello-chart/ --set greeting="Changed"
helm get manifest hello-release > /tmp/after.yaml
diff /tmp/before.yaml /tmp/after.yaml
```
Diff shows exactly one changed line: the `GREETING` env var's value in the Deployment's rendered manifest. The real `helm-diff` plugin does something more useful *in workflow terms*: it hooks into `helm upgrade` (via `helm diff upgrade`) to show you this **exact same kind of diff BEFORE the upgrade is actually applied**, as a dry-run — the manual approach here only shows you the diff *after* the change already happened (useful for audit/history, but too late to catch a mistake before it ships). This before-vs-after-application distinction is precisely why `helm-diff` is a near-universal addition to real CI/CD pipelines doing automated Helm deployments.

## Exercise 5
```bash
kubectl get all -l app.kubernetes.io/instance=hello-release
kubectl get all -l app.kubernetes.io/instance=hello-release-2
```
Every object name is unique (`hello-release-hello-chart` vs. `hello-release-2-hello-chart`) because `hello-chart.fullname` interpolates `.Release.Name` (which Helm guarantees is unique per release in a namespace) into every generated name. **If `deployment.yaml` had hardcoded the literal string `hello-chart`** as the Deployment's `metadata.name` instead, installing `hello-release-2` would have failed outright with `Error: rendered manifests contain a resource that already exists... Deployment "hello-chart" in namespace "default" exists and cannot be imported`, or worse, silently overwritten/taken ownership of the first release's Deployment depending on exact Helm/Kubernetes version behavior — hardcoded names are precisely why the `fullname` helper pattern is considered mandatory chart-authoring practice, present in virtually every real-world chart (it's literally what `helm create`'s scaffold generates by default).

## Exercise 6
```yaml
version: 0.2.0      # the CHART's own version — bump this for ANY change to the chart itself
                     # (a new template, a values.yaml default change, a bug fix in templating logic)
appVersion: "2.0.0"  # the version of the APPLICATION the chart deploys — purely informational metadata
```
```bash
helm upgrade hello-release hello-chart/    # after bumping version to 0.2.0
helm history hello-release
```
Yes — `helm history` records a new revision even if the rendered manifest content is byte-for-byte identical to before, because Helm tracks revisions per **install/upgrade invocation against this chart**, not per "did the output actually differ" — every `helm upgrade` call is a new tracked event by design, useful for audit trails even when a change was a no-op in practice.

`appVersion` does **not** by itself change which image gets deployed because nothing in this chart's `templates/deployment.yaml` actually references `.Chart.AppVersion` for the image tag — it references `.Values.image.tag` (with `.Chart.AppVersion` only used as a *fallback default* via `| default .Chart.AppVersion`, and only when `image.tag` is completely unset in `values.yaml`, which it isn't here — it's explicitly `"1.0.0"`). `appVersion` is purely a documentation/labeling convention (commonly surfaced by tools like `helm list` and Artifact Hub to tell a human "this chart packages app version X") — the actual deployed behavior is controlled entirely by whatever `values.yaml` (or an override) sets for `image.tag`, completely independently.
