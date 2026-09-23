---
---
# Day 9 — Solutions

## Exercise 1
```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: scratch-job
spec:
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: scratch-job
          image: busybox:1.36
          command: ["echo", "hello"]
```
```bash
kubectl apply -f scratch-job.yaml
kubectl get job scratch-job   # COMPLETIONS: 1/1
kubectl logs -l job-name=scratch-job
kubectl delete -f scratch-job.yaml
```
`completions` defaulted to `1` and `backoffLimit` to `6` — neither needed to be written, exactly as section 1.1 states. The only field that differs from a bare Pod spec is `restartPolicy: Never`.

## Exercise 2
```bash
kubectl apply -f daemonset-nodeselector.yaml   # daemonset.yaml + nodeSelector added
kubectl get pods -l app=node-agent
# the existing Pod is TERMINATED — no nodes currently match agent-enabled=true
kubectl label node $(kubectl get nodes -o jsonpath='{.items[0].metadata.name}') agent-enabled=true
kubectl get pods -l app=node-agent -w
# a new Pod is created almost immediately on the now-matching node
```
This proves the DaemonSet controller is **continuously** reconciling against the live set of Nodes matching its `nodeSelector` (or all Nodes, with none set) — it's not a one-time "create a Pod per Node at apply time" action. Adding or removing a matching label from a Node triggers the DaemonSet controller to create or delete that Node's Pod immediately, exactly like a Deployment reacting to a scale change.
```bash
kubectl label node $(kubectl get nodes -o jsonpath='{.items[0].metadata.name}') agent-enabled-
kubectl delete -f daemonset-nodeselector.yaml
```

## Exercise 3
```bash
kubectl apply -f job-parallel.yaml
kubectl get pods -l job-name=parallel-job -w
```
Typical sequence: Pods 1 and 2 start together (parallelism cap), and as each finishes, a new one starts to replace it — 3 and 4 fill in as 1/2 complete, then 5 and 6 — never more than 2 `Running` at once, but eventually all 6 reach `Completed`. To run all 6 simultaneously, set `parallelism: 6` (or omit it and rely on it defaulting to matching `completions`, though being explicit is clearer) — parallelism is only ever capped by this field (and by how many Pods the cluster can actually schedule at once).

## Exercise 4
```bash
kubectl apply -f job-failing.yaml
kubectl apply -f ../../day03-pods/manifests/pod-crashloop.yaml
sleep 120
kubectl get pods -l job-name=doomed-job
kubectl get pod crash-demo
```
`doomed-job`'s Pods stop appearing after 3 total attempts (1 initial + `backoffLimit: 2` retries) — `kubectl get job doomed-job` shows `Failed` in `status.conditions`, and no further Pods are created; the Job **gives up permanently**. `crash-demo` (the bare Pod, `restartPolicy: Always`) is still actively restarting with a climbing `RESTARTS` count and no upper bound — the kubelet's restart-with-backoff has no concept of "give up," because a Pod's `restartPolicy` describes container-level restart behavior only, with no equivalent to a Job's `backoffLimit`/overall-failure concept. This is precisely why Jobs — not bare Pods — are the correct primitive for "this must eventually either succeed or be reported as failed," which any batch/CI system requires.
```bash
kubectl delete -f job-failing.yaml
kubectl delete pod crash-demo
```

## Exercise 5
```yaml
spec:
  schedule: "* * * * *"
  concurrencyPolicy: Forbid
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: work
              command: ["sh", "-c", "sleep 90"]
```
```bash
kubectl apply -f cronjob-forbid.yaml
sleep 240
kubectl get jobs
```
With `Forbid` and a 90s run on a 60s schedule, roughly every other scheduled trigger is skipped (the previous run is still active when the next would fire) — over 4 minutes you see about 2-3 Jobs, not 4. Switching to `Allow` and repeating produces overlapping Jobs — `kubectl get pods -l job-name --show-labels` around the 2-3 minute mark shows two or more `parallel-job`-style Pods from *different* Job instances running concurrently, something `Forbid` specifically prevents.

## Exercise 6
```bash
for i in $(seq 1 5); do kubectl create job "manual-run-$i" --from=cronjob/hello-cron; sleep 8; done
kubectl get jobs
```
Only the 3 most recent Job objects created via the CronJob's own schedule are retained under `successfulJobsHistoryLimit: 3` — older ones are garbage collected automatically (note: manually-created Jobs via `--from=cronjob` are separate objects, not counted against the CronJob's own history limit, since they weren't created by the CronJob controller itself). An operations team keeps this limit low on a cluster running thousands of CronJobs because every retained Job object also retains its Pod object(s) — at scale, tens of thousands of stale, long-finished Job/Pod objects sitting in etcd measurably bloats `kube-apiserver`/etcd load (list/watch operations, storage size) for no operational benefit once you've verified a run succeeded.

## Exercise 7
```yaml
apiVersion: batch/v1
kind: Job
metadata: {name: hello-job-ttl}
spec:
  ttlSecondsAfterFinished: 30
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: work
          image: busybox:1.36
          command: ["sh", "-c", "echo done; sleep 5"]
```
```bash
kubectl apply -f job-ttl.yaml
kubectl wait --for=condition=complete job/hello-job-ttl --timeout=30s
sleep 35
kubectl get job hello-job-ttl
# Error from server (NotFound) — cleaned up automatically
```
`ttlSecondsAfterFinished` is driven by the [TTL-after-finished controller](https://kubernetes.io/docs/concepts/workloads/controllers/ttlafterfinished/), which deletes the Job (cascading to its Pods) that many seconds after it reaches a terminal state — regardless of *how* the Job was created (Cron-driven or ad-hoc/one-off). `successfulJobsHistoryLimit` only exists on `CronJob` and only counts/prunes Jobs it created itself; for a high-volume ad-hoc batch workload (e.g., a CI system creating thousands of one-off Jobs per day with no CronJob involved at all), `ttlSecondsAfterFinished` is the only built-in mechanism that prevents unbounded accumulation of finished Job/Pod objects.
