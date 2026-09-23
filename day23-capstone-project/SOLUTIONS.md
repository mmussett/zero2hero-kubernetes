---
---
# Day 23 — Solutions

## Exercise 1
```bash
kubectl patch networkpolicy allow-frontend-to-backend -n capstone --type=json \
  -p='[{"op":"replace","path":"/spec/ingress/0/from/0/podSelector/matchLabels/app","value":"nonexistent"}]'
curl http://capstone.zero2hero.local/
# "Backend status: UNREACHABLE"
kubectl exec -n capstone deploy/frontend -- curl -s -m 3 backend/ || echo BLOCKED
kubectl describe networkpolicy allow-frontend-to-backend -n capstone
```
`describe` shows the policy's `Allow ingress from` now lists `PodSelector: app=nonexistent` — no Pod carries that label, so the policy allows traffic from nothing, functionally identical to a full deny for `backend`'s ingress (recall Day 14 Exercise 4's "policy with no effect" logic, applied here as "policy effectively denies everything" instead). Root cause: a bad label selector value. Fix:
```bash
kubectl patch networkpolicy allow-frontend-to-backend -n capstone --type=json \
  -p='[{"op":"replace","path":"/spec/ingress/0/from/0/podSelector/matchLabels/app","value":"frontend"}]'
kubectl exec -n capstone deploy/frontend -- curl -s -m 3 backend/   # works again
```

## Exercise 2
```bash
kubectl scale statefulset redis -n capstone --replicas=0
curl http://capstone.zero2hero.local/
# "Backend status: UNREACHABLE" or hits shows "?"
kubectl logs -n capstone -l app=backend --tail=20
# redis.exceptions.ConnectionError: Error connecting to redis:6379 ... Name or service not known / Connection refused
kubectl exec -n capstone deploy/backend -- curl -s -m 3 -o /dev/null -w "%{http_code}\n" localhost:8080/healthz
# 503 — backend's OWN /healthz correctly reports "degraded" once it can't reach Redis
kubectl get pods -n capstone -l app=redis
# no Pods — StatefulSet scaled to 0
```
Full chain: **frontend shows "UNREACHABLE"** because → **backend's `/`, called by frontend, returns an error** because → **backend's own `redis.Redis` client can't connect** because → **`redis-0` doesn't exist at all**, because → **the StatefulSet was scaled to 0**. Note this exact chain is *exactly* what Day 23's app-level `/healthz` design (each tier checking its own dependency and reporting `degraded` rather than crashing) was built to make diagnosable — this is the same principle as Day 3's readiness probes, applied at the application layer.
```bash
kubectl scale statefulset redis -n capstone --replicas=1
kubectl wait --for=condition=ready pod redis-0 -n capstone --timeout=60s
curl http://capstone.zero2hero.local/   # recovered
```

## Exercise 3
```bash
kubectl set image deployment/backend -n capstone backend=localhost:5000/capstone-backend:99.0.0-typo
kubectl rollout status deployment/backend -n capstone --timeout=30s || true
kubectl get pods -n capstone -l app=backend
# some Pods: ImagePullBackOff / ErrImagePull
kubectl describe pod -n capstone -l app=backend | grep -A3 Events | tail -10
```
Same diagnosis pattern as Day 2 Exercise 3 and Day 4 Exercise 4: `ErrImagePull`/`ImagePullBackOff`, and because the Deployment's `maxUnavailable: 0` (set in `backend.yaml`) blocks the rollout from removing any old, working Pods until enough new ones are Ready — which never happens — the site **stays fully functional throughout**, serving 100% from the old ReplicaSet, exactly as Day 4's rolling-update safety guarantee promised.
```bash
kubectl rollout undo deployment/backend -n capstone
# OR, equivalently and more "correctly" for a Helm-managed release:
helm upgrade capstone capstone/ --set images.backend=localhost:5000/capstone-backend:1.0.0
```
Either works technically (`kubectl rollout undo` acts directly on the Deployment object); `helm upgrade` back to the last-known-good `values` is the more correct choice for anything Helm-managed long-term, since a bare `kubectl rollout undo` leaves Helm's own release state (`helm get values`) still pointing at the broken tag — the next `helm upgrade` from that stale state would silently reintroduce the bug. Reconciling the source of truth (Helm's values) rather than just the live object is the safer habit.

## Exercise 4
```bash
kubectl patch resourcequota capstone-quota -n capstone --type=merge -p '{"spec":{"hard":{"pods":"3"}}}'
kubectl scale deployment frontend -n capstone --replicas=5
kubectl get pods -n capstone | grep -c frontend
kubectl describe resourcequota capstone-quota -n capstone
kubectl get events -n capstone --sort-by=.lastTimestamp | tail -5
```
`describe resourcequota` shows `pods: <current-count>/3` at the hard cap; Events on the ReplicaSet show `Error creating: pods "frontend-xxxx" is forbidden: exceeded quota: capstone-quota, requested: pods=1, used: pods=3, limited: pods=3` — identical mechanism to Day 10 Exercise 2: **admission-time rejection**, not a scheduling failure — the Pod objects for the excess replicas are never created at all, so they don't even show as `Pending`, they simply don't exist. This distinction (admission rejection vs. scheduling failure) is exactly why `kubectl describe resourcequota` — not `kubectl get pods` — is the first place to look when a Deployment's replica count doesn't match what you asked for and no Pods show any scheduling-related error at all.
```bash
kubectl patch resourcequota capstone-quota -n capstone --type=merge -p '{"spec":{"hard":{"pods":"20"}}}'
kubectl get pods -n capstone | grep -c frontend   # now 5
```

## Exercise 5
No answer key by design — the graded skill here is the diagnostic method itself: observe the actual symptom (don't assume), form one specific hypothesis, verify it with exactly one targeted `kubectl` command before acting, apply the smallest fix that addresses the root cause, then confirm the fix worked end-to-end (not just "the error message went away"). If you can narrate that process out loud for a failure you invented yourself, with no prior knowledge of what you broke, you've demonstrated the actual capability this whole course was built to teach — everything else was the vocabulary and the tools to make that process possible.
