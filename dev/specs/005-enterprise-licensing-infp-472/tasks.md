---

description: "Task list for Enterprise Licensing, Community Contract"
---

# Tasks: Enterprise Licensing, Community Contract

**Input**: Design documents from `specs/005-enterprise-licensing-infp-472/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Included. Constitution IV requires tests with every feature, and the plan names the test files. Write each test task before the implementation task it covers and confirm it fails first.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested on its own once the foundational phase is done.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: The user story the task belongs to (US1–US6, from spec.md)

## Path Conventions

Web application: backend in `backend/infrahub/` with tests in `backend/tests/`, frontend in `frontend/app/src/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependency and package skeleton.

- [ ] T001 Change `pyjwt==2.15.0` to `pyjwt[crypto]==2.15.0` in `pyproject.toml`, run `uv lock`, and confirm `uv.lock` adds no new package (`cryptography` is already locked through authlib, jwcrypto and prefect)
- [ ] T002 [P] Create the package `backend/infrahub/license/__init__.py` (empty) and the test package `backend/tests/unit/license/__init__.py` (empty)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The license types, the two pure functions, the replaceable service and the setting. Every user story reads these.

**⚠️ CRITICAL**: No user story work starts before this phase is complete.

- [ ] T003 [P] Write `backend/tests/unit/license/test_models.py`:
  - `License` accepts timezone-aware datetimes and normalizes them to UTC;
  - it rejects a naive `starts_at`, `ends_at` or `issued_at` with `ValueError`;
  - an unknown `license_type` value is kept as received;
  - `is_evaluation` is true only for `"evaluation"`.
- [ ] T004 [P] Write `backend/tests/unit/license/test_status.py` for `evaluate` (data-model.md "State derivation"):
  - `None` → unlicensed;
  - each `LicenseFailureReason` → invalid with that reason;
  - for evaluation, commercial and an unknown type, at one second before `starts_at`, at `starts_at`, one second before `ends_at - 30 days`, at `ends_at - 30 days`, one second before `ends_at`, and at `ends_at`;
  - `days_remaining` rounds up and `days_since_expiry` rounds down (11.5 days left → 12; 3.9 days expired → 3).
- [ ] T005 [P] Write `backend/tests/unit/license/test_notices.py` for `notice_for`: every one of the 7 states × 2 `NoticeMode` values returns the audience, dismissibility and `send_header` from the data-model.md Notice table
- [ ] T006 Implement `backend/infrahub/license/models.py`:
  - the enums `LicenseState`, `LicenseFailureReason`, `LicenseType`, `NoticeMode` and `NoticeAudience`;
  - the frozen dataclasses `License` (with the aware-datetime validation in `__post_init__`), `LicenseFailure`, `LicenseStatus` and `Notice`, as in data-model.md.

  Make T003 pass.
- [ ] T007 Implement `evaluate(outcome, now)` and `notice_for(status, mode)` in `backend/infrahub/license/status.py`, both pure, with the 30-day expiring window as a module constant; make T004 and T005 pass
- [ ] T008 [P] Write `backend/tests/unit/license/test_service.py`:
  - `LicenseServiceCommunity.status()` returns `not_required` with no license, `notice_mode` is `QUIET`, `enforcing_release` is `None`;
  - `read_license_status(service, now=...)` returns the service's status, and converts any exception from `service.status()` into `invalid` / `internal_error` with an ERROR log entry that includes the traceback.
- [ ] T009 Implement in `backend/infrahub/license/service.py`:
  - the abstract `LicenseService` (`notice_mode`, `enforcing_release`, `status(now: datetime | None = None)`) and `LicenseServiceCommunity`, as in contracts/license-service.md;
  - `read_license_status(service, now=None) -> LicenseStatus`, the single failure-containment boundary every surface uses (`except Exception` with `# noqa: BLE001` and a comment naming the top-level-boundary reason from `dev/guidelines/backend/exceptions.md`).

  Make T008 pass.
- [ ] T010 Add `build_license_service()` (cached in `_singletons` under `"license_service"`) and `get_license_service()` (with `@inject` and `Depends(build_license_service)`) to `backend/infrahub/workers/dependencies.py`, mirroring `build_ldap_auth_service` / `get_ldap_auth_service`
- [ ] T011 [P] Write `backend/tests/unit/license/test_settings.py`: `LicenseSettings().key` is `None` by default and reads `INFRAHUB_LICENSE_KEY` from the environment; `Settings().license` exists; setting the key does not add anything to `Settings.enterprise_features`
- [ ] T012 Add `LicenseSettings` (`env_prefix="INFRAHUB_LICENSE_"`, `key: str | None = Field(default=None, description="License for Infrahub Enterprise, as a signed token. Infrahub Community ignores it.")`) and register it as `license: LicenseSettings = LicenseSettings()` on `Settings` in `backend/infrahub/config.py`; make T011 pass

**Checkpoint**: The contract exists, the rules are fully tested, and nothing calls it yet.

---

## Phase 3: User Story 1 - Existing deployments see no change when this ships (Priority: P1) 🎯 MVP

**Goal**: Every process logs its license state at startup and builds the service eagerly. A key set where no license is required is ignored and logged once.

**Independent Test**: Start the API server and a task worker on Community with and without `INFRAHUB_LICENSE_KEY`. Check one INFO line in each case and no other change (quickstart.md §5).

- [ ] T013 [P] [US1] Write tests for `log_license_state(service, key_is_set)` in `backend/tests/unit/license/test_reporting.py`:
  - `not_required` without a key logs one INFO line;
  - `not_required` with a key logs one INFO line saying the key is ignored, without the key's value;
  - `valid` logs INFO; `unlicensed`, `not_yet_valid`, `expiring` and `expired` log WARNING; `invalid` logs ERROR with the reason code;
  - a service that raises still produces one ERROR line and no exception.
- [ ] T014 [US1] Implement `log_license_state(service, key_is_set)` in `backend/infrahub/license/reporting.py` using `read_license_status`; make T013 pass
- [ ] T015 [US1] Call `log_license_state(get_license_service(), key_is_set=config.SETTINGS.license.key is not None)` in `backend/infrahub/server.py::app_initialization`, right after `validate_graph_version`. It is the first caller, so an Enterprise service is built and verified at startup
- [ ] T016 [US1] Call `log_license_state(...)` the same way in `backend/infrahub/workers/infrahub_async.py::InfrahubWorkerAsync.setup`, right after `validate_graph_version`

**Checkpoint**: Startup behaviour is complete; the rest of the stories add surfaces.

---

## Phase 4: User Story 2 - Signed-in users can see the license state and details (Priority: P1)

**Goal**: `/api/info` returns the license object (contracts/api-info.md), `/api/config` stays license-free, and the About dialog shows the license rows.

**Independent Test**: With a test license service swapped in through `override_dependency`, read `/api/info` and the About dialog for each state (quickstart.md §2 and §4).

- [ ] T017 [P] [US2] Write `backend/tests/unit/api/test_internal_license.py`. Use `tests/helpers/dependency_override.py::override_dependency` on `build_license_service` with a test service returning a fixed status:
  - `get_info` returns the license object of contracts/api-info.md for `not_required`, `unlicensed`, `invalid` (reason set, details null), `expiring` and `valid`, including `notice_mode`, `enforcing_release` and `banner`;
  - a service that raises yields `invalid` / `internal_error`;
  - `get_config`'s response has no `license` key.
- [ ] T018 [US2] Add `BannerAPI` and `LicenseInfoAPI` (Pydantic) and `InfoAPI.license` to `backend/infrahub/api/internal.py`. Build the object in `get_info` from `read_license_status(get_license_service())` and `notice_for(status, service.notice_mode)`. Leave `ConfigAPI` and `get_config` unchanged. Make T017 pass
- [ ] T019 [US2] Extend `backend/tests/component/api/test_50_internals.py`:
  - on the real app, `/api/info` returns `license.state == "not_required"` by default and the swapped-in state with a test service;
  - `/api/config` carries no license information.
- [ ] T020 [US2] Regenerate `schema/openapi.json` (`uv run invoke schema.generate-jsonschema`) and `frontend/app/src/shared/api/rest/types.generated.ts` (`cd frontend/app && pnpm codegen`)
- [ ] T021 [P] [US2] Create `frontend/app/src/entities/license/domain/model/license.ts` with the license types taken from the generated REST types (state, failure reason, notice mode, audience, license info)
- [ ] T022 [P] [US2] Write `frontend/app/src/entities/license/ui/license-about-rows.test.tsx` from the "About dialog rows" table in contracts/frontend-banner.md:
  - commercial and evaluation licenses ("Evaluation license, N days left");
  - expired ("expired N days ago");
  - `unlicensed` ("Not installed") and `invalid` ("Could not be verified");
  - `not_required` (renders nothing).
- [ ] T023 [US2] Implement `frontend/app/src/entities/license/ui/license-about-rows.tsx`; make T022 pass
- [ ] T024 [US2] Render `LicenseAboutRows` in `frontend/app/src/entities/config/ui/about-modal.tsx` from the app-info data, and extend `about-modal.test.tsx` so the dialog is unchanged when the state is `not_required`

**Checkpoint**: The state is visible to every signed-in user through the API and the About dialog.

---

## Phase 5: User Story 3 - Users are warned by a banner according to state and release (Priority: P1)

**Goal**: The banner of contracts/frontend-banner.md: audience, dismissal, text per state and mode, and refresh.

**Independent Test**: With mocked app info and permission responses, render the layout for each state, mode and role (quickstart.md §4).

**Depends on**: T018–T021 (license object and generated types).

- [ ] T025 [P] [US3] Write `frontend/app/src/entities/license/domain/rules/license-banner.test.ts`:
  - `shouldShowBanner(audience, isSuperAdmin, permissionResolved)` for every audience and role, including `false` while the permission is unresolved for `super_admins`;
  - `bannerText(license)` for every state in both modes, including the quiet-mode suffix with and without `enforcing_release`.
- [ ] T026 [US3] Implement `frontend/app/src/entities/license/domain/rules/license-banner.ts` (pure, no React, no storage); make T025 pass
- [ ] T027 [P] [US3] Write `frontend/app/src/entities/license/ui/hooks/use-license-banner-dismissal.test.ts`:
  - dismissal is remembered in `sessionStorage` for the same license ID (or `none`) and state;
  - a new license ID or state shows the banner again;
  - storage access that throws falls back to not dismissed.
- [ ] T028 [US3] Implement `frontend/app/src/entities/license/ui/hooks/use-license-banner-dismissal.ts`; make T027 pass
- [ ] T029 [P] [US3] Write `frontend/app/src/entities/license/ui/license-banner.test.tsx`:
  - renders for `all_users`;
  - renders for `super_admins` only when the permission query says super-admin;
  - renders nothing while that query is pending, when the license object is missing, or when the app-info query errors;
  - shows the deployment ID with a copy action for `unlicensed`;
  - offers dismissal only when dismissible;
  - shows the reason explanation to super-admins only for `invalid`.
- [ ] T030 [US3] Implement `frontend/app/src/entities/license/ui/license-banner.tsx`:
  - use `useGetAppInfo` from `entities/config/ui/queries/get-app-info.query.ts` and `useHasGlobalPermission(SUPER_ADMIN)` from `entities/permission/ui/queries/has-global-permission.query.ts`;
  - use `CopyToClipboardButton` from `shared/components/buttons/copy-to-clipboard-button`.

  Make T029 pass.
- [ ] T031 [US3] Render `LicenseBanner` above `AppHeader` in `frontend/app/src/pages/app-layout.tsx`
- [ ] T032 [US3] In `frontend/app/src/entities/config/ui/queries/get-app-info.query.ts::getAppInfoQueryOptions`, add `refetchInterval` of one hour and `refetchOnWindowFocus: true`; update any test that asserts the query options

**Checkpoint**: All three P1 stories are done. With a test service, the UI behaves as the design's Behaviour table says.

---

## Phase 6: User Story 4 - API-only clients receive the license state (Priority: P2)

**Goal**: The `X-Infrahub-License-Status` header of contracts/response-header.md.

**Independent Test**: With a test service in each state and mode, call `/api/info`, `/graphql`, `/api-static/...` and a frontend route, then inspect the headers (quickstart.md §2).

- [ ] T033 [P] [US4] Write `backend/tests/unit/license/test_middleware.py` on a minimal Starlette app using the middleware:
  - the header is sent only in `ENFORCE` mode and only for states that need attention;
  - eligible paths: `/api`, `/api/x`, `/graphql`, `/graphql/x`;
  - never sent on `/api-static/x`, `/assets/x`, `/docs/x` or `/`;
  - present on 4xx responses;
  - a service that raises produces no header, an ERROR log, and an unaffected response.
- [ ] T034 [US4] Implement the middleware function in `backend/infrahub/license/middleware.py`, reading the service through `get_license_service()` and the notice through `read_license_status` and `notice_for`; make T033 pass
- [ ] T035 [US4] Register the middleware in `backend/infrahub/server.py` alongside the existing `@app.middleware("http")` functions
- [ ] T036 [US4] Write `backend/tests/component/api/test_license_header.py` on the real application with a test service:
  - in enforce mode, the header is on `/api/info` and `/graphql`;
  - it is absent on `/api-static/...` and on a frontend route;
  - it is absent in quiet mode and with the community default.

**Checkpoint**: API-only clients receive the state; the SDK and MCP follow-ups can build on it.

---

## Phase 7: User Story 5 - OpsMill sees each deployment's license in telemetry (Priority: P2)

**Goal**: The telemetry license block of contracts/telemetry-license-block.md.

**Independent Test**: With a test service, run the telemetry collection and read the stored snapshot (quickstart.md §2).

- [ ] T037 [P] [US5] Write tests for `license_block(status) -> TelemetryLicenseData | None` in `backend/tests/unit/license/test_reporting.py`:
  - `None` for `not_required`;
  - state only for `unlicensed` and `invalid`;
  - all fields for states carrying a license;
  - no `customer_name` field ever.
- [ ] T038 [US5] Add `TelemetryLicenseData` and `TelemetryData.license: TelemetryLicenseData | None = None` to `backend/infrahub/telemetry/models.py`
- [ ] T039 [US5] Implement `license_block(status)` in `backend/infrahub/license/reporting.py`; make T037 pass
- [ ] T040 [US5] In `backend/infrahub/telemetry/tasks.py`:
  - add a `license_service: LicenseService` constructor argument to `AnonymousTelemetryGatherer`, wired from `get_license_service()` in `build_anonymous_telemetry_gatherer`;
  - set `license=license_block(read_license_status(self.license_service))` in `gather()`;
  - log a failure and store `None` instead of failing the snapshot.

  Update every existing construction of `AnonymousTelemetryGatherer` in `backend/tests/` for the new argument.
- [ ] T041 [US5] Bump `TELEMETRY_VERSION` in `backend/infrahub/telemetry/constants.py` to a new date-based value; if the resource-allocation telemetry PR (#10003) has merged in the meantime, bump past its value
- [ ] T042 [US5] Extend `backend/tests/component/telemetry/test_tasks.py`:
  - the stored snapshot contains the license block with a test service and `null` with the community default;
  - the block is still stored when `telemetry_optout` is set.

**Checkpoint**: Every deployment's snapshot pairs its deployment ID with its license.

---

## Phase 8: User Story 6 - The upgrade command reminds operators about the license (Priority: P3)

**Goal**: The upgrade output of contracts/upgrade-output.md.

**Independent Test**: With a test service in each state, call the license section helper and check its output and that it returns normally (quickstart.md §3).

- [ ] T043 [P] [US6] Write tests for `license_report_lines(status, notice_mode, enforcing_release)` in `backend/tests/unit/license/test_reporting.py`, matching every example in contracts/upgrade-output.md:
  - empty for `not_required`;
  - quiet mode with and without `enforcing_release`;
  - enforce mode;
  - `valid`, `expiring`, `expired`, `not_yet_valid` and `invalid`;
  - the end date shown as the last covered day in UTC.
- [ ] T044 [US6] Implement `license_report_lines(...)` in `backend/infrahub/license/reporting.py`; make T043 pass
- [ ] T045 [P] [US6] Write `backend/tests/unit/cli/test_upgrade_license.py` for `_print_license_section()` in `backend/infrahub/cli/upgrade.py`:
  - it prints the report lines through the migration console;
  - it prints nothing for `not_required`;
  - a service that raises is logged and skipped;
  - it never calls `typer.confirm` and never raises `typer.Exit`.
- [ ] T046 [US6] Implement `_print_license_section()` in `backend/infrahub/cli/upgrade.py` and call it at the end of `_upgrade_check` (before the final "Run 'infrahub upgrade'" line) and at the end of `_upgrade_execute` (after "Upgrade complete"); make T045 pass

**Checkpoint**: All six stories are done.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [ ] T047 [P] Write `backend/tests/component/api/test_license_key_never_leaks.py`. Set `INFRAHUB_LICENSE_KEY` to a unique sentinel and assert it never appears in:
  - the startup log (`caplog`);
  - the `/api/info` and `/api/config` responses;
  - the stored telemetry snapshot;
  - the upgrade license lines.
- [ ] T048 [P] Regenerate `docs/docs/reference/configuration.mdx` with `uv run invoke docs.generate` and check the only change is the license key setting
- [ ] T049 [P] Write `dev/knowledge/backend/licensing.md`:
  - the service contract and how Enterprise overrides it;
  - the state table and the banner table;
  - the surfaces and their failure containment;
  - where the key is read.

  Follow `dev/guidelines/documentation.md`. Add it to the knowledge index if one lists backend pages.
- [ ] T050 [P] Add the license block to `dev/knowledge/backend/telemetry.md` (fields, no customer name, stored even when sending is turned off)
- [ ] T051 Release gate: confirm with the owner of the cloud telemetry processor that the new `TELEMETRY_VERSION` is accepted before the release containing this feature is cut. Record the answer and date in `dev/specs/005-enterprise-licensing-infp-472/checklists/release-gate.md`
- [ ] T052 Run the checks in quickstart.md §6:
  - `uv run invoke format lint`;
  - `uv run ruff check . --exclude python_sdk`;
  - mypy through lint;
  - in `frontend/app`, `node_modules/.bin/biome check`, `node_modules/.bin/tsc --noEmit` and `node_modules/.bin/vitest run`.

  Fix anything they report.
- [ ] T053 Verify quickstart.md §5 on a local Community stack:
  - no banner and an unchanged About dialog;
  - no header;
  - no license section in `infrahub upgrade --check`;
  - one INFO line when `INFRAHUB_LICENSE_KEY` is set.

  Note the result in the PR description.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none.
- **Foundational (Phase 2)**: after Setup; blocks every user story.
- **US1 (Phase 3)**: after Foundational.
- **US2 (Phase 4)**: after Foundational.
- **US3 (Phase 5)**: after US2's T018–T021, because the banner reads the license object and its generated types.
- **US4 (Phase 6)**: after Foundational; independent of the other stories.
- **US5 (Phase 7)**: after Foundational; independent of the other stories.
- **US6 (Phase 8)**: after Foundational; independent of the other stories.
- **Polish (Phase 9)**: T047 needs US1, US2, US5 and US6; the rest can start once their files exist.

### Within Each Story

Tests first (they fail), then implementation, then wiring into existing modules.

### Shared Files

These tasks touch the same files and must run one after another:

- `backend/infrahub/license/reporting.py`: T014, T039, T044.
- `backend/tests/unit/license/test_reporting.py`: T013, T037, T043.
- `backend/infrahub/server.py`: T015, T035.

---

## Parallel Examples

### Foundational

```text
T003 test_models.py   |  T004 test_status.py  |  T005 test_notices.py  |  T008 test_service.py  |  T011 test_settings.py
```

### After Foundational, by story

```text
US1: T013 → T014 → T015, T016
US2: T017 → T018 → T019, T020 → T021, T022 → T023 → T024
US4: T033 → T034 → T035 → T036
US5: T038 → T037 → T039 → T040 → T041 → T042
US6: T045 → T046 (after T043 → T044)
```

US4, US5 and US6 can be developed in parallel with US2 and US3 by different people.

---

## Implementation Strategy

### MVP First

1. Phases 1 and 2: the contract and its tests.
2. Phase 3 (US1): startup behaviour, which proves the feature changes nothing on Community.
3. Phases 4 and 5 (US2, US3): the state for people.

Stop here and validate with a test service.

### Incremental Delivery

4. US4 (header), US5 (telemetry), US6 (upgrade output), each independently testable.
5. Polish, then open the PR. It can merge to `develop` at any point, but the release containing it waits for T051.

### Notes

- The Enterprise checker, accepted issuers, daily license log and license command are out of scope (opsmill/infrahub-private).
- No changelog fragment: nothing a user can notice changes in behaviour (research R12).
- No end-to-end test in this feature (plan Complexity Tracking); the end-to-end banner tests ship with the first licensing release.
