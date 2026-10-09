# Implementation Report: Enterprise Licensing, Community Contract

**Status**: INCOMPLETE. Two tasks are still open: T051 needs an answer from the owner of the cloud telemetry processor, and T053 still needs the banner and the About dialog checked in a browser. Every test added or changed by this run passed locally (section 4).

| | |
| --- | --- |
| Feature | Licensing in Infrahub Enterprise, the part that lives in this repository ([INFP-472](https://opsmill.atlassian.net/browse/INFP-472), [design doc](https://app.notion.com/p/3ef228b830258130b788d4e2d9c2d357)) |
| Spec directory | `dev/specs/005-enterprise-licensing-infp-472/` |
| Base commit | `1920cd11d` (`origin/develop`) |
| Head commit before this report | `8f4f5e152` on `ds-licensing-8-polish`, 33 commits above the base |
| Wall-clock time | about 6 hours (2026-10-04, 12:05 to 18:05 UTC) |
| Delivery | 8 draft pull requests linked as GitHub stack #10875 on `develop`: [#10861](https://github.com/opsmill/infrahub/pull/10861), [#10863](https://github.com/opsmill/infrahub/pull/10863), [#10864](https://github.com/opsmill/infrahub/pull/10864), [#10865](https://github.com/opsmill/infrahub/pull/10865), [#10867](https://github.com/opsmill/infrahub/pull/10867), [#10868](https://github.com/opsmill/infrahub/pull/10868), [#10870](https://github.com/opsmill/infrahub/pull/10870), [#10872](https://github.com/opsmill/infrahub/pull/10872) |
| Tasks | 51 of 53 done; T051 blocked, T053 partial |

## 1. Chunk ledger

Each chunk ran in a fresh subagent. Its staged diff was reviewed by the local cubic reviewer before it was committed; cubic runs stopped at the user's request after the first review fix. "Commits" lists the chunk's own commits; the review fixes in section 5 added more commits on the same branches, merged upward and never rebased, so every SHA below still exists.

| # | Chunk | Tasks | Done / partial / blocked | Branch, pull request | Commits | Flagged by the subagent |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Phase 1, setup | T001–T002 | 2 / 0 / 0 | `ds-licensing-1-contract`, #10861 | `b493fc8dc` | The local uv (0.11.15) added an unrelated `pendulum` marker change to `uv.lock`; it was removed, so the lock change touches only `pyjwt` |
| 2 | Phase 2, foundation, plus T048 | T003–T012, T048 | 11 / 0 / 0 | `ds-licensing-1-contract`, #10861 | `4dce2d84f` | T048 (configuration reference) moved here because CI checks generated docs on every pull request. `INFRAHUB_LICENSE_KEY` declared in both compose files, as `backend/AGENTS.md` requires |
| 3 | Phase 3, startup log (US1) | T013–T016 | 4 / 0 / 0 | `ds-licensing-2-startup-log`, #10863 | `b4bbdf28c` | `get_license_service()` never raises: a stand-in reports `invalid` / `internal_error` when the service cannot be built. A blank key counts as unset |
| 4 | Phase 4, `/api/info` and About rows (US2) | T017–T024 | 8 / 0 / 0 | `ds-licensing-3-info-endpoint`, #10864 | `2304f59b9` | Anonymous read access is on by default, so `/api/info` is reachable without signing in; anonymous callers now get `license: null`. `InfoRow` moved to `shared/` |
| 5 | Phase 5, banner (US3) | T025–T032 | 8 / 0 / 0 | `ds-licensing-4-banner`, #10865 | `616cd58bf` | The server decides whether a quiet-release notice will reach every user (`shown_to_all_users_when_enforced`). `internal_error` stays with super-admins in both release modes. The reason explanations are new copy |
| 6 | Phase 6, response header (US4) | T033–T036 | 4 / 0 / 0 | `ds-licensing-5-header`, #10867 | `c91e3f8dd` | Pure ASGI middleware with the service provider injected. A 429 from load shedding and an unhandled 500 carry no header. A failing service is logged once per exception type |
| 7 | Phase 7, telemetry (US5) | T037–T042 | 6 / 0 / 0 | `ds-licensing-6-telemetry`, #10868 | `ffeb11e1d` | `TELEMETRY_VERSION` is `20261004`. #10003 is still open, does not change the version, and edits the same telemetry files |
| 8 | Phase 8, upgrade output (US6) | T043–T046 | 4 / 0 / 0 | `ds-licensing-7-upgrade`, #10870 | `23deed547` | The quiet-release note follows `shown_to_all_users_when_enforced`. Customer names are printed with Rich markup turned off |
| 9 | Phase 9, polish | T047, T049–T053 | 4 / 1 / 1 | `ds-licensing-8-polish`, #10872 | `4f7344049` | The leak test is split over three files by tier. `checklists/release-gate.md` holds three items that need a human answer |

## 2. Commits added by the review fixes

| Branch | Commits |
| --- | --- |
| `ds-licensing-1-contract` | `43cd14180` |
| `ds-licensing-2-startup-log` | merge `1cf585437`, fix `5bbe9df8a` |
| `ds-licensing-3-info-endpoint` | merge `d6669c85c`, fix `9f6f3d908`, docs `d585c020e` |
| `ds-licensing-4-banner` | merge `a5907290e`, fix `9fd511b32`, merge `e0aee8c4e`, docs `c95ae17fb` |
| `ds-licensing-5-header` | merge `7646e5024`, fix `d756ee195`, merge `eb5d0e365` |
| `ds-licensing-6-telemetry` | merge `2053b0235`, fix `325fc1fa1`, merge `34ffddd69` |
| `ds-licensing-7-upgrade` | merge `9a451621b`, fix `87b7e20b8`, merge `7ecae2ee6` |
| `ds-licensing-8-polish` | merge `d0271556b`, fix `c92174c7c`, merge `ca4f9e325`, docs `8f4f5e152` |

## 3. Tasks not completed

- **T051, release gate (blocked).** It needs answers from people outside this repository, recorded in `checklists/release-gate.md`:
  - the owner of the cloud telemetry processor confirms it accepts payload format `20261004`;
  - the public telemetry FAQ and page say that licensed Enterprise deployments send the license ID, type, tiers and dates, before the first licensing release (they now say all telemetry is anonymous);
  - product signs off the explanations of the six invalid reasons and the quiet-release notes.

  The checklist's open items will also stop the `speckit-implement` checklist gate on any later run until they are checked.
- **T053, Community stack check (partial).** On a local stack built from the `:local` image, with this branch's backend mounted, every backend item passed:
  - no `X-Infrahub-License-Status` header;
  - `/api/info` reports `not_required`, and `null` to anonymous callers;
  - `infrahub upgrade --check` prints no license section;
  - with a key set, each process logs one INFO line saying the key is ignored.

  The image's frontend predates this branch, so "no banner" and "About dialog unchanged" rest on the Vitest tests in section 4. A browser check on an image built from this branch is still needed.

## 4. Local-pass evidence

Every row passed on the code as finally committed. Unit tests need no service. Component and integration tests ran with `DOCKER_HOST=unix:///Users/Dimitris/.docker/run/docker.sock PYTHONPATH=$PWD/backend` against testcontainers through Docker Desktop. Frontend tests ran in Vitest browser mode (Chromium). Earlier runs during each chunk are in the subagent reports; the rows below are the last run of each test on its own branch after the review fixes, plus the final run on the top branch.

| Test id | Type | Run command | Passed at (UTC) | Environment | Pass line |
| --- | --- | --- | --- | --- | --- |
| `backend/tests/unit/license/test_models.py`: aware datetimes to UTC, naive and non-datetime rejected (3 + 3), non-text fields rejected (6), end not after start (2), unknown type kept, `is_evaluation` (4), invalid status combinations rejected (16) | unit | `uv run --no-sync pytest backend/tests/unit/license -v` | 2026-10-04T17:21:22Z (`ds-licensing-1-contract`) | n/a | `87 passed`; `test_status_with_a_missing_or_an_extra_detail_is_rejected[expired_with_days_remaining] PASSED` |
| `backend/tests/unit/license/test_status.py`: unlicensed, invalid per reason (6), 18 boundary cases, rounding (2) | unit | same | 2026-10-04T17:21:22Z | n/a | `87 passed` |
| `backend/tests/unit/license/test_notices.py`: `test_notice_for_each_state_and_mode` (16 incl. `invalid_internal_error_quiet` and `_enforce`), `test_every_state_and_mode_is_covered`, `test_shown_to_all_users_when_enforced` (10) | unit | `uv run --no-sync pytest backend/tests/unit/license backend/tests/unit/workers/test_dependencies.py backend/tests/unit/api/test_internal_license.py -v` | 2026-10-04T17:37:21Z (`ds-licensing-4-banner`) | n/a | `128 passed`; `test_notice_for_each_state_and_mode[invalid_internal_error_enforce] PASSED` |
| `backend/tests/unit/license/test_service.py`: Community service, unavailable stand-in, `read_license_status` returns status, logs traceback, logs a repeated failure once, logs each kind once | unit | same | 2026-10-04T17:37:21Z | n/a | `test_read_license_status_logs_each_kind_of_failure_once PASSED` |
| `backend/tests/unit/license/test_settings.py`: unset default, env read, settings section, no enterprise feature, blank key unset (3) | unit | same | 2026-10-04T17:37:21Z | n/a | `test_blank_license_key_counts_as_unset[newline] PASSED` |
| `backend/tests/unit/workers/test_dependencies.py`: `test_get_license_service_stands_in_once_for_a_service_that_cannot_be_built`, `test_startup_license_line_reports_a_service_that_cannot_be_built_as_invalid` | unit | same | 2026-10-04T17:37:21Z | n/a | `PASSED` |
| `backend/tests/unit/license/test_reporting.py`: `log_license_state` per state (9) and failing service; `license_block` per state and never the customer name; `license_report_lines` per state and mode (19), UTC days (4 incl. `end_less_than_a_second_after_midnight_shows_that_day`) | unit | `uv run --no-sync pytest backend/tests/unit/license backend/tests/unit/workers/test_dependencies.py backend/tests/unit/api/test_internal_license.py backend/tests/unit/cli/test_upgrade_license.py -v` | 2026-10-04T17:46:59Z (`ds-licensing-7-upgrade`) | n/a | `203 passed`; `test_license_report_lines_show_dates_as_utc_days[end_less_than_a_second_after_midnight_shows_that_day] PASSED` |
| `backend/tests/unit/license/test_middleware.py`: header per state and mode (7), eligible paths (4), excluded paths (4), error responses, failing service untouched and logged once (2) | unit | `uv run --no-sync pytest backend/tests/unit/license ... -q` (unit set) | 2026-10-04T17:39:05Z (`ds-licensing-5-header`) | n/a | `148 passed`; `test_header_carries_the_state_only_when_the_notice_asks_for_it[enforce_expired] PASSED` |
| `backend/tests/unit/api/test_internal_license.py`: license object per state and mode (9), anonymous `null`, internal error when the object cannot be built (2) | unit | `uv run --no-sync pytest backend/tests/unit/api/test_internal_license.py -v` | 2026-10-04T17:56:17Z (`ds-licensing-3-info-endpoint`) | n/a | `10 passed`; `test_info_reports_an_internal_error_when_the_license_object_cannot_be_built[license_object_rejects_the_status] PASSED` |
| `backend/tests/unit/cli/test_upgrade_license.py`: section through the migration console, verbatim customer name, nothing for `not_required`, failure logged and skipped, failing status read, never prompts (9 states), never prints the key (2), placement in `--check` and in the upgrade | unit | `uv run --no-sync pytest backend/tests/unit/license backend/tests/unit/workers/test_dependencies.py backend/tests/unit/api/test_internal_license.py backend/tests/unit/cli/test_upgrade_license.py -v` | 2026-10-04T17:46:59Z (`ds-licensing-7-upgrade`) | n/a | `test_upgrade_check_prints_the_license_section_before_the_closing_line PASSED`; `test_upgrade_prints_the_license_section_after_the_upgrade_completes PASSED` |
| All backend license unit tests on the top branch | unit | `uv run --no-sync pytest backend/tests/unit/license backend/tests/unit/workers/test_dependencies.py backend/tests/unit/api/test_internal_license.py backend/tests/unit/cli/test_upgrade_license.py -q -n 4` | 2026-10-04T17:59:22Z (`ds-licensing-8-polish`) | n/a | `205 passed, 84 warnings in 7.59s` |
| Whole backend unit suite (the reported-failure fixture is autouse for all unit tests) | unit | `uv run --no-sync pytest backend/tests/unit -n 4 -q` | 2026-10-04T18:03:30Z (`ds-licensing-8-polish`) | n/a | `3136 passed, 85 warnings in 29.14s` |
| `backend/tests/component/api/test_license_startup_log.py::test_api_server_logs_its_license_state_once_at_startup` (3) | component | `uv run --no-sync pytest backend/tests/component/api/test_50_internals.py backend/tests/component/api/test_license_header.py backend/tests/component/api/test_license_startup_log.py backend/tests/integration/workers/test_infrahubasync.py -v` | 2026-10-04T17:52:08Z (`ds-licensing-8-polish`) | testcontainers Neo4j | `28 passed` |
| `backend/tests/integration/workers/test_infrahubasync.py::TestWorker::test_worker_logs_its_license_state_once_at_setup` (key pinned, whole event asserted) | integration | same | 2026-10-04T17:52:08Z; also 17:25:39Z with `INFRAHUB_LICENSE_KEY` exported in the shell | testcontainers Neo4j, RabbitMQ | `PASSED` |
| `backend/tests/component/api/test_50_internals.py`: `test_info_endpoint`, `test_info_endpoint_reports_the_license_service_state`, `test_info_endpoint_carries_no_license_object_for_anonymous_callers`, `test_config_endpoint_carries_no_license_information` | component | same | 2026-10-04T17:52:08Z | testcontainers Neo4j | `28 passed` |
| `backend/tests/component/api/test_license_header.py` (5, incl. `test_enforced_license_problem_is_sent_to_callers_who_are_not_signed_in`) | component | same | 2026-10-04T17:52:08Z | testcontainers Neo4j | `28 passed` |
| `backend/tests/component/telemetry/test_tasks.py`: license block with a test service, `null` with the Community default, stored when sending is off, block that cannot be built stored as `null`, snapshot never carries the key (2) | component | `uv run --no-sync pytest backend/tests/component/api/test_license_key_never_leaks.py backend/tests/component/telemetry/test_tasks.py -v` | 2026-10-04T17:51:09Z (`ds-licensing-8-polish`) | testcontainers Neo4j, Prefect test server | `15 passed` |
| `backend/tests/component/api/test_license_key_never_leaks.py::test_license_key_never_appears_in_the_startup_log_or_the_api_responses` (2) | component | same | 2026-10-04T17:51:09Z | testcontainers Neo4j | `15 passed` |
| Frontend `src/entities/license` and `src/entities/config`: banner rules, dismissal hook, banner, About rows (incl. start row, anonymous, `null`, "expired today", UTC day), license dates, About dialog, app-info query refresh | unit (Vitest) | `cd frontend/app && node_modules/.bin/vitest run src/entities/license src/entities/config` | 2026-10-04T17:59Z (`ds-licensing-8-polish`) | Vitest browser mode, Chromium | `Test Files 11 passed (11)`, `Tests 117 passed (117)` |
| Frontend full suite, plus `tsc --noEmit` (185 errors, the baseline, none in a file this stack changed) and `knip` (only the existing configuration hint) | unit (Vitest) | `cd frontend/app && node_modules/.bin/vitest run` | 2026-10-04T18:04:03Z (`ds-licensing-8-polish`) | Vitest browser mode, Chromium | `Test Files 219 passed (219)`, `Tests 1688 passed (1688)` |
| T053 Community stack check (backend items) | manual end-to-end | `docker compose ... up -d --pull never`, `curl`, `docker exec <project>-server-1 infrahub upgrade --check` | 2026-10-04, chunk 9 | `:local` image with this branch mounted at `/source`, 4 gunicorn workers, 2 task workers | all four backend items as expected (section 3) |

No end-to-end test was added; the plan moves the end-to-end banner tests to the first licensing release, where the Enterprise license service exists.

## 5. Review findings

**Per-chunk cubic reviews (local).** 41 findings over 15 rounds, not counting one round that reviewed unrelated untracked files by mistake. All were fixed except two:

- the bare `LICENSE` environment variable crashes startup; rejected here because `DEV`, `API` and every other settings section have the same problem, and filed as a follow-up task;
- the public telemetry FAQ calls all telemetry anonymous; recorded as a release-gate item, because public docs for licensing ship with the first licensing release.

The rounds caught three high-severity defects before they were committed:

- anonymous callers received the license holder's details from `/api/info`;
- an exception while building the license service escaped the startup failure boundary;
- `internal_error` became a banner every user had to see in the enforcing release.

**Whole-stack review (Phase 6, three read-only agents: code and errors, tests and comments, types and simplification).** No critical findings.

| Severity | File | Finding | Outcome |
| --- | --- | --- | --- |
| Important | `backend/infrahub/license/models.py` | `LicenseStatus` did not reject impossible field combinations, so five surfaces handled them five ways | Fixed in `ds-licensing-1-contract` |
| Important | `backend/infrahub/api/internal.py` | A non-text license field made `/api/info` return 500 while every other surface survived it | Fixed: `License` rejects non-text and non-datetime fields, and `get_info` has its own boundary |
| Important | `backend/infrahub/cli/upgrade.py` | No test proved where the license section prints | Fixed: placement tests for `--check` and the upgrade |
| Important | `license-banner.test.tsx` | The pending-permission test could not fail | Fixed, checked by removing the guard |
| Important | `license-banner.tsx` | The guard that keeps a non-dismissible banner visible after an earlier dismissal had no test | Fixed |
| Important | `test_infrahubasync.py` | The worker test did not pin the license key | Fixed |
| From the GitHub review | `license-dates.ts`, `reporting.py` | The last covered day was a day early for an end time with a fraction of a second | Fixed, frontend and backend |
| From the GitHub review | `use-license-banner-dismissal.ts` | Dismissing an `internal_error` notice also hid a later `bad_signature` one | Fixed: the dismissal key includes the reason |
| From the GitHub review | `license-about-rows.tsx` | A license that has not started looked active | Fixed: a "Starts" row |
| Suggestion | `dependencies.py` | `get_license_service()` calls the overridden builder on every request | Documented: the Enterprise builder must cache its instance |
| Suggestion | several | Duplicated `License` literals and auth fakes in tests, `notice_mode` unused by the UI, `InfoAPI` built in two branches, `TelemetryLicenseData.state` typed `str` | Deferred |

**GitHub cubic comments on the pull requests.** 44 inline comments across the 8 pull requests. None was replied to or resolved. The fixes above cover several; the rest are mostly spec wording. One P1 on #10861 says licenses must be bound to the deployment ID, as the INFP-472 card states. That contradicts the approved design and needs an answer from you.

## 6. Autonomous decisions

- **Stack mechanics:**
  - The 8 pull requests are linked as native stack #10875. `gh stack link` first set the bottom pull request's base to `stable` (the repository default); it was unstacked, set back to `develop` and linked again with `--base develop`.
  - Review fixes were merged upward, never rebased, so no branch was force-pushed.
- **Scope beyond `tasks.md`:**
  - the compose declaration of `INFRAHUB_LICENSE_KEY` (repository rule);
  - T048 moved to the first pull request;
  - `get_license_service()` and `get_info` failure boundaries;
  - stricter validation of `License` and `LicenseStatus`.
- **Behaviour that refines the design doc:**
  - Anonymous `/api/info` callers get `license: null`. The design doc assumed the endpoint requires sign-in, but anonymous read access is on by default.
  - In the enforcing release the response header still reaches anonymous callers, as designed.
  - `invalid` / `internal_error` is a dismissible notice for super-admins in every release, with no header, because it is a defect in Infrahub rather than in the customer's license.
- **Copy written during implementation:** the explanations of the six invalid reasons, the "Starts" row, and the quiet-release notes in the upgrade output for states other than `unlicensed`. All are in the release-gate checklist for product sign-off.
- **Test design trade-offs:**
  - The upgrade placement tests replace 13 module functions with `monkeypatch`, which `testing.md` advises against; they fail when the section moves.
  - `license_block` lost its exhaustive `match` when unreachable branches were removed.
  - `pluralize` replaced `dayCount`; it would print "0 day", but every caller passes at least 1.
- **CI:** two failures on #10868 and #10870 were unrelated (a RabbitMQ connection cancelled before any license code ran, and a random-string flake in a changelog test this stack does not touch). Both jobs were re-run; the later pushes started new runs on every pull request.

## 7. Next steps

1. Answer the P1 comment on #10861 about binding licenses to the deployment ID, then reply to or resolve the other GitHub review comments.
2. Get the three release-gate answers in `checklists/release-gate.md` (T051).
3. Check the banner and the About dialog in a browser on an image built from this branch (T053).
4. [CLAUDE RECOMMENDED – based on the anonymous `/api/info` finding] Update the design doc: `/api/info` is not signed-in only, and `internal_error` stays with super-admins.
5. [CLAUDE RECOMMENDED – based on #10003 touching the same telemetry files] Merge #10003 or this stack first and rebase the other; check `TELEMETRY_VERSION` after the second one lands.
6. [CLAUDE RECOMMENDED – based on the deferred suggestions in section 5] Consider a shared backend `License` builder for tests and adding the failure reason to the telemetry block, so OpsMill can tell an internal error from a customer's invalid license.
7. Mark the pull requests ready for review once CI is green on the stack.
