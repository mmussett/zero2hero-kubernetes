---
---
# Day 12 — Solutions

## Exercise 1
```bash
sed 's/default: false/default: true/' values-ingress-nginx.yaml > values-ingress-nginx-default.yaml
helm upgrade ingress-nginx ingress-nginx/ingress-nginx -n ingress-nginx -f values-ingress-nginx-default.yaml
kubectl apply -f - <<'EOF'
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata: {name: no-class-test}
spec:
  rules:
    - host: no-class-test.zero2hero.local
      http:
        paths: [{path: /, pathType: Prefix, backend: {service: {name: hello-app-svc, port: {number: 80}}}}]
EOF
kubectl get ingress no-class-test -o jsonpath='{.spec.ingressClassName}'; echo
```
Result varies by exact timing/version, but is fundamentally **undefined/ambiguous** behavior: with two IngressClasses both marked `ingressclass.kubernetes.io/is-default-class: "true"`, the [Kubernetes docs explicitly state](https://kubernetes.io/docs/concepts/services-networking/ingress/#default-ingress-class) this is invalid configuration and the API server does not guarantee which one wins — in practice it's often whichever was marked default most recently, or arbitrary. This is a genuine, documented misconfiguration risk in any cluster where multiple teams or automated installers (a platform team's Traefik, an app team's `helm install ingress-nginx` with defaults) might each mark their own controller default without coordinating — the fix is always to have every Ingress specify `ingressClassName` explicitly and never rely on "no class" defaulting in a multi-controller cluster.
```bash
helm upgrade ingress-nginx ingress-nginx/ingress-nginx -n ingress-nginx -f values-ingress-nginx.yaml
kubectl delete ingress no-class-test
```

## Exercise 2
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: hello-nginx-stripprefix
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  rules:
    - host: icd-nginx-strip.zero2hero.local
      http:
        paths:
          - path: /hello
            pathType: Prefix
            backend: {service: {name: hello-app-svc, port: {number: 80}}}
```
```bash
kubectl apply -f hello-nginx-stripprefix.yaml
echo "127.0.0.1 icd-nginx-strip.zero2hero.local" | sudo tee -a /etc/hosts
curl http://icd-nginx-strip.zero2hero.local:30100/hello/
```
`rewrite-target: /` with a plain `Prefix` path (no regex capture groups needed here, unlike the earlier `/app(/|$)(.*)` example) strips the `/hello` prefix entirely before forwarding, landing on the backend's `/` route — behaviorally identical to Day 11's Traefik `stripPrefix` Middleware, achieved via a single annotation instead of a separate CRD object. This is a good concrete example of NGINX's "config encoded directly in the annotation" philosophy from section 1.2's table, contrasted with Traefik's separate-object approach.

## Exercise 3
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: hello-kong-ratelimited-2
  annotations:
    konghq.com/plugins: hello-rate-limit
spec:
  ingressClassName: kong
  rules:
    - host: icd-kong-ratelimit-2.zero2hero.local
      http:
        paths: [{path: /, pathType: Prefix, backend: {service: {name: hello-app-svc, port: {number: 80}}}}]
```
```bash
kubectl apply -f hello-kong-ratelimited-2.yaml
echo "127.0.0.1 icd-kong-ratelimit-2.zero2hero.local" | sudo tee -a /etc/hosts
for i in $(seq 1 6); do curl -s -o /dev/null -w "%{http_code}\n" http://icd-kong-ratelimit-2.zero2hero.local:30200/; done
```
With `policy: local` (as configured in `kong-rate-limit-plugin.yaml`), each Kong Gateway Pod tracks its own counter **per plugin instance attachment**, and by default a `KongPlugin` referenced from **multiple** Ingress resources is applied as **independent, separate plugin instances per route/Ingress** — exhausting `icd-kong-ratelimit`'s limit does **not** consume `icd-kong-ratelimit-2`'s separate limit; both allow their own 5-per-minute independently. This matters operationally: reusing one `KongPlugin` object across many Ingresses is a config-reuse convenience (write the limit once), not a shared quota — a team wanting one *combined* quota across multiple routes needs a different mechanism (e.g. applying the plugin at the Service level via a `KongClusterPlugin`/Service-level annotation rather than per-Ingress, or a shared external rate-limiting store instead of `policy: local`).

## Exercise 4
```bash
kubectl top pod -n kube-system -l app.kubernetes.io/name=traefik
kubectl top pod -n ingress-nginx
kubectl top pod -n kong
```
Typical combined memory: Traefik ~20-40Mi, NGINX Ingress Controller ~50-90Mi, Kong (gateway + controller sidecar) ~150-250Mi — combined often 250-350Mi+ just for three controllers doing overlapping jobs. **To minimize idle resource cost alone**, Traefik is the clear winner here (it's also already running, at zero additional install cost, in any k3s cluster) — a single lightweight controller with adequate routing features for most needs. **If the team additionally needs built-in rate limiting and auth without a fourth component**, Kong is the justified choice DESPITE its higher footprint, because the alternative — bolting a separate auth/rate-limiting layer onto Traefik or NGINX — likely costs more total resources and operational complexity than Kong's heavier-but-consolidated footprint. The "right" answer genuinely depends on which requirement (minimum footprint vs. minimum component count for a given feature set) matters more for that specific team — this exercise is testing that you can hold both trade-offs at once, not that there's one universally correct controller.

## Exercise 5
```bash
kubectl delete kongplugin hello-rate-limit
curl -s -o /dev/null -w "%{http_code}\n" http://icd-kong-ratelimit.zero2hero.local:30200/
kubectl describe ingress hello-kong-ratelimited
kubectl logs -n kong -l app.kubernetes.io/component=controller --tail=20
```
Routing **still works** — the Ingress's core routing rule is independent of the plugin annotation, so requests reach `hello-app-svc` normally with `200`. Rate limiting, however, **silently stops being enforced** — Kong has nothing to attach, since the named `KongPlugin` object no longer exists. `kubectl describe ingress` shows the annotation is still present (Kubernetes doesn't validate that annotation values reference real objects — annotations are opaque strings to the API server), but the Kong controller's own logs typically show a warning/error along the lines of `plugin config hello-rate-limit not found` when it next reconciles. This is a real operational trap: deleting a referenced `KongPlugin` (or any similarly-referenced CRD, like Traefik's `Middleware`) doesn't break the Ingress outright — it silently degrades a specific behavior, which can go unnoticed until someone asks "why isn't rate limiting working anymore?"

## Exercise 6
No single correct answer sheet here by design — self-check by comparing your from-memory table against section 1.2. Most learners forget at least one of: NGINX's config-in-annotation-value style (vs. Traefik/Kong's separate-CRD style), or that both NGINX Ingress Controller and Kong are actually built on the same underlying nginx engine despite feeling like completely different products at the Kubernetes-object level. If you got the "full API gateway" column right for all three without hesitation, you've internalized today's single most practically useful distinction.
