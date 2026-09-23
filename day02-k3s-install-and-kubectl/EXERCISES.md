---
---
# Day 2 — Exercises

## Exercise 1 — Read the architecture from your own cluster
Run `kubectl get pods -n kube-system`. Match each Pod you see to a component described in section 1.1 (some, like `local-path-provisioner` or `coredns`, are k3s add-ons, not core control-plane — note which is which).

[→ solution](SOLUTIONS.md#exercise-1)

## Exercise 2 — kubeconfig internals
Run `kubectl config view`. Identify the `cluster` (API server URL), `user` (credentials), and `context` (the pairing of the two) sections. Then run `kubectl config current-context`. What happens if you run `kubectl --context=doesnotexist get nodes`?

[→ solution](SOLUTIONS.md#exercise-2)

## Exercise 3 — Diagnose a bad image reference
Run `kubectl run broken --image=localhost:5000/does-not-exist:1.0.0`. Use `kubectl get pods`, `kubectl describe pod broken`, and `kubectl get events` to determine the exact reason the Pod isn't running, without looking at the solution first. Write down the `Reason` field you find.

[→ solution](SOLUTIONS.md#exercise-3)

## Exercise 4 — Node capacity
Using `kubectl describe node <your-node-name>`, find your node's total allocatable CPU and memory, and the current `Non-terminated Pods` resource requests table. Explain in your own words what "allocatable" means vs. "capacity."

[→ solution](SOLUTIONS.md#exercise-4)

## Exercise 5 — Namespace isolation preview
Run `kubectl create namespace training`. Create a Pod named `hello` in that namespace using `--image=localhost:5000/hello-k8s:1.0.0 -n training`. Confirm `kubectl get pods` (no `-n`) does *not* show it, but `kubectl get pods -n training` does. Clean up the namespace (this deletes everything inside it).

[→ solution](SOLUTIONS.md#exercise-5)

## Exercise 6 — Service outage simulation
With a Pod running (`kubectl run hello --image=localhost:5000/hello-k8s:1.0.0`), run `sudo systemctl stop k3s`. Try `kubectl get pods` — what happens, and why (think about what component `kubectl` actually talks to)? Now run `sudo systemctl start k3s`, wait 30 seconds, and check whether `hello` is still `Running`. What does this prove about where Pod state actually lives while the control plane is down?

[→ solution](SOLUTIONS.md#exercise-6)

## Exercise 7 — Full reset
Practice disaster recovery: run `sudo /usr/local/bin/k3s-uninstall.sh`, confirm `kubectl get nodes` now fails entirely (no server to talk to), then reinstall following section 3.2 and reconfigure `kubectl` following section 3.3. Re-verify `kubectl get nodes` shows `Ready`. Time yourself — this should take under 3 minutes end to end.

[→ solution](SOLUTIONS.md#exercise-7)

## Exercise 8 — jsonpath and custom-columns from scratch
Without looking at section 4.1's examples, write a `jsonpath` expression that prints only the `restartCount` of the first container in a Pod named `hello`, and a `custom-columns` expression that lists every Pod in the `default` namespace with columns `NAME`, `NODE` (`.spec.nodeName`), and `IP` (`.status.podIP`). Run both and confirm the output.

[→ solution](SOLUTIONS.md#exercise-8)

## Exercise 9 — Patch type behavior difference
Create a Pod with two labels, `a=1` and `b=2`. Using `kubectl patch --type merge`, set a third label `c=3` — confirm `a` and `b` are untouched (merge patch merges *objects* like the labels map field-by-field; it only replaces *arrays* wholesale). Now find (or write) a field on that same Pod that IS an array (hint: `spec.containers` or `spec.tolerations` if you add one), and demonstrate that a `merge`-type patch touching that array **replaces it entirely** rather than merging entries — contrast this with what a `strategic` merge patch would do to the same array (strategic merge understands `containers` should merge by the `name` key instead).

[→ solution](SOLUTIONS.md#exercise-9)

## Exercise 10 — kubectl debug on a shell-less container
Run a Pod from `gcr.io/distroless/static-debian12` (or any minimal/distroless image you can find) with a long-running command if possible, or just let it exit — try `kubectl exec -it <pod> -- sh` against it first and confirm it fails (`OCI runtime exec failed... exec: "sh": executable file not found`). Then use `kubectl debug -it <pod> --image=busybox:1.36 --target=<container-name> -- sh` and confirm you get a working shell that can still see the original container's process (if it's still running) via the shared process namespace.

[→ solution](SOLUTIONS.md#exercise-10)

## Exercise 11 (stretch) — kubectl proxy vs. port-forward, side by side
With `hello-k8s-svc` from Day 5 not yet created (that's fine — use the `hello` Pod from this day instead), start `kubectl proxy --port=8001` in one terminal and `kubectl port-forward pod/hello 8080:8080` in another, simultaneously. Using `curl`, reach the same Pod through BOTH: once via `localhost:8080/` (port-forward) and once via `localhost:8001/api/v1/namespaces/default/pods/hello/proxy/` (kubectl proxy's Pod-proxy subresource). Explain in one sentence what's fundamentally different about what each command is tunneling.

[→ solution](SOLUTIONS.md#exercise-11)
