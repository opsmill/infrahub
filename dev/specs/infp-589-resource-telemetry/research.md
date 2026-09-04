# Research: Licensing Resource-Allocation Telemetry

Phase 0 decisions. Each resolves an unknown surfaced while planning against the existing telemetry code, the heartbeat service, and the deployment topology. No `NEEDS CLARIFICATION` markers remain.

## D1 — psutil promoted from dev-only to a runtime dependency; no new package added

- **Decision**: Read host CPU/RAM via `psutil` and the enforced limit via stdlib `/sys/fs/cgroup` file reads.
- **Correction (found during CI, not planning)**: `psutil==6.1.0` was already pinned in `pyproject.toml`, but only under `[dependency-groups] dev` — the production images are built with `uv sync --frozen --no-dev`, so the shipped `task-worker`/`api_server` containers never had it installed. This surfaced as every Docker-stack-based CI job (`backend-docker-integration`, all `E2E-*`) failing with the Prefect worker unable to load its collection (`ModuleNotFoundError: No module named 'psutil'`) — not a CI quirk, a real gap that would have shipped a broken feature. Fixed by moving the `psutil==6.1.0` entry from `dev` to `[project] dependencies` and regenerating `uv.lock` (package version unchanged; no new third-party package pulled in).
- **Rationale**: cgroup quota/usage is not exposed by psutil and must be read from the pseudo-filesystem regardless — that read is stdlib. No new package is added to the dependency set, but promoting an existing dev-only pin to a runtime dependency is itself an Ask-First "new dependency" change (confirmed with the user before editing `pyproject.toml`), since it is new to what ships in production.
- **Alternatives**: adding a cgroup helper library — rejected (a few lines of file parsing do not justify a dependency + review gate).

## D2 — Logical cores, never physical

- **Decision**: All core counts are logical CPUs (vCPUs). Server/workers use `psutil.cpu_count(logical=True)` (already a dependency; a cleaner interface than, and equivalent to, `os.cpu_count()`); the database uses the JMX `AvailableProcessors` already collected.
- **Rationale**: (a) the enforced limit lives in cgroup, which is denominated in logical CPU-time only; a physical `available` would be un-comparable to a logical `assigned`; (b) the database figure already shipped is logical (`Runtime.availableProcessors()`); (c) tiers, cloud vCPUs, and container limits are all logical. `psutil.cpu_count(logical=False)` also returns `None` under most containers.
- **Alternatives**: physical cores — rejected on all three counts above.

## D3 — `processor_assigned` = the configured limit, `null` when not enforced (live read, no fallback)

`assigned` means *configured* (confirmed by the backend owner). Infrahub does not enforce any core limit today — neither the database nor the workers — so **every `assigned` field is `null` today** and only becomes a real number once enforcement is added. Two rules:

1. `assigned` is **never** back-filled from `available` (FR-003). An unenforced component genuinely has no assignment; fabricating one erases the over-provisioning signal the audit needs. Until enforcement, `assigned == available` *in meaning* (both reflect the same unbounded infra) — so we report the measured `available` and a `null` `assigned`, not the same number duplicated into a field that implies a limit that isn't there.
2. Each `assigned` field is a **live read that returns `null` today** and lights up automatically once the corresponding limit is configured — carrying a comment documenting the intended source. Not a dead stub, not a fabricated value.

- **Database** — source is the Neo4j setting `server.cypher.parallel.worker_limit`, read over Bolt: `SHOW SETTINGS YIELD name, value WHERE name = 'server.cypher.parallel.worker_limit'`. It defaults to `0` (auto = use all cores), which maps to `null` (not enforced). This is the confirmed intended knob — "we do not enforce this value today (and we should)". When a tier sets it to a positive value, the read returns that number with no code change. (Supersedes the earlier `server.threads.worker_count` candidate, which is HTTP-only and does not influence Bolt/query execution.)
- **Server / workers (per-worker CPU cap)** — source is the container cgroup CPU quota (v2 `cpu.max`, v1 `cpu.cfs_quota_us`/`cpu.cfs_period_us`), read locally by each process. `max` / `-1` (unlimited) → `null`. The sized docker/helm configs set the replica count, not `limits.cpus`, so this is `null` until a CPU limit is configured. Fractional quotas (e.g. `--cpus=1.5`) round **up** to the next whole core (integer field; conservative for an audit).
- **Number of workers** — Pete's "number of workers configured" is the existing `workers.total`/`active` count, which telemetry already reports; it is distinct from the per-worker CPU cap above and is a real value today (no new field needed — see D14).

## D4 — Memory: reuse the DB representation (`memory_total` + `memory_available`)

- **Decision**: memory is reported as `memory_total` (capacity — cgroup `memory.max` when limited, else `psutil.virtual_memory().total`) and `memory_available` (free — `memory.max − memory.current` when limited, else `psutil.virtual_memory().available`), in bytes — the exact fields and semantics the database `system_info` already uses. Usage is derived by the consumer as `memory_total − memory_available`; there is no `*_used` field.
- **Rationale**: adopting the existing `memory_*` names/semantics for the new components makes DB, server, and workers byte-for-byte comparable (the naming decision, D14), and matches how the DB JMX (`TotalMemorySize` / `FreeMemorySize`) already reports. Pete's "RAM used" is preserved as a derived value, consistent with the DB.
- **No `memory_assigned`**: memory has no enforced-limit field — the container memory limit surfaces as `memory_total` capacity. Only `processor_assigned` carries the FR-003 no-fallback-null rule.

## D5 — cgroup v2 primary, v1 fallback, `null` otherwise; resolve the process's own cgroup path

- **Decision**: Read cgroup v2 first (`cpu.max`, `memory.max`, `memory.current`); fall back to v1 (`/sys/fs/cgroup/cpu/cpu.cfs_quota_us` + `cpu.cfs_period_us`, `/sys/fs/cgroup/memory/memory.limit_in_bytes` + `memory.usage_in_bytes`); return `null` for the affected field where neither is readable (non-Linux dev, unusual mounts).
- **Correction (review finding, post-implementation)**: the v2 files were initially read only at `/sys/fs/cgroup` itself. That is correct under a *private cgroup namespace* (the default on Docker 20.10+/modern K8s, where the apparent root *is* the container's cgroup) but wrong without one (older runtimes on v2, explicit `cgroupns: host`, bare-metal systemd services with unit limits): the v2 root cgroup carries no `cpu.max`/`memory.max` at all, so a limited component reported `processor_assigned = null` and — worse for an audit — the whole **host's** memory as `memory_total`. Fixed by resolving the process's own cgroup from the `0::<path>` line of `/proc/self/cgroup` and consulting **every level up to the root**, taking the most restrictive limit (a limit may be enforced on an ancestor slice); memory usage is read at the level holding the effective limit, since an ancestor limit is shared with siblings. Any resolution failure falls back to the previous root-only read.
- **Known limitation**: limits set *above* a private namespace root (e.g. a K8s pod-level limit when the container itself has none) are invisible from inside the namespace and cannot be self-reported — a fundamental property of self-observation, not an implementation gap.
- **Rationale**: production runs containers (v2 on current hosts, v1 still common); developer machines are macOS (neither) and correctly report `null` for `assigned`. v1 `memory.limit_in_bytes` reports a sentinel near `INT64_MAX` when unlimited — treat values at/above a high threshold as unlimited → `null`. v1 keeps the root-level read: container runtimes bind-mount the container's own v1 controller directories at `/sys/fs/cgroup/<controller>`, so the root read is already container-scoped there.

## D6 — Self-report through the existing heartbeat channel

- **Decision**: Each process writes its own reading to a new cache key `workers:resources:{component}:worker:{WORKER_IDENTITY}` alongside the existing `workers:active:` key, at heartbeat time, with the same short TTL. The value is the JSON of a per-process reading including a **host identifier**. The gatherer reads these keys during the existing `workers:*` scan.
- **Rationale**: reuses the mechanism telemetry already uses to know which workers are alive; no new transport, no new schedule. Reading own resources is local and cheap. A component that fails to read retries a small bounded number of times (FR-005) and, failing that, writes `null` for the unknown fields.
- **Alternatives**: a dedicated resources query flow — rejected (duplicates the heartbeat's liveness scan; more moving parts).

## D7 — Host identifier for dedup

- **Decision**: Host identifier = `socket.gethostname()`. Under Docker/Kubernetes this is the container ID (per container, shared by all processes inside it).
- **Rationale**: enables D8. Stdlib, no privilege needed.

## D8 — Aggregate over distinct hosts, not processes

- **Decision**: For the `server` (api_server) and `workers` (git_agent) rows, group active processes' readings by host identifier, take one reading per host (readings within a host are identical), and **sum across distinct hosts**.
- **Rationale**: `api_server` runs several gunicorn processes in one container sharing one cgroup; `git_agent` runs one process per container (`replicas: N`). Dedup-by-host counts each container's cores exactly once for both. See Complexity Tracking in the plan.
- **Worker count**: unchanged — the existing `workers.total`/`active` (all worker processes by identity). The new `workers` resource fields are the git_agent fleet aggregate; no separate count field is added (D14).

## D9 — Aggregation null and undercount rules

- **Decision**:
  - No host reported a given field → that aggregate field is `null` (unknown). The aggregate has no worker count of its own to tell a genuinely empty fleet from one where nothing reported, so both collapse to `null`; in practice at least one worker always runs (telemetry itself runs in one).
  - A host whose self-read failed writes a reading with every figure `null`; such a reading is **dropped** before summing, so it undercounts like a non-reporting host rather than nulling the whole field.
  - Some hosts reported, some did not → **sum the reporters** (undercount tolerated per FR-005); the separately-tracked worker count still reflects all active workers, so the discrepancy is detectable.
  - For a field where any *contributing* host is `null` because it is genuinely unbounded (e.g. one worker host has no cgroup CPU quota) → the aggregate for that field is `null`: a fleet containing an unbounded node has no finite total.
- **Rationale**: keeps `null` meaning "unknown / unbounded" throughout (no separate measured-empty `0` the consumer would have to distinguish), and makes an undercount observable via the worker count rather than silently nulling the fleet.

## D10 — Payload version bump + receiving-service coordination

- **Decision**: Increment `TELEMETRY_VERSION` (`payload_format`, currently `"20260628"`) to the change date. All new fields are additive; no existing field is renamed or removed.
- **Rationale**: FR-008. The receiving cloud processor + data mart must tolerate the new block and the new version — a cross-team dependency tracked outside this branch. Additive-only + version bump lets older ingestion ignore what it does not recognise rather than break.

## D11 — Reuse `safe_metric` for independent degradation

- **Decision**: Wrap each component's resource assembly (database row, server aggregate, workers aggregate) in the existing `safe_metric` helper so one failing source yields `null` for that block/field only and never blocks the snapshot (FR-006).
- **Rationale**: single degradation boundary already established in the parent telemetry work; no new error-handling pattern.
- **Component self-read logging**: the per-process self-read (at heartbeat time) is a path *separate* from `safe_metric` — it is not wrapped by it. When its bounded retries are exhausted, it MUST log a warning carrying the component type, the worker identity, and the failing source before writing `null` (FR-005). Without this, a worker that silently stops reporting resources shows only as an aggregate undercount with no way to trace which worker or why; the log closes that gap. Warning level (a tolerated degradation, consistent with the existing `safe_metric` warning), structured context, no sensitive data (cores/RAM/host/worker-id only).

## D12 — Read static resource facts once per process

- **Decision**: `host`, `processor_available`, `processor_assigned`, and `memory_total` are constant for a process's lifetime; read them once (at process start / first heartbeat) and cache them. Only `memory_available` (free, which changes with usage) is re-read on each heartbeat.
- **Rationale**: avoids re-reading `/sys/fs/cgroup` and `psutil.cpu_count()` on every heartbeat (~15 s), keeps the liveness loop cheap, and bounds the FR-005 read-retries to process start rather than every cycle.

## D13 — Additive-only is the invariant; the version bump is gated

- **Decision**: The payload change is additive-only (no existing field renamed/removed/retyped). The `payload_format` identifier is **not** incremented until the receiving service confirms it tolerates the new `resources` block; until then the fields ship under the existing version.
- **Rationale**: a version-strict receiver could break on an unexpected version string — the exact regression to avoid. Additive-under-existing-version guarantees current ingestion is untouched, and the bump becomes a coordinated follow-up rather than a unilateral producer change.

## D14 — Extend existing payload sections in place; one new `server` block

- **Decision**: Do not add a parallel `resources` block. Extend the database's existing `system_info` with `processor_assigned`; extend the existing `workers` block with `processor_available`/`processor_assigned`/`memory_total`/`memory_available` (git_agent fleet aggregate); add a single new `server` block for the api_server (which has no existing representation), with the same four fields. All new fields **reuse the existing `system_info` names** (`processor_*`/`memory_*`), so every component is represented identically. The worker count stays the existing `workers.total`/`active`.
- **Rationale**: a parallel block duplicated DB cores/RAM (already in `system_info`) and the worker count — a confusing second API surface. Extending in place, with the existing field names, keeps each component's resources attached to that component, adds nothing redundant, and keeps DB/server/workers directly comparable. Pete's ask is DB + workers; `server` is an explicitly-chosen future-proofing addition.
- **Accepted trade-off**: `workers.total`/`active` count all worker processes (api_server + git_agent) while the new `workers` resource fields cover the git_agent fleet only (api_server resources live in `server`). Documented in the contract. (Naming is *not* a trade-off — the new fields reuse the legacy `processor_*`/`memory_*` names, so the payload is uniform.)
