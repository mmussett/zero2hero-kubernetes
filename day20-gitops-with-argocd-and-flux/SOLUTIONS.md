---
---
# Day 20 — Solutions

## Exercise 1
```bash
# add templates/extra-configmap.yaml to the chart, commit, push
kubectl get configmap -n argocd-demo | grep extra    # appears automatically within one sync cycle
# remove the file, commit, push
sleep 30
kubectl get configmap -n argocd-demo | grep extra    # gone -- pruned automatically
```
With `prune: true`, ArgoCD treats Git as the **complete** desired state — anything it previously created that's no longer present in Git gets deleted automatically on the next sync. With `prune: false` (the ArgoCD default, notably NOT what today's automated Application used), the ConfigMap would be **left behind indefinitely** — ArgoCD stops "owning" it once it's removed from Git, but never deletes it proactively. Some teams deliberately choose `prune: false` specifically to avoid an accidental deletion in Git (a bad merge, a careless file removal) silently deleting live infrastructure — trading "some manual cleanup debt over time" for "never auto-delete something in production by mistake." This is a real, actively-debated GitOps configuration choice, not a settled best practice either way.

## Exercise 2
```bash
sed 's#path: day19-helm/chart/hello-chart#path: day19-helm/chart/does-not-exist#' argocd-application-hello-chart.yaml | \
  sed "s#REPO_URL_PLACEHOLDER#${REPO_URL}#" | kubectl apply -f -
kubectl get application hello-chart -n argocd -o jsonpath='{.status.conditions}'; echo
```
The Application's health/sync status reports an error condition (something like `ComparisonError` referencing the path not being found), and the ArgoCD UI shows the Application in a degraded/error state. Critically, this **only blocks future syncs** — the previously-deployed, already-running resources in `argocd-demo` are **left completely untouched**; ArgoCD doesn't tear down a working deployment just because its *next* sync attempt failed to even resolve a source. This is an important safety property: a broken Git commit degrades your ability to *change* the deployment further, but does not itself cause an outage of what's already correctly running.
```bash
sed "s#REPO_URL_PLACEHOLDER#${REPO_URL}#" argocd-application-hello-chart.yaml | kubectl apply -f -   # fix it back
```

## Exercise 3
```bash
# push a change, then just wait and time it
time (while [ "$(kubectl get helmrelease hello-chart -n flux-system -o jsonpath='{.status.lastAppliedRevision}')" == "$OLD_REV" ]; do sleep 2; done)
# push another change, immediately force it
flux reconcile source git zero2hero-repo
```
Without forcing, the change lands somewhere within the `interval: 1m` window (up to ~60s, since Flux polls rather than receiving a webhook by default in this simple setup — production Flux installs commonly add a Git webhook receiver to react instantly instead of waiting for the poll). `flux reconcile` triggers an immediate, out-of-band check, landing in a few seconds. The trade-off with a very short interval (`10s`) at scale: **every** `GitRepository` object independently polls its Git host on its own schedule — with hundreds of `GitRepository` objects across a large organization all polling every 10 seconds, this becomes meaningful, sustained load against the Git hosting provider (GitHub/GitLab rate limits are a real, commonly-hit constraint in large Flux deployments) — this is exactly why production setups favor webhooks (push-triggered reconciliation) over aggressively short polling intervals once they outgrow a single small demo repo.

## Exercise 4
```bash
argocd app history hello-chart
argocd app rollback hello-chart <previous-revision-id>
```
This rollback **works entirely inside ArgoCD's own tracked history** — the live cluster now matches an older deployed revision, but the **HEAD of your Git repository still contains the newer, "rolled-back-from" version** — Git and the cluster are now silently out of sync, and if automated `selfHeal` is enabled, ArgoCD's OWN self-heal logic will shortly re-apply the newer Git version right back over your rollback, undoing it. Reverting via `git revert && git push` instead keeps Git as the accurate, single source of truth throughout — the cluster and Git converge to the SAME older state, with no hidden drift. This is a genuine, easy-to-hit trap with ArgoCD's built-in rollback feature: it's convenient for a quick manual fix, but using it instead of a Git revert on a `selfHeal`-enabled Application silently sets up exactly the kind of drift GitOps was supposed to eliminate — the safe habit is to always prefer reverting in Git and letting the controller reconcile, reserving the UI/CLI rollback for genuine emergencies where you fix Git properly immediately afterward.

## Exercise 5
```bash
kubectl get clusterrolebinding | grep -i argocd
kubectl describe clusterrole argocd-application-controller
```
ArgoCD's application controller typically holds very broad permissions — often close to cluster-admin-equivalent across every namespace it's configured to manage — because it must be able to create, update, and delete **any resource type** any Application might declare (Deployments, Services, ConfigMaps, RBAC objects, CRDs, arbitrarily). This is not a contradiction of Day 16's least-privilege principle so much as a **relocation of the trust boundary**: instead of every individual developer or CI pipeline holding broad cluster credentials (the push-model risk from section 1.1), that broad privilege is now concentrated in ONE tightly-scoped, auditable, in-cluster component whose only inputs are commits to specific, access-controlled Git repositories. The security model shifts from "many external systems, each with cluster credentials" to "one internal system with cluster credentials, gated entirely by who can merge to Git" — genuinely better in most real organizations, but it makes **Git repository access control and branch-protection rules** just as security-critical as RBAC itself, since anyone who can merge to a repo ArgoCD watches effectively has whatever permissions that Application's controller has.

## Exercise 6
Both tools, pointed at separate namespaces (`argocd-demo` vs. `flux-demo`), coexist with zero interference — they're simply two independent reconciliation loops watching two independent target namespaces, exactly as Day 9's DaemonSet-per-Node loops never interfered with each other. If both were instead pointed at the **exact same namespace/resources** with automated sync + self-heal both enabled, they would actively **fight each other**: each tool continuously tries to reconcile that namespace back to ITS OWN idea of desired state (potentially from different Git paths, or even the same path read at slightly different poll times), producing a livelock where resources are repeatedly modified back and forth by competing controllers, neither ever settling — visible as constant, spurious "sync" events in both tools' status with no actual convergence. This is exactly why real organizations standardize on **one** GitOps tool per cluster (or, at most, per non-overlapping set of namespaces/resources) — running two isn't a matter of style preference once they'd actually overlap, it's a correctness bug waiting to happen.
