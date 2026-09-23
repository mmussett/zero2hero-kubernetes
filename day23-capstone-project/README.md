# Day 23 — Capstone: Deploy, Secure, Scale & Troubleshoot a Full Application

Nineteen days, one cluster, every topic. Today you deploy a real three-tier application — **frontend → backend → Redis** — packaged as a single Helm chart that deliberately exercises nearly every mechanism from this course at once, then you break it on purpose and fix it using nothing but the diagnostic skills you've built since Day 2.

## Learning objectives
- Integrate workloads, storage, networking, security, and scaling into one coherent deployment
- Trace a request across every layer: Ingress → Service → Pod → Service → Pod → Service → Pod
- Diagnose multi-layer failures using only `kubectl` (no looking at the chart source first)
- Produce a personal checklist proving mastery of all 23 days

## 1. Architecture

```
                     ┌─────────────── capstone namespace ────────────────┐
                     │                                                    │
 client ──HTTP──▶ Ingress ──▶ frontend Svc ──▶ frontend Pods (x2)          │
                     │              (Deployment, RollingUpdate)           │
                     │                    │  HTTP, NetworkPolicy-allowed   │
                     │                    ▼                                │
                     │            backend Svc ──▶ backend Pods (HPA 2-6)   │
                     │                    │  TCP:6379, NetworkPolicy-allowed│
                     │                    ▼                                │
                     │            redis Svc (headless) ──▶ redis-0          │
                     │                                  (StatefulSet + PVC) │
                     └────────────────────────────────────────────────────┘

 Every Pod: hardened securityContext, restricted Pod Security Standard,
            dedicated ServiceAccount (token automount disabled),
            explicit requests/limits inside a namespace ResourceQuota.
```

| Course topic | Where it appears in this capstone |
|---|---|
| Day 1 — Docker | `app/frontend/`, `app/backend/` — two more Dockerfiles you build yourself |
| Day 3 — Pods | Every Pod uses readiness/liveness probes |
| Day 4 — Deployments | frontend & backend, `RollingUpdate` with `maxUnavailable: 0` |
| Day 5 — Services | ClusterIP Services chain the three tiers together by DNS name |
| Day 6 — Config | `REDIS_HOST`/`BACKEND_URL` injected via env, Service-name based, no hardcoded IPs |
| Day 7/8 — Storage/StatefulSets | Redis as a StatefulSet with a `volumeClaimTemplates`-backed PVC |
| Day 10 — Namespaces/Quota | Dedicated `capstone` namespace, `ResourceQuota` + `LimitRange` |
| Day 11 — Ingress | Public entry point for `frontend` |
| Day 14 — NetworkPolicy | Default-deny + tier-by-tier allow rules (frontend ← anywhere, backend ← frontend only, redis ← backend only) |
| Day 16 — RBAC/ServiceAccounts | Dedicated SAs per tier, token automount disabled (neither app calls the K8s API) |
| Day 17 — Pod Security | Namespace enforces the `restricted` Pod Security Standard |
| Day 19 — Helm | The entire capstone is one chart, `-f values.yaml` configurable per environment |
| Day 21 — HPA | `backend` autoscales 2→6 replicas on CPU |

### Official documentation

Today integrates every topic above rather than teaching new ones, so instead of a new reading list, revisit the **Official documentation** section at the bottom of each day's `README.md` linked in the table — in particular:
- [Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) and [StatefulSets](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/) (Days 4, 8)
- [Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/) (Day 14)
- [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/) (Day 17)
- [Horizontal Pod Autoscaling](https://kubernetes.io/docs/concepts/workloads/autoscaling/) (Day 21)
- [Helm Chart Best Practices](https://helm.sh/docs/chart_best_practices/) (Day 19) — worth a first read now that you've built and operated a full chart, not just a single-page example
- [Production Environment Considerations](https://kubernetes.io/docs/setup/production-environment/) — the natural next read once this course is finished: everything this capstone approximates locally, at real production scale

## 2. Hands-on lab

### 2.1 Build and push both app images

```bash
cd day23-capstone-project/app/backend
docker build -t localhost:5000/capstone-backend:1.0.0 .
docker push localhost:5000/capstone-backend:1.0.0

cd ../frontend
docker build -t localhost:5000/capstone-frontend:1.0.0 .
docker push localhost:5000/capstone-frontend:1.0.0
```

### 2.2 Deploy the whole stack with one command

```bash
cd ../../chart
helm lint capstone/
helm install capstone capstone/
kubectl get pods -n capstone -w   # wait for everything Running/Ready
```

### 2.3 Trace a request through every layer

```bash
echo "127.0.0.1 capstone.zero2hero.local" | sudo tee -a /etc/hosts
curl http://capstone.zero2hero.local/
curl http://capstone.zero2hero.local/     # refresh a few times — watch "hits" increase
```

```bash
kubectl get ingress -n capstone
kubectl get endpoints -n capstone
kubectl get pods -n capstone -o wide
kubectl logs -n capstone -l app=backend --tail=10
kubectl exec -n capstone -it redis-0 -- redis-cli get hits
```

### 2.4 Prove NetworkPolicy segmentation is real

```bash
kubectl run -n capstone netshoot --rm -it --image=nicolaka/netshoot --restart=Never -- \
  curl -s -m 3 backend/ || echo "expected to hang/fail — netshoot isn't a frontend Pod"
kubectl exec -n capstone deploy/frontend -- curl -s -m 3 backend/   # this one works
```

### 2.5 Load-test and watch the backend autoscale

```bash
kubectl run -n capstone load-gen --image=busybox:1.36 --restart=Never -- \
  sh -c "while true; do wget -q -O- http://backend/ >/dev/null; done"
kubectl get hpa -n capstone -w   # ctrl-c once you see replicas climb
kubectl delete pod -n capstone load-gen
```

### 2.6 Perform a zero-downtime rolling update

```bash
# Edit app/frontend/app.py's <h1> title, rebuild, push as :1.0.1
docker build -t localhost:5000/capstone-frontend:1.0.1 app/frontend/
docker push localhost:5000/capstone-frontend:1.0.1
helm upgrade capstone capstone/ --set images.frontend=localhost:5000/capstone-frontend:1.0.1
kubectl rollout status deployment/frontend -n capstone
curl http://capstone.zero2hero.local/   # new title, zero downtime, hit counter unaffected
```

## 3. Final troubleshooting scenario

Without reading the chart's templates first, diagnose and fix each of the following, applied one at a time (revert each before moving to the next):

1. `kubectl patch networkpolicy allow-frontend-to-backend -n capstone --type=json -p='[{"op":"replace","path":"/spec/ingress/0/from/0/podSelector/matchLabels/app","value":"nonexistent"}]'` — the frontend can no longer reach the backend. Diagnose using only Day 14's technique (no reading YAML) and fix it.
2. `kubectl scale statefulset redis -n capstone --replicas=0` — the whole site breaks. Trace the failure from the frontend's error message all the way down to this root cause, then restore it.
3. `kubectl set image deployment/backend -n capstone backend=localhost:5000/capstone-backend:99.0.0-typo` — diagnose the rollout getting stuck (Day 4's exact technique) and roll it back.
4. `kubectl patch resourcequota capstone-quota -n capstone --type=merge -p '{"spec":{"hard":{"pods":"3"}}}'` — try to scale `frontend` up and watch it fail. Explain why using Day 10's model, then revert.

See `EXERCISES.md` for the graded version of this scenario, plus the course's final self-assessment checklist. If you get stuck on any of the four break scenarios (or the one you invent yourself in Exercise 5), [Debugging Common Kubernetes Issues](../TROUBLESHOOTING.md) is the same addendum every earlier day pointed you to — by now, you shouldn't need it as often as Day 3 did.

## 4. Clean up

```bash
helm uninstall capstone -n capstone
kubectl delete namespace capstone
```

Next: `EXERCISES.md` — the final scenario and your 23-day mastery checklist.
