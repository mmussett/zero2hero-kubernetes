# Day 15 — Exercises

## Exercise 1 — Time the ndots penalty yourself
From `netshoot`, run `dig +stats api.example.com` and note the `Query time`. Now run `dig +stats api.example.com.` (trailing dot). Compare the two — is there a measurable difference in this lab environment? Explain what you'd expect to observe on a cluster with a slow/rate-limited external upstream resolver, even if the difference here is small.

[→ solution](SOLUTIONS.md#exercise-1)

## Exercise 2 — Break CoreDNS on purpose
Scale CoreDNS to 0 replicas: `kubectl scale deployment coredns -n kube-system --replicas=0`. From `netshoot`, try `nslookup hello-k8s-svc` and `curl hello-k8s-svc`. Then try `curl <hello-k8s-svc's ClusterIP directly>` (get it via `kubectl get svc hello-k8s-svc -o jsonpath='{.spec.clusterIP}'` *before* scaling down). What still works and what doesn't? What does this prove about the difference between Service *networking* (kube-proxy) and Service *discovery* (DNS)? Restore CoreDNS: `kubectl scale deployment coredns -n kube-system --replicas=1`.

[→ solution](SOLUTIONS.md#exercise-2)

## Exercise 3 — Headless vs. ClusterIP DNS answers, side by side
Create a headless variant of `hello-k8s-svc` (same selector, `clusterIP: None`) named `hello-k8s-headless`. Run `dig +short hello-k8s-svc.default.svc.cluster.local` and `dig +short hello-k8s-headless.default.svc.cluster.local` back to back. Explain the difference in the number of records returned, tying it back to section 1.3.

[→ solution](SOLUTIONS.md#exercise-3)

## Exercise 4 — Cross-namespace search list gap
Create namespace `other-ns` and deploy `deployment-service.yaml` into it (renaming objects to avoid clashes). From `netshoot` in `default`, try the short name, the `<name>.<namespace>` form, and the fully-qualified form against the service in `other-ns`. Which one(s) succeed, and why — connect your answer to the exact `search` list from section 2.1.

[→ solution](SOLUTIONS.md#exercise-4)

## Exercise 5 — Corefile edit: a custom local hosts entry
Edit the `coredns` ConfigMap in `kube-system` to add a `hosts` block resolving `training.internal` to `10.0.0.99` (see the [CoreDNS hosts plugin docs](https://coredns.io/plugins/hosts/) for exact syntax), inserted into the Corefile's main server block. After saving, you'll need to restart CoreDNS's Pods for the change to take effect (`kubectl rollout restart deployment coredns -n kube-system`) — why doesn't editing a ConfigMap alone suffice here, in contrast to Day 6's mounted-volume live-update behavior? Confirm `dig training.internal` from `netshoot` now returns `10.0.0.99`.

[→ solution](SOLUTIONS.md#exercise-5)

## Exercise 6 (stretch) — dnsPolicy comparison
Compare all four values of `dnsPolicy` by reading `kubectl explain pod.spec.dnsPolicy`: `ClusterFirst` (default), `Default`, `ClusterFirstWithHostNet`, and `None`. Write one sentence each on when you'd choose something other than the default `ClusterFirst`. Then explain specifically why `pod-custom-dnspolicy.yaml` uses `dnsPolicy: "None"` rather than `Default`, referencing what `dnsConfig` requires.

[→ solution](SOLUTIONS.md#exercise-6)
