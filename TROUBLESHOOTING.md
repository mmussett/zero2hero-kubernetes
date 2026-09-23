---
---
# Debugging Common Kubernetes Issues — A Beginner's Field Guide

This is the addendum every day's own **Troubleshooting** section links back to. Where a day's section covers issues specific to that day's topic, this file covers the issues that show up **everywhere**, regardless of which day you're on — the ones almost every beginner hits at some point between Day 1 and Day 23. Bookmark it; you will come back to it.

## How to debug anything in Kubernetes — the method, not just the symptoms

Before the specific issues below, internalize this sequence. It solves the overwhelming majority of problems in this course and in real clusters, in this order:

1. **`kubectl get pods`** — what's the `STATUS` column say? Note it exactly; it names the failure category.
2. **`kubectl describe pod <name>`** — scroll to the **Events** section at the bottom. This is the single highest-signal command in Kubernetes. Read it bottom-to-top (most recent last) or top-to-bottom by timestamp — either way, read *every* line before acting.
3. **`kubectl logs <pod> [-c container] [--previous]`** — what did the application itself say? `--previous` gets logs from a container that already crashed and restarted, otherwise you're reading the new attempt's (empty) logs.
4. **`kubectl get events --sort-by=.lastTimestamp -A`** — every Event across the whole cluster, in one chronological stream, instead of scoped to one object. Reach for this specifically when:
   - You don't know *which* object is broken yet (a Deployment scaled up but you're not sure which Pod, if any, is the problem).
   - The failure happened **before** a Pod object even existed — a quota rejection (Day 10) or an admission-policy denial (Day 17) can prevent creation entirely, so there's no Pod to `describe` at all, but the rejection still shows up here.
   - Something cluster-wide changed recently and you want to see everything that happened around that time, across every namespace, without checking object by object.

   `kubectl describe <object>` shows you Events **for that one object only** — it's `get events` filtered down and formatted nicely. `kubectl get events` is the wider net you cast when `describe` requires you to already know the right object to point it at.
5. Only *then* start changing things. Changing YAML before you've read the Events is how a five-minute problem becomes a fifty-minute one.

If you remember nothing else from this file, remember: **`describe`, then `logs`, then `get events` — in that order, every time, before you touch anything.**

---

## 1. Pod won't even start

### `ImagePullBackOff` / `ErrImagePull`

**What you see:** `kubectl get pods` shows `STATUS: ImagePullBackOff` (or briefly `ErrImagePull` before backoff kicks in).

**What it means:** the kubelet cannot pull the image named in `spec.containers[].image`.

**Diagnose:**
```bash
kubectl describe pod <name> | grep -A5 Events
```
Read the exact message — it tells you which of the causes below applies.

**Common causes & fixes:**
| Cause | Fix |
|---|---|
| Typo in image name or tag | Fix the manifest, re-`apply` |
| Image genuinely doesn't exist at that tag | Confirm with `docker pull <same-image>` from your terminal — if that fails too, the image/tag is wrong, not Kubernetes |
| Private registry, no credentials | Create an `imagePullSecret` (`kubectl create secret docker-registry ...`) and reference it in `spec.imagePullSecrets` |
| Using `localhost:5000/...` (this course's local registry) but the registry container isn't running, or k3s's `containerd` isn't configured to trust it | See Day 1 §2.6 and Day 2 §3.5 — confirm `docker ps --filter name=registry` shows it running, and `/etc/rancher/k3s/registries.yaml` exists |
| Rate-limited by a public registry (Docker Hub) | Wait, or authenticate to raise your rate limit |

### `CrashLoopBackOff`

**What you see:** `STATUS: CrashLoopBackOff`, `RESTARTS` climbing, growing delay between restarts.

**What it means:** the container starts, then **exits** (successfully or not) faster than the kubelet expects a real long-running process to, and `restartPolicy: Always` (or `OnFailure`, on a nonzero exit) keeps retrying with exponential backoff.

**Diagnose:**
```bash
kubectl logs <name>              # what did it print before dying?
kubectl logs <name> --previous   # if it's already mid-restart, get the PRIOR attempt's logs
kubectl describe pod <name>      # check "Last State: Terminated" — Reason and Exit Code
```

**Common causes & fixes:**
| Exit code / signal | Typical meaning | Fix |
|---|---|---|
| `0` (clean exit) | Your command is a one-shot script, not a server — e.g. `CMD ["echo", "hi"]` with no long-running process | Run the real server process, or use a Job (Day 9) instead of a Deployment if it's genuinely meant to finish |
| `1` (generic error) | Application crashed — check `logs` for a stack trace/error message | Fix the application bug the logs point to |
| `127` | Command not found (typo'd `CMD`/`ENTRYPOINT`, or the binary doesn't exist in this image) | Fix the Dockerfile's `CMD`; test with `docker run -it <image> sh` locally first |
| `137` (`128 + 9`, `SIGKILL`) | Almost always **OOMKilled** — check `describe pod` for `Reason: OOMKilled` explicitly | Raise `resources.limits.memory`, or fix a real memory leak |
| `143` (`128 + 15`, `SIGTERM`) | Graceful shutdown that took too long and got force-killed | Handle `SIGTERM` in your app, or raise `terminationGracePeriodSeconds` |

### `CreateContainerConfigError`

**What you see:** Pod stuck, never reaches `Running`, this exact reason in `describe`.

**What it means:** the Pod references a `ConfigMap` or `Secret` key (via `envFrom`, `env.valueFrom`, or a volume) that **doesn't exist** — the kubelet can't build the container's environment/mounts at all.

**Diagnose:**
```bash
kubectl describe pod <name>   # Events will name the exact missing ConfigMap/Secret/key
kubectl get configmap,secret  # confirm what actually exists, and compare names carefully
```

**Fix:** create the missing object first, or fix the typo'd name/key in the Pod spec — this is overwhelmingly a naming mismatch (Day 6).

### `InvalidImageName`

**What it means:** the image string itself is malformed (bad characters, missing registry syntax). Almost always a copy-paste error. Fix the string.

---

## 2. Pod stuck `Pending`

A `Pending` Pod was never even scheduled to a Node — this is fundamentally different from the crash-related states above, which all happen *after* scheduling.

**Diagnose (always start here):**
```bash
kubectl describe pod <name>   # Events section explains EXACTLY why the scheduler rejected every node
```

If the Pod doesn't even show up in `kubectl get pods` at all (a Deployment scaled up but you're missing replicas, with no matching Pod object to `describe`), it was likely rejected at **admission time** before a Pod was ever created — a `ResourceQuota` (Day 10) or admission policy (Day 17) can do this. In that case, `describe` has nothing to show you, so go straight to the cluster-wide view instead:
```bash
kubectl get events --sort-by=.lastTimestamp -n <namespace>
```
This catches the rejection Event even though no Pod object exists to `describe`.

**Common causes & fixes:**
| Events message contains... | Cause | Fix |
|---|---|---|
| `Insufficient cpu` / `Insufficient memory` | No Node has enough allocatable capacity for this Pod's `requests` | Lower the request, free up capacity, or add a Node |
| `didn't match Pod's node affinity/selector` | `nodeSelector`/`affinity` rules exclude every Node | Fix the selector, or label a Node to match (Day 10) |
| `node(s) had untolerated taint` | A taint on every candidate Node isn't tolerated by this Pod | Add a matching `toleration`, or remove the taint (Day 10) |
| `Unbound PersistentVolumeClaims` | A referenced PVC never bound to a PV | See the storage section below (Day 7) |
| No Events at all, `Pending` for a long time | Rare — check `kubectl get nodes` for a Node stuck `NotReady`, or the scheduler component itself (`kubectl get pods -n kube-system`) | Investigate node/control-plane health directly |
| Blocked by a `ResourceQuota` | This is actually **admission-time rejection**, not scheduling — the Pod may not even exist yet | `kubectl describe resourcequota -n <ns>`; see Day 10 |

---

## 3. Pod is `Running` but something's still wrong

### `READY 0/1` while `STATUS: Running`

**What it means:** the container process is alive, but its **readiness probe is failing** — it's deliberately excluded from Service endpoints (Day 3, Day 5).

**Diagnose:**
```bash
kubectl describe pod <name>   # "Readiness probe failed: ..." with the exact HTTP status/error
kubectl exec <name> -- curl -v localhost:<port><path>   # reproduce the probe's own check manually
```
**Fix:** either the app genuinely isn't ready (check its own startup logs) or the probe's `path`/`port` is simply wrong — the single most common cause.

### Liveness probe restart-looping a healthy-but-slow app

**Symptom:** `RESTARTS` climbing on a container whose logs show no crash — it was killed and restarted by the **kubelet**, not by its own code.

**Fix:** the `livenessProbe` is too aggressive for how long the app actually takes to respond under load/GC pause. Increase `initialDelaySeconds`/`timeoutSeconds`/`failureThreshold`, or add a `startupProbe` (Day 3) to give slow starts more room before liveness checks even begin.

### `OOMKilled`

**What you see:** `Reason: OOMKilled`, exit code `137`, possibly with no obvious crash in the app's own logs (the kernel killed it, the app never got a chance to log anything).

**Fix:** raise `resources.limits.memory` if the usage is legitimate (confirm with `kubectl top pod`, Day 16/18), or fix a real leak if usage climbs unbounded over time.

### `Evicted`

**What you see:** Pod `STATUS: Evicted`, removed from its Node entirely (not restarted in place).

**What it means:** the **Node** ran low on memory/disk and the kubelet evicted lower-priority Pods to protect itself — this is a Node-level pressure response, distinct from one container's own `resources.limits` (Day 10's QoS classes decide eviction order).

**Fix:** `kubectl describe node <node>` for `Conditions` like `MemoryPressure`/`DiskPressure`; free up Node resources, or set proper `requests` so the scheduler doesn't overcommit that Node in the first place.

---

## 4. Networking: "I can't reach my app"

The single most useful diagnostic habit here: **isolate which hop is broken** — Pod itself, Service, or Ingress — rather than guessing at the whole chain.

```bash
# Hop 1: does the Pod work directly, bypassing Service/Ingress entirely?
kubectl port-forward pod/<pod-name> 8080:<container-port>
curl localhost:8080/

# Hop 2: does the Service work, bypassing Ingress?
kubectl port-forward svc/<service-name> 8080:<service-port>
curl localhost:8080/

# Hop 3: only now suspect Ingress/Gateway if hops 1-2 both worked
```

### Service has no endpoints

```bash
kubectl get endpoints <service-name>   # ENDPOINTS column: <none>?
```
**Cause:** the Service's `selector` matches zero Pods (typo'd label — the single most common Service bug, Day 5), or it matches Pods that are all failing readiness (see above).
**Fix:** `kubectl get pods --show-labels` and compare against the Service's `spec.selector` character-by-character.

### "Connection refused" vs. "connection timed out" — they mean different things

| Error | Meaning | Look at |
|---|---|---|
| `Connection refused` | Something answered at that IP:port and actively said "no" — a process IS listening on the target host, but not on the port you asked for (or nothing's listening on that specific port at all) | Is your app actually listening on the port your Service/probe expects? (`containerPort` vs. the app's real `PORT` env var — a very common mismatch) |
| `Connection timed out` | Nothing answered at all — the packet never got a response | NetworkPolicy blocking it (Day 14)? Wrong IP/Service entirely? Firewall between Nodes? |

### DNS resolution failures

```bash
kubectl exec <pod> -- nslookup <service-name>
kubectl exec <pod> -- cat /etc/resolv.conf
```
See Day 15 in full for the complete resolution path; the two most common beginner mistakes: using a bare short name across namespaces (needs `<svc>.<namespace>`, Day 15 §Exercise 4), and CoreDNS itself being unhealthy (`kubectl get pods -n kube-system -l k8s-app=kube-dns`).

### NodePort/LoadBalancer unreachable from outside

Confirm you're hitting the right port (`kubectl get svc` — the `NodePort` is the *second* port number shown, not the Service's own `port`), and that nothing else on the host already owns it (`sudo ss -tulnp | grep <port>`).

---

## 5. "Forbidden" / permission errors

```bash
kubectl auth can-i <verb> <resource> --as=<user-or-serviceaccount> -n <namespace>
```
This single command (Day 16) answers "would this be allowed" without trial-and-error. If the answer is `no`, you're missing a `Role`/`ClusterRole` + `RoleBinding`/`ClusterRoleBinding` granting that verb on that resource to that subject — walk through Day 16 again for the exact objects needed. If you're inside a Pod calling the API and get `Forbidden`, remember every Pod authenticates as its **ServiceAccount** (default: the namespace's `default` SA, which has zero permissions by design) — not as you.

---

## 6. Storage issues

### PVC stuck `Pending` forever

```bash
kubectl describe pvc <name>   # Events explain why nothing bound
```
**Common causes:** no `StorageClass` exists matching the requested one (typo, or none installed — k3s's default is `local-path`, confirm with `kubectl get storageclass`); a *static* PV exists but its capacity/access-mode doesn't match the claim (Day 7).

### `multi-attach error for volume ... Volume is already exclusively attached`

**Cause:** a `ReadWriteOnce` volume is already mounted by a Pod on a **different** Node, and you're trying to schedule a second Pod using the same PVC (Day 7 §1.3). **Fix:** confirm you actually need RWX instead of RWO, or ensure only one Pod at a time uses that claim.

### Permission denied writing inside a mounted volume

**Cause:** the container runs as a non-root UID (correctly, per Day 14/17) but the volume's on-disk ownership doesn't match. **Fix:** set `securityContext.fsGroup` at the Pod level so the kubelet `chown`s the volume to that group on mount.

---

## 7. kubectl and cluster-connectivity issues

### `The connection to the server <IP>:6443 was refused`

**Cause:** `k3s` itself isn't running. `sudo systemctl status k3s` — if it's not `active`, `sudo systemctl start k3s` (Day 2 §3.4/3.9).

### `error: You must be logged in to the server (Unauthorized)`

**Cause:** your `~/.kube/config` credentials are stale/wrong, or `KUBECONFIG` points somewhere unexpected. Check `echo $KUBECONFIG` and `kubectl config view --minify`; re-copy `/etc/rancher/k3s/k3s.yaml` per Day 2 §3.3 if needed.

### `error: context "..." does not exist`

You typo'd a `--context` name, or never had it. `kubectl config get-contexts` to see what's actually available (Day 2 §4.5).

### Everything "hangs" with no error at all

Usually a `kubectl port-forward` or `proxy` left running in a background shell from an earlier step, silently holding the port/terminal. Check `jobs`, `kill %1` (or whichever job number), and retry.

---

## 8. General principles that resolve half of everything above

- **`kubectl describe` before you Google the error message.** The Events section usually contains the exact, specific reason — a generic web search sends you down unrelated paths first.
- **One change at a time.** If you fix three things simultaneously and it works, you don't know which one mattered — you'll be back here next time with the same uncertainty.
- **Compare against a manifest you know works.** Every day's `manifests/` folder has a working baseline — diff your broken version against it before assuming something exotic is wrong.
- **Never assume a resource exists — check.** `kubectl get <kind> <name> -n <namespace>` costs one command and eliminates an entire category of "but I definitely created that" debugging.
- **Read the whole error message, not just the first line.** Kubernetes error strings are unusually information-dense; the actual root cause is often in the second half of the sentence.

---

Still stuck after working through this file and the specific day's own **Troubleshooting** section? That's exactly what `kubectl get events --sort-by=.lastTimestamp -A` and `kubectl describe` on every object in the chain (Pod → Service → Ingress/Gateway, in order) are for — there is almost always a specific, discoverable reason, not a mysterious one.
