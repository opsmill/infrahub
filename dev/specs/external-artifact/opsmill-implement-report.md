# Implementation report: Artifacts rendered by an external engine

| Item | Value |
|------|-------|
| Spec directory | `dev/specs/external-artifact/` |
| Branch | `external-artifact` (not pushed) |
| Base commit | `a2d123f88` |
| Head commit | `5d0855d61`, before this report's commit |
| Wall-clock time | About 7.5 hours (08:16Z to 15:40Z), including one paused session and one interrupted session |
| Status | DONE. 33 of 34 tasks complete. T034 is partial (see §3). |

## 1. Summary

- **What teams can now do:** declare `external_transforms` in `.infrahub.yml`. Infrahub then:
  - selects which artifacts to render again with the existing selection;
  - emits `infrahub.artifact.render_requested` events, which webhooks deliver with a render token that is never stored;
  - accepts results on `POST /api/artifact/render/{render_id}`;
  - completes proposed-change checks when results arrive;
  - sets renders that get no answer to `Error` with a cron sweep that runs every minute.
- **Review:** it found 8 important issues and 2 minor ones. All 10 are fixed.

## 2. Chunk ledger

| # | Chunk | Tasks | Outcome | Commit | Decisions or surprises reported upward |
|---|-------|-------|---------|--------|----------------------------------------|
| 1 | Setup: SDK config | T001–T003 | 3 ✅ | `bba8d104c` (SDK `2f53c55d`) | SDK changelog fragment added. The SDK commit is local only, as the user decided. |
| 2 | Schema, constants, event | T004–T008 | 5 ✅ | `dfb026991` (SDK `a6fc47b9`) | The event subclasses `InfrahubEvent`, because `ArtifactEvent` requires checksum fields. No migration needed. The event's node kind is the target's kind. |
| 3 | Token, locks, fingerprint, import | T009–T012 | 4 ✅ | `81f55d56f` | The import test is under `integration/`, where existing tests that import repositories live. A missing query fingerprint still folds in the commit ID, as for every kind. |
| 4 | Render request | T014, T017 | 2 ✅ | `bf05e2f95` | Settings are passed in, following the component-design rules. `query_result` holds `response["data"]`. |
| 5 | Result and callback API | T013, T018, T019 | 3 ✅ | `5858e3667` | Writes use `SYSTEM_USER_ID`. `format_artifact_content` and `artifact_checksum` were moved into `artifacts/content.py`. |
| 6 | Generate path, checks, races | T015, T020, T021 (+T018 step 4) | 3 ✅ | `f08550118` | `CheckPending` type added. The concurrency test found a validator that was completed twice; fixed. Interrupted once and resumed. |
| 7 | Token delivery, hidden data | T016, T022, T023 | 3 ✅ | `b563b1675` | The render fields reach `webhook_send` as a parameter that holds no secret. The signature covers the body with the token in it. |
| 8 | US1 integration test | T024 | 1 ✅ | `92468054a` | Bug found and fixed: the artifact was saved outside a transaction. The test runs `WEBHOOK_PROCESS` itself, because automations do not run in-process. |
| 9 | US2 version release | T025, T026 | 2 ✅ | `dbc833836` | No production change was needed. A version change on a branch renders each target twice: once at import and once when the proposed change opens. |
| 10 | US3 timeout sweep | T027–T030 | 4 ✅ | `39904c0db` | A callback after the deadline gets 401, not 409, because the token has expired. Contract and quickstart updated in `f0f7d3c81`. |
| 11 | Polish | T031–T034 | 3 ✅, 1 ⚠️ | `9b018c55b` | User guide `docs/docs/transformations/external.mdx`, changelog fragment, knowledge page `dev/knowledge/backend/external-artifacts.md`. |
| R | Review fixes | 10 findings | 10 fixed | `5d0855d61` | Interrupted by the user's pause and resumed. The agent accidentally reverted its changes and applied them again. The suites were re-run on the committed code (§4). |

## 3. Tasks not completed

- **T034 (partial):** format, lint, `biome:fix` and `docs.validate` pass. The quickstart scenarios were **not** run by hand against a local stack (`invoke dev.start` with a reference engine). The automated integration file covers scenarios 1–3 and 5, and the component tests cover scenario 4.

## 4. Local-pass evidence

Environment for every run: macOS Darwin 24.5.0, Python 3.13.12 through `uv` (`/opt/homebrew/bin/uv`), Docker 29.2.0 with testcontainers (Neo4j 2026.05.0-enterprise, Prefect 3.8.6, Redis 8.4.0), worktree branch `external-artifact`.

| Test ID | Type | Run command | Passed at (UTC) | Verbatim pass line |
|---------|------|-------------|-----------------|--------------------|
| `python_sdk/tests/unit/sdk/test_schema_repository.py` (8 external-transform tests) | unit | `cd python_sdk && uv run pytest tests/unit/sdk/test_schema_repository.py tests/unit/sdk/test_repository.py -v` | 2026-11-20T08:18:15Z | `85 passed` (for example `test_external_transforms_parsed PASSED`) |
| `backend/tests/unit/events/test_artifact_action.py` (5 render-requested tests) | unit | `uv run pytest backend/tests/unit/events/test_artifact_action.py backend/tests/unit/core/node/test_delete_validator.py -v -p no:randomly` | 2026-11-20T08:26:05Z | `test_render_requested_payload_contains_every_render_field PASSED` |
| `backend/tests/unit/core/node/test_delete_validator.py::test_repository_cascade_reaches_exactly_expected_kinds` (modified) | unit | same as above | 2026-11-20T08:26:05Z | `[read-write-repository] PASSED` |
| `backend/tests/unit/artifacts/test_render_token.py` (9 tests) | unit | `uv run pytest backend/tests/unit/artifacts/test_render_token.py -rA` | 2026-11-20T08:41:09Z | `PASSED ...::test_access_token_validation_refuses_render_token` |
| `backend/tests/unit/git/fingerprint/test_composer_transformation.py` (4 external tests), `test_composition_completeness.py[external_transform]`, `closure_builder/test_dispatcher.py`, `unit/git/test_integrator.py` (modified) | unit | `uv run pytest <files> -rA` | 2026-11-20T08:40:46Z | `PASSED ...::test_external_is_stable_across_commits` |
| `backend/tests/integration/git/test_import_external_transforms.py::TestImportExternalTransforms::test_create_update_and_delete` | integration | `uv run pytest backend/tests/integration/git/test_import_external_transforms.py -rA` | 2026-11-20T08:42:49Z | `PASSED` |
| `backend/tests/unit/core/validators/test_checks_runner.py::test_a_pending_check_leaves_the_validator_in_progress` | unit | `uv run pytest <file> -v` | 2026-11-20T13:08:09Z | `PASSED` |
| `backend/tests/unit/core/regeneration/test_definitions.py::test_external_transform_carries_its_name_and_version_and_has_no_location` | unit | same run | 2026-11-20T13:08:09Z | `PASSED` |
| `backend/tests/unit/webhook/test_render_token_delivery.py` (6 tests, including 2 added in the review) | unit | `uv run pytest backend/tests/unit/webhook/test_render_token_delivery.py -v` | 2026-11-20T15:37:46Z | `test_webhook_subscribed_to_all_events_gets_no_token PASSED` |
| `backend/tests/unit/artifacts/test_content.py` (4 cases) | unit | `uv run pytest backend/tests/unit/artifacts/test_content.py -v` | 2026-11-20T15:37:46Z | `[json_list] PASSED` |
| `backend/tests/unit/graphql/queries/test_task.py::TestFlowRunConnectionSerializer::test_query_result_is_hidden_from_render_request_webhook_parameters` | unit | `uv run pytest <id> -v` | 2026-11-20T13:21:12Z | `PASSED` |
| `backend/tests/component/graphql/queries/test_event.py::test_event_query_hides_the_query_result_of_render_requests` | component | `uv run pytest <id> -v` | 2026-11-20T13:21:12Z | `PASSED` |
| `backend/tests/component/artifacts/` (render request, concurrency, timeouts) and `backend/tests/component/api/test_artifact_render_callback.py` | component | `uv run pytest backend/tests/component/artifacts/ backend/tests/component/api/test_artifact_render_callback.py -p no:randomly -q` | 2026-11-20T15:40:13Z (orchestrator re-run on the final commit) | `30 passed, 2 warnings in 114.67s` |
| `backend/tests/component/proposed_change/test_validate_artifacts_generation{,_widening}.py` (modified paths) | component | `uv run pytest <files>` | 2026-11-20T15:31:02Z | `13 passed` |
| `backend/tests/integration/artifacts/test_external_artifact.py` (7 tests: US1 including merge, token never stored, version change, unrelated commit, manual generation, engine failure, no answer) | integration | `uv run pytest backend/tests/integration/artifacts/test_external_artifact.py -v` | 2026-11-20T15:33:04Z | `7 passed, 4 warnings in 230.14s` |

**Failures unrelated to this feature, seen in full unit runs:**
- `test_local_stamping` needs a Prefect server on 127.0.0.1:4200.
- `backend/tests/unit/git/writeback/test_git_adapter.py::test_an_unreadable_object_store_raises_with_no_path_of_the_worker` and `backend/tests/unit/git/test_remote_refs.py::test_list_remote_heads_keeps_the_git_output_of_refused_credentials`: chunk 6 reported that both fail with and without these changes.

## 5. Review findings

Review mode: command (`/code-review`, level high, range `a2d123f88..9b018c55b`)

| Severity | File | Summary | Status |
|----------|------|---------|--------|
| important | `core/validators/checks_runner.py` | A crashed check could be overwritten to SUCCESS by a recomputation, and checks from earlier runs were counted | Fixed: a crashed check stores FAILURE, a failed validator stays failed, only current-run checks count |
| important | `artifacts/render_result.py` | A fast callback could complete a validator while other checks were not yet written | Fixed: for external definitions, every check is created as UNKNOWN before any check flow runs |
| important | `artifacts/tasks.py` | An exception after the waiting check was stored left it UNKNOWN forever | Fixed: stores a FAILURE check and sets the artifact to `Error` |
| important | `webhook/tasks/process.py` | `query_result` was written to the webhook task logs | Fixed: replaced in both log lines |
| important | `webhook/tasks/process.py` | Webhooks subscribed to `all` received a working render token | Fixed: only webhooks with `event_type` exactly `infrahub.artifact.render_requested` get a token and count as engines |
| important | `artifacts/render_request.py` | The webhook subscription check ignored `node_kind` | Fixed |
| important | `proposed_change/tasks.py` | The validator was recomputed on the root database object instead of a session | Fixed: wrapped in `start_session()` |
| important | `artifacts/timeouts.py` | One artifact that could not be loaded stopped the sweep for every later artifact | Fixed: errors are handled per artifact, and a missing transformation still expires the render |
| nit | `artifacts/content.py` | A mapping sent for a text definition was stored as Python repr text | Fixed: 400 unless the definition is JSON or YAML; lists accepted for JSON and YAML |
| nit | `api/artifact.py` | The token header name was defined twice | Fixed: one owner in `webhook/constants.py` |
| nit | `python_sdk` pointer | The pointer refers to a commit that exists only locally | Deferred by the user's decision (§6) |

## 6. Decisions made without the user

- **Chunking:** User Story 1 (12 tasks) was split into five chunks: request; result and endpoint; generate path and checks; token delivery and hidden data; integration test.
- **Environment:** `uv` was installed with Homebrew, because the existing `~/.local/bin/uv` was a broken symlink.
- **401 after the deadline:** a callback after the deadline gets 401, not the 409 the plan first stated. The spec only requires that the content is refused and the artifact stays unchanged. The contract and quickstart were updated.
- **`all` webhooks no longer count as render engines** (review finding 5). Only webhooks that subscribe to the render-requested event type explicitly receive tokens.
- **Double render on a version change:** on a branch, a version change renders each target at import and again when a proposed change opens. This renders more than needed but misses nothing. It was left as it is.
- **SDK submodule:** the pointer refers to local SDK commits on branch `external-artifact` (`2f53c55d`, `a6fc47b9`), as the user decided on 2026-11-20. Other checkouts cannot resolve it until those commits are pushed.

## 7. Next steps

1. Push the SDK branch to `infrahub-sdk-python` and open a pull request against `infrahub-develop`. After it merges, point the submodule at the merged commit.
2. Run `/pre-ci`, then open the pull request for `external-artifact`.
3. Optionally, run quickstart scenarios 1–5 by hand against `invoke dev.start` with a reference engine, to close T034.
4. Run `/speckit-opsmill-extract` after reviewing this report.
