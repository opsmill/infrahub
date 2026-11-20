# Implementation Plan: Artifacts rendered by an external engine

**Branch**: `external-artifact` | **Date**: 2026-11-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/external-artifact/spec.md`

## Summary

Teams declare an external transformation in `.infrahub.yml`: a GraphQL query, a version value and a timeout. Artifact definitions reference it in the same way they reference Jinja2 and Python transformations.

**Selection.** Infrahub selects which artifacts to render with the existing code, with no change:
- the selective regeneration after a merge;
- the proposed-change artifact checks;
- the manual generate endpoint.

**Render request.** For each selected target, Infrahub:
1. runs the query, and registers the artifact as a subscriber of the query's group, as internal renders do;
2. sets the artifact to `Pending`, with a render ID and a deadline;
3. emits `infrahub.artifact.render_requested`, with the full query result.

**Delivery.** Existing webhooks deliver the event. Their Python transformations can reshape it for the engine.

**Render token.** Infrahub mints a JWT for one render request on each delivery attempt and sends it in a header. A placeholder in the body lets an engine receive it in the body instead. The token is never stored in events, flow parameters or logs ([research.md](research.md) R3, R4).

**Callback.** The engine calls `POST /api/artifact/render/{render_id}` with the content or a failure message. The endpoint:
- stores the content through the existing artifact storage path;
- sets the artifact to `Ready` or `Error`;
- completes the proposed-change check and recomputes the validator (R5, R6).

**Before emitting**, the request fails at once with a specific `Error` message in three cases:
- no active webhook subscribes to the event type;
- `main.public_url` is not set;
- the event would exceed the size limit (critique X1).

**Concurrency.** Every change to an artifact's render state runs under a lock per artifact and branch. The render ID is checked inside that lock. Validator recomputation runs under a lock per validator and reads the stored checks (critique E1, E2).

**Permissions.** The `Events` and `Task` GraphQL queries leave `query_result` out of this event type's payload, so query data stays behind object permissions (critique E5).

**Timeout.** A cron workflow that runs every minute sets pending artifacts past their deadline to `Error` (R7).

**Fingerprint.** It hashes the version and does not fold in the commit ID. A version change therefore selects every target, and an unrelated commit selects none (R8).

## Technical Context

**Language/Version**: Python 3.14 (backend and the SDK submodule). The frontend gets regenerated GraphQL types only. It already displays `Pending` and `Error`.

**Primary Dependencies**: existing only.
- FastAPI for the callback endpoint.
- Prefect for events, webhooks and the cron workflow.
- PyJWT, already used in `auth/auth.py`.
- Pydantic 2 for the SDK config model.

**Storage**: Neo4j. One new node kind, `CoreTransformExternal`, and two optional attributes on `CoreArtifact`. The object store keeps artifact content, unchanged.

**Testing**:
- pytest unit tests: fingerprint and token.
- Component tests with testcontainers: endpoint, status transitions, sweep and validator.
- Integration tests: scenarios 1 to 3 in [quickstart.md](quickstart.md).
- SDK unit tests for the `.infrahub.yml` model.

**Target Platform**: Infrahub server and task workers (Linux containers).

**Project Type**: web service (backend) plus the Python SDK submodule.

**Performance Goals**:
- An artifact is `Ready` less than 5 seconds after a valid callback (SC-003).
- No pending render outlives its deadline by more than 1 minute (SC-004).

**Constraints**:
- The render-request event must stay under the Prefect event size limit. 1,500,000 bytes was read from Prefect 3.7.5 and must be confirmed for 3.8.6 (R9).
- The token must not reach persisted storage (R3).
- `main.public_url` must be set to build `callback_url`. When it is not set, the render request fails with a clear `Error` message.

**Scale/Scope**:
- One request per target. Target groups of several hundred devices must not occupy workers while they wait (R6).
- The pending work is stored on the artifacts themselves, so the number of pending renders is bounded by the number of artifacts.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Schema-Driven Integrity | Pass | `CoreTransformExternal` and the two `CoreArtifact` attributes are added in the schema layer. Generated files are regenerated with `uv run invoke backend.generate`, `schema.generate-graphqlschema`, `pnpm codegen` and `docs.generate`. Whether existing databases need a graph migration must be checked against `dev/guides/backend/creating-migrations.md`. |
| II. Branch-Safe by Default | Pass | The transformation is branch-aware, as are the other transformation kinds. The artifact render state is branch-local, as are `status` and `storage_id`. Each render token is bound to one branch. Merge behaviour is specified: render again on the destination branch (spec FR-001, US1 scenario 4). |
| III. Type Safety & Explicit Contracts | Pass | Pydantic models for the event, the callback body and the SDK config. The exhaustive `match` in `FingerprintComposer` gets a new case. The other `if/elif` dispatches get an explicit external branch, and an `else` that raises. |
| IV. Test Discipline | Pass | The tests are listed under Testing, and each functional requirement is mapped to a test in [quickstart.md](quickstart.md). |
| V. Query Performance | Pass | The sweep reads `CoreArtifact` filtered on `status = Pending` and `render_deadline < now`. The query runs once per target, as for internal renders. |
| VI. Security & Input Boundaries | Pass with gates | The new endpoint validates the token, the body schema, the content size and the content type. The `Events` and `Task` queries leave out `query_result` for this event type (critique E5). The token is scoped to one render, branch and artifact, and expires at the deadline. Error messages expose no internals. The token is kept out of stored data. **Gate:** authentication change and new REST endpoint, see below. |
| VII. Simplicity | Pass | Reuses webhooks, webhook transformations, the artifact storage path, artifact checks, the fingerprint and cron workflows. No new dependency. No second pipeline. |

**Governance gates crossed, which need the user's confirmation before implementation**:
- Core schema change (`AGENTS.md` and `backend/AGENTS.md`): the new node kind and two `CoreArtifact` attributes.
- GraphQL schema change: the new kind and attributes are exposed.
- New REST endpoint (`backend/AGENTS.md`): `POST /api/artifact/render/{render_id}`, and the `schema/openapi.json` update. A GraphQL mutation was rejected in R5.
- Authentication change: a new JWT `type` accepted on one endpoint only.
- A change to the SDK submodule: lands first in `infrahub-sdk-python`, on the `infrahub-develop` branch.

**Post-design re-check**: no new violations. Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/external-artifact/
├── spec.md
├── plan.md              # This file
├── research.md          # R1–R10
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── callback-api.md
│   ├── render-request.md
│   └── infrahub-yml.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
python_sdk/infrahub_sdk/schema/repository.py          # InfrahubExternalTransformConfig, external_transforms section

backend/infrahub/
├── core/constants/infrahubkind.py                     # TRANSFORMEXTERNAL
├── core/constants/__init__.py                         # EventType.ARTIFACT_RENDER_REQUESTED
├── core/schema/definitions/core/transform.py          # core_transform_external
├── core/schema/definitions/core/artifact.py           # render_request_id, render_deadline
├── core/schema/definitions/core/__init__.py           # register the new node
├── core/diff/conflicts_enricher.py                    # fingerprint of the new kind
├── core/regeneration/definitions.py                   # external fragment, no repository requirement on the render
├── core/validators/checks_runner.py                   # pending check results, recompute validator
├── message_bus/types.py                               # transform_location for external
├── git/integrator.py                                  # import plan steps, render dispatch -> request
├── git/closure_builder/                               # empty complete closure
├── git/fingerprint/composer.py                        # ExternalTransformationFingerprintInput
├── git/tasks.py                                       # generate path: external branch
├── artifacts/
│   ├── render_request.py                              # fail-fast checks, run query, set Pending, emit event
│   ├── render_lock.py                                 # per-artifact/branch and per-validator lock names
│   ├── render_result.py                               # accept result: store, status, check, events
│   ├── render_token.py                                # mint and validate the render JWT
│   ├── timeouts.py                                    # cron sweep flow
│   └── tasks.py                                       # proposed-change check: external branch
├── api/artifact.py                                    # POST /api/artifact/render/{render_id}
├── events/artifact_action.py                          # ArtifactRenderRequestedEvent
├── task_manager/event/query.py                        # leave query_result out for render_requested
├── graphql/queries/task.py                            # leave query_result out of webhook flow parameters
├── webhook/tasks/process.py                           # mint token per attempt, header and placeholder
├── webhook/log_formatter.py                           # redact the token from logged bodies
└── workflows/catalogue.py                             # sweep cron workflow

backend/tests/{unit,component,integration}/            # see quickstart.md
frontend/app/src/entities/events/domain/model/event-constants.ts   # new event filter choice
changelog/+external-artifact.added.md
docs/docs/                                             # user docs for external transforms
```

**Structure Decision**:
- The backend logic is in `backend/infrahub/artifacts/`, next to the existing artifact check flow.
- The integration points are the five dispatch sites listed in R1.
- The SDK change is a prerequisite pull request in the submodule's own repository.

## Complexity Tracking

No constitution violations to justify.
