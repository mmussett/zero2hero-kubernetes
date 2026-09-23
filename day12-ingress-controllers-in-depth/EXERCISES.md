# Day 12 — Exercises

## Exercise 1 — Default IngressClass collision
Try setting `controller.ingressClassResource.default: true` in a copy of `values-ingress-nginx.yaml` and upgrade the release (`helm upgrade ingress-nginx ingress-nginx/ingress-nginx -n ingress-nginx -f your-copy.yaml`). Create a new Ingress with **no** `ingressClassName` set at all. Which controller picks it up — Traefik or NGINX? Look up how a cluster resolves "no class specified" when two IngressClasses both claim to be default, and explain why this is a real misconfiguration risk in clusters where multiple teams install controllers independently.

[→ solution](SOLUTIONS.md#exercise-1)

## Exercise 2 — Find an equivalent nginx annotation for a Traefik Middleware
Day 11 used a Traefik `Middleware` with `stripPrefix`. Find the NGINX Ingress Controller's equivalent capability in its [annotations reference](https://kubernetes.github.io/ingress-nginx/user-guide/nginx-configuration/annotations/) and rebuild `ingress-nginx.yaml`'s routing using that mechanism to strip (not just rewrite) a `/hello` prefix, matching Day 11's original path-based routing example. Confirm it behaves identically to Day 11's Traefik version.

[→ solution](SOLUTIONS.md#exercise-2)

## Exercise 3 — Kong plugin reuse across multiple Ingresses
Create a **second** Ingress pointing at `hello-app-svc` under a new host, and attach the **same** `hello-rate-limit` KongPlugin to it via the same `konghq.com/plugins` annotation. Confirm both Ingresses share ONE rate limit bucket or two independent ones (test by exhausting one host's limit and immediately checking whether the other host is still allowed). Look up `KongPlugin`'s scoping rules to explain the result precisely.

[→ solution](SOLUTIONS.md#exercise-3)

## Exercise 4 — Resource cost at scale
Using the `kubectl top` numbers from section 2.5, calculate the **combined** memory footprint of running all three controllers simultaneously. If a real cluster only needed ONE controller in production, which would you choose purely to minimize idle resource cost, and which would you choose if the team also needed built-in rate limiting and auth without adding a fourth component? Justify both answers using this lab's actual measurements, not just the concepts table.

[→ solution](SOLUTIONS.md#exercise-4)

## Exercise 5 — Break Kong's DB-less mode understanding
Delete the `hello-rate-limit` `KongPlugin` object directly (`kubectl delete kongplugin hello-rate-limit`) while its Ingress annotation still references it by name. Reapply traffic against `icd-kong-ratelimit.zero2hero.local`. Does the Ingress still route traffic at all? Does rate limiting still apply? What does `kubectl describe ingress hello-kong-ratelimited` (or the Kong controller's own logs, `kubectl logs -n kong -l app.kubernetes.io/component=controller`) say about the dangling reference?

[→ solution](SOLUTIONS.md#exercise-5)

## Exercise 6 (stretch) — Write a decision matrix
Without re-reading section 1.2's table, write your own comparison table from memory covering: extension mechanism, whether it's also a full API gateway, and typical fit — for Traefik, NGINX Ingress Controller, and Kong. Then check it against section 1.2 and note anything you got wrong or forgot. This exercise is deliberately testing recall, not lookup — the real skill this day teaches is being able to reason about controller choice in a design conversation without the table in front of you.

[→ solution](SOLUTIONS.md#exercise-6)
