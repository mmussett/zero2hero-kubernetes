---
---
# Day 14 — Solutions

## Exercise 1
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: scratch-deny
spec:
  podSelector: {}
  policyTypes:
    - Ingress
```
```bash
kubectl apply -f scratch-deny.yaml
kubectl describe networkpolicy scratch-deny   # Allowing ingress traffic: <none>
kubectl delete -f scratch-deny.yaml
```
No `ingress:` key at all — an absent list under a declared `policyTypes` entry means "allow nothing for that direction," exactly as section 1.1 states. This is the standard starting point every real NetworkPolicy rollout begins from.

## Exercise 2
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {name: allow-frontend-egress-to-backend}
spec:
  podSelector:
    matchLabels: {role: frontend}
  policyTypes: [Egress]
  egress:
    - to:
        - podSelector: {matchLabels: {role: backend}}
      ports:
        - {protocol: TCP, port: 8080}
```
```bash
kubectl apply -f allow-frontend-egress-to-backend.yaml
kubectl exec frontend-client -- curl -s -m 3 backend-svc/
```
Now succeeds. With all four policies applied, `frontend-client` has exactly two egress allowances (DNS on 53, backend Pods on 8080) and `backend` has exactly one ingress allowance (from `role: frontend` on 8080) — a fully least-privilege pair of Pods, which is the production pattern this whole lab builds toward.

## Exercise 3
```bash
kubectl create namespace team-beta
kubectl label namespace default purpose=frontend-source
sed -e 's/name: backend/name: backend-beta/' -e 's/name: backend-svc/name: backend-svc-beta/' backend.yaml \
  | kubectl apply -n team-beta -f -
kubectl apply -n team-beta -f netpol-default-deny-ingress.yaml
```
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {name: allow-cross-ns-frontend, namespace: team-beta}
spec:
  podSelector: {matchLabels: {role: backend}}
  policyTypes: [Ingress]
  ingress:
    - from:
        - namespaceSelector: {matchLabels: {purpose: frontend-source}}
          podSelector: {matchLabels: {role: frontend}}
      ports: [{protocol: TCP, port: 8080}]
```
```bash
kubectl apply -n team-beta -f allow-cross-ns-frontend.yaml
kubectl exec frontend-client -- curl -s -m 3 backend-svc-beta.team-beta.svc.cluster.local/
```
Succeeds — proving cross-namespace policies work by combining both selectors in a single `from` entry.

## Exercise 4
```yaml
# (a) AND — must be a frontend Pod AND in a namespace labeled team=trusted
ingress:
  - from:
      - podSelector: {matchLabels: {role: frontend}}
        namespaceSelector: {matchLabels: {team: trusted}}
---
# (b) OR — any Pod labeled role=frontend (in the policy's OWN namespace, since
#     no namespaceSelector is given for that entry) OR any Pod at all in a
#     namespace labeled team=trusted
ingress:
  - from:
      - podSelector: {matchLabels: {role: frontend}}
      - namespaceSelector: {matchLabels: {team: trusted}}
```
Two YAML list items (`- podSelector...` and `- namespaceSelector...` as **separate** dashes) means separate `from` peer entries — a logical OR across the whole `ingress[].from` array. One list item with two keys under it (both `podSelector:` and `namespaceSelector:` as sibling fields of the *same* dash) means both conditions must hold on the *same* peer Pod — a logical AND. Concrete scenario: a Pod labeled `role: frontend` sitting in an *untrusted* namespace (not labeled `team: trusted`) is allowed under variant (b) (it matches the `podSelector` OR-branch regardless of namespace) but blocked under variant (a) (it fails the namespace half of the AND condition) — variant (a) is the correct, tighter policy when "frontend, and specifically from a trusted namespace" was the actual intent.

## Exercise 5
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {name: irrelevant-policy}
spec:
  podSelector: {matchLabels: {role: nonexistent}}
  policyTypes: [Ingress]
  ingress:
    - from: []
```
```bash
kubectl apply -f irrelevant-policy.yaml
kubectl exec rogue-client -- curl -s -m 3 backend-svc/    # still blocked exactly as before, unaffected
```
`backend` Pods (labeled `role: backend`) never match `podSelector: {role: nonexistent}`, so this policy simply never applies to them at all — it has zero effect on any traffic in the namespace. A policy's `podSelector` scopes **which Pods the policy's rules apply to as a destination (for Ingress) or source (for Egress)** — it does not describe a blanket cluster rule. This is a common authoring mistake: writing a policy with a typo'd or stale label selector that silently does nothing, giving a false sense of security.
```bash
kubectl delete -f irrelevant-policy.yaml
```

## Exercise 6
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {name: rogue-egress-lockdown}
spec:
  podSelector: {matchLabels: {role: rogue}}
  policyTypes: [Egress]
  egress:
    - to:
        - ipBlock: {cidr: 1.1.1.1/32}
      ports: [{protocol: TCP, port: 443}]
```
```bash
kubectl apply -f rogue-egress-lockdown.yaml
kubectl exec rogue-client -- curl -m 3 -s -o /dev/null -w "%{http_code}\n" https://1.1.1.1/    # 200
kubectl exec rogue-client -- curl -m 3 -s -o /dev/null -w "%{http_code}\n" https://8.8.8.8/    # times out, no output
```
(Note: with no explicit DNS-egress allow for `rogue-client` specifically, use the IP directly rather than a hostname, or add a DNS allow scoped to `role: rogue` too.) This exact pattern — restricting a Pod's egress to a named, narrow set of external IPs — is how teams lock down a Pod that legitimately needs to call one external SaaS API/webhook endpoint while preventing that same Pod (if compromised via a dependency vulnerability) from exfiltrating data to an arbitrary attacker-controlled destination or being used as a pivot point to scan/attack other external or internal systems.

## Exercise 7
Reachability matrix from testing (before checking the file):
| Source | Destination | Result |
|---|---|---|
| `frontend-client` (role=frontend) | `backend-svc` (role=backend), port 8080/HTTP | Allowed |
| `rogue-client` (role=rogue) | `backend-svc`, port 8080 | Blocked |

Inference: the policy's `podSelector` targets Pods labeled `role: backend` as the protected destination, its single ingress rule's `from` matches source Pods labeled `role: frontend`, and it restricts to TCP port `8080`. Checking `netpol-allow-frontend-to-backend.yaml` confirms exactly this. In a real incident with an unfamiliar cluster, this exact "binary search via reachability tests across labeled Pods" technique is often faster than reading through dozens of overlapping NetworkPolicy YAML files, especially across multiple namespaces.
