---
---
# Day 11 — Ingress Controllers & Ingress Resources

## Learning objectives
- Explain what problem Ingress solves that Services (even `LoadBalancer`) don't
- Understand the Ingress controller / Ingress resource split
- Route traffic by hostname and by URL path to different backend Services
- Terminate TLS at the Ingress layer
- Diagnose a misconfigured Ingress (wrong backend, missing class, path gotchas)

## 1. Concepts

### 1.1 Anatomy of a minimal Ingress

`ingress-minimal.yaml` is the smallest valid Ingress — one host, one path, one backend, no annotations, no TLS:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: hello-world
spec:
  ingressClassName: traefik    # WHICH controller handles this — §1.3
  rules:
    - host: hello-world.zero2hero.local
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: hello-app-svc   # an ordinary Service, from Day 5 — Ingress never talks to Pods directly
                port:
                  number: 80
```

Everything else in this day — path-based routing, TLS, rewrite Middlewares — is additional `rules` entries or fields layered onto this exact shape. Note that Ingress routes to a **Service name and port**, never a Pod directly — the Service (with its own selector, Day 5) is still what actually finds the right Pods.

### 1.2 The problem: one LoadBalancer per Service doesn't scale

Recall Day 5: a `LoadBalancer` Service gets its own external IP. If you have 20 HTTP services, do you want 20 separate cloud load balancers (20× the cost, 20 different IPs/DNS entries to manage)? [**Ingress**](https://kubernetes.io/docs/concepts/services-networking/ingress/) solves this: a single entry point (one IP, one LoadBalancer) that routes to many backend Services based on **HTTP-layer** information — hostname and/or URL path — that a plain L4 Service load balancer can't see at all (a `LoadBalancer` Service only knows about IP:port, not HTTP headers or paths).

### 1.3 Two separate pieces: controller and resource

This trips up almost everyone at first, so be deliberate about it:
- **Ingress controller** — an actual running workload (a Deployment, usually fronted by its own `LoadBalancer`/`NodePort` Service) that watches Ingress objects and does the real proxying — [Traefik](https://doc.traefik.io/traefik/), [ingress-nginx](https://kubernetes.io/docs/reference/networking/ingress/#glossary), and others are all "an Ingress controller." **k3s ships Traefik pre-installed** — nothing to install today.
- **Ingress resource** — the declarative YAML object (`kind: Ingress`) describing routing *rules*. Creating an Ingress object with no controller running does **nothing** — it just sits there as inert configuration nobody is acting on. The `ingressClassName` field is what ties a given Ingress resource to a specific installed controller when more than one exists in a cluster.

```
 client ──HTTP(S)──▶ Ingress controller Pod(s) ──reads config from──▶ Ingress resource(s)
                              │
                              ├── host: hello.zero2hero.local  ──▶  hello-app-svc  ──▶ Pods
                              └── host: goodbye.zero2hero.local──▶  goodbye-app-svc──▶ Pods
```

### 1.4 Routing strategies

- **Host-based (virtual hosting)** — different hostnames route to different backends on the same IP, using the HTTP `Host` header — this is exactly how one web server traditionally hosts many unrelated sites on one IP.
- **Path-based** — one hostname, different URL path prefixes route to different backends. **Gotcha to internalize today:** by default the controller forwards the **full original path** to the backend unchanged — a request to `/hello/foo` is proxied to the backend as `/hello/foo`, not `/foo`. If your backend app doesn't understand that prefix, you need controller-specific path-rewriting (Traefik's `Middleware` CRD, used in this lab; ingress-nginx uses an annotation instead). This exact confusion — "my Ingress routes correctly but the backend 404s" — is one of the most common real-world Ingress bugs.

### 1.5 TLS termination

An Ingress can terminate HTTPS itself, decrypting traffic at the edge and forwarding plain HTTP to backend Pods (simplifying every backend — they never handle TLS themselves). The certificate/key pair is supplied as a `kubernetes.io/tls`-type Secret (the exact shape from Day 6, Exercise 3), referenced under `spec.tls`. In production you'd automate certificate issuance with [cert-manager](https://cert-manager.io/) rather than hand-rolling self-signed certs as today's lab does for simplicity.

**Adding a `tls:` block does not, by itself, turn off plain HTTP.** Traefik (and most controllers) keep serving the *same* host on its ordinary HTTP entrypoint alongside the new HTTPS one — `tls-ingress` in today's lab is reachable on **both** `http://secure.zero2hero.local/` and `https://secure.zero2hero.local/` the instant you apply it, whether you intended that or not. This is a genuinely common real-world surprise: a team adds TLS expecting it to replace HTTP, ships it, and later discovers plaintext access was silently still open the whole time. If you want HTTPS-only, you must say so explicitly — either with a controller-specific redirect (a Traefik `Middleware` of type `redirectScheme`, used in today's lab) or by not exposing an HTTP listener for that host at all.

### Official documentation
- [Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/)
- [Ingress Controllers](https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/)
- [Networking Glossary — Ingress](https://kubernetes.io/docs/reference/networking/ingress/)
- [Traefik Kubernetes Ingress documentation](https://doc.traefik.io/traefik/providers/kubernetes-ingress/)
- [Traefik Middleware: StripPrefix](https://doc.traefik.io/traefik/middlewares/http/stripprefix/)
- [k3s: Traefik Ingress Controller](https://docs.k3s.io/networking/networking-services#traefik-ingress-controller)
- [cert-manager](https://cert-manager.io/docs/)

## 2. Hands-on lab

```bash
cd day11-ingress/manifests

# 2.1 Deploy the two backend apps
kubectl apply -f deployments-services.yaml
kubectl wait --for=condition=ready pod -l app=hello-app --timeout=60s
kubectl wait --for=condition=ready pod -l app=goodbye-app --timeout=60s

# 2.2 The absolute minimum
kubectl apply -f ingress-minimal.yaml
echo "127.0.0.1 hello-world.zero2hero.local" | sudo tee -a /etc/hosts
curl http://hello-world.zero2hero.local/
kubectl delete -f ingress-minimal.yaml

# 2.3 Confirm Traefik is already running (k3s bundled it)
kubectl get pods -n kube-system -l app.kubernetes.io/name=traefik
kubectl get ingressclass    # "traefik" listed

# 2.4 Path-based routing (with the strip-prefix Middleware)
kubectl apply -f traefik-strip-prefix-middleware.yaml
kubectl apply -f ingress-path-based.yaml
echo "127.0.0.1 zero2hero.local" | sudo tee -a /etc/hosts
curl http://zero2hero.local/hello/
curl http://zero2hero.local/goodbye/

# 2.5 Host-based routing
kubectl apply -f ingress-host-based.yaml
echo "127.0.0.1 hello.zero2hero.local goodbye.zero2hero.local" | sudo tee -a /etc/hosts
curl http://hello.zero2hero.local/
curl http://goodbye.zero2hero.local/

# 2.6 TLS termination with a self-signed cert — exposed over HTTPS *and* HTTP
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /tmp/tls.key -out /tmp/tls.crt \
  -subj "/CN=secure.zero2hero.local" \
  -addext "subjectAltName=DNS:secure.zero2hero.local"
kubectl create secret tls zero2hero-tls --cert=/tmp/tls.crt --key=/tmp/tls.key
kubectl apply -f ingress-tls.yaml
echo "127.0.0.1 secure.zero2hero.local" | sudo tee -a /etc/hosts
curl -k https://secure.zero2hero.local/     # -k: skip self-signed cert verification -- HTTPS works
curl http://secure.zero2hero.local/          # ...and so does plain HTTP, on the SAME host, unless you say otherwise (section 1.5)

# 2.6b Force HTTPS-only with a redirect Middleware (a SEPARATE secret — never overwrite zero2hero-tls above)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /tmp/tls-redirect.key -out /tmp/tls-redirect.crt \
  -subj "/CN=secure-redirect.zero2hero.local" \
  -addext "subjectAltName=DNS:secure-redirect.zero2hero.local"
kubectl create secret tls zero2hero-tls-redirect --cert=/tmp/tls-redirect.crt --key=/tmp/tls-redirect.key
kubectl apply -f traefik-https-redirect-middleware.yaml
echo "127.0.0.1 secure-redirect.zero2hero.local" | sudo tee -a /etc/hosts
curl -i http://secure-redirect.zero2hero.local/ 2>&1 | grep -i "^location\|^HTTP"   # 301/308 redirect to https://
curl -k https://secure-redirect.zero2hero.local/                                    # https itself still works, no redirect loop

# 2.7 Inspect what Traefik actually configured
kubectl describe ingress path-based-ingress
kubectl get ingress -A

# 2.8 Clean up
kubectl delete -f .
sudo sed -i '/zero2hero.local/d' /etc/hosts
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `kubectl get ingress` shows an empty `ADDRESS` column forever | No controller is watching that `ingressClassName` — either it's not installed, or the name is typo'd | `kubectl get ingressclass` to see what's actually registered; compare against your Ingress's `spec.ingressClassName` |
| Routes correctly by hostname, but returns 404 for a path you expect to work | Path-based routing forwards the **full original path** to the backend by default — the app doesn't have a route matching it (section 1.4's gotcha) | Add a rewrite/strip-prefix Middleware, or confirm the backend genuinely serves that exact path |
| Everything looks right in the Ingress YAML, but nothing routes at all | The backend Service has no endpoints — an Ingress problem often isn't an Ingress problem at all | `kubectl get endpoints <service-name>` first, before assuming the Ingress config is wrong |
| `curl -k https://...` works but a real browser shows a certificate warning | Expected — `-k` disables all TLS verification including hostname matching; a self-signed cert for the wrong hostname fails that check for a real client | Confirm the cert's CN/SAN actually matches the hostname you're serving, or use a real cert (cert-manager) outside this lab |
| A host with a `tls:` block is *still* reachable over plain `http://`, even though you only wanted HTTPS | Adding `tls:` terminates HTTPS for that host — it does not disable the HTTP listener for it (section 1.5) | Add a `redirectScheme` Middleware (or equivalent controller-specific redirect) if HTTP must be blocked/redirected, as `traefik-https-redirect-middleware.yaml` does |
| Two Ingress objects for the same host both seem to apply, unpredictably | Overlapping path prefixes resolve by longest-prefix-match, not declaration order — check for an unintentional overlap | `kubectl describe ingress` on both, and compare their `path` values directly |

See also: [Debugging Common Kubernetes Issues](../TROUBLESHOOTING.md).

## 3. Key commands reference

| Command | Purpose |
|---|---|
| `kubectl get ingressclass` | List available Ingress controllers registered in the cluster |
| `kubectl get ingress [-A]` | List Ingress resources and their assigned address |
| `kubectl describe ingress <name>` | Rules, backends, and TLS config at a glance |
| `kubectl create secret tls <name> --cert=<crt> --key=<key>` | Create a TLS Secret for use in `spec.tls` |

Next: [Day 12 — Ingress Controllers in Depth: NGINX & Kong](../day12-ingress-controllers-in-depth/README.md)
