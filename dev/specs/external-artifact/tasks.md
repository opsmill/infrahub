---
description: "Task list for artifacts rendered by an external engine"
---

# Tasks: Artifacts rendered by an external engine

**Input**: Design documents from `specs/external-artifact/`: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Included. `AGENTS.md` requires tests for new functionality, and constitution IV requires them.

**Governance gates**: The user approved the four "Ask First" items on 2026-11-20: the core schema change, the GraphQL schema change, the new REST endpoint and the authentication change.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1, US2 or US3 from spec.md
- Paths are relative to the repository root. Backend Python paths start at `backend/infrahub/`.

---

## Phase 1: Setup (SDK prerequisite)

**Purpose**: The `.infrahub.yml` model lives in the `python_sdk` submodule. It must land upstream before the backend can import external transformations.

- [X] T001 In `python_sdk/infrahub_sdk/schema/repository.py`, add `InfrahubExternalTransformConfig` with these fields:
  - `name: str`
  - `query: str`
  - `version: str` (non-empty, `min_length=1`)
  - `description: str | None = None`
  - `timeout: int = 600` (`ge=1`)

  Add `external_transforms: list[InfrahubExternalTransformConfig]` (default empty) to `InfrahubRepositoryConfig`, include it in the `unique_items` validator, and add `has_external_transform` / `get_external_transform` next to the existing `has_*` / `get_*` methods. Contract: [contracts/infrahub-yml.md](contracts/infrahub-yml.md).
- [X] T002 [P] Add SDK unit tests in `python_sdk/tests/unit/sdk/test_repository_config.py` (or the existing test module for `InfrahubRepositoryConfig`). Cover:
  - parsing `external_transforms`;
  - refusing duplicate names;
  - refusing an empty `version`;
  - the default `timeout` of 600.
- [X] T003 Commit the SDK change locally inside the `python_sdk` submodule, on a new submodule branch `external-artifact`, and build the backend against it. Do not push and do not open the upstream pull request: the user opens and merges it in `infrahub-sdk-python` (branch `infrahub-develop`) before the submodule pointer lands upstream (user decision, 2026-11-20).

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: Schema, constants, the event, the token and the locks, which every story uses.

**⚠️ No user story work starts until this phase is complete.**

- [X] T004 Add `TRANSFORMEXTERNAL = "CoreTransformExternal"` in `backend/infrahub/core/constants/infrahubkind.py`, and `ARTIFACT_RENDER_REQUESTED = "infrahub.artifact.render_requested"` to `EventType` in `backend/infrahub/core/constants/__init__.py`.
- [X] T005 In `backend/infrahub/core/schema/definitions/core/transform.py`, add `core_transform_external`:
  - `NodeSchema` named `TransformExternal`, namespace `Core`, `inherit_from=[InfrahubKind.TRANSFORM]`;
  - the same `branch` support as `core_transform_python`;
  - one attribute: `Attr(name="version", kind="Text", description="Version of the external template, part of the fingerprint")`.

  Register it in `backend/infrahub/core/schema/definitions/core/__init__.py`.
- [X] T006 In `backend/infrahub/core/schema/definitions/core/artifact.py`, add two optional attributes to `core_artifact`:
  - `Attr(name="render_request_id", kind="Text", optional=True, description="ID of the only external render request whose result is accepted")`;
  - `Attr(name="render_deadline", kind="DateTime", optional=True, description="Time after which a pending external render is set to Error")`.

  Check `dev/guides/backend/creating-migrations.md` and add a migration if existing databases need one.
- [X] T007 Regenerate the generated files and commit them:
  - `uv run invoke backend.generate`, then commit the SDK protocol and generated files inside the submodule as part of T003's pull request, or a follow-up one;
  - `uv run invoke schema.generate-graphqlschema`;
  - `cd frontend/app && pnpm codegen:graphql && pnpm codegen`;
  - `uv run invoke docs.generate`.
- [X] T008 [P] Add `ArtifactRenderRequestedEvent(ArtifactEvent)` in `backend/infrahub/events/artifact_action.py`:
  - `event_name = f"{EVENT_NAMESPACE}.artifact.render_requested"`, and `infrahub_node_kind_event = True`;
  - the fields listed in [data-model.md](data-model.md#artifactrenderrequestedevent-new-event): `render_id`, `callback_url`, `deadline`, `artifact_id`, `artifact_name`, `artifact_definition_id`, `artifact_definition_name`, `transformation_name`, `transformation_version`, `content_type`, `target_id`, `target_kind`, `target_name`, `branch` and `query_result`.

  `get_resource()` must include `infrahub.branch.name`, and `get_related()` must call `super()`. Export it in `backend/infrahub/events/__init__.py`. Add the choice to `frontend/app/src/entities/events/domain/model/event-constants.ts::EVENT_TYPE_CHOICES`.
- [X] T009 [P] Create `backend/infrahub/artifacts/render_token.py` with two functions:
  - `mint_render_token(render_id, artifact_id, branch, deadline) -> str`: an HS256 JWT signed with `config.SETTINGS.security.secret_key`, with claims `type="render"`, `render_id`, `artifact_id`, `branch` and `exp=deadline`.
  - `validate_render_token(token) -> RenderTokenClaims`: raises an authentication error when the signature is bad, the token is expired, `type != "render"` or a claim is missing.

  Unit tests in `backend/tests/unit/artifacts/test_render_token.py` must also show that `auth/auth.py::validate_jwt_access_token` refuses a render token.
- [X] T010 [P] Create `backend/infrahub/artifacts/render_lock.py` with helpers that return the lock names `artifact-render:<branch>:<artifact_id>` and `validator:<validator_id>`, using the `infrahub.lock` registry (research R11).
- [X] T011 Add the external-transformation fingerprint:
  - In `backend/infrahub/git/fingerprint/`, add `ExternalTransformationFingerprintInput` (`name`, `query_name`, `dependencies`, `dependencies_complete`, `version`).
  - In `FingerprintComposer.compose_transformation`, add a `match` case that adds a `version` term, sets `watch_required=False` and does not fold the commit ID.
  - In `backend/infrahub/git/closure_builder/`, add an empty, complete closure for external configs, add it to the `TransformConfig` union and wire it in `build_default_closure_builder`.
  - Add `(InfrahubKind.TRANSFORMEXTERNAL, "fingerprint")` to `backend/infrahub/core/diff/conflicts_enricher.py::_IMPORT_COMPUTED_ATTRIBUTES`.

  Unit tests in `backend/tests/unit/git/fingerprint/` must show that the fingerprint changes with `version` and with the query fingerprint, and does not change with the commit ID.
- [X] T012 Import external transformations from `.infrahub.yml` in `backend/infrahub/git/integrator.py`. Copy the Jinja2 pattern:
  - `_build_external_transform_definitions`, `_apply_external_transform_definitions`, `create_external_transform`, `compare_external_transform` and `update_external_transform`;
  - a new `ImportSummaryStep` member placed before artifact definitions;
  - a new `ObjectImportPlan` field;
  - the new kind in `stale_nodes_in_delete_order`.

  Write `timeout` from the config. Component test in `backend/tests/component/git/`: importing a repository creates, updates and deletes `CoreTransformExternal` nodes, and artifact definitions resolve it by name.

**Checkpoint**: External transformations import, carry a version-driven fingerprint, and the event, token and lock helpers exist.

---

## Phase 3: User Story 1 - Review an externally rendered configuration change (Priority: P1) 🎯 MVP

**Goal**: A data change on a branch produces one render request per affected target. The engine's callback makes the artifact `Ready`, the proposed-change check passes, and a merge renders again on the destination branch.

**Independent Test**: [quickstart.md](quickstart.md) scenarios 1, 4 and 5 with the reference engine in `ok` mode.

### Tests for User Story 1

- [X] T013 [P] [US1] Component tests for the callback endpoint in `backend/tests/component/api/test_artifact_render_callback.py`. Cover every row of the responses table in [contracts/callback-api.md](contracts/callback-api.md):
  - 204 success and 204 failure;
  - 400 missing `content`, and 400 mismatched `content_type`;
  - 401 no token, 401 expired token, 401 API key only;
  - 403 path and token mismatch;
  - 409 replaced request, 409 already ended;
  - 413 content over `StorageSettings.max_file_size`.
- [X] T014 [P] [US1] Component test in `backend/tests/component/artifacts/test_render_request.py` covering:
  - The request runs the query with `update_group=True` and `subscribers=[artifact.id]`, sets `Pending`, `render_request_id` and `render_deadline`, and emits one `ArtifactRenderRequestedEvent`.
  - It fails fast to `Error`, emitting no event, with these messages:
    - when no webhook subscribes: "no webhook subscribed to infrahub.artifact.render_requested";
    - when `main.public_url` is not set: "main.public_url must be set for external transformations";
    - when the event is too large: "query result too large for a render request (N bytes, limit M)".
- [X] T015 [P] [US1] Concurrency tests in `backend/tests/component/artifacts/test_render_concurrency.py`:
  - a callback for render R runs at the same time as a new request R2, and the artifact never ends `Ready` with R's content while `render_request_id` is R2;
  - two callbacks for checks of the same validator leave the validator `completed` with the right conclusion.
- [X] T016 [P] [US1] Unit test in `backend/tests/unit/webhook/test_render_token_delivery.py`:
  - delivery of a render-requested event adds `X-Infrahub-Render-Token`;
  - `${INFRAHUB_RENDER_TOKEN}` in a transformed body is replaced;
  - the token is absent from the payload passed to `WebhookLogFormatter`;
  - other event types are unchanged.

### Implementation for User Story 1

- [X] T017 [US1] Create `backend/infrahub/artifacts/render_request.py` with `request_external_render(...)`. Under the artifact render lock (T010) it:
  1. checks for an active webhook subscribed to `infrahub.artifact.render_requested` or `all` with a matching branch scope, and checks that `main.public_url` is set;
  2. runs `client.query_gql_query(name=query_id, variables=..., update_group=True, subscribers=[artifact.id], branch_name=..., timeout=...)`;
  3. builds the event, measures its serialized size against the Prefect event size limit, and fails fast when it is over;
  4. writes `status=Pending`, a new UUID in `render_request_id`, and `render_deadline = now + transformation timeout`;
  5. emits the event, with `callback_url = <main.public_url>/api/artifact/render/<render_id>`.

  For each fail-fast case it sets `Error` with the exact messages from research R12 and emits nothing.
- [X] T018 [US1] Create `backend/infrahub/artifacts/render_result.py` with `accept_render_result(render_id, claims, body)`. Under the artifact render lock it:
  1. checks that `render_id == claims.render_id == artifact.render_request_id` and that `render_deadline` is set;
  2. on success: serializes the content, compares the MD5 checksum, uploads to the object store when it changed, sets `Ready`, `checksum`, `storage_id` and `content_type`, clears `render_deadline`, and emits `ArtifactCreatedEvent` / `ArtifactUpdatedEvent` when the content changed;
  3. on failure: sets `Error` and clears `render_deadline`;
  4. when a proposed-change check is linked, updates the check and calls the validator recomputation (T021).

  Reuse the storage logic of `git/integrator.py::InfrahubRepositoryIntegrator.render_artifact` by extracting the shared part rather than duplicating it.
- [X] T019 [US1] Add `POST /api/artifact/render/{render_id}` in `backend/infrahub/api/artifact.py`:
  - It reads `X-Infrahub-Render-Token`, calls `validate_render_token` and refuses API keys and account sessions.
  - It validates the body model: `status` is `success` or `failure`; `content` is required for success; `message` is required for failure, at most 4096 characters; `content` is at most `StorageSettings.max_file_size`.
  - It calls `accept_render_result` and maps errors to 400, 401, 403, 409 and 413 as in [contracts/callback-api.md](contracts/callback-api.md).

  Regenerate `schema/openapi.json` (`uv run invoke schema.generate-jsonschema`) and `frontend/app/src/shared/api/rest/types.generated.ts` (`pnpm codegen`).
- [X] T020 [US1] Branch the generate path on the external kind:
  - In `backend/infrahub/git/tasks.py::generate_request_artifact_definition`, accept `TRANSFORMEXTERNAL` when building the request: no `transform_location`, `convert_query_response=False`. Raise on any unknown kind.
  - In `backend/infrahub/git/tasks.py::generate_artifact`, call `request_external_render` instead of `render_artifact` for the external kind.
  - In `backend/infrahub/git/integrator.py::InfrahubRepositoryIntegrator.render_artifact`, add an `else` that raises for unknown kinds.
- [X] T021 [US1] Make proposed-change checks complete later:
  - In `backend/infrahub/core/regeneration/definitions.py`, add the `... on CoreTransformExternal` fragment and fill the model.
  - In `backend/infrahub/message_bus/types.py::ProposedChangeArtifactDefinition.transform_location`, return an empty location for the external kind.
  - In `backend/infrahub/artifacts/tasks.py::create`, for the external kind, call `request_external_render`, write the check with `conclusion=unknown` and the message "waiting for external engine", and return a pending result.
  - In `backend/infrahub/core/validators/checks_runner.py::run_checks_and_update_validator`, leave the validator `in_progress` when any result is pending.
  - Add a shared `recompute_validator(validator_id)` there. Under the validator lock, it reads the stored checks, sets the state and conclusion, and sends the existing passed or failed validator events.
- [X] T022 [US1] Deliver the token in `backend/infrahub/webhook/tasks/process.py::webhook_send`:
  - for `infrahub.artifact.render_requested` events only, mint the token on each attempt from `data.render_id`, `data.artifact_id`, `data.branch` and `data.deadline`;
  - add the `X-Infrahub-Render-Token` header;
  - replace `${INFRAHUB_RENDER_TOKEN}` in the serialized body;
  - pass a redacted body to `backend/infrahub/webhook/log_formatter.py::WebhookLogFormatter`.
- [X] T023 [US1] Hide query data from read APIs:
  - In `backend/infrahub/task_manager/event/query.py`, leave `query_result` out of the payload for `infrahub.artifact.render_requested`.
  - In `backend/infrahub/graphql/queries/task.py::_serialize_node`, leave `query_result` out of the webhook flow-run parameters of these events.

  Component test: the `Events` query returns the event without `query_result`.
- [X] T024 [US1] Integration test in `backend/tests/integration/artifacts/test_external_artifact.py`, with an in-process reference engine (plain HTTP, no Infrahub libraries). Cover quickstart scenario 1, including the merge rendering on `main`, and scenario 5 (no token in events, task parameters or logs).

**Checkpoint**: User Story 1 works on its own with the engine in `ok` mode.

---

## Phase 4: User Story 2 - Release a new template version (Priority: P2)

**Goal**: A version change committed on a branch renders every target of the definition again, an unrelated commit renders none, and manual regeneration works.

**Independent Test**: [quickstart.md](quickstart.md) scenario 2.

- [X] T025 [P] [US2] Extend `backend/tests/integration/artifacts/test_external_artifact.py` with three cases:
  - a `version` change on branch `template-1-1` emits one request per member of the target group;
  - an unrelated commit emits none;
  - `POST /api/artifact/generate/{definition_id}` emits one request per member.
- [X] T026 [US2] Verify that `backend/infrahub/api/artifact.py::generate_artifact` and the proposed-change selection (`core/regeneration/predicates.py::definition_changed`) select external definitions through the fingerprint without extra code. Fix any gap that T025 reveals in those modules.

**Checkpoint**: User Stories 1 and 2 work independently.

---

## Phase 5: User Story 3 - Find out that the engine failed (Priority: P3)

**Goal**: An engine failure or no answer sets the artifact to `Error` and fails the check within the timeout plus 1 minute.

**Independent Test**: [quickstart.md](quickstart.md) scenario 3.

- [X] T027 [P] [US3] Component test in `backend/tests/component/artifacts/test_render_timeouts.py`. The sweep must:
  - set a pending artifact past its `render_deadline` to `Error`;
  - fail its check with "no response from engine";
  - recompute the validator;
  - leave artifacts before their deadline unchanged.

  A callback after the sweep must return 409.
- [X] T028 [US3] Create `backend/infrahub/artifacts/timeouts.py` with a flow that:
  - queries `CoreArtifact` on every branch with `status=Pending` and `render_deadline` earlier than now;
  - under the artifact render lock, sets `Error`, clears `render_deadline`, updates the linked check and calls `recompute_validator`;
  - logs each timeout with the artifact, the branch and the transformation name.

  Check whether `render_deadline` needs an index (`dev/knowledge/backend/database-indexes.md`).
- [X] T029 [US3] Register the sweep in `backend/infrahub/workflows/catalogue.py` as an `INTERNAL` workflow with `cron="* * * * *"`, `concurrency_limit=1` and `ConcurrencyLimitStrategy.CANCEL_NEW`, following `CRASH_ZOMBIE_FLOW_RUNS`.
- [X] T030 [US3] Extend `backend/tests/integration/artifacts/test_external_artifact.py` with the engine in `fail` mode (the check fails with the engine's message) and in `silent` mode with `timeout: 60` (`Error` within 2 minutes, and a late callback gets 401 because its token expired at the deadline; the 409 after the sweep is covered by T027).

**Checkpoint**: All three user stories work independently.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T031 [P] Write user documentation in `docs/docs/` (follow `docs/AGENTS.md`). Cover:
  - declaring `external_transforms`;
  - subscribing a webhook to `infrahub.artifact.render_requested`;
  - using a webhook transformation with `${INFRAHUB_RENDER_TOKEN}` (AWX example from [contracts/render-request.md](contracts/render-request.md));
  - the callback contract;
  - the requirement that `main.public_url` is set;
  - retrying on 429;
  - choosing a timeout that covers webhook retries (at least 7 minutes);
  - local testing with a reference engine.

  Run `uv run invoke docs.lint`.
- [X] T032 [P] Add `changelog/+external-artifact.added.md` with the `creating-changelog-entries` skill.
- [X] T033 [P] Add `dev/knowledge/backend/external-artifacts.md` describing the request, delivery, callback and timeout flow, and link it from `dev/knowledge/backend/` neighbours (`webhooks.md`, `selective-merge-regeneration.md`).
- [ ] T034 Run `uv run invoke format`, `uv run invoke lint`, `cd frontend && pnpm biome:fix` and `uv run invoke docs.validate`, then run [quickstart.md](quickstart.md) scenarios 1 to 5 against a local stack.
  - ⚠️ Partial: format, lint, biome and docs.lint pass. Scenarios 1 to 5 were not run by hand against `dev.start`; their automated coverage passed instead (`backend/tests/integration/artifacts/test_external_artifact.py`, the render callback and artifact component tests).

---

## Dependencies & Execution Order

- **Phase 1 (T001–T003)**: no dependencies. T003 blocks T007 and T012, which need the merged SDK model.
- **Phase 2 (T004–T012)**: T004 → T005, T006 → T007. T008, T009 and T010 are parallel after T004. T011 → T012.
- **US1 (Phase 3)**: depends on Phase 2.
  - T017 → T018 → T019.
  - T020 depends on T017.
  - T021 depends on T017 and T018.
  - T022 depends on T009.
  - T023 depends on T008.
  - T024 depends on everything in US1.
- **US2 (Phase 4)**: depends on Phase 2 and T017 and T020. Independent of US3.
- **US3 (Phase 5)**: depends on Phase 2 and T018 and T021. Independent of US2.
- **Polish (Phase 6)**: after the stories that are delivered.

## Parallel Opportunities

- Phase 2: T008, T009 and T010 in parallel.
- US1 tests: T013, T014, T015 and T016 in parallel, written before T017–T023.
- After US1: US2 (T025–T026) and US3 (T027–T030) in parallel.
- Polish: T031, T032 and T033 in parallel.

## Implementation Strategy

1. **MVP**: Phases 1 and 2, then US1. Stop and run quickstart scenarios 1, 4 and 5. This delivers externally rendered artifacts in proposed changes and after merges.
2. Add US2: version-driven template releases.
3. Add US3: failure and timeout handling. Until US3 is in, an engine that never answers leaves artifacts `Pending`. Ship US3 together with US1 when releasing to users.
4. Polish: documentation, changelog, knowledge doc.
