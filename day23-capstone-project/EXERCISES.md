---
---
# Day 23 — Final Exercises & Course Assessment

These four scenarios are the four "breaks" introduced in `README.md` section 3, formalized as graded exercises. Work through each independently, in order, reverting your fix before starting the next. For each one, write down: (a) the exact `kubectl` commands you used to diagnose it, (b) the root cause, (c) the fix.

## Exercise 1 — NetworkPolicy diagnosis
Apply the NetworkPolicy break from README section 3, item 1. Using only reachability testing and `kubectl describe networkpolicy` (Day 14's techniques — no reading the chart's YAML source), determine exactly why `frontend` can no longer reach `backend`, and fix it with a `kubectl patch` or `kubectl edit`.

[→ solution](SOLUTIONS.md#exercise-1)

## Exercise 2 — Cascading failure from storage
Apply the Redis scale-to-zero break from README section 3, item 2. Starting from `curl http://capstone.zero2hero.local/` showing "Backend status: UNREACHABLE" (or similar), work **backward** through the stack — check backend Pod logs, backend's own `/healthz`, then Redis — to find the actual root cause. Write out the full chain of "X is broken because Y is broken because Z is broken."

[→ solution](SOLUTIONS.md#exercise-2)

## Exercise 3 — Stuck rollout diagnosis and rollback
Apply the bad image break from README section 3, item 3. Use `kubectl rollout status`, `kubectl get pods -n capstone`, and `kubectl describe pod` on the stuck Pod to confirm the exact failure reason (Day 4/Day 2's technique), then roll back using `kubectl rollout undo` or `helm upgrade` (either is valid — explain which you chose and why).

[→ solution](SOLUTIONS.md#exercise-3)

## Exercise 4 — Quota-induced scheduling failure
Apply the tightened quota from README section 3, item 4. Try `kubectl scale deployment frontend -n capstone --replicas=5`. Confirm via `kubectl describe resourcequota` and `kubectl get events -n capstone` exactly why it's blocked, referencing Day 10's model of admission-time rejection (not scheduling-time).

[→ solution](SOLUTIONS.md#exercise-4)

## Exercise 5 — Design your own break
Introduce one failure of your own choosing, anywhere in the stack, that isn't one of the four above (ideas: a typo'd `readinessProbe` path, an over-restrictive `LimitRange`, an `imagePullPolicy` issue, a `ResourceQuota` memory cap, a broken `ingressClassName`). Diagnose and fix it using the same "observe symptoms, form a hypothesis, verify with one targeted command, fix, confirm" method you've now used all course. This is the exercise with no answer key — the skill is the point.

---

[→ solution](SOLUTIONS.md#exercise-5)

## Final self-assessment checklist

Check off each item honestly — for anything you can't do confidently without looking it up, that's your best signal for what to revisit before considering yourself "done":

**Foundations**
- [ ] I can explain the difference between an image and a container, and why layers matter
- [ ] I can install a k3s cluster from scratch, including diagnosing a failed install
- [ ] I can write a Pod manifest from memory, including probes and resource requests/limits
- [ ] I understand the Deployment → ReplicaSet → Pod ownership chain and can perform a safe rolling update and rollback
- [ ] I can explain how a Service routes traffic to Pods, end to end, including DNS

**Workloads, Config & Storage**
- [ ] I know when to use a ConfigMap vs. a Secret, and their real security limitations
- [ ] I can provision persistent storage both statically and dynamically, and explain reclaim policy risk
- [ ] I can explain what a StatefulSet gives you that a Deployment can't, concretely
- [ ] I know which controller (Deployment/StatefulSet/DaemonSet/Job/CronJob) fits a given workload shape without hesitating
- [ ] I can enforce namespace-level resource budgets and explain QoS classes

**Networking**
- [ ] I can configure host- and path-based Ingress routing, including the path-stripping gotcha
- [ ] I can write a default-deny NetworkPolicy and layer specific allow rules on top, remembering the DNS trap
- [ ] I can explain the full DNS resolution path from a Pod to a Service IP

**Security**
- [ ] I can write RBAC rules granting exactly the permissions a workload needs, and verify with `kubectl auth can-i`
- [ ] I can write a hardened `securityContext` and explain each field's purpose
- [ ] I can enforce Pod Security Standards namespace-wide and read a rejection message
- [ ] I understand tags vs. digests and why `:latest` is a supply-chain risk

**Observability & Packaging**
- [ ] I can query live metrics with `kubectl top` and basic PromQL/LogQL
- [ ] I can read and write a Helm chart, including values layering and rollback

**Scaling & Extensibility**
- [ ] I can configure and explain HPA's scaling decisions, and know what VPA/Cluster Autoscaler each add
- [ ] I can choose between RollingUpdate, blue-green, and canary based on risk tolerance
- [ ] I understand what a CRD does (and doesn't do) and what an Operator adds on top
- [ ] I can use Kustomize overlays to manage environment variants without templating

**The capstone test**
- [ ] Given a broken multi-tier application I've never seen before, I can diagnose the root cause using only `kubectl` — no guessing, no random restarts — and explain my reasoning at each step

If every box is checked: you started this course with zero Kubernetes skills twenty-three days ago. You are, by any reasonable definition, no longer a beginner. Go build something real.

