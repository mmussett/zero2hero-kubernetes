# Day 20 — Exercises

## Exercise 1 — Prune behavior
With automated sync active, add a brand-new template (e.g. a `ConfigMap`) to `day19-helm/chart/hello-chart/templates/` in your repo, commit, and push. Confirm ArgoCD creates it automatically. Now delete that same file, commit, and push again. With `prune: true` (already set in `argocd-application-automated.yaml`), does ArgoCD delete the ConfigMap from the cluster automatically? What would happen instead if `prune` were `false` — would the object be left behind, and why might a team deliberately choose that safer-but-messier default?

[→ solution](SOLUTIONS.md#exercise-1)

## Exercise 2 — Break the source on purpose
Change `argocd-application-hello-chart.yaml`'s `path` to a directory that doesn't exist (`day19-helm/chart/does-not-exist`) and reapply. Check `kubectl get application hello-chart -n argocd -o jsonpath='{.status.conditions}'` and the ArgoCD UI. What status/health does it report, and does it affect the PREVIOUSLY deployed (correct) resources still running in the cluster, or only block future syncs?

[→ solution](SOLUTIONS.md#exercise-2)

## Exercise 3 — Flux reconciliation interval
`flux-helmrelease.yaml` sets `interval: 1m` on both the `GitRepository` and `HelmRelease`. Make a change to `values.yaml` in Git, push it, then time how long it takes Flux to pick it up WITHOUT running `flux reconcile`. Then push another change and immediately run `flux reconcile source git zero2hero-repo` — how much faster is the forced reconcile? What real-world trade-off does a very short `interval` (e.g. `10s`) introduce at scale across many GitRepository objects polling the same Git host?

[→ solution](SOLUTIONS.md#exercise-3)

## Exercise 4 — Compare the two rollback experiences
Perform a rollback via ArgoCD's own UI/CLI history (`argocd app history hello-chart`, `argocd app rollback hello-chart <revision-id>`) WITHOUT touching Git at all. Then perform an equivalent rollback via Flux by reverting the Git commit. Which one leaves Git as an accurate record of what's actually running in the cluster afterward, and which one creates a (temporary) mismatch between Git and the live cluster? What does this reveal about a subtle risk of ArgoCD's built-in rollback feature if used casually instead of always rolling back via Git?

[→ solution](SOLUTIONS.md#exercise-4)

## Exercise 5 — RBAC for GitOps controllers
Run `kubectl get clusterrolebinding | grep -i argocd` and `kubectl describe clusterrole argocd-application-controller` (name may vary by ArgoCD version). What scope of permissions does ArgoCD's own controller have, and why does it need broader permissions than almost any other workload you've deployed this course (tie back to Day 16's least-privilege principle — is this a contradiction, or does GitOps's whole security model just move the trust boundary somewhere else)?

[→ solution](SOLUTIONS.md#exercise-5)

## Exercise 6 (stretch) — Multi-tool coexistence
With both ArgoCD's `hello-chart` (in `argocd-demo`) and Flux's `hello-chart` (in `flux-demo`) running simultaneously from the same source chart, deliberately make them diverge (edit one values file only, or scale one independently with self-heal temporarily disabled). Confirm both tools operate completely independently with no interference, then explain why a REAL organization would almost never intentionally run two GitOps tools targeting overlapping resources — what specific conflict would arise if both were pointed at the exact same namespace with automated sync/self-heal both enabled?

[→ solution](SOLUTIONS.md#exercise-6)
