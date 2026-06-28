# Phase 0 Research: Phase 1 Telemetry Collection

All technical context was grounded by reading the existing telemetry module and its
collaborators. No open `NEEDS CLARIFICATION` items remain.

## Decision 1 — Branch/temporal-correct managed-node count (`corenode`)

**Decision**: Compute `database.node_count["corenode"]` with
`NodeManager.count(db=..., schema=InfrahubKind.NODE, branch=<default>)`. `InfrahubKind.NODE`
== `"CoreNode"`, the generic every managed node inherits.

**Rationale**: `NodeManager.count` builds `NodeGetListQuery` which applies branch + temporal
filters (Constitution II). The existing `gather_database_information` uses raw
`utils.count_nodes(db, label=...)` over `GRAPH_SCHEMA["nodes"]` — those are graph-internal
labels (`Node`, `Attribute`, …) and produce raw vertex tallies with no branch/temporal
correctness. `node_count["total"]` is the raw `count_nodes(db)` vertex total and must stay
as-is (FR-009). The key `corenode` does not collide with any `GRAPH_SCHEMA["nodes"]` label,
so it is a clean additive key.

**Namespace semantics (locked, so `corenode` and the future `user` can never become
synonyms)**: `get_labels()` (`core/node/__init__.py`) applies the `CoreNode` label to every
node whose namespace is **not** `Schema`/`Internal` and which is not a group. So
`NodeManager.count(CoreNode)` counts the **`Core` + `Builtin` + user-defined namespaces** —
including Infrahub's own management objects (`CoreAccount`, `CoreRepository`,
`CoreProposedChange`, `CoreWebhook`, profiles, resource pools, artifacts, …). The three node
metrics therefore nest strictly:

```
user  ⊆  corenode  ⊆  total
```

- `total` — raw vertices (incl. attributes/values/internal bookkeeping).
- `corenode` — **all** managed nodes across `Core` + `Builtin` + user namespaces (this phase).
- `user` (future, IFC-2825) — customer-facing subset that **excludes the `Core` management
  namespace**; the parked decision only chooses whether `Builtin` is in or out, i.e. it slides
  the `user` ⊂ `corenode` gap but never closes it (the `Core` namespace is always non-empty).

This pins the definitions at the namespace level so a later `user` definition cannot
accidentally equal `corenode` — a real concern given FR-011 forbids removing a shipped field.

**Alternatives considered**: `count_nodes(label="CoreNode")` — rejected: no branch/temporal
filter, would diverge from how GraphQL resolvers count and would not match an
independently-computed fixture (fails SC-003).

## Decision 2 — Account & branch metrics

**Decision**:
- `accounts.active` = `NodeManager.count(db, schema=InfrahubKind.ACCOUNT, filters={"status__value": AccountStatus.ACTIVE.value}, branch=<default>)`.
- `accounts.groups` = `NodeManager.count(db, schema=InfrahubKind.ACCOUNTGROUP, branch=<default>)`.
- `branches.active` = count of `registry.branch.values()` where `not is_default and not is_global`.

**Rationale**: `NodeManager.count` is the same path the account GraphQL resolver uses
(grounded in `graphql/queries/account.py`). `CoreAccount.status` is an enum attribute, so the
`status__value` filter selects `AccountStatus.ACTIVE`. The registry already holds all open
branches; `branches.total` today is `len(registry.branch)`. `is_default` marks `main`,
`is_global` marks `-global-` (`GLOBAL_BRANCH_NAME`), so excluding both yields open
non-system branches. Closed/merged/deleted branches are removed from the registry, so
"registry membership" already means "open".

**Alternatives considered**: Querying branches from the DB — rejected: the registry is the
in-memory source of truth used elsewhere and avoids an extra query (Constitution V, VII).

## Decision 3 — NEW 24h-windowed Prefect event path (logins, unique_logins)

**Window anchor (decided)**: The 24h window is anchored to a **deterministic calendar
boundary, NOT to `datetime.now()` at gather time**. Compute:

```
window_end   = floor_to_midnight_utc(now)   # 00:00:00 UTC of the current day
window_start = window_end - 24h             # 00:00:00 UTC of the previous day
```

so each daily run reports the **previous full UTC calendar day** `[window_start, window_end)`.

Rationale: the daily flow is scheduled `f"{random.randint(0, 59)} 2 * * *"`
(`workflows/catalogue.py`) — a per-deployment-fixed minute, firing at 02:XX. Anchoring the
window to execution `now` is fragile: gather time drifts day-over-day (worker contention, the
flow's own retries, queue latency), so consecutive `[now-24h, now]` windows either **overlap**
(events double-counted) or leave a **gap** (events counted in neither run). SC-002 explicitly
requires "no retention leakage/overlap", so the window must tile exactly. Flooring to midnight
UTC makes the daily series tile perfectly regardless of the random minute or execution jitter;
because the job runs at 02:XX, `window_end` (00:00 today) is always 2-3h settled in the past,
so every prior-day event has landed. A missed run simply yields an absent day rather than a
smeared one, and tests can pin a real boundary with `freezegun` instead of a moving `now`. The
field name `activity_24h` is retained (it is a 24h window); only the anchor is fixed.

**Decision**: Add a new windowed counter that posts to `/events/count-by/event` with an
`occurred` window (`since = window_start`, `until = window_end` as defined above) in the
filter, alongside the existing `event.name` filter. For `account.logged_in`:
- `activity_24h.logins` = the windowed count of `infrahub.account.logged_in` events.
- `activity_24h.unique_logins` = distinct accounts in the same window, obtained by counting
  by **resource** (`/events/count-by/resource`) over the windowed `logged_in` filter and
  taking the number of buckets. Each login event's `prefect.resource.id` is
  `infrahub.account.{account_id}` (grounded in `AccountLoggedInEvent.get_resource`), so one
  bucket per distinct account ⇒ bucket count = unique logins.

The existing `gather_prefect_events` (no time window) is **left untouched** (FR-007); the new
path is separate functions feeding `activity_24h`.

**Rationale**: Logins are events stored in Prefect (ADR 0002); Neo4j has no `last_login`. The
event name is `infrahub.account.logged_in` (`AccountLoggedInEvent.event_name`). The 24h
window (≪ 7-day event retention) guarantees no retention leakage when the `occurred` filter
is applied (SC-002). Counting by resource id is the natural distinct-count primitive without
pulling every event.

**Alternatives considered**: (a) modify `gather_prefect_events` to add a window — rejected by
FR-007 (must not change existing output). (b) pull all events and de-dup in Python —
rejected: heavier, and Prefect's count-by primitives do it server-side (Constitution V).

## Decision 4 — Webhook success/failure over 24h

**Decision**: `activity_24h.webhooks_fired_success` / `_failure` come from Prefect **flow
runs** of the `webhook-process` flow (grounded: `@flow(name="webhook-process")` in
`webhook/tasks/process.py`) started within the **same `[window_start, window_end)` calendar-day
window as the event metrics** (Decision 3 anchor — not `now`), split by terminal state:
`COMPLETED` ⇒ success; `FAILED` / `CRASHED` (and `TIMEDOUT`) ⇒ failure. Query via the Prefect
client's flow-run read API filtered by flow name and `start_time` in `[window_start, window_end)`.

**Rationale**: Webhook delivery is a flow run, not an InfrahubEvent, so flow-run state is the
correct signal. Webhook flow-run retention is 90 days (≫ 24h), so the window is always fully
covered. Counts are best-effort trend signals (dispatch can drop), framed against windowing
correctness, not an external ground truth.

**Alternatives considered**: Deriving from events — rejected: webhook outcome lives in the
flow-run state, not an event.

## Decision 5 — Graceful degradation contract (`null` vs `0`)

**Decision**: New payload fields are `int | None`. Introduce a single async helper in
`tasks.py` that runs a metric coroutine, returns its value on success, and on any exception
logs a warning and returns `None`. The orchestrator (`gather_anonymous_telemetry_data`)
gathers each new metric through this helper, so one failing source ⇒ that field `null`, the
rest of the payload still built, stored, and sent. A source that succeeds with nothing to
count returns `0` naturally (e.g. `NodeManager.count` ⇒ 0, empty window ⇒ 0).

**Rationale**: FR-010 / SC-001 require per-metric isolation and a `null`-means-failure,
`0`-means-empty convention. A single helper serving ≥2 callers is the justified extraction
(Constitution VII). Existing required fields are **not** widened to optional (FR-011) — only
the new fields are nullable.

**`node_count` value-type note**: `node_count` is currently `dict[str, int]`. To let
`corenode` be `null` on failure while keeping it inside `node_count` (the field name the
contract mandates), the value type widens to `dict[str, int | None]`. This is additive in
practice: existing keys (`total`, graph labels) are always populated `int`; only the new
`corenode` key can be `null`. A forward-compatible consumer is unaffected. Documented as an
accepted, additive type-widening rather than a meaning/name change (FR-011 honored).

**Alternatives considered**: Wrapping the whole gather in one try/except — rejected: a single
failure would null unrelated metrics, violating per-metric isolation.

## Decision 6 — `payload_format` bump

**Decision**: Bump `TELEMETRY_VERSION` in `constants.py` from `"20250318"` to a new date
string (`"20260628"`). `DEFAULT_PAYLOAD_FORMAT` follows it. The value flows into both the
stored snapshot and the remote payload (`payload_format` key) already.

**Rationale**: FR-007 requires advancing the format identifier when fields are added. The
codebase already uses a `YYYYMMDD` convention.

## Decision 7 — Test strategy (grounded)

**Decision**:
- **SC-003 (corenode)** — component test in `test_datatabase.py`: seed a known number of
  managed nodes via existing schema fixtures, independently compute the expected count, assert
  `node_count["corenode"]` matches exactly (±0).
- **SC-002 (windowing)** — component/unit test in `test_task_manager.py`: emit `logged_in`
  and `webhook-process` records inside and outside the 24h window; assert in-window-only
  counts and that `unique_logins` collapses repeat logins per account.
- **SC-001 (presence + degradation)** — new `test_tasks.py`: run the gather flow; assert all
  in-scope fields present; force one source to fail (via an injected failing adapter/fixture,
  not `unittest.mock`) and assert that field is `null`, others populated, payload still built;
  assert genuine-empty ⇒ `0`.

**Rationale**: Aligns with Constitution IV and `testing-python.md` (no mocking; component
tests via TestContainers; adapter/fixture injection; files mirror source). Existing
`prefect_test_fixture` and telemetry component fixtures are reused.

**No-mock seam (decided, not open)**: The `null`-vs-`0` contract is proven WITHOUT any
`unittest.mock` by two complementary, decided approaches:

1. **Degradation helper unit test** (`test_degradation.py`): the helper takes a coroutine and
   returns its value or `None` on exception. Pass it (a) a coroutine that `raise`s → assert
   `None`; (b) a coroutine returning `0` → assert `0`; (c) a coroutine returning `N` → assert
   `N`. No DB, no mock — a plain failing/succeeding coroutine is the test double.
2. **Flow presence test** (`test_tasks.py`): assert every in-scope field is present in the
   gathered payload on a healthy stack. End-to-end "one source nulled, rest populated" is
   covered by composing the helper (proven in #1) with the orchestrator wiring; if a natural
   failing-source fixture is cheap (e.g. pointing a gather at an absent Prefect resource) it is
   added, but the contract does NOT depend on mocking a failure end-to-end.

**Deterministic time (decided)**: the 24h-window tests (SC-002) use `freezegun` to pin "now"
(an explicitly allowed exception in `testing-python.md` for time-dependent behavior), so
in-window vs out-of-window fixtures are unambiguous and non-flaky.

**Prefect `.fn` + logger**: where a `@task`/`@flow`-decorated function is exercised via `.fn`
outside a flow context, `get_run_logger` is handled per the allowed `testing-python.md`
pattern (return a stdlib logger), not via general mocking.

## Decision 9 — Phase split by "is the event already flowing?" (checks & artifacts pulled in)

**Decision**: Once the windowed event path exists (Decision 3), any metric derived from an
**already-emitted, already-counted** event costs ~one event name + a parametrized test. So the
Phase 1/2 boundary for event-derived metrics is drawn on *"is the event already flowing and is
a raw windowed count the valuable signal?"* — not on the original card's labelling. Verified
against `get_all_events()`:

- **Pulled into Phase 1** (events emitted & counted today; raw per-period count *is* the
  depth-of-adoption signal): `validator.started/passed/failed` → `checks_*`;
  `artifact.created/updated` → `artifacts_*`; `branch.created/merged/deleted` → `branches_*`.
  Near-zero marginal cost, serves a stated Phase 1 goal. Branch lifecycle counts need no
  correlation — only branch *lifetime* (duration) does.
- **Held in Phase 2 although the events exist** (a bare count would be permanent contract
  surface per FR-011 without clear standalone Phase 1 value):
  - PR governance — `proposed_change.*` exist, but "merged without review" needs per-PR
    review↔merge correlation.
  - Branch *lifetime* — the create→merge duration needs durable per-branch correlation (the
    lifecycle *counts* are pulled in above; only the duration is deferred).
  - Node churn — `node.created/updated/deleted` exist, but `node.updated` fires on every
    attribute mutation incl. automated/computed writes, so the count is machine-dominated — a
    noisy adoption proxy, not a clean signal. (Held on signal quality, not cost.)
  - Branch `rebased`/`migrated` counts — maintenance/automation-driven, lower-signal than
    create/merge/delete; deferred to keep the permanent field set focused.
- **Stay Phase 2 — no events at all**: generators/transformations (no `generator.*`/`transform.*`
  events), distinct API tokens (no token identity in events), CLI/MCP/Sync (greenfield SDK
  instrumentation), licensing cores/RAM (product-scope decision).

**Rationale**: This keeps Phase 1 disciplined (every field must serve a stated goal, not just
be cheap) while harvesting the genuine free wins the windowing enabler unlocks. The discipline
matters because FR-011 makes every shipped field unremovable.

**Scope note (divergence from handoff PRD)**: checks/artifacts and branch-lifecycle counts
were not in the handoff PRD's in-scope FR list; they are a deliberate, user-directed expansion
recorded in `alignment-check.md` §6. The events being verified-present is what makes the
expansion safe.

## Decision 8 — Webhook run terminality & count cost (secondary)

**Webhook non-terminal runs**: a `webhook-process` run that started in-window but is still
`PENDING`/`RUNNING`/`SCHEDULED` at gather time is counted as neither success nor failure. This
is correct for a best-effort daily trend signal — only terminal outcomes are tallied. Captured
in the contract and data model.

**`corenode` count cost (Constitution V)**: `NodeManager.count(CoreNode)` is a single aggregate
query (order disabled) over the managed-node generic with branch/temporal filters — no N+1, no
node materialization. On very large deployments this is still a full count; it runs once per
day in a batch job, so the cost is acceptable. A benchmark is not required for this phase but
the single-aggregate shape is a deliberate choice over per-label summation.
