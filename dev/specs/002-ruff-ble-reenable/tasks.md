# Tasks: Re-enable ruff BLE (blind-except) rule and fix all violations

**Input**: Design documents from `specs/002-ruff-ble-reenable/`

**Prerequisites**: plan.md, spec.md, research.md, **data-model.md (authoritative per-site treatment matrix — every fix task below references its batch table)**, quickstart.md

**Tests**: No new tests are written (spec FR-008: existing tests must pass unchanged). Verification is lint-gate + existing-suite based.

**Organization**: Grouped by user story. **Execution order is inverted relative to story priority**: US1 (P1, enforcement flip) *depends on* US2+US3 (all 78 sites fixed) because CI lints the whole repo the moment the ignore entry is removed. US3 and US2 are mutually independent and internally parallel.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 = enforcement active; US2 = handlers narrowed; US3 = broad catches justified

**Editing rules for every fix task** (data-model.md "Normalization rules"): SUPPRESS = justification comment on its own line immediately above the `except` line + bare `# noqa: BLE001` appended to the `except` line; keep existing adjacent comments; zero semantic tokens changed. NARROW = change only the caught-type expression + add the import per file convention. Never touch handler bodies. After each task: `uv run ruff check --select=BLE <files>` reports 0 for those files AND `uv run ruff format --check <files>` is clean.

---

## Phase 1: Setup

**Purpose**: Confirm the working inventory still matches the plan before editing.

- [X] T001 Re-measure the violation inventory from repo root with `uv run ruff check --select=BLE --output-format=concise .` and reconcile against the 78 sites in specs/002-ruff-ble-reenable/data-model.md; if any site moved (line drift) locate it by handler shape in the same file; if any *new* site appeared, classify it with the same policy (constraint area → SUPPRESS; defensive boundary → SUPPRESS; enumerable surface → NARROW) and append it to the matching batch table in specs/002-ruff-ble-reenable/data-model.md before proceeding

---

## Phase 2: Foundational

**No foundational tasks** — the feature has no shared scaffolding; Phase 1's inventory check is the only prerequisite. Proceed directly to the story phases.

---

## Phase 3: User Story 3 — Genuinely-broad catches are explicit and justified (Priority: P3) — executes first

**Goal**: All 70 SUPPRESS sites carry a truthful justification comment + line-targeted `# noqa: BLE001`, with zero behavioral change (annotation-only diffs).

**Independent Test**: `uv run ruff check --select=BLE <the 70 sites' files>` reports 0; `git diff` for migration/auth files shows only comment/noqa additions.

### Implementation for User Story 3

- [X] T002 [P] [US3] Apply SUPPRESS per data-model.md Batch A rows to migrations m014–m047 (13 sites): backend/infrahub/core/migrations/graph/m014_remove_index_attr_value.py:39, m029_duplicates_cleanup.py:656, m036_drop_attr_value_index.py:39, m043_create_hfid_display_label_in_db.py:116+168, m044_backfill_hfid_display_label_in_db.py:382+514, m045_backfill_hfid_display_label_in_db_profile_template.py:82+163, m046_fill_agnostic_hfid_display_labels.py:141+196, m047_backfill_or_null_display_label.py:416+465 — use each row's exact justification comment
- [X] T003 [P] [US3] Apply SUPPRESS per data-model.md Batch A rows to migrations m059–m074 (14 sites): backend/infrahub/core/migrations/graph/m059_fix_hfid_display_label_nulls.py:238+247+381+420, m062_recompute_permission_display_labels.py:454+473, m063_template_number_pool_cleanup.py:82, m064_template_ip_pool_relationship_cleanup.py:98, m066_consolidate_duplicate_number_pools.py:82, m070_normalize_mac_address_values_to_colon.py:225, m071_recompute_hfid_for_ip_attributes.py:180, m072_index_hfid_values.py:169, m073_unify_ip_pool_resource_identifier.py:336, m074_normalize_indexed_hfid_values.py:156 — m066/m073 use the transaction-safe wording (no atomicity claims)
- [X] T004 [P] [US3] Apply SUPPRESS per data-model.md Batch A rows to backend/infrahub/core/migrations/shared.py:157+245+277 (3 sites; :157/:245 use the per-query wording without atomicity claims)
- [X] T005 [P] [US3] Apply SUPPRESS per data-model.md Batch B rows to the 8 auth sites: backend/infrahub/api/auth.py:63+116, backend/infrahub/api/oauth2.py:205, backend/infrahub/api/oidc.py:259, backend/infrahub/auth/auth.py:542+558+668+679 — annotation-only; fail-closed comments exactly as tabled
- [X] T006 [P] [US3] Apply SUPPRESS per data-model.md Batch C rows (part 1, 9 sites / 8 files): backend/infrahub/artifacts/tasks.py:49, backend/infrahub/cli/upgrade.py:65+244, backend/infrahub/core/schema/update_coordinator.py:350+365, backend/infrahub/core/validators/tasks.py:85, backend/infrahub/generators/tasks.py:253, backend/infrahub/git/integrator.py:383, backend/infrahub/git/sync.py:120 (sync.py: keep the existing lines-121-122 comment, add noqa only)
- [X] T007 [P] [US3] Apply SUPPRESS per data-model.md Batch C rows (part 2, 7 sites / 5 files): backend/infrahub/message_bus/operations/__init__.py:34, backend/infrahub/services/scheduler.py:89, backend/infrahub/task_manager/flow_run/retention.py:63, backend/infrahub/telemetry/tasks.py:129+152+159 (:129 has an existing intent comment ~line 125 — add noqa, extend comment only if it doesn't say why broad), backend/infrahub/webhook/tasks/process.py:90
- [X] T008 [P] [US3] Apply SUPPRESS per data-model.md Batch D rows to the 7 backend-test suppress sites: backend/tests/helpers/diagnostics.py:103+179, backend/tests/helpers/events.py:51, backend/tests/helpers/test_worker.py:107 (**stays `except BaseException`** — use the ready-future justification comment verbatim), backend/tests/integration_docker/test_merge_kill_recovery.py:85 (keep existing lines-86-88 comment, add noqa + tabled comment), backend/tests/scale/common/protocols.py:28+53
- [X] T009 [P] [US3] Apply SUPPRESS per data-model.md Batch E rows to the 9 tooling suppress sites: tests/e2e/data/parity.py:81 (keep/extend the existing trailing comment) and utilities/infrahub_load_tester.py:47+69+84+108+113+138+148+165 (do **not** fix the pre-existing missing-`return` at :69 — behavior preservation, see data-model.md Latent defects)
- [X] T010 [US3] Story checkpoint: run `uv run ruff check --select=BLE backend/infrahub backend/tests tests/e2e/data/parity.py utilities/infrahub_load_tester.py` — every remaining violation must be one of the 8 NARROW sites only; run `uv run ruff format --check` on all files touched by T002–T009 (clean); run `git diff -- backend/infrahub/core/migrations/ backend/infrahub/api/auth.py backend/infrahub/api/oauth2.py backend/infrahub/api/oidc.py backend/infrahub/auth/` and verify every hunk is comment/noqa-only (spec SC-007)

**Checkpoint**: All intentional broad catches are now auditable; only the 8 NARROW sites still flag.

---

## Phase 4: User Story 2 — Existing blind handlers are narrowed to real failure modes (Priority: P2)

**Goal**: The 8 analyzable handlers catch the specific exception types the guarded code raises; handler bodies untouched.

**Independent Test**: `uv run ruff check --select=BLE backend/tests/component/core/schema/schema_branch backend/tests/integration/git/conftest.py tasks/release.py` reports 0; existing tests pass unchanged.

### Implementation for User Story 2

- [X] T011 [P] [US2] Narrow the duplicated `_describe_hash_diff` helper per data-model.md Batch D: replace `except Exception` with `except SchemaNotFoundError` at backend/tests/component/core/schema/schema_branch/test_process_idempotency.py:158+164 and backend/tests/component/core/schema/schema_branch/test_uniqueness_propagation.py:42+48, adding `from infrahub.exceptions import SchemaNotFoundError` to each file's imports
- [X] T012 [P] [US2] Narrow the two poll loops in backend/tests/integration/git/conftest.py:31+53 per data-model.md Batch D: `except Exception` → `except httpx.HTTPError` (httpx already imported) and **remove the now-stale `# noqa: S110` on those lines** (typed excepts are S110-exempt; RUF100 fails on unused noqa)
- [X] T013 [P] [US2] Narrow the two version-probe handlers in tasks/release.py:155+242 per data-model.md Batch E: `except Exception` → `except InvalidVersion`, extending the **function-local** imports (~line 115 and ~line 213) to `from packaging.version import InvalidVersion, Version` — do not hoist to module level (locals are deliberate so invoke runs without dev deps)
- [X] T014 [US2] Story checkpoint: `uv run ruff check --select=BLE .` from repo root reports **0** (all 78 resolved); `uv run ruff format --check` clean on the 6 narrowed files; sanity checks `uv run python -c "from packaging.version import Version; Version('1.2.3-foo')"` (expect InvalidVersion raised) and `uv run invoke --list > /dev/null` (imports OK); run `uv run pytest backend/tests/component/core/schema/schema_branch/test_process_idempotency.py backend/tests/component/core/schema/schema_branch/test_uniqueness_propagation.py` if the local environment supports testcontainers — otherwise record "deferred to CI" with the reason (critique E4: conftest narrowings are CI-verified by design; documented fallback = SUPPRESS per data-model.md)

**Checkpoint**: Zero BLE001 violations repo-wide; rule can now be activated.

---

## Phase 5: User Story 1 — Blind-except enforcement is active for all future code (Priority: P1) 🎯 the durable value

**Goal**: BLE is enforced by the normal lint gates; a new unjustified blind except fails lint locally and in CI.

**Independent Test**: spec US1 acceptance scenarios — config flipped, full gates green, canary mutation fails lint.

### Implementation for User Story 1

- [ ] T015 [US1] Remove the `"BLE",      # flake8-blind-except (BLE)` line from the `[tool.ruff.lint]` `ignore` list in pyproject.toml (~line 511) — depends on T010 + T014 (all sites resolved)
- [ ] T016 [P] [US1] Add towncrier fragment changelog/+ruff-ble-blind-except.housekeeping.md: one sentence stating the BLE (flake8-blind-except) ruff rule is now enforced — blind `except Exception` handlers are either narrowed or carry an explicit justified `# noqa: BLE001`
- [ ] T017 [US1] Full-gate verification (quickstart.md §1–2): `uv run ruff check --select=BLE .` → 0; `uv run ruff check . --exclude python_sdk` → exit 0; `uv run ruff format --check --diff --exclude python_sdk .` → exit 0; `uv run invoke backend.lint` → exit 0 (ruff + ty + mypy)
- [ ] T018 [US1] Enforcement mutation check (quickstart.md §3, spec SC-006): append the canary `except Exception: pass` function to tasks/utils.py, verify `uv run ruff check --select=BLE tasks/utils.py` reports exactly 1 × BLE001, then `git checkout -- tasks/utils.py` and verify the tree is clean

**Checkpoint**: Enforcement live; all card acceptance criteria met except final audits.

---

## Phase 6: Polish & Cross-Cutting Verification

**Purpose**: Auditability proofs and existing-suite regression evidence (spec SC-003/004/005).

- [ ] T019 [P] Suppression audit (quickstart.md §4): `grep -rn "noqa: BLE001" --include="*.py" . --exclude-dir=python_sdk --exclude-dir=.venv` — count must equal the SUPPRESS total from data-model.md (70, plus any T001 additions); each hit sits on an `except Exception`/`except BaseException` line with a justification comment on or immediately above it; `uv run ruff check --select=E722 .` → 0 bare excepts
- [ ] T020 [P] Run `uv run invoke backend.test-unit` — must pass with unchanged results (spec SC-005); if any failure, it must be traceable to something other than this change (compare against base) before proceeding
- [ ] T021 Re-verify hard-constraint diffs end-state (spec SC-007): `git diff <base-of-branch>..HEAD -- backend/infrahub/core/migrations/ backend/infrahub/api/auth.py backend/infrahub/api/oauth2.py backend/infrahub/api/oidc.py backend/infrahub/auth/` contains only comment/`noqa` additions; record the diff summary in the implementation report
- [ ] T022 Run the complete quickstart.md top-to-bottom as a final pass and record each command's outcome (this is the evidence table for the implementation report; include the T014 component-test outcome or its CI-deferral note)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none — start immediately.
- **Foundational (Phase 2)**: empty — skip.
- **US3 (Phase 3) and US2 (Phase 4)**: both depend only on T001. T002–T009 and T011–T013 are all [P] — 11 independent fix tasks touching disjoint file sets; T010 and T014 are their story checkpoints.
- **US1 (Phase 5)**: T015 depends on T010 + T014 (every site resolved). T016 is independent [P]. T017–T018 depend on T015.
- **Polish (Phase 6)**: T019–T021 depend on T017; T022 last.

### Story Dependency Note (deviation from template independence)

US1 (P1) is *implemented last* despite being the highest-value story: activating the rule before the 78 sites are resolved would fail every lint gate. This inversion is inherent to lint-enablement work and was accepted in the spec ("enforcement without narrowing is impossible — CI would fail"). US2 and US3 are fully independent of each other (disjoint files) and each independently testable via per-file `ruff check --select=BLE`.

### Parallel Opportunities

```text
After T001:
  T002 | T003 | T004 | T005 | T006 | T007 | T008 | T009   (US3 — 8 parallel suppress batches)
  T011 | T012 | T013                                      (US2 — 3 parallel narrow batches)
Then: T010 (US3 gate) and T014 (US2 gate)
Then: T015 → (T016 parallel) → T017 → T018
Then: T019 | T020 → T021 → T022
```

## Implementation Strategy

Single-branch, incremental, committed per logical group (checkpoint-commit convention). MVP = all of US3+US2+US1 — this feature only ships whole (the config flip is all-or-nothing). Stop-and-validate points are T010, T014, T017. If T017 fails on a rule other than BLE (e.g. RUF100 on a mistyped noqa), fix within the offending task's scope and re-run. If a NARROW site proves wrong at T014/T020 (an expected exception type escapes in tests), fall back to that site's documented SUPPRESS treatment rather than widening the narrow set speculatively.

**PR narrative reminder** (plan.md / critique X2): enforcement on; 78 sites — 8 narrowed (tests/tooling only), 70 justified suppressions; zero production behavior change; 5 latent defects documented for follow-up, deliberately untouched.
