# Day 13 — Exercises

## Exercise 1 — Break allowedRoutes on purpose
Change `envoy-gatewayclass-and-gateway.yaml`'s Gateway to `allowedRoutes: {namespaces: {from: Selector, selector: {matchLabels: {gateway-access: "allowed"}}}}` and reapply. Without labeling any namespace, try re-applying `httproute-portability-demo.yaml`'s `hello-route-envoy`. Check `kubectl describe httproute hello-route-envoy` — does it report `Accepted`? Now label the `default` namespace `gateway-access=allowed` and check again. Explain what real-world problem this field solves (tie back to section 1.2's role-separation explanation).

[→ solution](SOLUTIONS.md#exercise-1)

## Exercise 2 — Three-way weight test
Modify `httproute-traffic-split.yaml` to a three-way split: `hello-v1-svc` weight 50, `hello-v2-svc` weight 30, and a **new** third backend (copy `vip-backend` as `hello-v3`) weight 20. Run 50 requests and tally the distribution. How close to 50/30/20 did you get, and what would you do differently (larger sample size? repeated runs?) to get a more statistically confident measurement in a real capacity-testing exercise?

[→ solution](SOLUTIONS.md#exercise-2)

## Exercise 3 — HTTPRoute rejected by a nonexistent Gateway
Apply an `HTTPRoute` with `parentRefs: [{name: does-not-exist}]`. Does `kubectl apply` itself error? Check `kubectl describe httproute` for its `parentRefs` status condition. Compare this error-reporting behavior to Day 11 Exercise 4 (an Ingress created for a nonexistent IngressClass) — which API gives you a clearer, more immediate signal that something is misconfigured, and why might that design difference matter operationally?

[→ solution](SOLUTIONS.md#exercise-3)

## Exercise 4 — Path AND header, combined
Write an `HTTPRoute` rule that matches BOTH a specific path prefix (`/special`) AND a header (`X-Feature: beta`) in the *same* `matches` entry — routing only requests satisfying both conditions to `vip-backend-svc`, with a fallback rule for everything else. Confirm with `curl` that a request to `/special` without the header, and a request to `/` with the header, both fall through to the default backend — only the combination of both matches the special rule.

[→ solution](SOLUTIONS.md#exercise-4)

## Exercise 5 — Compare GatewayClass acceptance across implementations
Run `kubectl get gatewayclass -o wide` and `kubectl describe gatewayclass envoy nginx kong`. Confirm all three show `Accepted: True`. Then temporarily scale one implementation's controller Deployment to 0 (e.g. `kubectl scale deployment envoy-gateway -n envoy-gateway-system --replicas=0`) and recheck `kubectl describe gatewayclass envoy` — does its `Accepted` condition change immediately, eventually, or not at all? What does this tell you about how (or whether) GatewayClass status reflects the live health of its controller versus just its initial registration?

[→ solution](SOLUTIONS.md#exercise-5)

## Exercise 6 (stretch) — Migrate a Day 12 Ingress to an HTTPRoute
Take `day12-ingress-controllers-in-depth/manifests/ingress-kong.yaml`'s routing rule (plain path `/` to `hello-app-svc`) and rewrite it as an `HTTPRoute` attached to `kong-gw` from today. Confirm both produce equivalent routing behavior. Then explain, referencing what you now know about both APIs, why a large organization migrating hundreds of existing Ingress objects to Gateway API would likely want to do this incrementally, one team/namespace at a time, rather than all at once — what does the Gateway/HTTPRoute role split make easier about that kind of staged migration compared to Ingress's flatter model?

[→ solution](SOLUTIONS.md#exercise-6)

## Exercise 7 — Add a plain-HTTP listener alongside the TLS one
`envoy-gw-tls` (section 2.10) has only ONE listener, on HTTPS port `30350` — there is deliberately no plain-HTTP fallback, unlike Day 11's Ingress. Add a *second* listener to that same `Gateway` object, named `http`, on a new port `30351`, protocol `HTTP`, and confirm `curl http://gw-secure.zero2hero.local:30351/` now succeeds even though `:30350` still refuses plain HTTP. Does adding the second listener require touching `hello-route-tls` at all, or does the existing `HTTPRoute` automatically apply to both listeners? Explain why, referencing how `parentRefs` attaches to the whole `Gateway` object rather than one specific listener within it.

[→ solution](SOLUTIONS.md#exercise-7)
