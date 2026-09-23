---
---
# Day 18 — Observability: Metrics, Traces & Logging (Node-Agent, Sidecar & ELK/EFK)

> **Resource & time note:** this is the heaviest day in the course. It installs Prometheus, Grafana, Elasticsearch, Kibana, Filebeat, Fluent Bit, Fluentd, and Jaeger across five sequential parts, each with its own teardown before the next begins. **Bump your lab VM to at least 4 vCPU / 8GB RAM for today** (see Day 2's environment options if you need to resize a Multipass/cloud VM) — the values files here are already trimmed as far as reasonably possible, but Elasticsearch alone wants ~1.5GB comfortably. Budget **3-4 hours**, and it's entirely reasonable to split this across two sessions at the Part boundaries below. Do the teardown step at the end of each Part before starting the next — running everything at once will not fit even on 8GB.

## Learning objectives
- Explain the three pillars of observability: metrics, logs, and traces — and get hands-on with all three, not just metrics
- Use the built-in metrics pipeline (`metrics-server`, `kubectl top`) that powers autoscaling (Day 21)
- Install and query Prometheus, and build a dashboard in Grafana
- Understand and compare the **two architectural patterns for log collection**: node-level DaemonSet agents vs. per-Pod **sidecars** — and build both
- Install a real ELK/EFK stack (Elasticsearch + Kibana + Filebeat) and compare it directly against Loki
- Deploy **Fluent Bit** and **Fluentd** as logging sidecars, following Day 3's sidecar pattern for real, and compare their resource footprint and configuration style
- Install Jaeger and view a real distributed trace across two services, instrumented with zero application code changes via OpenTelemetry auto-instrumentation

## 1. Concepts

### 1.1 The three pillars

- **Metrics** — numeric time-series (CPU %, request count, queue depth). Cheap to store at high volume and long retention; great for dashboards, alerting thresholds, and autoscaling decisions. Today's tool: [Prometheus](https://prometheus.io/).
- **Logs** — discrete, timestamped text/structured events. Richer detail per event than a metric, but far more expensive to store/query at scale. Today's tools: [Loki](https://grafana.com/oss/loki/), the [ELK/EFK stack](https://www.elastic.co/what-is/elk-stack), [Fluent Bit](https://fluentbit.io/) and [Fluentd](https://www.fluentd.org/).
- **Traces** — the path a single request takes across multiple services, with per-hop timing. Essential in microservice architectures for finding *which* service in a call chain is slow. Today's tool: [Jaeger](https://www.jaegertracing.io/), fed by [OpenTelemetry](https://opentelemetry.io/) instrumentation.

### 1.2 Why Pod-level metrics need a separate pipeline

Recall Day 10: `requests`/`limits` are static numbers you write in YAML. **Actual, live resource *usage*** is a different thing entirely, and Kubernetes doesn't track it by default. [**metrics-server**](https://kubernetes.io/docs/tasks/debug/debug-cluster/resource-metrics-pipeline/) is a lightweight, cluster-wide component that periodically scrapes real-time CPU/memory usage from every kubelet (which itself gets it from cAdvisor) and exposes it through the **Metrics API** — this is exactly what powers `kubectl top` and the **Horizontal Pod Autoscaler** (Day 21). k3s bundles metrics-server by default — nothing to install for this part.

### 1.3 Prometheus's model: pull, not push

Prometheus **scrapes** (pulls) metrics from targets on an interval, rather than applications pushing metrics to it. Applications expose a `/metrics` HTTP endpoint; the [Prometheus Operator](https://prometheus-operator.dev/) (installed by `kube-prometheus-stack`) manages *what* to scrape via `ServiceMonitor`/`PodMonitor` CRDs (Day 22's CRD lesson, in production use).

**PromQL** essentials:
```promql
container_memory_working_set_bytes{namespace="default"}
rate(container_cpu_usage_seconds_total{namespace="default"}[5m])
sum by (pod) (rate(container_cpu_usage_seconds_total{namespace="default"}[5m]))
```

### 1.4 Grafana — the visualization layer

[Grafana](https://grafana.com/oss/grafana/) doesn't store data itself — it queries data sources (Prometheus for metrics, Loki or Elasticsearch for logs) and renders dashboards. One Grafana instance commonly visualizes multiple backends side by side.

### 1.5 Two architectures for log collection: node-agent vs. sidecar

Recall Day 9: a **DaemonSet** runs exactly one Pod per Node. Applied to logging, that Pod is a **node-level log-shipping agent** — Promtail, Filebeat, or a Fluent Bit DaemonSet — that reads every container's log files directly off that Node's disk (wherever the container runtime writes stdout/stderr) and ships them onward. This is the architecture behind everything in Part 2 and Part 4 below, and it's the right default for the overwhelming majority of applications, because it requires **zero changes to the application or its Pod spec** — the agent lives entirely outside the app's own Pods.

But recall Day 3's **sidecar pattern**: a second container in the *same* Pod, sharing a volume with the main app container. Logging sidecars exist for cases the node-agent pattern handles poorly:

| | Node-agent (DaemonSet) | Sidecar |
|---|---|---|
| Where it runs | One per **Node**, outside any app's Pod | One per **Pod**, alongside that one app |
| App changes needed | None — reads container runtime's own log capture | The app's Pod spec must add the sidecar container + a shared volume |
| Handles apps that log to **stdout** | Yes — this is exactly what it's built for | Overkill — the node-agent already has this |
| Handles apps that log **only to a file** (many legacy/off-the-shelf apps, or apps writing multiple distinct log files) | Awkward — needs `hostPath`-mounting into arbitrary app-chosen paths, fragile | **This is the sidecar's actual reason to exist** — tail the exact file(s) that one app writes, no assumptions about where every app on the Node puts its logs |
| Per-app custom parsing/enrichment before shipping | Shared config across every Pod on the Node | Per-Pod config, tailored exactly to that one app |
| Resource cost | One agent per Node, shared across all Pods on it | One extra container **per Pod**, multiplied across every replica |

Today's lab builds both, on purpose, so the trade-off in that resource-cost row is something you've actually measured (`kubectl top`), not just read about.

### 1.6 Fluent Bit vs. Fluentd

Both are graduated CNCF projects and both can act as either a DaemonSet node-agent *or* a sidecar — they solve the same problem with different design centers:

| | Fluent Bit | Fluentd |
|---|---|---|
| Written in | C | Ruby (with C extensions) |
| Typical memory footprint | ~10-30MB | ~50-150MB+ (higher with many plugins loaded) |
| Plugin ecosystem | Smaller, built-in set (most common outputs included) | Much larger — hundreds of community plugins, but often need to be baked into a custom image (as today's `elasticsearch`-flavored Fluentd image does) |
| Config style | Compact, INI-like (`fluent-bit.conf`) | More expressive Ruby-DSL-like blocks (`fluent.conf`), steeper learning curve |
| Common real-world role | Lightweight collector — DaemonSet **or** sidecar, at the edge, close to the app | Heavier aggregator — often receiving from many Fluent Bit instances centrally, doing complex multi-destination routing/enrichment before final storage |

A very common production topology combines both: **Fluent Bit at the edge (DaemonSet or sidecar) forwarding to a smaller number of central Fluentd aggregators**, which then handle the heavier parsing/routing/fan-out logic — lightweight collection at scale, heavyweight processing concentrated in fewer places. Today's lab runs each standalone as a sidecar so the comparison is direct and isolated.

### 1.7 ELK/EFK — the other major logging stack

[**Elasticsearch**](https://www.elastic.co/elasticsearch) (a distributed search/analytics datastore), [**Logstash**](https://www.elastic.co/logstash) (a heavyweight, highly-flexible log processing pipeline), and [**Kibana**](https://www.elastic.co/kibana) (the visualization/query UI) together form the classic **"ELK" stack**. In Kubernetes specifically, Logstash is very often swapped out for a lighter, Kubernetes-native collector — Filebeat or Fluent Bit — giving the commonly-seen **"EFK"** variant (Elasticsearch + Fluent Bit/Filebeat + Kibana) you're building in Part 4 today. Logstash itself hasn't disappeared — it's still heavily used centrally for complex, multi-source parsing/enrichment pipelines — but for straightforward "collect every container's logs and get them into a searchable store," the lighter shippers have become the default.

**Loki vs. ELK/EFK**, the practical comparison:

| | Loki (Grafana stack) | Elasticsearch (ELK/EFK) |
|---|---|---|
| Indexing | Indexes only **labels** (like Prometheus), log content itself stored compressed, unindexed | Full-text indexes **every field**, including complete log body |
| Query language | LogQL (label-first, `\|=` for text filtering) | Kibana Query Language / full Elasticsearch DSL, powerful ad-hoc full-text search |
| Resource footprint | Deliberately lightweight | Heavier — full-text indexing costs real CPU/memory/disk at any real log volume |
| Best fit | You mostly filter logs *by known labels* (service, pod, namespace) and grep within them | You need arbitrary, ad-hoc full-text search/analytics across huge unstructured log volumes, and can afford the resource cost |

Today's lab installs both in parts 2 and 4, so this table is something you can verify with `kubectl top`, not just take on faith.

### 1.8 Tracing and OpenTelemetry

A **trace** represents one logical request end-to-end; a **span** is one unit of work within it (e.g. "frontend handling the request," "the HTTP call to backend"). Spans are linked into a tree by a shared **trace ID**, propagated between services via the [W3C `traceparent` HTTP header](https://www.w3.org/TR/trace-context/) — this is *how* two completely independent services' spans end up joined into one trace in Jaeger's UI.

[**OpenTelemetry**](https://opentelemetry.io/) is the vendor-neutral standard for producing this data — an API/SDK plus, critically, **auto-instrumentation** agents that patch common libraries (Flask, `requests`, and hundreds of others) at process startup with **no source code changes**, automatically creating spans for incoming/outgoing HTTP calls and propagating the `traceparent` header between them. Today's `trace-frontend`/`trace-backend` apps prove this directly: neither `app.py` imports anything OpenTelemetry-related — the Dockerfiles simply run `opentelemetry-bootstrap -a install` at build time and wrap the start command with `opentelemetry-instrument` at runtime.

### Official documentation
- [Resource Metrics Pipeline (metrics-server)](https://kubernetes.io/docs/tasks/debug/debug-cluster/resource-metrics-pipeline/)
- [Kubernetes Monitoring Architecture](https://kubernetes.io/docs/concepts/cluster-administration/monitoring/)
- [Logging Architecture](https://kubernetes.io/docs/concepts/cluster-administration/logging/)
- [Prometheus documentation](https://prometheus.io/docs/introduction/overview/) / [PromQL basics](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Grafana documentation](https://grafana.com/docs/grafana/latest/)
- [Loki documentation](https://grafana.com/docs/loki/latest/) / [LogQL](https://grafana.com/docs/loki/latest/query/)
- [Elastic Stack (ELK) overview](https://www.elastic.co/what-is/elk-stack)
- [Filebeat: Kubernetes autodiscover](https://www.elastic.co/guide/en/beats/filebeat/current/configuration-autodiscover-hints.html)
- [Fluent Bit documentation](https://docs.fluentbit.io/manual)
- [Fluentd documentation](https://docs.fluentd.org/)
- [Jaeger documentation](https://www.jaegertracing.io/docs/latest/)
- [OpenTelemetry documentation](https://opentelemetry.io/docs/) / [OpenTelemetry Python auto-instrumentation](https://opentelemetry.io/docs/zero-code/python/)
- [W3C Trace Context](https://www.w3.org/TR/trace-context/)
- [kube-prometheus-stack Helm chart](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack)

## 2. Hands-on lab

```bash
cd day18-observability/manifests
kubectl create namespace monitoring
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo add elastic https://helm.elastic.co
helm repo update
```

### Part 1 — Metrics: metrics-server, Prometheus, Grafana

```bash
# 1.1 metrics-server / kubectl top — already available, no install
kubectl top nodes
kubectl top pods -A --sort-by=cpu | head -10

# 1.2 Install kube-prometheus-stack
helm install monitoring prometheus-community/kube-prometheus-stack \
  -n monitoring -f values-kube-prometheus-stack.yaml
kubectl get pods -n monitoring -l release=monitoring -w   # ctrl-c once Running

# 1.3 Reach Grafana and Prometheus
kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80 &
kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-prometheus 9090:9090 &
# Grafana: http://localhost:3000 (admin / zero2hero) — browse Dashboards ->
#   "Kubernetes / Compute Resources / Namespace (Pods)"
# Prometheus: http://localhost:9090/graph — try: sum by (namespace) (rate(container_cpu_usage_seconds_total[5m]))

# 1.4 Teardown before Part 2 (frees ~1GB+ for the logging stacks)
kill %1 %2 2>/dev/null
helm uninstall monitoring -n monitoring
```

### Part 2 — Centralized logging, node-agent pattern: Loki + Promtail

```bash
# 2.1 Generate continuous log volume
kubectl apply -f log-generator.yaml
kubectl logs -n monitoring -l app=log-generator --tail=5

# 2.2 Install Loki + Promtail
helm install loki grafana/loki-stack -n monitoring -f values-loki-stack.yaml
kubectl get pods -n monitoring -l app=promtail -o wide   # one per node
kubectl get pods -n monitoring -l app=loki

# 2.3 Query Loki directly (no Grafana needed to prove it's working)
kubectl port-forward -n monitoring svc/loki 3100:3100 &
curl -s -G "http://localhost:3100/loki/api/v1/query_range" \
  --data-urlencode 'query={app="log-generator"} |= "ERROR"' | head -c 500; echo
kill %1

# 2.4 Prove centralized logging outlives the Pod (Day 9/16's core lesson)
POD=$(kubectl get pod -n monitoring -l app=log-generator -o jsonpath='{.items[0].metadata.name}')
kubectl delete pod -n monitoring $POD
kubectl port-forward -n monitoring svc/loki 3100:3100 &
sleep 2
curl -s -G "http://localhost:3100/loki/api/v1/query_range" \
  --data-urlencode "query={pod=\"$POD\"}" | head -c 300; echo   # still returns results!
kill %1

# 2.5 Teardown before Part 3
helm uninstall loki -n monitoring
```

### Part 3 — Sidecar logging: Fluent Bit and Fluentd

This part needs a real Elasticsearch to ship into — install it now (shared by Part 3 and Part 4):

```bash
# 3.1 Install Elasticsearch + Kibana once, reused by both remaining log parts
helm install es elastic/elasticsearch -n monitoring -f values-elasticsearch.yaml
kubectl get pods -n monitoring -l app=elasticsearch-master -w   # wait for Running (can take a few minutes)
ES_SVC=$(kubectl get svc -n monitoring -l app=elasticsearch-master -o jsonpath='{.items[0].metadata.name}')
echo "Elasticsearch service: $ES_SVC"

helm install kibana elastic/kibana -n monitoring \
  -f values-kibana.yaml --set "elasticsearchHosts=http://${ES_SVC}:9200"
kubectl get pods -n monitoring -l app=kibana -w

# 3.2 Deploy the Fluent Bit sidecar demo (substituting the real ES service name)
sed "s/HOST_PLACEHOLDER/${ES_SVC}/" sidecar-fluentbit-configmap.yaml | kubectl apply -f -
kubectl apply -f sidecar-fluentbit-pod.yaml
kubectl logs -n monitoring sidecar-fluentbit-demo -c app --tail=5        # the app's OWN file-based log lines never hit `kubectl logs` for THIS container...
kubectl exec -n monitoring sidecar-fluentbit-demo -c app -- tail -5 /var/log/app/app.log   # ...they're only ever in the file
kubectl logs -n monitoring sidecar-fluentbit-demo -c fluent-bit --tail=10   # the SIDECAR's own stdout, showing it tailing+shipping

# 3.3 Deploy the Fluentd sidecar demo, same app pattern
sed "s/HOST_PLACEHOLDER/${ES_SVC}/" sidecar-fluentd-configmap.yaml | kubectl apply -f -
kubectl apply -f sidecar-fluentd-pod.yaml
kubectl logs -n monitoring sidecar-fluentd-demo -c fluentd --tail=10

# 3.4 Confirm both sidecars' logs actually landed in Elasticsearch
sleep 15
kubectl exec -n monitoring sidecar-fluentbit-demo -c app -- true   # (just ensure the demo pod is still up)
kubectl run -n monitoring es-query --rm -it --image=curlimages/curl --restart=Never -- \
  curl -s "http://${ES_SVC}:9200/app-sidecar-fluentbit*/_count"
kubectl run -n monitoring es-query --rm -it --image=curlimages/curl --restart=Never -- \
  curl -s "http://${ES_SVC}:9200/app-sidecar-fluentd*/_count"

# 3.5 Compare resource footprint directly — the whole point of section 1.5/1.6's tables
kubectl top pod -n monitoring sidecar-fluentbit-demo --containers
kubectl top pod -n monitoring sidecar-fluentd-demo --containers

# 3.6 View both in Kibana
kubectl port-forward -n monitoring svc/kibana-kibana 5601:5601 &
# http://localhost:5601 -> Stack Management -> Data Views -> create one matching "app-sidecar-*"
# -> Discover -> see log lines from BOTH sidecars, each tagged by their own index
kill %1
kubectl delete pod -n monitoring sidecar-fluentbit-demo sidecar-fluentd-demo
```

### Part 4 — Centralized logging, node-agent pattern again: EFK with Filebeat

```bash
# 4.1 Install Filebeat as a DaemonSet, pointed at the SAME Elasticsearch
helm install filebeat elastic/filebeat -n monitoring -f values-filebeat.yaml \
  --set daemonset.extraEnvs[0].value=${ES_SVC}
kubectl get pods -n monitoring -l app=filebeat-filebeat -o wide   # one per node, just like Promtail was

# 4.2 Confirm it picked up log-generator-style container stdout automatically
#     (redeploy log-generator briefly if you tore it down after Part 2)
kubectl apply -f log-generator.yaml
sleep 20
kubectl run -n monitoring es-query --rm -it --image=curlimages/curl --restart=Never -- \
  curl -s "http://${ES_SVC}:9200/_cat/indices?v"   # a filebeat-* index now exists, growing

# 4.3 Teardown everything from Parts 3 & 4 before moving to Part 5
kubectl delete -f log-generator.yaml
helm uninstall filebeat kibana es -n monitoring
```

### Part 5 — Distributed tracing: Jaeger + OpenTelemetry

```bash
# 5.1 Build and push the two traced apps
cd ../app/trace-backend
docker build -t localhost:5000/trace-backend:1.0.0 .
docker push localhost:5000/trace-backend:1.0.0
cd ../trace-frontend
docker build -t localhost:5000/trace-frontend:1.0.0 .
docker push localhost:5000/trace-frontend:1.0.0
cd ../../manifests

# 5.2 Deploy Jaeger and the traced apps
kubectl apply -f jaeger-allinone.yaml
kubectl apply -f trace-apps.yaml
kubectl wait --for=condition=ready pod -n monitoring -l app=jaeger --timeout=60s
kubectl wait --for=condition=ready pod -n monitoring -l app=trace-backend --timeout=60s
kubectl wait --for=condition=ready pod -n monitoring -l app=trace-frontend --timeout=60s

# 5.3 Generate some traced requests
kubectl port-forward -n monitoring svc/trace-frontend 8080:80 &
for i in $(seq 1 10); do curl -s localhost:8080/; echo; done
kill %1

# 5.4 View a real trace waterfall in the Jaeger UI
kubectl port-forward -n monitoring svc/jaeger 16686:16686 &
# http://localhost:16686 -> Service: trace-frontend -> Find Traces
# open one -> see TWO spans (trace-frontend, trace-backend) joined into
# one trace, with trace-backend's simulated work time visible as its
# span's duration -- context propagation happened with ZERO app code
kill %1

# 5.5 Final teardown
kubectl delete -f jaeger-allinone.yaml -f trace-apps.yaml
kubectl delete namespace monitoring
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `helm install` for any of today's stacks hangs or times out, Pods stuck `Pending` | Ran out of RAM/CPU on the lab VM — this is the heaviest day in the course by design (see the resource note at the top) | Tear down the previous Part fully before starting the next one; confirm with `kubectl top nodes` that you actually have headroom |
| Elasticsearch Pod stuck `Running` but never `Ready` for several minutes | This is normal for Elasticsearch specifically — it can take a few minutes to form its single-node "cluster" and pass its readiness check | Give it up to 5 minutes before assuming it's broken; `kubectl logs -n monitoring -l app=elasticsearch-master` while waiting |
| Grafana/Prometheus/Kibana `port-forward` connection resets or hangs | A previous `port-forward` from an earlier lab step is still running in the background, holding the port | `jobs` in your shell, `kill %N` the stale one, then retry |
| Fluent Bit/Fluentd sidecar's own logs show connection errors to Elasticsearch | Used the placeholder `HOST_PLACEHOLDER` literally instead of substituting the real service name | Re-run the `sed "s/HOST_PLACEHOLDER/${ES_SVC}/"` substitution step exactly as written in the lab |
| Jaeger UI shows no traces at all after generating requests | `OTEL_EXPORTER_OTLP_ENDPOINT` env var missing/wrong on the app Deployments, or the apps were built without `opentelemetry-bootstrap -a install` having run | `kubectl exec <pod> -- env \| grep OTEL`; confirm the Dockerfile's bootstrap step actually ran during build (check build logs) |
| Loki/Kibana query returns nothing even though `kubectl logs` shows output | Wrong label selector in the query, or the shipping agent (Promtail/Filebeat/Fluent Bit) isn't actually running on that Pod's Node | `kubectl get pods -n monitoring -l app=promtail -o wide` (or the Filebeat/Fluent Bit equivalent) — confirm one exists on the right Node |

See also: [Debugging Common Kubernetes Issues](../TROUBLESHOOTING.md).

## 3. Key commands reference

| Command | Purpose |
|---|---|
| `kubectl top nodes` / `kubectl top pods [-A] [--containers]` | Live resource usage via metrics-server — `--containers` breaks it down per-container, essential for comparing sidecar overhead |
| `helm repo add/update`, `helm install <release> <chart> -n <ns> -f values.yaml` | Install a chart (full detail Day 19) |
| `kubectl port-forward -n <ns> svc/<name> <local>:<remote>` | Reach a cluster-internal UI locally |
| PromQL in Prometheus/Grafana Explore | Query metrics |
| LogQL in Grafana Explore (Loki data source) | Query Loki-shipped logs |
| Kibana Discover / KQL | Query Elasticsearch-shipped logs (DaemonSet or sidecar-shipped) |
| Jaeger UI: Service → Find Traces | View a distributed trace's span waterfall |

Next: [Day 19 — Helm](../day19-helm/README.md)
