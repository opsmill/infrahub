# Implementation Plan: Enterprise Licensing, Community Contract

**Branch**: `enterprise-licensing-infp-472` | **Date**: 2026-10-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/005-enterprise-licensing-infp-472/spec.md`

## Summary

Add the community side of Infrahub Enterprise licensing: a replaceable `LicenseService` with a community default that always reports "not required", pure functions that derive the license state from a verification outcome and the clock (`evaluate`) and decide the banner audience, dismissibility and header from the state and the release mode (`notice_for`), and every surface that shows the state: a `license` object on `/api/info`, an `X-Infrahub-License-Status` header middleware, a license block in the telemetry snapshot, a license section in `infrahub upgrade`, startup log lines, and a frontend banner plus About dialog rows. The license key setting (`INFRAHUB_LICENSE_KEY`) and the explicit `pyjwt[crypto]` dependency are added. Because the community default reports "not required" and the Enterprise package only registers its service once a production issuer exists, the feature merges with no visible effect. Design decisions D1–D12 of the [design doc](https://app.notion.com/p/3ef228b830258130b788d4e2d9c2d357) are approved input; [research.md](research.md) records how each lands here.

## Technical Context

**Language/Version**: Python 3.14 (backend), TypeScript 5.9 with React 19.2 (frontend)

**Primary Dependencies**: FastAPI 0.131 (routes, middleware), fast_depends (service replacement), pydantic-settings (license setting), PyJWT 2.15 with the crypto extra (declared only; verification code lives in the Enterprise package), Rich console (upgrade output), TanStack Query (app-info refresh)

**Storage**: none. License data is held in memory; the telemetry block rides in the existing snapshot node.

**Testing**: pytest unit (`backend/tests/unit/license/`, `backend/tests/unit/api/`), pytest component (`backend/tests/component/api/test_50_internals.py`, `backend/tests/component/telemetry/test_tasks.py`), Vitest (`frontend/app/src/entities/license/`, `frontend/app/src/entities/config/`). Test services are swapped in with `tests/helpers/dependency_override.py::override_dependency`.

**Target Platform**: Infrahub API servers and task workers (Linux containers), the web UI, the `infrahub` command line

**Project Type**: web service + web frontend + CLI (monorepo: `backend/`, `frontend/app/`)

**Performance Goals**: the per-request cost of the header and of the info endpoint's license object is a clock comparison on in-memory data; no I/O per request.

**Constraints**:

- no visible change on Community or on Enterprise without a registered service (spec SC-001);
- licensing never fails a startup or a request (spec FR-010);
- the key never leaves the process (spec FR-012);
- no database schema change and no GraphQL schema change (design D9 and D10).

**Scale/Scope**: about 10 backend modules touched or added, 1 new frontend entity, 2 frontend files touched, 3 generated files regenerated.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Schema-Driven Integrity**: PASS. No schema change; no node kind added.
- **II. Branch-Safe by Default**: PASS. Licensing reads no graph data and is the same on every branch.
- **III. Type Safety & Explicit Contracts**: PASS. Internal values are frozen dataclasses (`License`, `LicenseStatus`, `Notice`); the API object and the telemetry block are Pydantic models; the REST contract is defined first ([contracts/api-info.md](contracts/api-info.md)) and consumed through regenerated frontend types.
- **IV. Test Discipline**: PASS with one justified deviation. Unit, component and Vitest tests cover every requirement. The end-to-end banner tests move to the first licensing release; see Complexity Tracking.
- **V. Query Performance & Efficiency**: PASS. No queries added.
- **VI. Security & Input Boundaries**:
  - PASS. The key is configuration input read only by the Enterprise service; this repository never logs, returns or reports it (FR-012, enforced by a test).
  - `/api/info` keeps its sign-in requirement; `/api/config` stays license-free.
  - Users see short reason codes; tracebacks stay in logs.
  - The dependency change adds no package (research R11).
- **VII. Simplicity & Maintainability**: PASS. One abstract service with a community default, the same pattern as LDAP and log forwarding. The second implementation lives in the Enterprise package by design. No configurability beyond the one key setting; the release mode is a constant owned by Enterprise.

**Post-design re-check**: PASS. The design artifacts add no schema, query or GraphQL change, and no new package.

## Project Structure

### Documentation (this feature)

```text
specs/005-enterprise-licensing-infp-472/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── license-service.md
│   ├── api-info.md
│   ├── response-header.md
│   ├── telemetry-license-block.md
│   ├── upgrade-output.md
│   └── frontend-banner.md
├── checklists/requirements.md
└── tasks.md            # created by /speckit-tasks
```

### Source Code (repository root)

```text
backend/infrahub/
├── license/                         # new package
│   ├── __init__.py
│   ├── models.py                    # LicenseState, LicenseFailureReason, LicenseType, NoticeMode, NoticeAudience,
│   │                                #   License, LicenseFailure, LicenseStatus, Notice
│   ├── status.py                    # evaluate(), notice_for()
│   ├── service.py                   # LicenseService (abstract), LicenseServiceCommunity
│   ├── middleware.py                # X-Infrahub-License-Status header middleware
│   └── reporting.py                 # log_license_state(), license_report_lines(), license_block()
├── config.py                        # + LicenseSettings, Settings.license
├── workers/dependencies.py          # + build_license_service(), get_license_service()
├── server.py                        # + header middleware registration, startup log
├── workers/infrahub_async.py        # + startup log in InfrahubWorkerAsync.setup
├── api/internal.py                  # + LicenseInfoAPI, BannerAPI, InfoAPI.license
├── telemetry/models.py              # + TelemetryLicenseData, TelemetryData.license
├── telemetry/tasks.py               # + license service in AnonymousTelemetryGatherer
├── telemetry/constants.py           # TELEMETRY_VERSION bump
└── cli/upgrade.py                   # + license section in _upgrade_check, _upgrade_execute

backend/tests/
├── unit/license/                    # test_models, test_status, test_notices, test_service,
│                                    #   test_reporting, test_middleware, test_settings
├── unit/api/test_internal_license.py
├── component/api/test_50_internals.py      # + /api/info license object, /api/config unchanged
└── component/telemetry/test_tasks.py       # + license block in the stored snapshot

frontend/app/src/
├── entities/license/
│   ├── domain/model/license.ts
│   ├── domain/rules/license-banner.ts (+ .test.ts)
│   ├── ui/license-banner.tsx (+ .test.tsx)
│   ├── ui/license-about-rows.tsx (+ .test.tsx)
│   └── ui/hooks/use-license-banner-dismissal.ts (+ .test.ts)
├── entities/config/ui/queries/get-app-info.query.ts   # hourly refetch + refetch on focus
├── entities/config/ui/about-modal.tsx                  # renders the license rows
└── pages/app-layout.tsx                                # renders the banner above AppHeader

pyproject.toml, uv.lock                                 # pyjwt -> pyjwt[crypto]
schema/openapi.json                                     # regenerated
frontend/app/src/shared/api/rest/types.generated.ts     # regenerated
docs/docs/reference/configuration.mdx                   # regenerated
dev/knowledge/backend/licensing.md                      # new
dev/knowledge/backend/telemetry.md                      # license block
```

**Structure Decision**: Web application layout already used by the repository. Backend logic sits in a new `infrahub.license` package next to `infrahub.ldap_auth` and `infrahub.log_forwarding`, which follow the same replaceable-service pattern. Frontend work is one new entity plus small edits to the config entity and the app layout.

## Implementation Notes

- **Order**:
  1. models and pure functions;
  2. service and dependency;
  3. settings;
  4. API, middleware, startup logs;
  5. telemetry;
  6. upgrade output;
  7. frontend;
  8. generated files and docs.

  The pure functions come first because every surface depends on them.
- **Failure containment**: every call site that reads the service wraps the call so a raised exception becomes `invalid` / `internal_error` with an ERROR log (spec FR-010). This is the one place a broad `except Exception` is justified: a top-level boundary that must not take the process down (`dev/guidelines/backend/exceptions.md`, `# noqa: BLE001` with that reason).
- **Days arithmetic**: `days_remaining` rounds up and `days_since_expiry` rounds down, so a license with 11.5 days left reads "12 days" and one expired 3.9 days ago reads "3 days ago".
- **Path eligibility for the header**: `/api`, `/api/…`, `/graphql`, `/graphql/…`; never `/api-static`.
- **Telemetry format**: bump `TELEMETRY_VERSION`; if the resource-allocation telemetry PR (#10003) lands first, bump again on rebase.
- **Release gate**: the format bump changes every deployment's snapshot, Community included. The feature may merge to `develop`, but the release containing it waits until the cloud telemetry processor accepts the new format. A task confirms it before the release branch is cut.
- **Eager construction**: `log_license_state(...)` runs at startup in every API server and task worker and is the first caller of `get_license_service()`, so the Enterprise service verifies its key at startup, never inside a request.
- **Ignored key**: the "license key ignored" INFO line is logged whenever the state is `not_required` and a key is set, so it also covers Enterprise with no service registered. It never includes the value.
- **Tests beyond the unit level**:
  - a component test on the real application checks the header on `/api/info` and `/graphql` in enforce mode, and its absence on `/api-static` and on a frontend route;
  - a sentinel test sets the key to a unique value and asserts it never appears in startup logs, the info endpoint, the stored telemetry snapshot or the upgrade output.
- **Follow-up**: the Enterprise part (opsmill/infrahub-private: checker, accepted issuers, daily log, license command) is scheduled right after this feature, so the contract does not sit unused.
- **Generated files**: regenerate `schema/openapi.json`, the frontend REST types and the configuration reference; CI validates all three.
- **Changelog**: none in this feature, because nothing user-visible changes (research R12). The first licensing release adds it.

## Complexity Tracking

| Deviation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| No end-to-end test in this feature (constitution IV requires them for user-facing features) | The community default never shows anything, and the only way to show a banner end to end is a registered license service, which lives in the Enterprise package. The end-to-end tests ship with the first licensing release, using an internal OpsMill license in Enterprise CI (design follow-up) | An end-to-end test of "no banner on Community" passes today without this feature and verifies nothing. A test-only license service reachable from configuration would let anyone switch on a fake license in production |
| No user documentation in `docs/` beyond the generated configuration reference | Nothing is configurable or visible until the first licensing release; the install page ships then | Writing the install page now would document a setting that has no effect yet |
