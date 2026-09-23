# Day 19 — Exercises

## Exercise 1 — Add a new configurable value
Add a `replicaMinReadySeconds` value to `values.yaml` (default `0`) and wire it into `deployment.yaml`'s `spec.minReadySeconds`. Confirm via `helm template hello-chart/ --set replicaMinReadySeconds=10` that it renders correctly, then install/upgrade a release with it set and verify with `kubectl get deployment ... -o jsonpath='{.spec.minReadySeconds}'`.

[→ solution](SOLUTIONS.md#exercise-1)

## Exercise 2 — A template bug, deliberately
Introduce a typo into `service.yaml`: change `{{ .Values.service.port }}` to `{{ .Values.service.Port }}` (wrong case — Helm/Go templates are case-sensitive and this key doesn't exist). Run `helm template hello-chart/`. Does it error, or silently render something wrong? Explain what you see and why `helm lint` alone would **not** have caught this particular mistake (hint: think about what `lint` actually checks vs. what it doesn't).

[→ solution](SOLUTIONS.md#exercise-2)

## Exercise 3 — Enable the Ingress conditionally
Install a **second** release, `hello-release-2`, with `--set ingress.enabled=true --set ingress.host=hello2.zero2hero.local`. Confirm via `kubectl get ingress` that only this release created an Ingress object, while `hello-release` (Ingress disabled by default) has none. Add the host to `/etc/hosts` and `curl` it successfully.

[→ solution](SOLUTIONS.md#exercise-3)

## Exercise 4 — helm diff before upgrading (concept + manual approximation)
Without installing the `helm-diff` plugin, manually approximate what it does: run `helm get manifest hello-release > /tmp/before.yaml`, make an upgrade (`helm upgrade hello-release hello-chart/ --set greeting="Changed"`), then `helm get manifest hello-release > /tmp/after.yaml` and `diff /tmp/before.yaml /tmp/after.yaml`. What changed? Then look up what the real `helm-diff` plugin (`helm plugin install https://github.com/databus23/helm-diff`) adds beyond this manual approach — specifically, at what point in the workflow it lets you see the diff.

[→ solution](SOLUTIONS.md#exercise-4)

## Exercise 5 — Two releases, one chart, one namespace
Install `hello-release` and `hello-release-2` simultaneously in the same namespace (both from Exercise 3, if you still have them). Confirm via `kubectl get all -l app.kubernetes.io/instance=hello-release` vs. `...=hello-release-2` that Helm's naming (`{{ include "hello-chart.fullname" . }}`, which embeds `.Release.Name`) kept every object's name unique despite both coming from the identical chart. What would have happened if `deployment.yaml` had hardcoded the name `hello-chart` instead of using the helper template?

[→ solution](SOLUTIONS.md#exercise-5)

## Exercise 6 (stretch) — Chart versioning and appVersion vs. version
Explain, using `Chart.yaml`, the difference between `version` (currently `0.1.0`) and `appVersion` (currently `"1.0.0"`). Bump `version` to `0.2.0` in `Chart.yaml` without changing anything else, run `helm upgrade hello-release hello-chart/`, then `helm history hello-release` — does Helm treat this as a meaningful new revision even though no rendered manifest content actually changed? Then change `appVersion` to `"2.0.0"` (without actually changing `image.tag` in `values.yaml`, which is independent) and explain in one sentence why `appVersion` is documentation/metadata only and does **not** by itself change which image tag gets deployed.

[→ solution](SOLUTIONS.md#exercise-6)
