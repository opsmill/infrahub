---
description: "Task list for INFP-468 — Enriched GraphQL Error Catalogue"
---

# Tasks: Enriched GraphQL Error Catalogue (INFP-468)

**Input**: Design documents in `specs/infp-468-graphql-error-catalogue/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included. The constitution gate (plan.md §Constitution Check) and Success Criteria SC-001/SC-004/SC-005/SC-008 require unit, functional, and E2E coverage; tests appear inside each user story phase and are not strictly TDD-ordered (the wire-format contracts in `contracts/` already pin the expected behaviour).

**Organization**: Tasks are grouped by user story. Phase 2 (foundational) MUST complete before any user story starts. Within a story, tests and implementation can be interleaved as long as the test exists for any code merged.

## Format

`- [ ] [TaskID] [P?] [Story?] Description with file path`

`[P]` = parallelizable (different files, no incomplete dependencies). `[USx]` = belongs to user story x.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the new package directories so subsequent phases can populate them. No user-visible behaviour changes here.

- [X] T001 Create the new backend package directory `backend/infrahub/errors/` with an empty `backend/infrahub/errors/__init__.py`

> **Note**: The original T002 (placeholder `.gitkeep` for `frontend/app/src/shared/api/errors/`) was dropped — US2's binding generator (T029) creates the directory when it writes `catalogue.generated.ts`, so an empty placeholder is unnecessary. The original T003 (towncrier changelog fragment) was moved to Phase 3 as T015a because the fragment describes a behaviour change that doesn't ship until US1's formatter and exception-handler updates land.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the authoritative Python catalogue, its export pipeline, and the committed schema artefact. Every user story depends on this phase.

**⚠️ CRITICAL**: No user story (US1–US5) work begins until this phase is complete.

- [X] T004 Define `CatalogueEntry` Pydantic model (frozen, fields per data-model.md §`CatalogueEntry`) in `backend/infrahub/errors/catalogue.py`
- [X] T005 [P] Define all 10 payload Pydantic models (`NodeNotFoundData`, `AuthenticationRequiredData`, `TokenExpiredData`, `PermissionDeniedData`, `AttributeRequiredData`, `AttributeInvalidTypeData`, `AttributeConstraintViolationData`, `BranchNotFoundData`, `SchemaNotFoundData`, `UndefinedErrorData`) per data-model.md §Payload models in `backend/infrahub/errors/payloads.py` with `model_config = {"extra": "forbid"}`
- [X] T006 [P] Introduce new exception subclasses `AttributeRequiredError`, `AttributeInvalidTypeError`, `AttributeConstraintViolationError` (derived from existing `ValidationError`) in `backend/infrahub/errors/exceptions.py` with the typed payload attributes per data-model.md §Payload models: `AttributeRequiredError` → `node_kind`, `field_name`; `AttributeInvalidTypeError` → adds `expected_type`, `received_type`; `AttributeConstraintViolationError` → adds `constraint`, optional `detail`. No `CATALOGUE_CODE` class attribute — catalogue routing is recovered via the reverse-lookup `EXCEPTION_TO_CODE` map built in `catalogue.py` so the OrderedDict key stays the single source of truth.
- [X] T007 ~~Annotate the five adopted exception classes in `backend/infrahub/exceptions.py` with `CATALOGUE_CODE`.~~ Dropped during review: keeping `backend/infrahub/exceptions.py` untouched is preferable. Build `EXCEPTION_TO_CODE: dict[type[Exception], str]` in `backend/infrahub/errors/catalogue.py` (derived from each `CatalogueEntry.exception_class`, excluding `AuthorizationError` whose split routing happens at the formatter per R-005). `ValidationError` is not in the map — its catalogue routing is handled by the new subclasses introduced in T006.
- [X] T008 Build the ordered `CATALOGUE: OrderedDict[str, CatalogueEntry]` registry in `backend/infrahub/errors/catalogue.py`, populating all 9 v1 codes plus `UNDEFINED_ERROR` per data-model.md §Registry construction (depends on T004, T005, T006, T007)
- [X] T009 Implement `export_catalogue() -> dict` and CLI entrypoint in `backend/infrahub/errors/export.py` producing the JSON Schema document specified in `contracts/catalogue-schema.md` (uses `BaseModel.model_json_schema()` per R-002, R-003)
- [X] T010 Add Invoke task `backend.export-error-catalogue` to `tasks/backend.py` that writes `schema/error-catalogue.json` via the exporter from T009
- [X] T011 [P] Generate and commit the initial `schema/error-catalogue.json` by running `uv run invoke backend.export-error-catalogue`; verify it conforms to the contract in `contracts/catalogue-schema.md`; `contracts/catalogue.example.json` is a structural reference (depends on T010)
- [X] T012 [P] Add `unit/errors/__init__.py` and unit tests for the catalogue registry in `backend/tests/unit/errors/test_catalogue.py` (asserts every code has a payload model, every payload model has `extra="forbid"`, every adopted exception class is reachable from a `CatalogueEntry.exception_class`)
- [X] T013 [P] Add unit tests for payload model JSON Schema export in `backend/tests/unit/errors/test_payloads.py` (asserts each `model_json_schema()` contains `additionalProperties: false` and the expected required fields)
- [X] T013a [P] FR-013 enforcement test in `backend/tests/unit/errors/test_payloads.py`: assert `PermissionDeniedData` exposes only `action` and `resource_kind` (no `identifier`, no `resource_id`); add a formatter-level test in `backend/tests/unit/graphql/test_error_formatter.py` asserting that when `PermissionDeniedError` carries a target identifier on its exception attributes, the emitted `extensions.data` does NOT include it (constitution Principle VI; FR-013). (Payload-level half done; formatter-level half blocked on T015.)
- [X] T014 [P] Add unit test for `export_catalogue()` round-trip in `backend/tests/unit/errors/test_export.py` (asserts wrapper version, `codes` keys, and that each entry has the four required fields per `contracts/catalogue-schema.md`)

**Checkpoint**: Catalogue is in code, exported to JSON, and unit-tested. User-story phases can now proceed in parallel.

---

## Phase 3: User Story 1 — Structured Error Codes and Data in GraphQL Responses (Priority: P1) 🎯 MVP

**Goal**: Every GraphQL error response carries `extensions.code` (string) + `extensions.http_status` (int) + `extensions.data` (typed). Catalogued exceptions surface their code; everything else degrades to `UNDEFINED_ERROR`. Multi-field validation produces one `errors[]` entry per failing field, with `path` pointing at the offending field.

**Independent Test**: Issue a GraphQL request that triggers each of the 9 codes (and one synthetic uncatalogued exception); assert response matches `contracts/graphql-error-envelope.md`. Auth-short-circuit case on `/graphql` returns the GraphQL envelope rather than the REST envelope.

### Implementation for User Story 1

- [X] T015 [US1] Implement `catalogue_error_formatter(error: GraphQLError) -> GraphQLFormattedError` in `backend/infrahub/graphql/error_formatter.py` per research R-005: call `format_error(error)` for the baseline, look up `type(original_error)` in `EXCEPTION_TO_CODE` (defined in `backend/infrahub/errors/catalogue.py`) to recover the catalogue code, handle the `AuthorizationError` split separately (no-creds → `AUTHENTICATION_REQUIRED`, expired-signature → `TOKEN_EXPIRED`) since that class is intentionally not in the reverse map, build typed payload via `model.model_dump(mode="json")`, fall back to `UNDEFINED_ERROR`
- [X] T015a [P] [US1] Add towncrier changelog fragment `changelog/+graphql-error-catalogue.changed.md` calling out the breaking change to GraphQL `extensions.code` (integer→string), the new `extensions.http_status` field, and the new error catalogue + docs page (per spec.md §Breaking Changes and §Release-notes requirement). `changed` is the correct towncrier section per `pyproject.toml`; `feature` is not a valid directory. **MUST land in the same PR/release as T016, T019, and US2's T031/T032** — the fragment describes a behaviour change those tasks introduce; landing it earlier would advertise a change that has not actually shipped.
- [X] T016 [US1] Wire the formatter into `InfrahubGraphQLApp` construction in `backend/infrahub/graphql/initialization.py` (pass `error_formatter=catalogue_error_formatter` to the existing constructor; no infra change per R-005)
- [X] T017 [US1] Implement `raise_classified_validation_errors(input_value: dict[str, str], *, node_kind: str, path: list[str]) -> NoReturn` in `backend/infrahub/errors/validation.py` per research R-011: parse reason text, raise one of `AttributeRequiredError` / `AttributeInvalidTypeError` / `AttributeConstraintViolationError` per field, attach `path` via `GraphQLError(original_error=exc, path=[...])`
- [X] T018 [US1] Update GraphQL mutation handlers in `backend/infrahub/graphql/mutations/` to call `raise_classified_validation_errors` instead of letting the raw `ValidationError` propagate (one entry per failing field — satisfies FR-016, FR-017)
- [X] T019 [US1] Modify `generic_api_exception_handler` in `backend/infrahub/api/exception_handlers.py` to branch on `request.url.path.startswith("/graphql")`: emit the GraphQL envelope `{"data": null, "errors": [...]}` shape from `contracts/graphql-error-envelope.md` §Auth-short-circuit example; preserve the existing REST shape for `/api/...` (R-006)
- [X] T020 [US1] Thread the catalogue `code` through structlog inside the formatter (single emission point per FR-018, R-010) and through `backend/infrahub/log_forwarding/` so `ForwardableError`-derived exceptions carry their code into forwarded log payloads
- [X] T021 [US1] Add `unstructured` exception (or similar synthetic uncatalogued raise) handling: verify `UNDEFINED_ERROR` defaults `http_status` to `exc.HTTP_CODE` when the exception derives from `infrahub.exceptions.Error`, else `500` (per data-model.md §`UNDEFINED_ERROR`)

### Tests for User Story 1

- [X] T022 [P] [US1] Unit tests for `catalogue_error_formatter` covering each of the 9 catalogued codes + `UNDEFINED_ERROR` + `AuthorizationError` split in `backend/tests/unit/graphql/test_error_formatter.py` (assert `extensions.code`, `extensions.http_status`, `extensions.data` shape per code)
- [X] T023 [P] [US1] Functional test `backend/tests/functional/graphql/test_error_catalogue.py` that triggers every catalogued code through a real GraphQL request and asserts response matches the wire contract in `contracts/graphql-error-envelope.md` (covers SC-001, SC-008)
- [X] T024 [P] [US1] Functional test for multi-field validation in the same file: submit `BuiltinTagCreate` with one missing required field plus one wrong-typed field; assert two entries in `errors[]`, each with correct `code`, `data`, and `path` (FR-016, FR-017)
- [X] T025 [P] [US1] Functional test for the `/graphql` auth-short-circuit path in `backend/tests/functional/api/test_exception_handlers.py`: unauthenticated POST returns GraphQL envelope with `extensions.code = "AUTHENTICATION_REQUIRED"` and `extensions.http_status = 401`; same exception on `/api/...` returns the unchanged REST shape
- [X] T026 [P] [US1] Functional test for `UNDEFINED_ERROR` fallback: raise a synthetic uncatalogued exception from a resolver; assert response carries `extensions.code = "UNDEFINED_ERROR"`, `http_status = 500`, `data = {}` (SC-008); additionally capture structlog output via `caplog` and assert the emitted record carries `code = "UNDEFINED_ERROR"` (FR-018)

**Checkpoint**: US1 is independently demonstrable end-to-end — every documented code can be triggered and validated against the wire contract. MVP shippable here.

---

## Phase 4: User Story 2 — Frontend Type-Safe Error Handling (Priority: P2)

**Goal**: Frontend imports a generated discriminated union from `frontend/app/src/shared/api/errors/`, switches on `extensions.code` with full type-safety, and uses it to (a) highlight every offending field on a single submit and (b) route `PERMISSION_DENIED` through the permission dialog rather than the generic toast.

**Independent Test**: With US1 shipped, the generator produces typed bindings, an example consumer compiles under strict TS, and the multi-field form scenario (SC-004) succeeds in Playwright.

### Implementation for User Story 2

- [ ] T027 [US2] Add `json-schema-to-typescript` to `frontend/app/package.json` `devDependencies` and register pnpm scripts `generate:error-bindings` and `check:error-bindings` (R-004)
- [ ] T028 [US2] Create generator script `frontend/app/scripts/generate-error-bindings.ts` that reads `schema/error-catalogue.json`, feeds it through `json-schema-to-typescript`, and writes `frontend/app/src/shared/api/errors/catalogue.generated.ts` including a generated `CatalogueError` discriminated union (R-004 sketch)
- [ ] T029 [US2] Run the generator to produce the initial `frontend/app/src/shared/api/errors/catalogue.generated.ts` and commit it (depends on T011 and T028)
- [ ] T030 [US2] Hand-write `frontend/app/src/shared/api/errors/index.ts` re-exporting generated types and exposing the `CatalogueError` union plus a `isCatalogueError(extensions): extensions is CatalogueError` guard
- [X] T031 [US2] Migrate `frontend/app/src/shared/api/graphql/graphqlClientApollo.tsx` (currently reads integer `extensions.code` at line ~66): switch on string `extensions.code`, read `extensions.http_status` for any integer-based logic
- [X] T031a [US2] Add hand-written catalogue mirror at `frontend/app/src/shared/api/graphql/errors.ts` per [frontend-errorlink-refactor.md §New module](./frontend-errorlink-refactor.md): `ERROR_CODES` const, `ErrorCode` union, `GraphQLErrorExtensions` discriminated union with one variant per code, and `parseErrorExtensions(extensions: unknown): GraphQLErrorExtensions` that narrows by `code` and falls back to `UNDEFINED_ERROR` (http_status 500, empty data) for unknown / non-object inputs. Header comment names T029 as the eventual replacement so the file is deleted cleanly when generated bindings land. Payload shapes mirror [data-model.md §Payload models](./data-model.md) one-to-one
- [X] T031b [P] [US2] Add `frontend/app/src/shared/api/graphql/errors.test.ts` (vitest, GIVEN/WHEN/THEN style matching neighbouring `utils.test.ts`): each known `code` narrows to its expected variant with `http_status` and `data` passed through; unknown codes, missing `code`, `null`, `undefined`, and non-object inputs all return `UNDEFINED_ERROR` with `http_status: 500`; missing `data` defaults to `{}`; a compile-time exhaustiveness check (`satisfies`-style or `never`-narrowing helper) fails the build if `ErrorCode` gains a value without a matching variant
- [X] T031c [US2] Refactor `frontend/app/src/shared/api/graphql/graphqlClientApollo.tsx` `errorLink` to a `switch (parsed.code)` per [frontend-errorlink-refactor.md §Refactored `errorLink`](./frontend-errorlink-refactor.md): call `parseErrorExtensions(graphQLError.extensions)` once per error, log `parsed.code` in the existing `console.error`, route `TOKEN_EXPIRED` → `retryWithRefreshedToken`, `PERMISSION_DENIED` → silent return, everything else → `notifyUser`. Extract `retryWithRefreshedToken(operation, forward)` and `notifyUser(message, operation)` as file-local helpers carrying the existing `Observable`/`processErrorMessage`/toast bodies verbatim — no behaviour change inside the helpers
- [X] T031d [US2] Fix silent-failure on `AUTHENTICATION_REQUIRED`: by virtue of the T031c switch, only `TOKEN_EXPIRED` routes through `retryWithRefreshedToken`; `AUTHENTICATION_REQUIRED` falls into the `default` arm and surfaces via toast / `processErrorMessage`. Verify by hand that submitting bad credentials now shows the backend message instead of swallowing it (the bug is shared with `develop` and resolves with this swap; no dedicated unit test, covered by manual QA and the existing login E2E)
- [X] T032 [US2] Migrate `frontend/app/src/pages/login.tsx` (lines 27–29): replace `extensions.code === 401` checks with `extensions.code === "AUTHENTICATION_REQUIRED" || extensions.code === "TOKEN_EXPIRED"`
- [ ] T033 [US2] Wire `ATTRIBUTE_REQUIRED` / `ATTRIBUTE_INVALID_TYPE` / `ATTRIBUTE_CONSTRAINT_VIOLATION` from the response into the existing form-field error display (under `frontend/app/src/shared/components/form/`), feeding `data.field_name` + `message` into `form.setFieldError` (US2 acceptance #2)
- [ ] T034 [US2] Wire `PERMISSION_DENIED` into the existing permission/toast routing layer so it opens the permission dialog rather than a generic toast (US2 acceptance #3)
- [ ] T034a [P] [US2] Add `frontend/app/scripts/check-no-message-parsing.mjs` that greps `frontend/app/src/**/*.{ts,tsx}` for catalogue-error message substrings (e.g. `"Unable to find the node"`, `"Permission denied"`, `"not a valid"`); fails non-zero on net-new occurrences. Register as `pnpm check:no-message-parsing` and add to the existing lint CI step (SC-002)

### Tests for User Story 2

- [ ] T035 [P] [US2] Vitest unit test for the discriminated-union guard in `frontend/app/src/shared/api/errors/index.test.ts` (asserts compile-time narrowing of `data` and exhaustiveness check via `never`)
- [ ] T036 [P] [US2] Playwright E2E test for multi-field form validation in `frontend/app/tests/e2e/error-catalogue.spec.ts`: submit a Create-Node form with N invalid fields, assert all N field-error indicators render after one round-trip (SC-004)
- [ ] T037 [P] [US2] Playwright E2E test in the same file for `PERMISSION_DENIED` routing: trigger a mutation the current user is not permitted to perform; assert the permission dialog opens (not a generic toast)

**Checkpoint**: US2 is independently demonstrable — the frontend consumes the catalogue, both legacy integer-code call sites are removed, and the form/permission UX wins are visible.

---

## Phase 5: User Story 3 — Python SDK Typed Errors (Priority: P3)

**Goal**: SDK consumers receive typed errors aligned to the catalogue. SDK code lives in the `python_sdk/` submodule (separate repo); in-repo work is limited to making the catalogue schema reliably available to the SDK's CI.

**Independent Test**: After the catalogue artefact is published in a tagged Infrahub release, the SDK repo's binding generator can fetch `schema/error-catalogue.json` from that release and regenerate its types without coordinated changes.

### Implementation for User Story 3

- [ ] T039 [US3] Update the release pipeline in `tasks/release.py` (and/or the GitHub Actions release workflow) to publish `schema/error-catalogue.json` as a release asset alongside the existing `schema/schema.graphql` artefact (research R-012)
- [ ] T040 [US3] Document the SDK-consumption contract in `docs/docs/reference/error-catalogue/index.md` §"For SDK and third-party consumers" (the release-download URL pattern and the `infrahub_catalogue_version` semantics)

**Checkpoint**: SDK repo can now drive its bindings off a stable, versioned, downloadable schema.

---

## Phase 6: User Story 4 — CI Enforcement of Frontend Binding Sync (Priority: P3)

**Goal**: A PR to Infrahub that changes the backend catalogue without regenerating the frontend bindings (and/or `schema/error-catalogue.json`) fails CI with a self-explanatory message naming the regeneration command.

**Independent Test**: Intentionally break sync (modify catalogue, skip regeneration), open a PR, confirm CI fails with the documented message. Regenerate, push, confirm CI passes.

### Implementation for User Story 4

- [ ] T041 [US4] Create new `tasks/frontend.py` exposing two Invoke tasks: (a) `frontend.regenerate-error-bindings` — runs `backend.export-error-catalogue`, then `pnpm generate:error-bindings`, then `docs.generate-error-catalogue`, each writing its canonical committed file; (b) `frontend.check-error-bindings` — calls (a), then runs `git diff --exit-code schema/error-catalogue.json frontend/app/src/shared/api/errors/catalogue.generated.ts docs/docs/reference/error-catalogue/index.md`; on non-zero diff, prints the failure message from quickstart.md §"CI sync check" naming `uv run invoke frontend.regenerate-error-bindings` as the fix command (R-009)
- [ ] T042 [US4] Register `frontend` collection in `tasks/__init__.py` (`from . import frontend; ns.add_collection(frontend)`)
- [ ] T043 [US4] Add `uv run invoke frontend.check-error-bindings` step to the existing codegen-freshness GitHub Actions workflow under `.github/workflows/` (same job that runs GraphQL codegen freshness check; FR-009)

### Tests for User Story 4

- [ ] T044 [P] [US4] Integration test simulating sync drift in `backend/tests/integration/errors/test_sync_check.py`: programmatically mutate the in-process catalogue, run the export, diff against the committed file, assert non-zero exit and that the failure message includes the regeneration command (SC-005)

**Checkpoint**: CI now guards against silent catalogue drift in this repo.

---

## Phase 7: User Story 5 — Public Error Schema for Third-Party Consumers (Priority: P4)

**Goal**: External integrators can fetch the catalogue schema from a released Infrahub artefact and generate their own bindings or validators. Version-to-version differences are detectable via diff of the schema files.

**Independent Test**: Download `schema/error-catalogue.json` from two consecutive release artefacts, diff them; observe that any added/removed/modified codes appear as JSON diffs.

### Implementation for User Story 5

- [ ] T045 [US5] Ensure the docs page at `docs/docs/reference/error-catalogue/index.md` includes a "Third-party consumers" section pointing at the released schema URL (FR-012, builds on T040)
- [ ] T046 [US5] Add an example external consumer snippet (any language, smallest demonstrating consumption) to the same docs page, e.g. `jq '.codes | keys'` against the published file (US5 acceptance #1)

**Checkpoint**: External consumers have a documented, machine-readable entry point.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, telemetry visibility, and final validation.

- [ ] T047 [P] Implement `docs.generate-error-catalogue` Invoke task in `tasks/docs.py` that reads `schema/error-catalogue.json` and renders the Docusaurus page at `docs/docs/reference/error-catalogue/index.md` per research R-008 (every code's description, stability badge, HTTP status, `data` shape table, worked example); include a header line `**Catalogue version**: <infrahub_catalogue_version> — <N> codes` so the count is part of the rendered page and appears in release diffs (SC-007)
- [ ] T048 [P] Add `docs.generate-error-catalogue` to the existing `docs.build` task chain in `tasks/docs.py`
- [ ] T049 [P] Add a Sidebar entry for the new docs page in the Docusaurus config so it appears under Reference
- [ ] T050 [P] Run `uv run invoke docs.lint` and `uv run invoke lint` and fix any findings
- [ ] T051 Validate quickstart.md end-to-end by running each command block from a clean checkout: `backend.export-error-catalogue`, `pnpm generate:error-bindings`, `docs.generate-error-catalogue`, `pytest backend/tests/functional/graphql/test_error_catalogue.py -v`
- [ ] T052 Run `cd frontend/app && pnpm test && pnpm test:e2e` for the US2/US4 E2E suites against a live backend; capture results in the PR description
- [ ] T053 [P] Playwright E2E test for `TOKEN_EXPIRED` silent-refresh on `/graphql` auth-short-circuit in `frontend/app/tests/e2e/error-catalogue.spec.ts` — verifies the end-to-end pattern illustrated in quickstart.md; not part of US2's acceptance criteria but cheap to add once T032 is live
- [ ] T054 Audit `ValidationError` raise-site coverage on the GraphQL path: grep `raise ValidationError` under `backend/infrahub/graphql/` and confirm each one either flows through `raise_classified_validation_errors` (T017) or has an explicit catalogue-fallback acceptance (lands as `UNDEFINED_ERROR` intentionally). File the follow-up ticket (referencing research R-011) for migrating remaining raise sites to typed subclasses and promoting them from `backend/infrahub/errors/exceptions.py` up to `backend/infrahub/exceptions.py` once the text-classifier helper can be retired; link the ticket in the catalogue docs page §"Known gaps"
- [ ] T055 File the follow-up ticket to align `BranchNotFoundError.HTTP_CODE` and `SchemaNotFoundError.HTTP_CODE` (and the corresponding catalogue `http_status` values) to a semantically correct 404. v1 ships with the existing 400/422 values mirrored into the catalogue to avoid a REST-side breaking change; the alignment should bundle the REST status change, the catalogue update, the spec/data-model.md fix, and a towncrier `changed` fragment in a single deprecation-cycle release. Link the ticket in the catalogue docs page §"Known gaps"

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: no dependencies — start immediately.
- **Phase 2 (Foundational)**: depends on Phase 1; BLOCKS all user stories.
- **Phase 3 (US1)**: depends on Phase 2. Strict prerequisite for US2 consumer migrations (T031–T034) and US4 CI integration. **NOT** a prerequisite for US3 (T039/T040 only consume the Phase 2 schema artefact) or US5 (T045/T046 are docs additions). US3 and US5 can run in parallel with US1.
- **Phase 4 (US2)** — split: bindings generation (T027–T030, T035) depends only on Phase 2 (T011); consumer migrations (T031–T034) and E2E tests (T036–T037) depend on US1 being live end-to-end.
- **Phase 5 (US3)**: depends on Phase 2 (only the schema artefact); independent of US2.
- **Phase 6 (US4)**: depends on US2 (the generated `catalogue.generated.ts` must exist for the sync check to compare against).
- **Phase 7 (US5)**: depends on US3 release-artefact publication (T039) and the docs page from Phase 8 (T047).
- **Phase 8 (Polish)**: depends on US1 minimally; T047/T048/T049 can run as soon as Phase 2 is done.

### Within Each User Story

- Foundational catalogue and exporter (Phase 2) must exist before any formatter or generator runs.
- Within US1: formatter (T015) before mutation handler updates (T018); exception-handler split (T019) is independent of T015 and can run in parallel.
- Within US2: bindings must be generated (T029) before consumers (T031–T034) can compile. T031a–T031d are independent of T027–T030 and may land before or alongside them; they are the bridge state while generated bindings are pending. When T029 lands, T031a's hand-written `errors.ts` is deleted per [frontend-errorlink-refactor.md §Removal step](./frontend-errorlink-refactor.md).
- Tests can be written in parallel with implementation as long as a test exists by the time code merges.

### Parallel Opportunities

- **Phase 2**: T005, T006, T012, T013, T014 are independent files and can run in parallel after T004 lands. T011 depends on T010.
- **Phase 3 (US1)**: T015, T017, T019 touch different files and are parallelizable after Phase 2. All four test tasks T022–T026 are parallel.
- **Phase 4 (US2)**: T035–T038 (tests) are parallel; T031, T032 are independent files. T031a + T031b can land in parallel with T031c (the refactor consumes them, so T031c sequences after both); T031d is a behaviour assertion covered by T031c's switch shape and adds no separate file.
- **Phase 8**: T047, T048, T049, T050, T053 are independent.
- Across stories: once Phase 2 is done, US1 and the artefact-publication portion of US3 (T039) can proceed in parallel.

---

## Parallel Example: Phase 2 launch

```bash
# After T004 lands, run these in parallel:
Task: "Define payload Pydantic models in backend/infrahub/errors/payloads.py"
Task: "Introduce AttributeRequiredError/AttributeInvalidTypeError/AttributeConstraintViolationError in backend/infrahub/errors/exceptions.py"
Task: "Unit tests for catalogue registry in backend/tests/unit/errors/test_catalogue.py"
Task: "Unit tests for payload model JSON Schema export in backend/tests/unit/errors/test_payloads.py"
Task: "Unit tests for export_catalogue() round-trip in backend/tests/unit/errors/test_export.py"
```

## Parallel Example: US1 tests

```bash
# After Phase 2 is complete, all US1 tests can be written in parallel:
Task: "Unit test catalogue_error_formatter coverage in backend/tests/unit/graphql/test_error_formatter.py"
Task: "Functional test per-code wire shape in backend/tests/functional/graphql/test_error_catalogue.py"
Task: "Functional test multi-field validation in backend/tests/functional/graphql/test_error_catalogue.py"
Task: "Functional test /graphql auth short-circuit in backend/tests/functional/api/test_exception_handlers.py"
Task: "Functional test UNDEFINED_ERROR fallback in backend/tests/functional/graphql/test_error_catalogue.py"
```

---

## Implementation Strategy

### MVP First (US1 only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (catalogue + exporter + committed JSON + unit tests)
3. Complete Phase 3: US1 — every catalogued code reaches the GraphQL wire with `extensions.code` / `http_status` / `data`, fallback `UNDEFINED_ERROR` works, auth-short-circuit emits the GraphQL envelope
4. **STOP and VALIDATE**: Run `backend/tests/functional/graphql/test_error_catalogue.py`; confirm SC-001 and SC-008 pass against a live instance
5. The MVP can ship here as a backend-only release, but the breaking change to `extensions.code` means US2 (frontend migration) is co-required for the same release to avoid breaking the in-repo UI

### Incremental Delivery (single release after MVP validation)

Per plan.md §Summary, US1 + US2 + part of US3 ship together in one release to avoid in-repo breakage:

1. Phase 1 + 2 → ready
2. US1 (Phase 3) → backend wire format ready
3. US2 (Phase 4) → frontend migrates the two legacy integer-code call sites
4. US3 release-artefact step (T039) → SDK repo can consume the new schema
5. US4 (Phase 6) → CI sync check active; subsequent PRs are guarded
6. Phase 8 polish (docs, telemetry smoke) → ship

### Parallel Team Strategy

With multiple developers after Phase 2 lands:

- Backend dev: US1 (Phase 3) + US3 release-artefact step (T039)
- Frontend dev: US2 (Phase 4)
- DevOps / shared: US4 (Phase 6) once US2 lands; Phase 8 docs/sidebar updates throughout
- US5 docs (Phase 7) and Phase 8 polish can be picked up by anyone after Phase 2

---

## Notes

- `[P]` tasks touch different files and have no incomplete dependencies.
- `[USx]` labels are required on every Phase 3–7 task and absent from Setup / Foundational / Polish.
- Generated files (`schema/error-catalogue.json`, `frontend/app/src/shared/api/errors/catalogue.generated.ts`, `docs/docs/reference/error-catalogue/index.md`) are committed; their freshness is enforced by Phase 6 CI.
- Per plan.md, no constitutional violations and no Complexity Tracking entries — all work follows existing patterns (Pydantic for typed payloads, `json-schema-to-typescript` for codegen, Invoke tasks for tooling, Docusaurus for docs).
- The breaking change to `extensions.code` ships in one release; no backward-compat shim (research R-007). The towncrier fragment from T015a carries the migration snippet and MUST land in the same PR/release as T016, T019, T031, T032.
