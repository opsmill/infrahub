# Contract: Helm values of the Grafana MCP server

**Requirements**: FR-001 to FR-010 | **Research**: R2 to R5, R12 | **Chart**:
[`infrahub-observability`](https://github.com/opsmill/infrahub-helm/tree/main/charts/infrahub-observability)

The server comes from the community chart
[`grafana-mcp`](https://github.com/grafana-community/helm-charts/tree/main/charts/grafana-mcp)
0.37.0, a pinned dependency of `infrahub-observability` (research R12). The dependency renders the
Deployment, the `ClusterIP` Service, the ServiceAccount of the server and the Secret of a token value.
The `infrahub-observability` chart keeps the hook Job that creates the Grafana service account and its
token, the Job's ServiceAccount, Role, RoleBinding and ConfigMap, the two scripts, and the render
checks.

## Values

The settings are under two keys, because the values schema of the dependency rejects a key it does
not know.

```yaml
grafana-mcp-setup:               # Settings of infrahub-observability
  enabled: false                 # FR-001: the only flag, also the condition of the dependency.
                                 # False: no Deployment, Service, Job or Secret.
  grafanaAdminSecret: ""         # Default: the admin Secret of the grafana sub-chart
  tokenJob:
    image:
      repository: grafana/grafana  # Has curl, sed, grep and base64 (research R5)
      tag: "11.1.5"
    securityContext:             # The Job pod runs as user and group 472
      runAsUser: 472
      runAsGroup: 472
      fsGroup: 472

grafana-mcp:                     # Values of the grafana-mcp dependency
  image:
    repository: grafana/mcp-grafana
    tag: "2.0.2@sha256:78d208116ec52b09b44f0eca66892073b39aefcb64483c54d43255c8eab7e97a"
                                 # The dependency builds the image as repository:tag, so the
                                 # digest is part of the tag.
  grafana:
    url: "http://obs-grafana"    # The Grafana Service of a release named obs
  serverAuth:
    token: ""                    # FR-003: no default
    tokenSecret:
      name: ""                   # Name of an existing Secret
      key: token
  disableWrite: true             # --disable-write (FR-010)
  disabledCategories: [api, docs, plugin]   # --disable-api --disable-docs --disable-plugin (FR-008)
  env:
    DO_NOT_TRACK: "1"
    GRAFANA_SERVICE_ACCOUNT_TOKEN_FILE: /var/run/grafana-mcp/token
  allowedHosts:
    extra: [localhost:8100, 127.0.0.1:8100]   # FR-007. The dependency adds the loopback
                                              # addresses and the names of the Service.
  extraArgs:                     # --transport streamable-http, --address 0.0.0.0:8000,
                                 # --healthz-address :8081, --usage-stats=disabled,
                                 # --instructions-append "<text of compose-settings.md>"
  securityContext:               # Server pod. The image runs as 1000:999; fsGroup lets the
    runAsNonRoot: true           # group read a mounted TLS key.
    runAsUser: 1000
    runAsGroup: 999
    fsGroup: 999
  volumes:
    - name: grafana-token        # Must stay: the hook Job writes the Secret that it names
      secret:
        secretName: grafana-mcp-service-account-token
        optional: true
        defaultMode: 0440
  volumeMounts:
    - name: grafana-token
      mountPath: /var/run/grafana-mcp
      readOnly: true
```

The other settings of the server (`service`, `replicas`, `resources`, `nodeSelector`, `tolerations`,
`affinity`, `podAnnotations`, `containerSecurityContext`, the probes) are keys of the dependency under
`grafana-mcp`. The dependency also offers an Ingress, an HTTPRoute, autoscaling and a ServiceMonitor.

## Objects

| Object | Name | Rendered by |
|--------|------|-------------|
| Deployment, Service, ServiceAccount of the server, Secret of a token value | `<release>-grafana-mcp` | The `grafana-mcp` dependency |
| Hook Job, its ServiceAccount, Role, RoleBinding and ConfigMap | `<release>-infrahub-observability-grafana-mcp-init` | `infrahub-observability` |
| Secret with the Grafana token | `grafana-mcp-service-account-token` | The hook Job, at run time |

The name of the Grafana token Secret has no release name, because a list of volumes in `values.yaml`
cannot be templated. The Job reads the name from the volume `grafana-token` in `grafana-mcp.volumes`.
Two releases of the chart in one namespace share the Secret, unless each one sets its own name in
`grafana-mcp.volumes`.

## Rules

`helm install` and `helm upgrade` fail, with these messages, when `grafana-mcp-setup.enabled` is true
and:

- `grafana-mcp.serverAuth.token` and `grafana-mcp.serverAuth.tokenSecret.name` are both empty, or the
  token is `null` (FR-004): `grafana-mcp.serverAuth.token or grafana-mcp.serverAuth.tokenSecret.name
  is required`. Without this check, the dependency would generate a token or turn authentication off.
- `service.type` is `LoadBalancer` or `NodePort` and `--server.tls-cert-file` is not in
  `grafana-mcp.extraArgs` (FR-006a, the Helm form of the Compose rule): `grafana-mcp.service.type is
  <type>, which is open to a network: serve HTTPS with --server.tls-cert-file and
  --server.tls-key-file in grafana-mcp.extraArgs`.
- `--disable-write`, `--disable-api`, `--disable-docs` or `--disable-plugin` is missing, or
  `extraArgs` sets one of them to `=false` (FR-008, FR-010): `grafana-mcp must pass <flag>, so that
  the server has no tool that writes: keep grafana-mcp.disableWrite true and api, docs and plugin in
  grafana-mcp.disabledCategories`, or `grafana-mcp.extraArgs has <argument>, which turns a read-only
  flag off`.
- `grafana-mcp.volumes` has no volume named `grafana-token` with a `secret.secretName`:
  `grafana-mcp.volumes must have a volume named grafana-token with a secret.secretName: the hook Job
  writes the Grafana token to that Secret`.
- `grafana.enabled` is false and `grafana-mcp.grafana.url` is the default: `grafana-mcp.grafana.url
  is required when grafana.enabled is false: set the address of your Grafana`.
- The release is not named `obs` and `grafana-mcp.grafana.url` is the default:
  `grafana-mcp.grafana.url is the default for a release named obs, and this release is named
  <release>: set it to <url>`.

Other rules:

- The server runs the same options as Compose (see [compose-settings.md](compose-settings.md)). The
  dependency adds `--disable-write`, the `--disable-<category>` flags and `--allowed-hosts` from
  `disableWrite`, `disabledCategories` and `allowedHosts`; the other options are in `extraArgs`. The
  server reads the caller token from the dependency's Secret, or from `serverAuth.tokenSecret`, and
  the Grafana token as a file mounted from the Secret written by the Job.
- TLS (FR-006a): add `--server.tls-cert-file=/etc/grafana-mcp/tls/tls.crt` and
  `--server.tls-key-file=/etc/grafana-mcp/tls/tls.key` to `grafana-mcp.extraArgs`, and mount a
  `kubernetes.io/tls` Secret with `grafana-mcp.volumes` and `grafana-mcp.volumeMounts`. A list in a
  values file replaces the default list, so the custom lists repeat the default arguments and keep
  the volume `grafana-token`. The README of the chart has the example.
- The probes use `GET /healthz` on the side listener `:8081` (`--healthz-address`), over plain HTTP,
  because a probe sends the pod IP as `Host` and the main port refuses it. The default liveness probe
  of the dependency calls the main port, so the values replace the three probes; `tcpSocket` and
  `httpHeaders` are set to `null` so that each probe keeps one handler.
- The Job is a `post-install,post-upgrade` hook with the delete policy
  `before-hook-creation,hook-succeeded`. Its Role allows `create` on Secrets, because Kubernetes
  cannot limit `create` to one name, and `get` and `update` on the one Secret that holds the Grafana
  token.
- The Job runs `run.sh`: it copies the existing token Secret into the token file, runs the shared
  `create-service-account.sh`, then writes the Secret again when the token changed. The volume
  `grafana-token` is `optional: true`, so the pod starts before the hook runs and `helm install
  --wait` does not wait for the Job.

## What the operator shares with users

The URL that reaches the Service, and the caller token. The Service is `ClusterIP` by default, so the
server is not reachable from outside the cluster (spec FR-006). The user reaches it with
`kubectl port-forward svc/<release>-grafana-mcp 8100:8000`, or through an Ingress or an HTTPRoute.
Without the two TLS flags, the server serves plain HTTP, so an Ingress MUST use TLS, and a
`LoadBalancer` or `NodePort` Service without them makes the install fail (see Rules). The chart does
not check an Ingress; the docs say that it MUST use TLS. When the URL uses another host name or port,
`grafana-mcp.allowedHosts.extra` must contain it.

## Checks

From the description of
[infrahub-helm #131](https://github.com/opsmill/infrahub-helm/pull/131) at `dbaa36a`:

- 44 `helm template` tests in `tests/unit/test_grafana_mcp_chart.py`, among them every render check
  above, one handler per probe, the Secret that the Job writes and the pod mounts, and two releases
  with their own names.
- The vcluster e2e test, on the chart with the dependency: the hook Job creates the token Secret; the
  server rejects a request without a token or with a wrong one (HTTP 401), lists no tool that creates,
  updates or deletes, and reads the Prometheus, Loki and Tempo data sources with the Job's token.
- With the first version of the chart, which rendered the server with its own templates, and by hand
  in a vcluster: the probes on the side listener pass over HTTP with and without a TLS Secret and
  fail over HTTPS; the server serves HTTPS with a self-signed certificate; on `helm upgrade` the Job
  keeps a working token, replaces a revoked token, recreates a deleted Secret and sets the role back
  to Viewer.

Not checked: the TLS setup with the dependency (no e2e test, and the manual check was not repeated
after the switch), an Ingress, an HTTPRoute, and a Grafana version other than 11.1.5.
