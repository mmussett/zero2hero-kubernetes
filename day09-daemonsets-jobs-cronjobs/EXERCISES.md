# Day 9 — Exercises

## Exercise 1 — Write the minimal Job from scratch
Without looking at `job-minimal.yaml`, write a Job named `scratch-job` that runs `busybox:1.36` with the command `echo hello`. Apply it, confirm `kubectl get job scratch-job` shows `COMPLETIONS: 1/1`, check its logs, then delete it. You should not need to set `completions` or `backoffLimit` at all.

[→ solution](SOLUTIONS.md#exercise-1)

## Exercise 2 — DaemonSet node targeting
Add `nodeSelector: {agent-enabled: "true"}` to `daemonset.yaml`'s Pod template and re-apply. What happens to the existing Pod (check `kubectl get pods -l app=node-agent`)? Then label your node with `kubectl label node <your-node> agent-enabled=true` and observe again. Explain what this proves about how DaemonSets decide "every Node."

[→ solution](SOLUTIONS.md#exercise-2)

## Exercise 3 — Job completion count vs. parallelism math
Apply `job-parallel.yaml` and, using `kubectl get pods -l job-name=parallel-job -w`, record the exact sequence of Pod creation (timestamps optional, order is what matters). Confirm exactly 6 Pods reach `Completed` and never more than 2 are `Running` simultaneously. What would you change to make all 6 run at once instead?

[→ solution](SOLUTIONS.md#exercise-3)

## Exercise 4 — Job vs. bare Pod retry behavior
Compare `job-failing.yaml` (`backoffLimit: 2`) against Day 3's `pod-crashloop.yaml` (a bare Pod). Apply both. After 2 minutes, check `kubectl get pods` for both. Which one has stopped retrying, and which one is still retrying indefinitely? Explain the mechanism difference (Job-level `backoffLimit` vs. kubelet-level `restartPolicy` retry with no attempt cap).

[→ solution](SOLUTIONS.md#exercise-4)

## Exercise 5 — CronJob concurrencyPolicy
Change `cronjob.yaml`'s schedule to `"* * * * *"` (every minute) and its container command to `sleep 90` (longer than the schedule interval), keeping `concurrencyPolicy: Forbid`. Apply it and watch for ~3-4 minutes. Confirm overlapping runs are skipped (fewer Job objects than minutes elapsed). Then change to `concurrencyPolicy: Allow`, reapply, and observe overlapping Jobs running simultaneously.

[→ solution](SOLUTIONS.md#exercise-5)

## Exercise 6 — History limits
With `successfulJobsHistoryLimit: 3` in place, let `hello-cron` run at least 5 times (wait ~10 minutes, or repeatedly use `kubectl create job --from=cronjob/...` to simulate runs faster). Confirm via `kubectl get jobs` that only the 3 most recent successful Job objects remain. Why would an operations team deliberately want this limit low on a cluster running thousands of CronJobs?

[→ solution](SOLUTIONS.md#exercise-6)

## Exercise 7 (stretch) — TTL cleanup
Add `ttlSecondsAfterFinished: 30` to `job-simple.yaml`'s `spec`. Apply it, wait for it to complete, then wait 30+ more seconds. Confirm with `kubectl get jobs` that the Job object itself (and its Pod) is automatically deleted, with no manual `kubectl delete` needed. Explain why this is preferable to `successfulJobsHistoryLimit` for a very high-volume, ad-hoc (non-Cron) batch Job workload.

[→ solution](SOLUTIONS.md#exercise-7)
