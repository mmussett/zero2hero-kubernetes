---
---
# Day 5 — Exercises

## Exercise 1 — Write the minimal Service from scratch
Without looking at `service-minimal.yaml`, write a Service manifest named `scratch-svc` that routes to Pods labeled `app: scratch-svc` on port `80`, forwarding to container port `8080` — and don't write a `type:` field at all. Apply it, then run `kubectl get svc scratch-svc` and confirm the `TYPE` column says `ClusterIP` anyway. Delete it afterward.

[→ solution](SOLUTIONS.md#exercise-1)

## Exercise 2 — Selector mismatch
Create a copy of `service-clusterip.yaml` named `service-broken.yaml` with `selector: {app: wrong-label}`. Apply it, then run `kubectl get endpoints service-broken` and `kubectl describe svc service-broken`. What do you see in the endpoints, and what would a client experience trying to connect?

[→ solution](SOLUTIONS.md#exercise-2)

## Exercise 3 — Cross-namespace DNS
Create namespace `other`. Deploy `deployment.yaml` and `service-clusterip.yaml` into it (`kubectl apply -f deployment.yaml -n other` etc. — rename the Service so it doesn't clash, e.g. `hello-k8s-other`). From the `netshoot` Pod in the `default` namespace, `curl` the fully-qualified name `hello-k8s-other.other.svc.cluster.local`. Then try just `hello-k8s-other` (short name) — does it resolve? Explain why, referencing DNS search domains.

[→ solution](SOLUTIONS.md#exercise-3)

## Exercise 4 — NodePort range boundaries
Try to apply a NodePort Service with `nodePort: 25000` (outside the default 30000-32767 range). Record the exact error. Then look up (`kubectl explain` or the docs) how a cluster admin could widen that range.

[→ solution](SOLUTIONS.md#exercise-4)

## Exercise 5 — Headless Service preview
Create a Service identical to `service-clusterip.yaml` but with `clusterIP: None` (a "headless" Service). Apply it, then `kubectl exec netshoot -- nslookup <that-service-name>`. Compare the result to the normal ClusterIP Service's DNS answer. What's fundamentally different about what DNS returns, and which future topic (hint: Day 8) does this preview?

[→ solution](SOLUTIONS.md#exercise-5)

## Exercise 6 (stretch) — Session affinity
Add `sessionAffinity: ClientIP` to a copy of `service-clusterip.yaml`. Apply it, then run the same repeated `curl` loop from section 2.2 of the lab from the *same* client Pod. What changes about which backend Pod handles each request, and why might a stateful legacy app need this even though it fights against even load distribution?

[→ solution](SOLUTIONS.md#exercise-6)

## Exercise 7 — port-forward vs. NodePort, side by side
Deploy `hello-k8s-clusterip` (a `ClusterIP`-only Service — no `NodePort`, no `LoadBalancer`). Using `kubectl port-forward svc/hello-k8s-clusterip 9090:80`, `curl localhost:9090/` from your own shell and confirm it works — this Service was never given any external-facing type at all. Now, while the port-forward is still running in one terminal, kill the Deployment's Pods one at a time (`kubectl delete pod <pod-name>`) and watch what happens to the port-forward tunnel versus what happens if you immediately re-run the same `curl`. Does the tunnel survive a Pod restart automatically? Contrast this with `service-nodeport.yaml` from section 2.5 — which one keeps working with zero manual intervention when a Pod restarts, and why (tie your answer to §1.5's "port-forward picks one Pod and stays with it" point).

[→ solution](SOLUTIONS.md#exercise-7)
