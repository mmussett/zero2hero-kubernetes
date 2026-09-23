# Day 18 — Exercises

Each exercise names which Part of the lab it depends on — do it before that Part's teardown step, or reinstall just that piece if you've already moved on.

## Exercise 1 (Part 1) — kubectl top vs. requests
Deploy `log-generator.yaml` (`-n monitoring`). Compare `kubectl top pod -n monitoring -l app=log-generator` (actual usage) against `kubectl get pod -n monitoring -l app=log-generator -o jsonpath='{.items[0].spec.containers[0].resources}'` (declared requests/limits — note `log-generator.yaml` sets none). Explain in one sentence why `kubectl top` and `kubectl describe node`'s "Allocated resources" table can show very different numbers for the same Pod.

[→ solution](SOLUTIONS.md#exercise-1)

## Exercise 2 (Part 1) — Write a PromQL query for restart counts
Using Prometheus's UI (`http://localhost:9090/graph`), find and run a query using the metric `kube_pod_container_status_restarts_total` to show restart counts by pod in the `monitoring` namespace. Force a restart of a Pod (e.g. `kubectl exec -n monitoring <pod> -- sh -c "kill 1"` on a Pod with `restartPolicy: Always`) and confirm the metric updates within Prometheus's scrape interval (usually 30s).

[→ solution](SOLUTIONS.md#exercise-2)

## Exercise 3 (Part 1) — Build a Grafana panel from scratch
In Grafana, create a new Dashboard with one Panel showing `sum(rate(container_cpu_usage_seconds_total{namespace="monitoring"}[5m])) by (pod)` as a time series. Generate some CPU load (`kubectl exec -n monitoring <log-generator-pod> -- sh -c "yes > /dev/null &"` briefly) and watch the panel update. Kill the `yes` process afterward.

[→ solution](SOLUTIONS.md#exercise-3)

## Exercise 4 (Part 2) — LogQL filtering practice
Using Grafana's Explore view against the Loki data source (or `curl` against Loki's HTTP API as in the lab), write LogQL queries to: (a) show only `ERROR`-level lines from `log-generator`, (b) count the rate of `WARN` lines over a 1-minute window using `count_over_time`, and (c) show log lines from a *specific* Pod name rather than the whole Deployment. Record all three queries.

[→ solution](SOLUTIONS.md#exercise-4)

## Exercise 5 (Part 2) — Prove log survival after a rolling update
Note the current `log-generator` Pod names. Trigger a rolling update (`kubectl set env deployment/log-generator -n monitoring DUMMY=1`). After the old Pods are gone, try `kubectl logs -n monitoring <old-pod-name>` (fails) versus querying that exact old Pod name in Loki via `{pod="<old-pod-name>"}` (still returns results). What does this demonstrate about log retention design?

[→ solution](SOLUTIONS.md#exercise-5)

## Exercise 6 (Part 3) — Kill the app container, not the sidecar
With `sidecar-fluentbit-demo` running, run `kubectl exec -n monitoring sidecar-fluentbit-demo -c app -- sh -c "kill 1"`. Watch `kubectl get pod -n monitoring sidecar-fluentbit-demo` — does the whole Pod restart, or just the `app` container? Check the Fluent Bit sidecar's own logs during this — does it error, or does it just pick back up once the app container restarts and resumes writing to the same file? What does this prove about container-level vs. Pod-level restart scope (recall Day 3)?

[→ solution](SOLUTIONS.md#exercise-6)

## Exercise 7 (Part 3) — Measure the sidecar cost, don't just read the table
Run `kubectl top pod -n monitoring sidecar-fluentbit-demo --containers` and `kubectl top pod -n monitoring sidecar-fluentd-demo --containers` back to back, at least 60 seconds after both Pods started (to let usage stabilize). Record the `app` container's usage (should be nearly identical in both, since it's the same busybox loop) and each sidecar's usage separately. By how much does memory usage differ between the Fluent Bit and Fluentd sidecar containers? Does this match section 1.6's stated typical footprint ranges?

[→ solution](SOLUTIONS.md#exercise-7)

## Exercise 8 (Part 3/4) — Query the same data two ways
With both Elasticsearch (Part 3/4) and, if you haven't torn it down yet, Loki (Part 2) available, write the *conceptually equivalent* query in both LogQL and Kibana/Elasticsearch query syntax for "every ERROR-level log line from the last 5 minutes." Which one required you to already know a label name in advance, and which one could search free-text without any prior schema knowledge? Tie your answer back to section 1.7's indexing comparison.

[→ solution](SOLUTIONS.md#exercise-8)

## Exercise 9 (Part 5) — Break trace context propagation on purpose
Edit `trace-frontend`'s `app.py` to call `trace-backend` using Python's raw `urllib` instead of `requests` (auto-instrumentation only patches libraries it knows about — `urllib` calls made this way, without going through an instrumented client, won't get a `traceparent` header injected the same way, depending on your OpenTelemetry distro's coverage). Rebuild, push, redeploy, generate a request, and check Jaeger: do you still get ONE joined trace, or two separate, unlinked traces (one per service)? Explain what this proves about auto-instrumentation's real limitation — it only covers libraries it has explicit instrumentation packages for.

[→ solution](SOLUTIONS.md#exercise-9)

## Exercise 10 (Part 5) — Find the slow span
Modify `trace-backend`'s `app.py` to widen its simulated work range to `random.randint(20, 2000)` (up to 2 full seconds), rebuild, push, and redeploy. Generate 20+ requests through `trace-frontend`. In the Jaeger UI, sort/filter traces by duration and find the slowest one. Confirm the backend span's duration accounts for nearly all of the total trace duration. In a real multi-service outage, explain how this exact workflow (find the slow trace, find which span dominates its duration) replaces having to guess which service to investigate first.

[→ solution](SOLUTIONS.md#exercise-10)

## Exercise 11 (stretch) — Resource cost of the observability stack itself
During whichever Part is currently running, run `kubectl top pods -n monitoring --sort-by=memory` and `--sort-by=cpu`. Identify the single heaviest component. Given that this whole stack exists to observe your *other* workloads, discuss in a few sentences the real-world trade-off between observability depth and the resource/cost overhead of running that observability stack itself — and why teams often run a lighter-weight setup (like today's trimmed values files, and Loki over ELK) in dev/staging while running full-featured, highly-available monitoring/logging/tracing only in production.

[→ solution](SOLUTIONS.md#exercise-11)
