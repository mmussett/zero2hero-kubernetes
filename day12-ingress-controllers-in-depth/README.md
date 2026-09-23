---
---
# Day 12 — Ingress Controllers in Depth: NGINX, Kong & Traefik Compared

> **Resource note:** running three Ingress controllers simultaneously (Traefik, already installed; NGINX Ingress Controller; Kong) is noticeably heavier than Day 11 alone. 4GB RAM is workable but tight — 6GB+ is more comfortable. Tear down whichever controller you're not actively comparing if things feel slow.

Day 11 taught Ingress with exactly one controller (Traefik) so the *concepts* weren't muddied by controller-specific quirks. Today installs two more of the most widely-adopted open-source options — **NGINX Ingress Controller** and **Kong Ingress Controller** — side by side with Traefik, routing the *same* backend through all three, so every difference you observe is a real, controller-specific difference, not a guess.

## Learning objectives
- Install and run multiple Ingress controllers simultaneously in one cluster, each handling its own `IngressClass`
- Explain why Ingress annotations are **not portable** across controllers, with a hands-on demonstration
- Compare three distinct configuration philosophies: Traefik's Middleware CRD, NGINX's annotation-encoded config, and Kong's KongPlugin CRD
- Use Kong's plugin system for rate limiting — a preview of full API-gateway functionality, not just routing
- Measure and compare each controller's real resource footprint
- Make an informed, criteria-based choice between Ingress controllers for a real project

## 1. Concepts

### 1.1 Why run more than one controller

Recall Day 11: `ingressClassName` ties an Ingress resource to a specific controller. Real clusters frequently run **more than one controller simultaneously** — a common pattern is a "public" controller handling internet-facing traffic with strict WAF/rate-limiting rules, and a separate "internal" controller (sometimes even the same software, differently configured) for cluster-internal-only routes never exposed externally. Today's lab runs three controllers purely for comparison, but the mechanism — multiple `IngressClass` objects, each with its own controller Deployment — is exactly what production multi-controller setups use.

### 1.2 Three real controllers, three philosophies

| | [Traefik](https://doc.traefik.io/traefik/) (Day 11) | [NGINX Ingress Controller](https://kubernetes.github.io/ingress-nginx/) | [Kong Ingress Controller](https://docs.konghq.com/kubernetes-ingress-controller/latest/) |
|---|---|---|---|
| Built on | Traefik's own Go proxy | The `nginx` web server, config-templated | Kong Gateway (built on nginx/OpenResty + Lua) |
| Extension mechanism | `Middleware` CRD | Annotations (`nginx.ingress.kubernetes.io/...`) with config **encoded directly in the annotation value** | `KongPlugin`/`KongClusterPlugin` CRDs, referenced by annotation |
| Also acts as a full API gateway (auth, rate limiting, transformations) beyond routing | Limited (some middleware types) | No — routing-focused | **Yes** — this is Kong's core identity; routing is one of many plugin-driven capabilities |
| Config source of truth | Kubernetes CRDs/annotations only | Kubernetes annotations (a `ConfigMap` for global settings) | Kubernetes CRDs (DB-less mode, today's lab) or an external Postgres database (traditional mode) |
| Typical fit | Simple-to-moderate routing needs, already bundled with k3s/Rancher | The most widely deployed Ingress controller in the ecosystem — huge community, huge annotation surface, safe default choice | Teams that want Ingress routing AND a full API gateway (auth, quotas, transformations, a plugin marketplace) from one component |

**Both NGINX Ingress Controller and Kong are, underneath, built on nginx** — the difference is the layer built on top (Kong adds a full Lua-plugin gateway architecture; the "NGINX Ingress Controller" project is a thinner, Kubernetes-native templating layer over plain nginx config). Knowing this helps explain why Kong's resource footprint and feature surface are both larger.

### 1.3 The annotation portability trap

This is the single most important lesson today. An Ingress's **core fields** (`rules`, `pathType`, `backend`, `tls`) are part of the portable, standard Kubernetes API — any conformant controller understands them identically. **Annotations are not.** `nginx.ingress.kubernetes.io/rewrite-target` means something very specific to the NGINX Ingress Controller and **is silently ignored by every other controller** — no error, no warning, the Ingress simply behaves as if the annotation weren't there at all. This is a genuinely common real-world outage: a manifest copy-pasted from a blog post or a different cluster's setup, still working (routing succeeds) but a specific behavior (a rewrite, a rate limit, a redirect) mysteriously doesn't happen — because the annotation assumed a different controller is actually running.

### 1.4 Kong's plugin model, and why it previews Day 13

Kong's `KongPlugin` CRD is a third distinct pattern: the annotation (`konghq.com/plugins: hello-rate-limit`) only **names** a plugin configuration object; the actual config lives in a separate `KongPlugin` resource. The same plugin mechanism that does rate limiting also does authentication (key-auth, JWT, OAuth2), request/response transformation, and dozens of other capabilities from Kong's plugin ecosystem — Ingress routing is just one of many things Kong does, which is exactly the "Ingress Controller vs. full Gateway" distinction Day 13 formalizes with the Gateway API.

### Official documentation
- [Ingress Controllers](https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/)
- [NGINX Ingress Controller documentation](https://kubernetes.github.io/ingress-nginx/)
- [NGINX Ingress Controller: Annotations reference](https://kubernetes.github.io/ingress-nginx/user-guide/nginx-configuration/annotations/)
- [Kong Ingress Controller documentation](https://docs.konghq.com/kubernetes-ingress-controller/latest/)
- [Kong: KongPlugin reference](https://docs.konghq.com/kubernetes-ingress-controller/latest/references/custom-resources/#kongplugin)
- [Kong: Rate Limiting plugin](https://docs.konghq.com/hub/kong-inc/rate-limiting/)
- [Kong Gateway: DB-less mode](https://docs.konghq.com/gateway/latest/production/deployment-topologies/db-less-and-declarative-config/)

## 2. Hands-on lab

```bash
cd day12-ingress-controllers-in-depth/manifests
kubectl apply -f backend-app.yaml
kubectl wait --for=condition=ready pod -l app=hello-app --timeout=60s
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo add kong https://charts.konghq.com
helm repo update

# 2.1 Confirm Traefik's existing IngressClass, then install the other two
kubectl get ingressclass
helm install ingress-nginx ingress-nginx/ingress-nginx -n ingress-nginx --create-namespace -f values-ingress-nginx.yaml
helm install kong kong/kong -n kong --create-namespace -f values-kong.yaml
kubectl get pods -n ingress-nginx -w &
sleep 30; kill %1 2>/dev/null
kubectl get pods -n kong -w &
sleep 30; kill %1 2>/dev/null
kubectl get ingressclass    # traefik, nginx, and kong all listed now

# 2.2 Route the SAME backend through all three
kubectl apply -f ingress-traefik.yaml -f ingress-nginx.yaml -f ingress-kong.yaml
echo "127.0.0.1 icd-traefik.zero2hero.local icd-nginx.zero2hero.local icd-kong.zero2hero.local icd-kong-annotation-test.zero2hero.local icd-kong-ratelimit.zero2hero.local" | sudo tee -a /etc/hosts

curl http://icd-traefik.zero2hero.local/                 # via Traefik, port 80 (k3s ServiceLB)
curl http://icd-nginx.zero2hero.local:30100/app/         # via NGINX, NodePort 30100, path REWRITTEN to /
curl http://icd-kong.zero2hero.local:30200/               # via Kong, NodePort 30200

# 2.3 The annotation portability trap, proven directly
curl http://icd-kong-annotation-test.zero2hero.local:30200/app/
# Kong ignores the nginx-specific rewrite-target annotation entirely --
# compare this response to icd-nginx's successful rewrite above

# 2.4 Kong's plugin system: rate limiting
kubectl apply -f kong-rate-limit-plugin.yaml
for i in $(seq 1 8); do
  curl -s -o /dev/null -w "%{http_code}\n" http://icd-kong-ratelimit.zero2hero.local:30200/
done
# first 5 succeed (200), then 429 Too Many Requests -- config.minute: 5 enforced

# 2.5 Resource footprint comparison
kubectl top pod -n kube-system -l app.kubernetes.io/name=traefik
kubectl top pod -n ingress-nginx
kubectl top pod -n kong

# 2.6 Clean up
kubectl delete -f .
helm uninstall ingress-nginx -n ingress-nginx
helm uninstall kong -n kong
kubectl delete namespace ingress-nginx kong
sudo sed -i '/icd-/d' /etc/hosts
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| An annotation you copied from a blog post/another cluster does nothing at all, no error | Annotations are controller-specific — the annotation's namespace (`nginx.ingress.kubernetes.io/...` vs. `traefik.ingress.kubernetes.io/...` vs. `konghq.com/...`) doesn't match the controller actually handling that Ingress (section 1.3) | Confirm `ingressClassName` and cross-check the annotation is the *right controller's* dialect for that class |
| Two controllers both claim to be the default IngressClass | Both were installed with `ingressClassResource.default: true` (or equivalent), independently, by different teams/charts | Set `default: false` on all but one, and going forward always set `ingressClassName` explicitly rather than relying on defaulting |
| Kong route works, but a referenced `KongPlugin` doesn't seem to apply | The `KongPlugin` object was deleted or renamed after the Ingress annotation referenced it — annotations are opaque strings, never validated against real objects | `kubectl get kongplugin`; check the Kong controller's own logs for a "plugin config not found" warning |
| Two controllers running, both bound to port 80/443, and traffic goes to the wrong one | Only one `LoadBalancer`-type Service can actually bind a given host port at a time on a single node — this normally errors loudly, but check for silent misrouting if you used NodePort ranges instead | Confirm each controller's Service is on a genuinely distinct port (this lab's `values-*.yaml` files deliberately assign different NodePorts) |

See also: [Debugging Common Kubernetes Issues](../TROUBLESHOOTING.md).

## 3. Key commands reference

| Command | Purpose |
|---|---|
| `kubectl get ingressclass` | List every registered controller's IngressClass |
| `helm install <name> <chart> -n <ns> --create-namespace -f values.yaml` | Install a controller via its official chart |
| `kubectl get pods -n <controller-namespace> -o wide` | Confirm a controller's own Pods are healthy |
| `kubectl top pod -n <ns>` | Compare real resource usage between controllers |
| `kubectl get kongplugin,kongclusterplugin` | List Kong's declarative plugin configs |

Next: [Day 13 — Ingress Gateways: The Gateway API](../day13-gateway-api/README.md)
