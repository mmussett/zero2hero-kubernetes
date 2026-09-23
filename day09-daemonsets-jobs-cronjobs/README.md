# Day 9 — DaemonSets, Jobs & CronJobs

## Learning objectives
- Use a DaemonSet to run exactly one Pod per Node
- Distinguish Jobs from Deployments: run-to-completion vs. run-forever
- Control Job parallelism and retry behavior
- Schedule recurring work with CronJobs and understand concurrency policy
- Know which controller fits a given workload shape without hesitating

## 1. Concepts

By Day 9 you've seen three controllers that all "manage Pods for you" in different shapes. Today adds the remaining three you'll meet in the wild, each solving a distinct scheduling problem Deployments/StatefulSets don't address:

### 1.1 Anatomy of a minimal Job

`job-minimal.yaml` is the smallest valid Job:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: hello-world
spec:
  template:
    spec:
      restartPolicy: Never     # required — Never or OnFailure, but not Always (Day 3)
      containers:
        - name: hello-world
          image: busybox:1.36
          command: ["echo", "Hello, minimal world!"]
```

The only thing that actually distinguishes this from a bare Pod manifest (Day 3) is `kind: Job` wrapping the Pod template one level deeper, plus `restartPolicy: Never`. `completions` and `backoffLimit` (§1.3) both have working defaults (`1` and `6`) — you don't need either until you want something other than "run once, retry up to 6 times." DaemonSets and CronJobs (below) follow the exact same "wrap a familiar Pod template, add one controller-specific field" pattern — `nodeSelector`/no `replicas` for a DaemonSet, `schedule` + `jobTemplate` (itself just this same Job shape, nested once more) for a CronJob.

### 1.2 DaemonSet — one Pod per Node, always

A [**DaemonSet**](https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/) ensures every Node (or every Node matching a `nodeSelector`) runs exactly one copy of a Pod. Add a Node to the cluster, and the DaemonSet controller schedules a copy there automatically — no `replicas` field exists because "how many" is defined entirely by "how many Nodes." Remove a Node, and its copy is cleaned up with it.

**Real-world uses:** log collectors (Fluent Bit, Filebeat), metrics agents (node-exporter — this is exactly what powers `kubectl top node`, Day 18), CNI plugins, storage daemons, security/compliance agents — anything that must observe or act on *every* Node individually, as opposed to "N copies of a service, anywhere is fine" (that's what a Deployment is for).

### 1.3 Job — run to completion, not forever

A [**Job**](https://kubernetes.io/docs/concepts/workloads/controllers/job/) creates Pod(s) that are expected to **exit successfully** and then be done — a Deployment would treat that same successful exit as a crash and restart it forever (with `restartPolicy: Always`), which is exactly wrong for batch work. A Job's Pod template must use `restartPolicy: Never` or `OnFailure`.

Key fields:
- `completions` — how many successful Pod completions are needed for the Job to be considered done (default 1).
- `parallelism` — how many Pods may run at once while working toward `completions`.
- `backoffLimit` — how many Pod failures are tolerated (with exponential backoff between retries, same mechanism as Day 3's CrashLoopBackOff) before the whole Job is marked `Failed` and given up on — unlike a bare Pod, a Job **does** eventually stop retrying.

**Real-world uses:** database migrations, batch data processing, one-off report generation, CI job runners, anything with a clear "done" state.

### 1.4 CronJob — a Job, on a schedule

A [**CronJob**](https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/) creates a new Job from `jobTemplate` on a [standard cron schedule](https://en.wikipedia.org/wiki/Cron) (`schedule: "*/2 * * * *"`). `concurrencyPolicy` decides what happens if a scheduled run fires while the previous run's Job is still active:

| Policy | Behavior |
|---|---|
| `Allow` (default) | Runs overlap freely |
| `Forbid` | Skip the new run entirely if the previous is still active |
| `Replace` | Cancel the still-running previous Job and start the new one |

`successfulJobsHistoryLimit`/`failedJobsHistoryLimit` cap how many old Job objects are kept around for inspection (`kubectl logs` on old runs) before being garbage collected.

### 1.5 Choosing the right controller — the full picture

| Controller | Shape of the workload |
|---|---|
| Deployment (Day 4) | Stateless, interchangeable replicas, run forever |
| StatefulSet (Day 8) | Stateful, identity-bearing replicas, run forever |
| DaemonSet | Exactly one per Node, run forever |
| Job | Run to completion, once (or N times), then stop |
| CronJob | Run to completion, on a recurring schedule |

### Official documentation
- [DaemonSet](https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/)
- [Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/)
- [CronJob](https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/)
- [Running Automated Tasks with a CronJob](https://kubernetes.io/docs/tasks/job/automated-tasks-with-cron-jobs/)
- [Parallel Processing using Expansions / Work Queues](https://kubernetes.io/docs/tasks/job/parallel-processing-expansion/)
- [Cron schedule syntax](https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/#cron-schedule-syntax)

## 2. Hands-on lab

```bash
cd day09-daemonsets-jobs-cronjobs/manifests

# 2.1 The absolute minimum
kubectl apply -f job-minimal.yaml
kubectl get pods -l job-name=hello-world
kubectl logs -l job-name=hello-world
kubectl delete -f job-minimal.yaml

# 2.2 DaemonSet
kubectl apply -f daemonset.yaml
kubectl get daemonset node-agent
kubectl get pods -l app=node-agent -o wide   # one per node (just 1 in this single-node lab)
kubectl logs -l app=node-agent --tail=3

# 2.3 Simple Job
kubectl apply -f job-simple.yaml
kubectl get jobs -w                # watch COMPLETIONS go 0/1 -> 1/1
kubectl get pods -l job-name=hello-job
kubectl logs -l job-name=hello-job

# 2.4 Parallel Job
kubectl apply -f job-parallel.yaml
kubectl get pods -l job-name=parallel-job -w   # never more than 2 at once, 6 total completions

# 2.5 A Job that exhausts its retries
kubectl apply -f job-failing.yaml
kubectl get pods -l job-name=doomed-job -w      # 3 attempts total (backoffLimit: 2 = 1 initial + 2 retries)
kubectl get job doomed-job -o jsonpath='{.status.conditions[0].type}'; echo   # Failed
kubectl describe job doomed-job | tail -10

# 2.6 CronJob
kubectl apply -f cronjob.yaml
kubectl get cronjob hello-cron
# wait ~2-4 minutes for at least one scheduled run
kubectl get jobs -l job-name --watch &
sleep 130; kill %1
kubectl get jobs
kubectl logs -l job-name=$(kubectl get jobs -o jsonpath='{.items[0].metadata.name}')

# 2.7 Trigger a CronJob run immediately (without waiting for the schedule)
kubectl create job hello-cron-manual --from=cronjob/hello-cron
kubectl logs job/hello-cron-manual

# 2.8 Clean up
kubectl delete -f .
kubectl delete job hello-cron-manual
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| DaemonSet's `DESIRED` count is lower than your actual Node count | A `nodeSelector`/taint on the DaemonSet's template excludes some Nodes — this is often intentional, but confirm it's what you meant | `kubectl get nodes --show-labels` and compare against the DaemonSet's `nodeSelector`; check `tolerations` against real Node taints |
| Job's Pod runs forever, never reaches `Completed` | The container's command never exits (it's behaving like a server, not a batch task) | Confirm the command genuinely finishes and exits `0`; a Job's Pod must actually terminate to count as complete |
| Job shows `Failed`, no more Pods being created | `backoffLimit` was exhausted — this is intentional, not a bug (Day 9 §1.3) | `kubectl describe job <name>` for the failure Events; fix the underlying issue and re-`apply` a fresh Job (Jobs aren't restartable once `Failed`) |
| CronJob never seems to run | Schedule syntax error, or `concurrencyPolicy: Forbid` skipping runs because a previous one never finished | `kubectl describe cronjob <name>` shows `Last Schedule Time`; `kubectl get jobs` to see if runs *are* happening but silently failing |
| CronJob's job history is empty even though it's clearly run before | `successfulJobsHistoryLimit`/`failedJobsHistoryLimit` pruned old Jobs — this is expected garbage collection, not data loss (there was nothing to preserve beyond those limits) | Increase the history limit *before* the next run if you need to keep more, or check external logs (Day 16/18) for historical output |

See also: [Debugging Common Kubernetes Issues](../TROUBLESHOOTING.md).

## 3. Key commands reference

| Command | Purpose |
|---|---|
| `kubectl get daemonset` (`ds`) | List DaemonSets; `DESIRED`/`CURRENT`/`READY` track Node count |
| `kubectl get jobs` | List Jobs and their completion counts |
| `kubectl get cronjob` (`cj`) | List CronJobs and their next/last schedule times |
| `kubectl create job <name> --from=cronjob/<cronjob-name>` | Manually trigger one run immediately |
| `kubectl delete job <name>` | Also deletes that Job's Pods (unless `--cascade=orphan`) |

Next: [Day 10 — Namespaces & Resource Management](../day10-namespaces-and-resource-management/README.md)
