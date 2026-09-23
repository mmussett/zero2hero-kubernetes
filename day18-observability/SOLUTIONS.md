# Day 18 — Solutions

## Exercise 1
```bash
kubectl top pod -n monitoring -l app=log-generator
kubectl get pod -n monitoring -l app=log-generator -o jsonpath='{.items[0].spec.containers[0].resources}'; echo
# {} — no requests/limits declared at all
```
`kubectl top` reports **live, real-time measured usage** pulled from cAdvisor via metrics-server. `kubectl describe node`'s "Allocated resources" table instead sums each Pod's **declared `requests`** — a purely-YAML-derived scheduling promise that has no obligation to match actual usage. A Pod with generous requests but low real usage, or (as here) tiny/no requests but real measurable usage, are both common — these two numbers are deliberately different questions.

## Exercise 2
```promql
kube_pod_container_status_restarts_total{namespace="monitoring"}
```
```bash
POD=$(kubectl get pod -n monitoring -l app=log-generator -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n monitoring $POD -- sh -c "kill 1"
sleep 35
```
Re-running the query shows the counter incremented by 1 for that pod/container — `kube_pod_container_status_restarts_total` comes from `kube-state-metrics` (installed with `kube-prometheus-stack`), deriving it from the exact same `status.containerStatuses[].restartCount` field `kubectl describe pod` has shown all course, now queryable and graphable over time.

## Exercise 3
In Grafana: **Dashboards → New → Add visualization → Prometheus data source**, paste the query, save.
```bash
POD=$(kubectl get pod -n monitoring -l app=log-generator -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n monitoring $POD -- sh -c "yes > /dev/null &"
```
The panel's line for that Pod climbs toward ~1.0 (100% of one core), then flattens once killed (`kubectl exec -n monitoring $POD -- pkill yes`).

## Exercise 4
```logql
(a) {app="log-generator"} |= "ERROR"
(b) sum(count_over_time({app="log-generator"} |= "WARN" [1m]))
(c) {pod="log-generator-<actual-suffix>"}
```
(a) filters raw text; (b) wraps a filtered stream in `count_over_time`+`sum()` to turn matching lines into a numeric rate; (c) swaps the label selector from the Deployment-wide `app` label to the Kubernetes-assigned `pod` label to scope to one replica.

## Exercise 5
```bash
kubectl get pods -n monitoring -l app=log-generator -o jsonpath='{.items[*].metadata.name}'; echo
OLD_POD=<one of the names printed above>
kubectl set env deployment/log-generator -n monitoring DUMMY=1
kubectl get pods -n monitoring -l app=log-generator -w
kubectl logs -n monitoring $OLD_POD
# Error from server (NotFound)
```
Loki's Explore view with `{pod="$OLD_POD"}` still returns every line that Pod ever emitted. This demonstrates centralized logging's entire point: `kubectl logs` is tied to a **live** Pod object on that Node's disk, gone the moment the Pod is deleted; a shipping agent decouples log *retention* from Pod *lifetime* — essential for investigating anything even minutes after the Pod involved is gone.

## Exercise 6
```bash
kubectl exec -n monitoring sidecar-fluentbit-demo -c app -- sh -c "kill 1"
kubectl get pod -n monitoring sidecar-fluentbit-demo -w
kubectl logs -n monitoring sidecar-fluentbit-demo -c fluent-bit --tail=10
```
Only the `app` container restarts — `kubectl get pod` shows the Pod stays `Running` throughout, with the `app` container's own restart count climbing while `fluent-bit`'s stays at 0. Fluent Bit's own logs show no error at all during this — it was simply tailing a file that briefly stopped growing, then resumed the moment the restarted `app` container started appending to it again (the file itself, on the shared `emptyDir`, was never deleted or truncated by the container restart). This is Day 3's "container restart is scoped to one container, not the whole Pod" lesson, now proven with a real logging sidecar: the sidecar's operation is completely decoupled from the app container's crash/restart cycle, precisely because they only interact through the shared volume, never through each other's process directly.

## Exercise 7
```bash
kubectl top pod -n monitoring sidecar-fluentbit-demo --containers
kubectl top pod -n monitoring sidecar-fluentd-demo --containers
```
Typical result: the `app` container's usage is nearly identical in both Pods (a few millicores, a few MB — it's the same busybox loop either way). The `fluent-bit` sidecar typically shows single-digit-to-low-tens of MB memory and low CPU; the `fluentd` sidecar typically shows noticeably higher memory (often 3-5x Fluent Bit's, consistent with running on a Ruby interpreter with a bundled Elasticsearch output plugin loaded) even doing the identical job. This matches section 1.6's stated ranges directly and is the concrete, measured version of "Fluent Bit is lighter-weight" rather than just an assertion to take on faith.

## Exercise 8
```
LogQL:    {app="log-generator"} |= "ERROR"
Kibana:   level: "ERROR"   (KQL, against the indexed "level" field)
          -- or, free-text without knowing any field name at all:
          "ERROR"          (matches the word ERROR anywhere in the full-text-indexed log body)
```
The LogQL query requires you to already know `app="log-generator"` is a valid **label** on the stream (Loki indexes only labels, so you must scope by one to run any query at all) — it then does a plain substring match on the raw log line for `"ERROR"`. The Kibana/Elasticsearch free-text query can search `"ERROR"` across the **entire indexed document** with no prior knowledge of field names or which service produced it, because Elasticsearch full-text-indexes the complete log body, not just labels — directly illustrating section 1.7's core trade-off: Loki demands you know your labels upfront in exchange for a far lighter resource footprint; Elasticsearch lets you search blind across everything, at a real, measured resource cost (Exercise 7-style comparisons on the Elasticsearch Pod itself would show this clearly too).

## Exercise 9
```python
# trace-frontend/app.py, replacing the requests.get call:
import urllib.request
def index():
    with urllib.request.urlopen(f"{BACKEND_URL}/", timeout=5) as resp:
        import json
        data = json.load(resp)
    return jsonify({"service": "trace-frontend", "backend_response": data})
```
```bash
docker build -t localhost:5000/trace-frontend:1.0.1 app/trace-frontend/
docker push localhost:5000/trace-frontend:1.0.1
kubectl set image deployment/trace-frontend -n monitoring trace-frontend=localhost:5000/trace-frontend:1.0.1
curl localhost:8080/   # (via port-forward, as in the lab)
```
In the Jaeger UI, you now see **two separate, unlinked single-span traces** — one for `trace-frontend`'s incoming request, one for `trace-backend`'s incoming request — instead of one joined two-span trace. This proves auto-instrumentation's real boundary: OpenTelemetry's zero-code approach works by patching **specific, known libraries** (here, the `requests` package) to inject/read the `traceparent` header automatically — `urllib` used directly has no such patching applied by the standard auto-instrumentation bundle, so no context is propagated, and `trace-backend` starts a brand-new, disconnected trace of its own. In practice, this is exactly the failure mode that shows up as "my traces mysteriously stop being connected across this one specific call" in real systems using an uncommon HTTP client or a hand-rolled network call.

## Exercise 10
```python
# trace-backend/app.py
work_ms = random.randint(20, 2000)
```
After rebuilding/pushing/redeploying and generating 20+ requests, sorting Jaeger's trace list by duration surfaces the outlier trace(s) immediately, and opening one shows the `trace-backend` span's bar visually dominating the waterfall — its duration is close to the total trace duration, with `trace-frontend`'s own span only adding a small fixed overhead around it. In a real multi-service outage with dozens of services in a call chain, this exact workflow — sort by duration, open the slowest trace, read which span's bar is largest — replaces manually guessing which of N services to start investigating, turning "something somewhere is slow" into "service X, specifically this one operation, is slow" in under a minute.

## Exercise 11
```bash
kubectl top pods -n monitoring --sort-by=memory
kubectl top pods -n monitoring --sort-by=cpu
```
Whichever stack is currently running: Elasticsearch (Part 3/4) is typically the single heaviest component by memory, often by a wide margin, since it reserves a fixed JVM heap (`esJavaOpts`) up front regardless of actual log volume; Prometheus (Part 1) is usually the heaviest by memory when that stack is up instead, since it holds the active metrics time-series database in-process. The core trade-off: **every additional metric, trace, or log line you capture costs real CPU/memory/disk, permanently, on every environment it runs in** — observability is not free, and at high enough log/metric/trace volume the observability stack's own footprint can rival or exceed the workloads it's observing. This is exactly why teams commonly run a deliberately lighter setup in dev/staging — short retention, no HA, Loki over Elasticsearch, sampling traces rather than capturing every single one — reserving full-featured, highly-available, long-retention observability (metrics AND logs AND traces) for production, where the cost of *not* having deep observability during a real incident far outweighs the infrastructure bill.
