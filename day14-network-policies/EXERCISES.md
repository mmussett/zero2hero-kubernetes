# Day 14 — Exercises

## Exercise 1 — Write the minimal NetworkPolicy from scratch
Without looking at `netpol-default-deny-ingress.yaml`, write a NetworkPolicy named `scratch-deny` that denies all ingress to every Pod in the namespace, using an empty `podSelector: {}`. Apply it and confirm with `kubectl describe networkpolicy scratch-deny` that it shows no allowed sources at all. Delete it afterward.

[→ solution](SOLUTIONS.md#exercise-1)

## Exercise 2 — Complete the egress lockdown
Continuing from the end of section 2.5 (DNS works, but `frontend-client -> backend-svc` traffic is still blocked by `default-deny-egress`), write and apply a NetworkPolicy `allow-frontend-egress-to-backend` that permits Pods labeled `role: frontend` to egress to Pods labeled `role: backend` on port `8080`. Confirm `frontend-client`'s `curl` to `backend-svc` now succeeds end-to-end with all four policies in place simultaneously.

[→ solution](SOLUTIONS.md#exercise-2)

## Exercise 3 — Namespace-scoped isolation
Create a namespace `team-beta`, deploy a copy of `backend.yaml` into it (rename the Deployment/Service if you like), and apply an identical `default-deny-ingress` there. Write a NetworkPolicy that allows ingress **only** from Pods in the `default` namespace with label `role: frontend` (hint: combine `namespaceSelector` matching a label on the `default` namespace itself — you'll need to label the `default` namespace first — with `podSelector` in the *same* `from` entry). Test from `frontend-client` in `default` against the new backend in `team-beta`.

[→ solution](SOLUTIONS.md#exercise-3)

## Exercise 4 — OR vs. AND selector combination
Write two variants of the same policy: **(a)** a single `from` entry containing both a `podSelector` and `namespaceSelector` (AND), and **(b)** two separate entries in the `from` list, one with each selector (OR). Using `kubectl describe networkpolicy`, explain in your own words, referencing the actual YAML structure, why these produce different effective permission sets, and construct a concrete scenario (which Pods, which namespaces) where the two variants would allow different traffic.

[→ solution](SOLUTIONS.md#exercise-4)

## Exercise 5 — Policy with no effect (unmatched selector)
Apply a NetworkPolicy with `podSelector: matchLabels: {role: nonexistent}` and an ingress rule allowing traffic from anywhere. Confirm via `kubectl exec` testing that `backend` Pods are completely unaffected by it. Explain why — tie your answer back to section 1.2's "a Pod is unaffected until at least one policy's `podSelector` matches it."

[→ solution](SOLUTIONS.md#exercise-5)

## Exercise 6 — ipBlock for external traffic
Apply a default-deny-egress policy to `rogue-client` specifically (`podSelector: matchLabels: {role: rogue}`), then add an `egress` rule with an `ipBlock` allowing only `1.1.1.1/32` on port 443. From `rogue-client`, confirm `curl -m 3 -s -o /dev/null -w "%{http_code}\n" https://1.1.1.1/` succeeds while `curl -m 3 -s -o /dev/null -w "%{http_code}\n" https://8.8.8.8/` times out. What real-world use case does restricting a Pod's egress to a specific external IP range serve?

[→ solution](SOLUTIONS.md#exercise-6)

## Exercise 7 (stretch) — Diagnose "it doesn't work" without describe
Without running `kubectl describe networkpolicy` or reading any YAML, use only `kubectl exec ... curl` reachability tests between various labeled Pods to reverse-engineer and write down what you believe `allow-frontend-to-backend.yaml`'s rule actually allows (source labels, destination labels, port). Then check your answer against the actual file. This is exactly the skill you need when debugging an unfamiliar cluster's existing policies during an incident.

[→ solution](SOLUTIONS.md#exercise-7)
