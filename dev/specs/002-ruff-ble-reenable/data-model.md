# Data Model: BLE001 violation-site inventory and treatment matrix

**Plan**: [plan.md](plan.md) | **Research**: [research.md](research.md)

The "entities" of this feature are the 78 violation sites. Each row below is authoritative for the implementation phase. Analysis performed 2026-07-22 by four parallel read-only reviews of every site (surrounding code, raisable-exception surface, handler behavior); line numbers verified against `ruff check --select BLE001` output on this branch.

## Treatment totals

| Treatment | Count | Where |
|-----------|-------|-------|
| NARROW (specific exception types) | 8 | 6 in backend tests, 2 in `tasks/release.py` |
| SUPPRESS (`# noqa: BLE001` + justification) | 70 | 30 migrations, 8 auth, 16 backend runtime, 7 backend tests, 9 tooling |
| **Total** | **78** | 46 files |

## Normalization rules (apply to every edit)

1. **Suppression form**: bare rule-targeted `# noqa: BLE001` appended to the `except` line. The justification comment goes on its own line immediately **above** the `except` line (not as prose trailing the noqa — keeps ruff's noqa parsing unambiguous and lines under length limits). Where an accurate explanatory comment already exists adjacent to the handler (e.g. `git/sync.py:121-122`, `telemetry/tasks.py:125`, `test_merge_kill_recovery.py:86-88`, `parity.py` trailing comment), keep it — add the `noqa` and only add a new comment if the existing one doesn't state *why broad*.
2. **Narrowing form**: replace the caught type; never touch the handler body; add the exception import following the file's existing import placement convention (module-level, except `tasks/release.py` where `packaging.version` imports are deliberately *function-local* so invoke works without dev deps — extend those local imports in place).
3. **Behavior invariants**: SUPPRESS edits are annotation-only (comments + noqa; zero semantic tokens). NARROW edits change only the exception type expression.
4. **Stale-suppression cleanup**: where narrowing makes an existing `# noqa: S110` unused (typed excepts are exempt from S110 by default), remove it in the same edit — RUF100 (enabled via `select=ALL`) fails on unused noqa.
5. Migration and auth files (Batches A/B): SUPPRESS only — mandated by hard constraints, regardless of narrowability.

## Batch A — Graph migrations (30 sites, all SUPPRESS, annotation-only)

Handler pattern is uniform: convert any failure into `MigrationResult.errors` so the runner (`backend/infrahub/cli/db.py`) reports it and halts without an unhandled traceback (verified: `MigrationResult.success = not errors`; runner logs errors, marks FAILED, does not bump graph version).

| File:Line | Handler behavior | Justification comment |
|-----------|------------------|----------------------|
| core/migrations/graph/m014_remove_index_attr_value.py:39 | Index-drop failure → result.errors, failed result | `# Migration contract: failures become MigrationResult errors; the runner reports them and halts` |
| core/migrations/graph/m029_duplicates_cleanup.py:656 | Whole cleanup wrapped → result.errors | same as m014 |
| core/migrations/graph/m036_drop_attr_value_index.py:39 | Index-drop failure → result.errors | same as m014 |
| core/migrations/graph/m043_create_hfid_display_label_in_db.py:116 | First failing sub-migration → record, return early | `# First failing sub-migration is recorded as a result error and aborts the remaining steps` |
| core/migrations/graph/m043_create_hfid_display_label_in_db.py:168 | Same, non-default branches | same as m043:116 |
| core/migrations/graph/m044_backfill_hfid_display_label_in_db.py:382 | Whole default-branch backfill → result.errors | same as m014 |
| core/migrations/graph/m044_backfill_hfid_display_label_in_db.py:514 | Whole per-branch backfill → result.errors | same as m014 |
| core/migrations/graph/m045_backfill_hfid_display_label_in_db_profile_template.py:82 | Whole backfill → result.errors | same as m014 |
| core/migrations/graph/m045_backfill_hfid_display_label_in_db_profile_template.py:163 | Per-branch backfill → result.errors | same as m014 |
| core/migrations/graph/m046_fill_agnostic_hfid_display_labels.py:141 | Whole `_do_execute` → result.errors | same as m014 |
| core/migrations/graph/m046_fill_agnostic_hfid_display_labels.py:196 | First failing sub-migration → record, return | same as m043:116 |
| core/migrations/graph/m047_backfill_or_null_display_label.py:416 | Default-branch pass → result.errors | same as m014 |
| core/migrations/graph/m047_backfill_or_null_display_label.py:465 | Per-branch pass → result.errors | same as m014 |
| core/migrations/graph/m059_fix_hfid_display_label_nulls.py:238 | Per-node recompute: log, record, skip node, continue | `# Best-effort per-node recompute: record the failure, skip this node, keep fixing the rest` |
| core/migrations/graph/m059_fix_hfid_display_label_nulls.py:247 | Per-node HFID recompute: same | same as m059:238 |
| core/migrations/graph/m059_fix_hfid_display_label_nulls.py:381 | Default+global pass → result.errors | same as m014 |
| core/migrations/graph/m059_fix_hfid_display_label_nulls.py:420 | Per-branch pass → result.errors | same as m014 |
| core/migrations/graph/m062_recompute_permission_display_labels.py:454 | Recompute (default) → result.errors | same as m014 |
| core/migrations/graph/m062_recompute_permission_display_labels.py:473 | Recompute (per branch) → result.errors | same as m014 |
| core/migrations/graph/m063_template_number_pool_cleanup.py:82 | Nullification loop → result.errors | same as m014 |
| core/migrations/graph/m064_template_ip_pool_relationship_cleanup.py:98 | Relationship cleanup → result.errors | same as m014 |
| core/migrations/graph/m066_consolidate_duplicate_number_pools.py:82 | Consolidation (inside open txn) → result.errors | `# Failures become MigrationResult errors so the runner reports them instead of crashing` |
| core/migrations/graph/m070_normalize_mac_address_values_to_colon.py:225 | Per-plan recompute loop → result.errors | same as m014 |
| core/migrations/graph/m071_recompute_hfid_for_ip_attributes.py:180 | Per-kind recompute loop → result.errors | same as m014 |
| core/migrations/graph/m072_index_hfid_values.py:169 | Normalize + index steps → result.errors | same as m014 |
| core/migrations/graph/m073_unify_ip_pool_resource_identifier.py:336 | Pool unification (inside open txn) → result.errors | same as m066 |
| core/migrations/graph/m074_normalize_indexed_hfid_values.py:156 | Normalization → result.errors | same as m014 |
| core/migrations/shared.py:157 | Per-query loop (SchemaMigration): record, abort remaining | `# Per-query failures become result errors so the runner reports them instead of crashing` |
| core/migrations/shared.py:245 | Per-query loop (GraphMigration): record, return early | same as shared:157 |
| core/migrations/shared.py:277 | Per-sub-migration loop: record, abort remaining | `# First failing sub-migration is recorded as a result error and aborts the remaining steps` |

**Comment-truthfulness caveat** (from verification): m066:82, m073:336, shared.py:157, shared.py:245 catch *inside* an open transaction, so a caught failure commits partial work (rollback never fires). The chosen comments deliberately do **not** claim atomicity. See "Latent defects" below.

## Batch B — Authentication paths (8 sites, all SUPPRESS, annotation-only)

| File:Line | Handler behavior | Justification comment |
|-----------|------------------|----------------------|
| api/auth.py:63 | Login-event emission failure: warn, login still succeeds | `# Login event emission is best-effort telemetry; it must never fail a successful login` |
| api/auth.py:116 | Logout-event emission failure: warn, logout completes | `# Logout event emission is best-effort telemetry; it must never fail a successful logout` |
| api/oauth2.py:205 | OAuth2 login-event emission failure: warn, token returned | `# Login event emission is best-effort telemetry; it must never fail a successful OAuth2 login` |
| api/oidc.py:259 | OIDC login-event emission failure: warn, token returned | `# Login event emission is best-effort telemetry; it must never fail a successful OIDC login` |
| auth/auth.py:542 | Any token decode/claim failure → `AuthorizationError` (401) | `# Fail closed: any undecodable or malformed token must map to a 401 auth error, never a 500` |
| auth/auth.py:558 | Any refresh-token decode failure → `AuthorizationError` (401) | `# Fail closed: any undecodable or malformed refresh token must map to a 401, never a 500` |
| auth/auth.py:668 | Provider body not JSON → fall back to text / `GatewayError` (502) | `# Providers may return non-JSON bodies: fall back to text or fail closed with GatewayError (502)` |
| auth/auth.py:679 | Body unreadable → log + `GatewayError` (502) chained | `# If the body cannot be read at all, fail closed with GatewayError (502) rather than a 500` |

Note: the four `auth/auth.py` handlers raise *new* exceptions (not the caught one), which BLE001 still flags — only re-raising the caught exception is exempt. Suppression preserves the fail-closed contract exactly.

## Batch C — Backend runtime (16 sites, all SUPPRESS)

All 16 are defensive boundaries; none has an enumerable raisable set. Every handler already logs or persists the failure (or returns it for rollback + re-raise), satisfying the house guideline.

| File:Line | Boundary type | Justification comment |
|-----------|--------------|----------------------|
| artifacts/tasks.py:49 | Check boundary | `# noqa rationale: check boundary — any render failure must be recorded as a failed artifact check, not crash the flow` → comment: `# Check boundary: any render failure must be recorded as a failed artifact check, not crash the flow` |
| cli/upgrade.py:65 | CLI prerequisite | `# CLI prerequisite boundary: report any failure as an unreachable database and abort cleanly` |
| cli/upgrade.py:244 | Best-effort dry-run probe | `# Best-effort dry-run report: a failed schema probe is reported inline and the remaining checks still run` |
| core/schema/update_coordinator.py:350 | Capture-for-rollback | `# Any migration failure must be captured so the caller can roll back before re-raising it` |
| core/schema/update_coordinator.py:365 | Capture-for-rollback | same as :350 |
| core/validators/tasks.py:85 | Degrade-to-violation | `# Degrade any checker failure into a reported violation so schema validation fails visibly instead of crashing the task` |
| generators/tasks.py:253 | Flow boundary | `# Flow boundary: any generator failure must surface as a Failed state carrying the error, not a crashed flow run` |
| git/integrator.py:383 | Stamp-status-then-reraise | `# Any import failure must stamp the repository sync status as errored before being re-raised` |
| git/sync.py:120 | Per-branch isolation | keep existing comment (lines 121-122); add noqa only |
| message_bus/operations/__init__.py:34 | Consumer boundary | `# Message-bus boundary: any handler failure must be routed to the reply/retry/dead-letter protocol, never crash the consumer` |
| services/scheduler.py:89 | Keep-alive loop | `# Keep-alive: a failing recurring task must not kill the scheduler loop` |
| task_manager/flow_run/retention.py:63 | Best-effort per-item purge | `# Best-effort retention: skip flow runs that fail to purge and keep processing the batch` |
| telemetry/tasks.py:129 | Best-effort telemetry | existing comment at line ~125 documents the bail-out; add noqa; extend comment only if it doesn't say why broad |
| telemetry/tasks.py:152 | Best-effort telemetry | `# Best-effort telemetry: any send failure is recorded as FAILED on the snapshot, never propagated` |
| telemetry/tasks.py:159 | Best-effort telemetry | `# Best-effort telemetry: failing to persist the send status only warrants a warning` |
| webhook/tasks/process.py:90 | Best-effort capture | `# Best-effort capture: an artifact write failure must never alter or mask the delivery outcome` |

(For artifacts/tasks.py:49 use the single comment line shown after the arrow.)

## Batch D — Backend tests (13 sites: 6 NARROW, 7 SUPPRESS)

| File:Line | Treatment | Detail |
|-----------|-----------|--------|
| tests/component/core/schema/schema_branch/test_process_idempotency.py:158 | NARROW | `except SchemaNotFoundError:` — add `from infrahub.exceptions import SchemaNotFoundError`; helper formats "only in after" diff lines; `get(name=...)` raises exactly this when absent |
| tests/component/core/schema/schema_branch/test_process_idempotency.py:164 | NARROW | same (mirror "only in before" case) |
| tests/component/core/schema/schema_branch/test_uniqueness_propagation.py:42 | NARROW | verbatim copy of the same helper — identical narrowing + import |
| tests/component/core/schema/schema_branch/test_uniqueness_propagation.py:48 | NARROW | same |
| tests/helpers/diagnostics.py:103 | SUPPRESS | `# Best-effort post-mortem dump: must never raise while reporting the original error` |
| tests/helpers/diagnostics.py:179 | SUPPRESS | `# Instrumentation must never break the real pool disconnect; log and continue` |
| tests/helpers/events.py:51 | SUPPRESS | `# Polling probe: query_event signals absence with a bare Exception; any failure means "not available yet"` (cannot narrow: `query_event` raises bare `Exception` by design — rewriting it is a behavior change) |
| tests/helpers/test_worker.py:107 | SUPPRESS — **stays `except BaseException`** | `# Any failure (incl. CancelledError) must resolve the "ready" future, else the fixture awaiting it hangs forever` — converting to `Exception` would let `CancelledError`/`SystemExit` escape and deadlock the fixture at `await ready` |
| tests/integration/git/conftest.py:31 | NARROW | `except httpx.HTTPError:` (httpx already imported); retry-poll loop; **remove the now-stale `# noqa: S110`** (typed excepts exempt from S110 → RUF100 would fail) |
| tests/integration/git/conftest.py:53 | NARROW | `except httpx.HTTPError:` — same poll pattern + same S110 cleanup. Residual: malformed-201-body errors now propagate loudly instead of retrying to deadline (acceptable: clearer fixture failure; medium confidence — fallback is SUPPRESS) |
| tests/integration_docker/test_merge_kill_recovery.py:85 | SUPPRESS | keep existing explanatory comment (lines 86-88); add noqa: `# Teardown: the deliberately-killed mutation may raise any SDK/transport error; retrieve and log it without masking the test result` |
| tests/scale/common/protocols.py:28 | SUPPRESS | `# Locust instrumentation: record every failure as a request event instead of crashing the user greenlet` |
| tests/scale/common/protocols.py:53 | SUPPRESS | same comment |

## Batch E — Tooling (11 sites: 2 NARROW, 9 SUPPRESS)

| File:Line | Treatment | Detail |
|-----------|-----------|--------|
| tasks/release.py:155 | NARROW | `except InvalidVersion:` — extend the *function-local* import at ~line 115 to `from packaging.version import InvalidVersion, Version` (do not hoist; locals are deliberate). Only `Version(...)` construction raises; in-file precedent at lines 273/297 |
| tasks/release.py:242 | NARROW | `except InvalidVersion:` — extend function-local import at ~line 213. Regex-permitted suffixes like `1.2.3-foo` are exactly `InvalidVersion` |
| tests/e2e/data/parity.py:81 | SUPPRESS | `_safe` wrapper returns error string per entry; keep/extend existing trailing comment: `# Diagnostic dump: record any per-entry failure as a string, never kill the whole dump` |
| utilities/infrahub_load_tester.py:47 | SUPPRESS | `# Load test: absorb any request failure and continue` |
| utilities/infrahub_load_tester.py:69 | SUPPRESS | same comment. **Do not fix** the pre-existing missing-`return` (unbound `all_branches`) — behavior preservation; see Latent defects |
| utilities/infrahub_load_tester.py:84 | SUPPRESS | `# Load test: absorb any request failure and continue with remaining branches` |
| utilities/infrahub_load_tester.py:108 | SUPPRESS | `# Load test: absorb any request failure and continue with remaining users` |
| utilities/infrahub_load_tester.py:113 | SUPPRESS | same as :108 |
| utilities/infrahub_load_tester.py:138 | SUPPRESS | same as :84 |
| utilities/infrahub_load_tester.py:148 | SUPPRESS | `# Load test: abort branch cleanup gracefully on any request failure` |
| utilities/infrahub_load_tester.py:165 | SUPPRESS | same as :84 |

SDK exception types are deliberately not used for narrowing here: `infrahub_sdk` is imported only under `TYPE_CHECKING` in these files and the submodule isn't guaranteed present at analysis time; httpx errors can also leak through.

## Batch F — Configuration flip

| File | Change |
|------|--------|
| pyproject.toml (~line 511) | Delete the `"BLE",      # flake8-blind-except (BLE)` entry from `[tool.ruff.lint] ignore` |
| changelog/+ruff-ble-blind-except.housekeeping.md | New towncrier fragment (housekeeping type, orphan `+` prefix) |

## Latent defects observed (explicitly OUT OF SCOPE — follow-up candidates)

Recorded so the review phase doesn't mistake them for regressions, and so they can become follow-up tickets:

1. `auth/auth.py:678-679` — the empty-body `GatewayError` raised inside the inner `try` is swallowed by the outer handler and re-raised with a generic message; the specific message never reaches callers.
2. `m066_...py:82` and `m073_...py:336` — catch inside an open `db.start_transaction()` block returns normally → partial work **commits**; rollback never fires.
3. `core/migrations/shared.py:157` and `:245` — same partial-commit-on-failure pattern for every SchemaMigration/GraphMigration using the default `execute`.
4. `utilities/infrahub_load_tester.py:69` — missing `return` after the failure log leaves `all_branches` unbound; the per-branch loop's handler then eats the `NameError`.
5. `backend/tests/helpers/events.py:44,66` — `query_event` raises bare `Exception(...)`; a dedicated exception type would allow narrowing site D-7.

None of these may be fixed in this pass (behavior preservation / hard constraints). All five would change runtime behavior.

## Unflagged look-alikes (no action)

`git/integrator.py` contains additional `except Exception` handlers (e.g. line 308) that BLE001 does **not** flag because their bodies re-raise the caught exception — ruff's built-in exemption. Ruff output is the sole authority for scope; do not "fix" unflagged handlers.
