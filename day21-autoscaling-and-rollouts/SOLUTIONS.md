# Day 21 — Solutions

## Exercise 1
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: scratch-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: php-apache
  minReplicas: 1
  maxReplicas: 4
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 60
```
```bash
kubectl apply -f scratch-hpa.yaml
kubectl get hpa scratch-hpa -w   # ctrl-c once TARGETS shows a real %
kubectl delete -f scratch-hpa.yaml
```
If `TARGETS` stayed `<unknown>`, the most common cause is the target Deployment missing `resources.requests.cpu` — `hpa-app.yaml`'s `php-apache` already sets it, which is precisely why this works without any extra setup (section 1.1).

## Exercise 2
```bash
sed -i 's/averageUtilization: 50/averageUtilization: 20/' hpa.yaml
kubectl apply -f hpa.yaml
kubectl apply -f load-generator.yaml
sleep 90
kubectl get hpa php-apache
```
Yes — for the same actual CPU load, a **lower** target utilization percentage produces a **higher** desired replica count. Directly from the formula `desiredReplicas = ceil(currentReplicas × (currentMetricValue / desiredMetricValue))`: shrinking the denominator (`desiredMetricValue`, i.e. the target) while the numerator (actual usage) stays the same increases the ratio, and therefore the computed desired replica count — a target of 20% effectively says "I want each Pod running at only 20% of its CPU request, so I need proportionally more Pods to absorb the same total load with that much headroom per Pod."

## Exercise 3
```bash
kubectl describe hpa php-apache | tail -15
```
Events/Conditions show something like `ScalingLimited: True (reason: TooManyReplicas)` — the HPA's own control loop explicitly reports that its computed desired replica count exceeds `maxReplicas` and that it's capping at the configured ceiling rather than scaling further, even though the metric itself is still well above target. In the real world, an HPA persistently pinned at `maxReplicas` under genuine sustained load is a strong, actionable signal that either (a) `maxReplicas` was set too conservatively for real traffic and should be raised, or (b) the cluster itself may be running out of Node capacity to actually schedule more replicas even if `maxReplicas` were raised — exactly the trigger condition Cluster Autoscaler (section 1.3) is designed to react to in a cloud environment.

## Exercise 4
```yaml
metrics:
  - type: Resource
    resource: {name: cpu, target: {type: Utilization, averageUtilization: 50}}
  - type: Resource
    resource: {name: memory, target: {type: Utilization, averageUtilization: 70}}
```
Per the [HPA docs on multiple metrics](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/#support-for-multiple-metrics), the HPA computes a desired replica count **independently for each metric**, then takes the **largest** (most conservative/safest, i.e. "scale out the most") of those computed values as the final decision — never an average. This makes sense operationally: if CPU says "3 replicas is enough" but memory says "you need 5 replicas to keep memory utilization in check," using anything less than 5 would leave the workload under memory pressure — HPA always errs toward whichever metric demands the most capacity.

## Exercise 5
```bash
kubectl apply -f bluegreen-blue.yaml -f bluegreen-green.yaml
GREEN_POD=$(kubectl get pod -l track=green -o jsonpath='{.items[0].metadata.name}')
kubectl port-forward pod/$GREEN_POD 8090:8080 &
curl localhost:8090/   # "I am GREEN" — verified in complete isolation, zero production traffic involved
kill %1
kubectl apply -f bluegreen-service.yaml
kubectl patch service hello-bg-svc -p '{"spec":{"selector":{"track":"green"}}}'
```
This ordering is the entire safety value of blue-green: you validate the **exact** Pods that will serve production traffic, running at full target scale, in the real cluster environment — before any real user request ever reaches them. A plain `RollingUpdate` over `blue` directly offers no equivalent isolated verification step — new Pods start receiving live production traffic (a fraction of it, per `maxSurge`/`maxUnavailable`) the moment they pass their readiness probe, meaning your *first* signal that something is subtly wrong (a readiness probe can't catch every bug) is real users hitting it, not a controlled pre-check.

## Exercise 6
```bash
kubectl scale deployment hello-canary-canary --replicas=0
for i in $(seq 1 20); do curl -s localhost:8081/ | grep -o '"message":"[^"]*"'; done | sort | uniq -c
# 20 STABLE, 0 CANARY
```
This "rollback" is effectively instant — a single `kubectl scale --replicas=0` command, taking effect the moment the canary Pod terminates (seconds). Compare to `kubectl rollout undo` mid-`RollingUpdate`: it's also fast in absolute terms, but it must still perform a **second rolling transition** (scaling the bad ReplicaSet down and the previous-good ReplicaSet back up, respecting `maxUnavailable`/readiness the whole way) — meaningfully slower than simply zeroing out a canary's replica count, and during that undo window *some* fraction of traffic is still hitting the bad version until the rollback rolling-update itself completes. Canary's fast, low-blast-radius rollback (zero the canary, no rolling transition needed for the untouched stable majority) is one of its core advantages over relying on rolling-update-and-undo alone for risky changes.

## Exercise 7
`updateMode: "Off"` means VPA computes and continuously **exposes recommended `requests`/`limits`** (viewable via `kubectl describe vpa <name>` or the `VerticalPodAutoscaler` object's `.status.recommendation`) based on real observed historical usage, but takes **zero automated action** — it never modifies, evicts, or resizes any actual Pod. A team deliberately runs `Off` mode for an extended period before ever switching to `Auto` because: (1) it lets them **observe and sanity-check** VPA's recommendations against their own judgment and any known upcoming traffic patterns (seasonal spikes, planned load tests) before trusting an automated system to act on those numbers unsupervised; (2) `Auto` mode's resizing has historically meant **evicting and recreating** Pods to apply new resource values (before in-place resize support), which is itself a disruptive event a team wants to fully understand the frequency/timing of before allowing it to happen automatically on a production workload; (3) it builds institutional trust in the tool incrementally — the same "audit → warn → enforce" caution pattern you already saw with Pod Security Standards on Day 17, applied here to an autoscaler instead of a security policy.
