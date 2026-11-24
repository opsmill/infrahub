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
    digest: "sha256:78d208116ec52b09b44f0eca66892073b39aefcb64483c54d43255c8eab7e97a"
                                 # Pulled as repository:tag@digest. Empty: tag only.
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
      repository: grafana/grafana  # Has curl, sed, grep and base64 (research R5)
      tag: "11.1.5"
  securityContext:               # Server pod. The image runs as 1000:999; fsGroup lets the
    runAsNonRoot: true           # group read the mounted TLS key.
    runAsUser: 1000
    runAsGroup: 999
    fsGroup: 999
```

The pod of the Job runs as user and group 472 (`serviceAccountJob.securityContext`).

## Rules

- When `grafanaMcp.enabled` is true and both `serverToken.value` and `serverToken.existingSecret` are
  empty, `helm install` and `helm upgrade` fail with `grafanaMcp.serverToken.value or
  grafanaMcp.serverToken.existingSecret is required` (FR-004).
- When `grafanaMcp.enabled` is true, `service.type` is not `ClusterIP` and `tls.existingSecret` is
  empty, `helm install` and `helm upgrade` fail with `grafanaMcp.service.type is <type>, which is open
  to a network: set grafanaMcp.tls.existingSecret` (FR-006a, the Helm form of the Compose rule).
- The Deployment runs the same options as Compose (see
  [compose-settings.md](compose-settings.md)), including `--disable-docs --disable-plugin` and
  `--instructions-append`. It reads the caller token through `secretKeyRef` and
  the Grafana token as a file mounted from the Secret written by the Job.
- When `tls.existingSecret` is set, the Deployment mounts the Secret read-only and passes
  `--server.tls-cert-file` and `--server.tls-key-file` with the mounted paths (FR-006a).
- The probes use `GET /healthz` on the side listener `:8081` (`--healthz-address`), over plain HTTP,
  because a probe sends the pod IP as `Host` and the main port refuses it. The side listener serves
  plain HTTP also when the main port serves HTTPS. The probes passed in the vcluster e2e test without
  TLS. With a TLS Secret they were checked by hand only, in a vcluster with a self-signed certificate:
  they pass over HTTP and fail over HTTPS
  ([infrahub-helm #131](https://github.com/opsmill/infrahub-helm/pull/131)).
- The Job is a `post-install,post-upgrade` hook with the delete policy
  `before-hook-creation,hook-succeeded`. Its Role allows `create` on Secrets, because Kubernetes
  cannot limit `create` to one name, and `get` and `update` on the one Secret that holds the Grafana
  token.
- The Job runs `run.sh`: it copies the existing token Secret into the token file, runs the shared
  `create-service-account.sh`, then writes the Secret again when the token changed. The Secret volume
  of the Deployment is `optional: true`, so the pod starts before the hook runs.

## What the operator shares with users

The URL that reaches the Service, and the caller token. The Service is `ClusterIP` by default, so the
server is not reachable from outside the cluster (spec FR-006). The user reaches it with
`kubectl port-forward svc/<fullname>-grafana-mcp 8100:8000`, where `<fullname>` is the full name of the chart release, or through an Ingress that the operator
adds. Without `tls.existingSecret`, the server serves plain HTTP, so an Ingress MUST use TLS, and a
`LoadBalancer` or `NodePort` Service without `tls.existingSecret` makes the install fail (see Rules).
An Ingress is not checked by the chart, because the operator adds it; the docs say that it MUST use
TLS.
When the URL uses another host name or port, `allowedHosts` must contain it.

## Checks before the templates are written

- Pin the image by digest next to the tag, as in Compose: done.
- Start the image with the probe settings above and confirm that the probes pass: done in the
  vcluster e2e test, without TLS.
- Repeat with `tls.existingSecret` set: checked by hand in a vcluster with a self-signed certificate,
  not in the e2e test.
