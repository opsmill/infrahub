# Contract: Helm values of the Grafana MCP server

**Requirements**: FR-001 to FR-010 | **Research**: R2 to R5 | **Chart**:
[`infrahub-observability`](https://github.com/opsmill/infrahub-helm/tree/main/charts/infrahub-observability)

The values follow the pattern of the existing
[`infrahub-mcp`](https://github.com/opsmill/infrahub-helm/tree/main/charts/infrahub-mcp) chart: a
plain value or an existing Secret for the token.

## Values

```yaml
grafanaMcp:
  enabled: false                 # FR-001: no Deployment, Service, Job or Secret when false
  image:
    repository: grafana/mcp-grafana
    tag: "2.0.2"
  serverToken:
    value: ""                    # FR-003: no default
    existingSecret: ""           # Name of an existing Secret
    existingSecretKey: token
  allowedHosts: "localhost:8100,127.0.0.1:8100"   # FR-007
  service:
    type: ClusterIP              # FR-006: LoadBalancer or NodePort opens it to a network
    port: 8000
  tls:
    existingSecret: ""           # FR-006a: a kubernetes.io/tls Secret (tls.crt, tls.key), for
                                 # example from cert-manager. Empty: plain HTTP.
  grafana:
    url: ""                      # Default: the Grafana Service of this release
    adminSecret: ""              # Default: the admin Secret created by the grafana subchart
  serviceAccountJob:
    image:
      repository: ""             # Image with curl (research R5)
      tag: ""
```

## Rules

- When `grafanaMcp.enabled` is true and both `serverToken.value` and `serverToken.existingSecret` are
  empty, `helm install` and `helm upgrade` fail with `grafanaMcp.serverToken.value or
  grafanaMcp.serverToken.existingSecret is required` (FR-004).
- The Deployment runs the same options as Compose (see
  [compose-settings.md](compose-settings.md)). It reads the caller token through `secretKeyRef` and
  the Grafana token as a file mounted from the Secret written by the Job.
- When `tls.existingSecret` is set, the Deployment mounts the Secret read-only and passes
  `--server.tls-cert-file` and `--server.tls-key-file` with the mounted paths (FR-006a).
- The probes use `/healthz` on a side listener (`--healthz-address`), because a probe sends the pod IP
  as `Host`. Not verified (research R3).
- The Job is a `post-install,post-upgrade` hook with the delete policy
  `before-hook-creation,hook-succeeded`. Its Role allows `get`, `create` and `update` on the one Secret
  that holds the Grafana token.

## What the operator shares with users

The URL that reaches the Service, and the caller token. The Service is `ClusterIP` by default, so the
server is not reachable from outside the cluster (spec FR-006). The user reaches it with
`kubectl port-forward svc/<release>-grafana-mcp 8100:8000`, or through an Ingress that the operator
adds. Without `tls.existingSecret`, the server serves plain HTTP, so an Ingress MUST use TLS, and a
`LoadBalancer` or `NodePort` Service MUST NOT be used without `tls.existingSecret`; the docs say so.
When the URL uses another host name or port, `allowedHosts` must contain it.

## Checks before the templates are written

- Start the image in kind with the probe settings above and confirm that the probes pass (research
  R3, `/healthz` and the `Host` check are not verified). Repeat with `tls.existingSecret` set, to find
  whether the probes need the `HTTPS` scheme.
- Pin the image by digest next to the tag, as in Compose.
