# Outbound TLS

> Part of: `dev/knowledge/backend/` | Related: [Architecture](architecture.md), [Git Sync](git-sync.md)

How Infrahub decides which certificate authorities an outbound TLS connection trusts, and where each
component applies that decision. Read this before adding a component that opens outbound connections
or before touching a `tls_*` setting: the resolution happens once at config load, so a component that
reads the global setting directly or skips the registration step silently falls back to the system store.

## Resolution order

For each component, the first rule that applies wins:

1. The component's `tls_insecure` is enabled: no verification, every CA setting is ignored.
2. The component's own `tls_ca_file` / `tls_ca_bundle`.
3. The global `tls.ca_bundle` (`INFRAHUB_TLS_CA_BUNDLE`).
4. The container's system trust store.

`infrahub/config.py::Settings.apply_global_tls_ca_bundle` implements rules 2 and 3 at load time by
copying the global path into every component field that is still `None` and whose component is not
insecure and connects over TLS. Adapters never read `tls.ca_bundle`; they keep reading their own
section, and the value they see is already resolved. Inspecting `config.SETTINGS.<section>` therefore
shows the effective CA, not what the operator typed.

A CA bundle *replaces* the system trust store, it never extends it: `ssl.create_default_context(cafile=...)`,
git's `http.sslCAInfo`, boto3's `verify`, the Neo4j driver's `TrustCustomCAs` and redis-py's `ssl_ca_certs`
all behave that way. The user docs tell operators to append the public roots when a component must keep
reaching public services.

## Where each component applies it

| Component | Setting read by the code | Applied in |
|-----------|--------------------------|------------|
| HTTP client (webhooks, SSO, telemetry) | `http.tls_ca_bundle`, `http.tls_insecure` | `services/adapters/http/httpx.py::InfrahubHTTP.verify_tls` through `TlsContextRegistry` |
| Prefect client | `http.tls_*` | `services/adapters/workflow/worker.py`, `workers/infrahub_async.py`, `workflows/utils.py` |
| SDK client to the Infrahub API | `http.tls_*` | `workers/dependencies.py::build_client` |
| Git credential helper | `http.tls_*` | `git_credential/helper.py::build_client_config` (own process, spawned by git) |
| Git | `git.tls_ca_file`, `git.tls_insecure` | `git/global_config.py::apply_git_tls_config` writes `http.sslCAInfo` / `http.sslVerify` into the global gitconfig at task-worker startup |
| Neo4j | `database.tls_ca_file` | `database/__init__.py` (`TrustCustomCAs`) |
| Cache (Redis, NATS) | `cache.tls_ca_file` | `services/adapters/cache/` |
| Broker (RabbitMQ, NATS) | `broker.tls_ca_file` | `services/adapters/message_bus/` |
| S3 object storage | `storage.s3.tls_ca_file` (alias `AWS_CA_BUNDLE`) | `storage.py::InfrahubS3ObjectStorage` passes `verify=` to boto3; inherits the global bundle only when `use_ssl` is on |
| OTLP trace exporter | `trace.tls_ca_bundle` | `trace.py`; inherits the global bundle only when `TraceSettings.uses_tls` |
| Log forwarding | `tls_ca_bundle` per destination | Infrahub Enterprise; this repo only defines the settings |
| LDAP | `ldap.tls_ca_bundle` | Infrahub Enterprise; this repo only defines the settings |

## Traps

- **Path or PEM text.** `http`, `ldap` and the syslog destinations accept inline PEM content; git, boto3,
  Neo4j and Redis only take a path. The global setting is path-only and validated as an existing,
  loadable file for that reason.
- **gRPC trace exporter.** Passing a CA bundle to the gRPC exporter switches it from plaintext to TLS,
  so the global bundle is only copied into `trace` when the exporter connection is already encrypted.
- **Plaintext S3 endpoint.** boto3 ignores `verify=` when `use_ssl` is off, so `S3StorageSettings` rejects an
  explicit `tls_ca_file` with `use_ssl=false`, and the global bundle is only copied into `storage.s3` when
  `use_ssl` is on.
- **`force_verify=bool(ca_bundle)`.** Some HTTP paths build the context with `force_verify` derived from
  the bundle, which re-enables verification despite `tls_insecure`. The fill-in skips insecure
  components so a global bundle never changes what an insecure component does.
- **Git runs only in the task worker**, but `GitSettings` is validated in every process. With the shared
  Compose env anchor the API server also needs the file mounted, or it refuses to start.
- **Persisted gitconfig.** `/opt/infrahub/.gitconfig` can outlive a container, so `apply_git_tls_config`
  unsets `http.sslCAInfo` / `http.sslVerify` when the settings are absent instead of leaving old values.
- **`--global` lies in an exec shell.** The worker selects `/opt/infrahub/.gitconfig` by exporting
  `GIT_CONFIG_GLOBAL` in its own process; `docker compose exec task-worker git config --global ...` does
  not inherit it and reads `$HOME/.gitconfig`, which only holds what the Dockerfile baked in. Inspect
  the file directly: `git config --file /opt/infrahub/.gitconfig --get http.sslCAInfo`.
- **Three TLS failure wordings.** git's HTTPS helper reports an untrusted certificate as "SSL certificate
  problem" (OpenSSL), "server certificate verification failed" (older GnuTLS) or "server verification
  failed" (GnuTLS with curl 8.x, what the shipped image uses). `git/base.py::GIT_TLS_VERIFICATION_ERRORS`
  lists them; a wording missing there drops the repository into the generic `error` status instead of
  `error-connection` with the certificate hint.
- **Component sections do not see the global.** A section-level validator cannot know whether the
  global bundle will fill it later; only `Settings`-level validators can reason about the resolved value.

## Adding an outbound component

1. Give its settings section a `tls_ca_file` (path) or `tls_ca_bundle` (path or PEM) field and, when the
   client supports it, a `tls_insecure` flag.
2. Register the field in `Settings.apply_global_tls_ca_bundle`.
3. Extend `tests/unit/config/test_tls_settings.py` and the component table in the private CA guide under
   `docs/docs/deploy-manage/install-configure/production-deployment/`.
