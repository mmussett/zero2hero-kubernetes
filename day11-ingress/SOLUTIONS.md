---
---
# Day 11 — Solutions

## Exercise 1
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: scratch-ingress
spec:
  ingressClassName: traefik
  rules:
    - host: scratch.zero2hero.local
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: hello-app-svc
                port:
                  number: 80
```
```bash
kubectl apply -f scratch-ingress.yaml
echo "127.0.0.1 scratch.zero2hero.local" | sudo tee -a /etc/hosts
curl http://scratch.zero2hero.local/
kubectl delete -f scratch-ingress.yaml
```
No annotations, no TLS block, no Middleware needed — every additional feature this day covers is layered onto this exact minimal shape, never a replacement for it.

## Exercise 2
```bash
kubectl apply -f - <<'EOF'
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata: {name: path-based-nostripping}
spec:
  ingressClassName: traefik
  rules:
    - host: zero2hero.local
      http:
        paths:
          - path: /hello
            pathType: Prefix
            backend: {service: {name: hello-app-svc, port: {number: 80}}}
EOF
curl -i http://zero2hero.local/hello/
```
Response is `404 Not Found` (Flask's default 404 page). The backend Flask app only defines routes for `/` and `/healthz` — without the `stripPrefix` Middleware, Traefik forwards the request to `hello-app-svc` with the path **unchanged** as `/hello/`, which doesn't match any Flask route. `kubectl logs -l app=hello-app` shows the access attempt hitting `/hello/` and Flask's own 404 response — proof the request *did* reach the correct backend, it just asked for a path that backend doesn't serve. This is exactly the class of bug the concepts section warned about.
```bash
kubectl delete ingress path-based-nostripping
```

## Exercise 3
```bash
curl -i http://zero2hero.local/nonexistent-path
# 404 Not Found — from Traefik itself
curl -i -H "Host: doesnotexist.local" http://127.0.0.1/
# 404 Not Found (or a slightly different Traefik default-backend page) — also from Traefik
```
Both ultimately return `404`, but conceptually they fail at different layers: an unmatched **path** under a *matched* host still gets proxied through routing logic that finds no rule and Traefik itself returns 404 (never reaching any backend Pod — confirm by checking backend logs show nothing new); an unmatched **host** fails even earlier, since Traefik's router table has no entry for that `Host` header at all, so it falls through to its built-in default 404 responder before path matching is even considered. Functionally identical to the caller, but the internal decision point differs — useful when debugging with `kubectl logs` on the Traefik Pod itself (`-n kube-system`), where you can see which case you're in from the router name Traefik logs.

## Exercise 4
```yaml
- path: /goodbye/extra
  pathType: Prefix
  backend: {service: {name: hello-app-svc, port: {number: 80}}}
```
```bash
curl http://zero2hero.local/goodbye/extra/
```
The **more specific** rule (`/goodbye/extra`, the longer prefix) wins, routing to `hello-app-svc` — confirmed by the response body showing `"You reached HELLO-APP"` despite `/goodbye` also technically matching as a prefix. Ingress controllers (Traefik included) resolve overlapping `Prefix` paths using **longest-prefix-match wins**, identical in principle to IP routing table longest-prefix-match — this lets you carve out specific exceptions under a broader path rule, which is a common real pattern (e.g. `/api` → general API backend, `/api/admin` → a separate, more locked-down backend).

## Exercise 5
```bash
sed 's/ingressClassName: traefik/ingressClassName: nginx/' ingress-host-based.yaml \
  | sed 's/name: host-based-ingress/name: nginx-ingress-demo/' | kubectl apply -f -
kubectl get ingress nginx-ingress-demo
```
It applies successfully with **no error** — `ADDRESS` stays empty indefinitely (never populated, since no controller is watching `ingressClassName: nginx`). A `curl` to that hostname would simply fail to connect to anything meaningful for this Ingress specifically (any response you got would come from whatever controller — Traefik — happens to still be listening on that IP/port for its *own* matched rules, not this one). Kubernetes allows creating Ingress resources for non-existent controllers by design: the API server's job is only to validate and persist the object's schema — it has no way to know which controllers are or aren't running, and Ingress resources are explicitly meant to be controller-agnostic declarations that any matching controller *may* pick up, including one installed later.
```bash
kubectl delete ingress nginx-ingress-demo
```

## Exercise 6
```bash
curl -k https://secure.zero2hero.local/ -v 2>&1 | grep -i subject
# subject: CN=secure.zero2hero.local
```
Reusing the same Secret against a different hostname requires temporarily adding a `tls:` block to `ingress-path-based.yaml`; doing so and hitting it under the wrong hostname, a real browser would show a prominent **"Your connection is not private" / NET::ERR_CERT_COMMON_NAME_INVALID**-style warning, because the certificate's Subject/SAN (`secure.zero2hero.local`) doesn't match the hostname the browser actually requested (`zero2hero.local`) — TLS explicitly requires this match to prevent impersonation. `curl -k` suppresses **all** certificate validation (expiry, trust chain, *and* hostname matching) specifically so this lab's self-signed, single-host cert doesn't block basic connectivity testing — `-k` should never be used against real production endpoints, since it defeats the entire point of TLS verification.

## Exercise 7
```yaml
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata: {name: hello-ratelimit}
spec:
  rateLimit:
    average: 2
    burst: 2
```
```yaml
# host-based-ingress annotation added:
metadata:
  annotations:
    traefik.ingress.kubernetes.io/router.middlewares: default-hello-ratelimit@kubernetescrd
```
```bash
kubectl apply -f ratelimit-middleware.yaml
kubectl apply -f ingress-host-based-ratelimited.yaml
for i in $(seq 1 10); do curl -s -o /dev/null -w "%{http_code}\n" http://hello.zero2hero.local/; done
```
The first couple of requests return `200`, then subsequent rapid requests return `429 Too Many Requests` once the configured rate is exceeded. Enforcing rate limiting at the Ingress layer is more efficient than per-backend implementation because: (1) it protects **every** backend behind that Ingress uniformly with one config, instead of duplicating rate-limit logic and its runtime cost into each application; (2) it rejects excess requests **before** they consume any backend Pod CPU/memory or database connections, protecting scarce downstream resources rather than merely protecting the app's own request-handling loop; (3) it centralizes the policy in one auditable place a platform team controls, independent of what any individual application team ships in their code.

## Exercise 8
```bash
curl -s -o /dev/null -w "%{http_code}\n" http://secure.zero2hero.local/     # 200
curl -sk -o /dev/null -w "%{http_code}\n" https://secure.zero2hero.local/    # 200
```
Both succeed — proving `ingress-tls.yaml` never disabled plain HTTP for that host, exactly as section 1.5 states.
```bash
kubectl apply -f traefik-https-redirect-middleware.yaml
curl -i http://secure-redirect.zero2hero.local/ 2>&1 | grep -i "^location\|^HTTP"
# HTTP/1.1 308 Permanent Redirect
# Location: https://secure-redirect.zero2hero.local/
curl -sk -o /dev/null -w "%{http_code}\n" https://secure-redirect.zero2hero.local/   # 200 — no loop
```
The plain-HTTP request gets a `308 Permanent Redirect` pointing at the `https://` version of the same URL — exactly the standard "always upgrade to HTTPS" pattern real sites use. The HTTPS request to the same host returns a normal `200`, with **no** redirect and no loop.

The `redirectScheme` Middleware avoids looping because it inspects the **scheme the request actually arrived on** at Traefik's entrypoint (`web`, plain HTTP, vs. `websecure`, already-TLS) — it only rewrites and redirects requests that arrived via the *non*-target scheme. A request that already arrived over HTTPS is, by definition, already on the target scheme, so the middleware is a no-op for it — if it instead redirected unconditionally regardless of the incoming scheme, every HTTPS request would be redirected right back to `https://` again, and the redirect Middleware would fire on its own output forever. This is the same "check before you act, not just after" principle Day 20's `selfHeal` discussion touched on, applied here to routing instead of GitOps reconciliation.
