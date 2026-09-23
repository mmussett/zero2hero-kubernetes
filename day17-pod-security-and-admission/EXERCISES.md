---
---
# Day 17 — Exercises

## Exercise 1 — Fix a non-compliant Pod, one violation at a time
Take `pod-noncompliant.yaml`, apply it against `restricted-ns`, and read the full rejection message. Fix **only** the `privileged: true` issue and reapply — record the (still failing) new error message, which should now be shorter. Keep iterating, fixing one violation per attempt, until it's accepted. How many distinct violations did the original Pod have in total?

[→ solution](SOLUTIONS.md#exercise-1)

## Exercise 2 — Migrate a namespace: audit → warn → enforce
Create a namespace `migrating-ns` with only `pod-security.kubernetes.io/audit: restricted` set (no `enforce`, no `warn`). Apply `pod-noncompliant.yaml` (retargeted to this namespace) — confirm it succeeds with no client-visible warning at all. Check `sudo journalctl -u k3s | grep -i audit` or the API server's audit behavior conceptually (k3s's default audit logging may not be enabled — note this as a limitation and describe, from the docs, where a production cluster's audit log would actually be found). Then add `warn: restricted` and reapply, noting the client-visible `Warning:` line this time despite still succeeding.

[→ solution](SOLUTIONS.md#exercise-2)

## Exercise 3 — CEL policy variations
Modify `validatingadmissionpolicy.yaml`'s CEL expression to instead **require** every Pod to have a label `team` present (hint: `has(object.metadata.labels) && has(object.metadata.labels.team)`, combined with the existing rule using `&&`, or as a second `validations` entry). Confirm a Pod with a non-`:latest` image but no `team` label is still rejected, and the rejection message correctly identifies which rule failed if you gave each `validations` entry a distinct `message`.

[→ solution](SOLUTIONS.md#exercise-3)

## Exercise 4 — validationActions: Warn vs. Deny
Change `no-latest-tag-binding`'s `validationActions` from `["Deny"]` to `["Warn"]`. Reapply and try creating a Pod using `nginx:latest` again in `restricted-ns`. Does it succeed or fail this time? What appears in the client's output? When would `Warn` be the better operational choice over `Deny` for a brand-new policy you're not 100% confident won't have false positives?

[→ solution](SOLUTIONS.md#exercise-4)

## Exercise 5 — Digest pinning
Find the digest for `localhost:5000/hello-k8s:1.0.0` using `docker inspect --format='{{index .RepoDigests 0}}' localhost:5000/hello-k8s:1.0.0` (push it first if you haven't, per Day 1). Create a Pod referencing the image by digest instead of tag (`localhost:5000/hello-k8s@sha256:...`) and confirm it runs identically. Then **rebuild and re-push** a completely different `app.py` under the *same* tag `1.0.0`. Does a Pod already referencing the old digest change what it's running? Does a *new* Pod created with the tag `1.0.0` (not the digest) get the old or new content? What does this prove about tag mutability in practice?

[→ solution](SOLUTIONS.md#exercise-5)

## Exercise 6 (stretch) — Write your own baseline-equivalent policy
Without looking up the built-in `baseline` standard's exact rule list first, write a `ValidatingAdmissionPolicy` from scratch that rejects any Pod setting `hostNetwork: true`, `hostPID: true`, or `hostIPC: true` (all are host-namespace-sharing settings the `baseline` PSS level blocks) — using CEL's `has()` function to safely check optional fields. Test it against a Pod that sets `hostPID: true`. Afterward, compare your policy's coverage against the [full baseline requirements table](https://kubernetes.io/docs/concepts/security/pod-security-standards/#baseline) and note at least two other checks the real `baseline` standard enforces that your hand-written policy doesn't cover.

[→ solution](SOLUTIONS.md#exercise-6)
