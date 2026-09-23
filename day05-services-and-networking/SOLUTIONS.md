# Day 5 — Solutions

## Exercise 1
```yaml
apiVersion: v1
kind: Service
metadata:
  name: scratch-svc
spec:
  selector:
    app: scratch-svc
  ports:
    - port: 80
      targetPort: 8080
```
```bash
kubectl apply -f scratch-svc.yaml
kubectl get svc scratch-svc   # TYPE: ClusterIP
kubectl delete -f scratch-svc.yaml
```
`ClusterIP` is the type every Service gets when `spec.type` is omitted entirely — it's not a placeholder or an error state, it's the documented default (section 1.4).

## Exercise 2
```yaml
apiVersion: v1
kind: Service
metadata: {name: service-broken}
spec:
  selector: {app: wrong-label}
  ports: [{port: 80, targetPort: 8080}]
```
```bash
kubectl apply -f service-broken.yaml
kubectl get endpoints service-broken
# NAME             ENDPOINTS   AGE
# service-broken   <none>      5s
kubectl describe svc service-broken
# Endpoints: <none>
```
No Pods match the selector, so the EndpointSlice controller records zero endpoints. A client connecting to this Service's ClusterIP would have its packets accepted by kube-proxy's rules (the Service IP itself is real) but there's no DNAT target — the connection hangs and eventually times out. This is the single most common "my Service doesn't work" bug in real clusters: a typo'd label.
```bash
kubectl delete -f service-broken.yaml
```

## Exercise 3
```bash
kubectl create namespace other
kubectl apply -f deployment.yaml -n other
sed 's/hello-k8s-clusterip/hello-k8s-other/' service-clusterip.yaml | kubectl apply -n other -f -
kubectl exec netshoot -- curl -s hello-k8s-other.other.svc.cluster.local/   # works
kubectl exec netshoot -- curl -s hello-k8s-other/                          # fails to resolve
```
The fully-qualified name always resolves. The short name fails from `default` because Pod DNS config only auto-searches the Pod's **own** namespace (plus `svc.cluster.local`, etc.) via `/etc/resolv.conf`'s `search` list — `kubectl exec netshoot -- cat /etc/resolv.conf` shows `search default.svc.cluster.local svc.cluster.local cluster.local`. `other` isn't in that list, so only cross-namespace calls need the namespace segment; same-namespace calls can use the short name.
```bash
kubectl delete namespace other
```

## Exercise 4
```bash
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Service
metadata: {name: bad-nodeport}
spec:
  type: NodePort
  selector: {app: hello-k8s}
  ports: [{port: 80, targetPort: 8080, nodePort: 25000}]
EOF
```
Error: `The Service "bad-nodeport" is invalid: spec.ports[0].nodePort: Invalid value: 25000: provided port is not in the valid range. The range of valid ports is 30000-32767`. The range is a cluster-wide API server flag, `--service-node-port-range`, settable at cluster install time (for k3s: pass `--service-node-port-range` to the `k3s server` install command) — not something changeable per-Service.

## Exercise 5
```yaml
apiVersion: v1
kind: Service
metadata: {name: hello-k8s-headless}
spec:
  clusterIP: None
  selector: {app: hello-k8s}
  ports: [{port: 80, targetPort: 8080}]
```
```bash
kubectl apply -f headless.yaml
kubectl exec netshoot -- nslookup hello-k8s-headless
```
A normal ClusterIP Service's DNS returns **one** A record — the virtual IP. A headless Service (`clusterIP: None`) returns **multiple** A records, one per backing Pod's actual IP directly — there's no virtual IP or kube-proxy load-balancing involved at all; the client's own DNS resolution does the "load balancing" by picking which record to use, and the client can also enumerate every individual Pod. This is exactly the mechanism StatefulSets (Day 8) use to give each replica a stable, individually addressable DNS name (`pod-0.service`, `pod-1.service`, ...).
```bash
kubectl delete -f headless.yaml
```

## Exercise 6
```yaml
spec:
  sessionAffinity: ClientIP
```
```bash
kubectl apply -f service-affinity.yaml
for i in 1 2 3 4 5; do kubectl exec netshoot -- curl -s hello-k8s-affinity/ | grep hostname; done
```
Without affinity, the `hostname` field cycles across all 3 backend Pods roughly evenly (kube-proxy picks a random/round-robin endpoint per new connection). With `sessionAffinity: ClientIP`, **every** request from the same source IP lands on the same backend Pod for the affinity timeout window (default 3 hours, tunable via `sessionAffinityConfig`). A legacy app that keeps in-memory session state (not externalized to a shared store like Redis) needs every request from a given user to hit the same instance or the user gets logged out/loses state — session affinity is a workaround for that architectural limitation, at the cost of uneven load distribution and losing failover transparency if that one Pod dies.

## Exercise 7
```bash
kubectl apply -f deployment.yaml -f service-clusterip.yaml
kubectl wait --for=condition=ready pod -l app=hello-k8s --timeout=60s
kubectl port-forward svc/hello-k8s-clusterip 9090:80 &
sleep 1
curl -s localhost:9090/    # works — no NodePort, no LoadBalancer, no type at all beyond the ClusterIP default

POD=$(kubectl get pod -l app=hello-k8s -o jsonpath='{.items[0].metadata.name}')
kubectl delete pod $POD
curl -s localhost:9090/    # fails immediately — "lost connection to pod" / connection reset
```
The `port-forward` tunnel does **not** survive that Pod's deletion — it was attached to that one specific Pod's IP at connection time (§1.5), and once that Pod is gone the tunnel is simply broken, requiring you to manually re-run `kubectl port-forward` to reconnect (possibly to a different replica). Meanwhle, `curl localhost:30080/` against `service-nodeport.yaml` (section 2.5) keeps working with **zero manual intervention** through the exact same Pod deletion — because `NodePort` traffic flows through kube-proxy's iptables/IPVS rules on every request, which already dynamically point at whichever Pods are currently healthy, the same mechanism a normal in-cluster `ClusterIP` call uses. This is the concrete, hands-on proof of §1.5's core claim: `port-forward` is a debugging convenience bound to one point-in-time Pod, never a resilient production traffic path.
```bash
kill %1
kubectl delete -f deployment.yaml -f service-clusterip.yaml
```
