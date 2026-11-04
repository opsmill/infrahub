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
    port: 8000
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
- The probes use `/healthz` on a side listener (`--healthz-address`), because a probe sends the pod IP
  as `Host`. Not verified (research R3).
- The Job is a `post-install,post-upgrade` hook with the delete policy
  `before-hook-creation,hook-succeeded`. Its Role allows `get`, `create` and `update` on the one Secret
  that holds the Grafana token.

## What the operator shares with users

The URL that reaches the Service, for example through an Ingress or
`kubectl port-forward svc/<release>-grafana-mcp 8100:8000`, and the caller token. When the URL uses
another host name or port, `allowedHosts` must contain it.
