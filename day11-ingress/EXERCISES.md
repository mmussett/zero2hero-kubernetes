---
---
# Day 11 — Exercises

## Exercise 1 — Write the minimal Ingress from scratch
Without looking at `ingress-minimal.yaml`, write an Ingress named `scratch-ingress` routing `scratch.zero2hero.local` (path `/`) to `hello-app-svc` on port `80`, using the `traefik` IngressClass. Apply it, add the host to `/etc/hosts`, `curl` it successfully, then delete it.

[→ solution](SOLUTIONS.md#exercise-1)

## Exercise 2 — The prefix-stripping gotcha, observed directly
Temporarily remove the `traefik.ingress.kubernetes.io/router.middlewares` annotation from `ingress-path-based.yaml` (or apply a copy without it) and re-`curl http://zero2hero.local/hello/`. What HTTP status do you get back, and why (tie your answer to what path the Flask app actually receives — check `kubectl logs -l app=hello-app`)?

[→ solution](SOLUTIONS.md#exercise-2)

## Exercise 3 — Default backend / no matching rule
`curl http://zero2hero.local/nonexistent-path`. What response do you get? Then `curl -H "Host: doesnotexist.local" http://127.0.0.1/`. Compare the two responses and explain, referencing Traefik's role as a reverse proxy, why an unmatched host behaves differently from an unmatched path under a matched host.

[→ solution](SOLUTIONS.md#exercise-3)

## Exercise 4 — Multiple paths, same host, ordering
Add a third path, `/goodbye/extra`, to `ingress-path-based.yaml`'s `zero2hero.local` host, routed to `hello-app-svc` instead of `goodbye-app-svc`. Given that `/goodbye` (routing to `goodbye-app-svc`) is also a prefix match for `/goodbye/extra`, which rule actually wins when you `curl http://zero2hero.local/goodbye/extra/`? Look up how Ingress controllers resolve overlapping path prefixes (hint: longest-prefix-match) and confirm your prediction.

[→ solution](SOLUTIONS.md#exercise-4)

## Exercise 5 — Missing IngressClass
Create a copy of `ingress-host-based.yaml` with `ingressClassName: nginx` (a controller that isn't installed in this cluster). Apply it and run `kubectl get ingress`. Does it error at apply time? What does the `ADDRESS` column show, and what would a `curl` to that host actually do? Explain why Kubernetes allows you to create an Ingress resource for a controller that doesn't exist.

[→ solution](SOLUTIONS.md#exercise-5)

## Exercise 6 — TLS certificate mismatch
`curl -k https://secure.zero2hero.local/ -v` and find the `subject`/`CN` line in the TLS handshake output. Now try `curl -k https://zero2hero.local:443/` (a hostname the cert was **not** issued for, assuming you've kept the path-based Ingress's plain-HTTP setup — you may need to add a temporary TLS block to `ingress-path-based.yaml` reusing the same Secret to test this). What warning would a browser show a real user in this situation, and why does `-k` suppress it for us here?

[→ solution](SOLUTIONS.md#exercise-6)

## Exercise 7 (stretch) — Ingress-level rate limiting
Add a second Traefik `Middleware` of kind `RateLimit` (`spec.rateLimit.average: 2`, `spec.rateLimit.burst: 2`) and attach it via the router.middlewares annotation to `ingress-host-based.yaml`'s `hello.zero2hero.local` rule. Hammer it with `for i in $(seq 1 10); do curl -s -o /dev/null -w "%{http_code}\n" http://hello.zero2hero.local/; done`. What status code appears once you exceed the limit, and why is enforcing this at the Ingress layer more efficient than every backend implementing its own rate limiting?

[→ solution](SOLUTIONS.md#exercise-7)

## Exercise 8 — Prove HTTP and HTTPS coexist, then lock it down
Before applying the redirect Middleware, confirm with two separate `curl` commands that `ingress-tls.yaml`'s host answers on **both** `http://secure.zero2hero.local/` (plain, 200 OK) and `https://secure.zero2hero.local/` (also 200 OK, with `-k`). Now apply `traefik-https-redirect-middleware.yaml` and repeat the plain-HTTP `curl` against `secure-redirect.zero2hero.local` — capture the exact status code and the `Location` response header. Finally, confirm the HTTPS request to that same redirected host does **not** also get redirected (i.e., there's no infinite redirect loop). Explain, from what you observed, why a `redirectScheme` Middleware must be able to tell an incoming HTTPS request apart from an HTTP one to avoid looping.

[→ solution](SOLUTIONS.md#exercise-8)
