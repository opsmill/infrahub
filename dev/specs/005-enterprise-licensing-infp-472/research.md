# Research: Enterprise Licensing, Community Contract

Each entry records a decision this plan needed, the reason, and what was rejected. Decisions D1–D12 of the [design doc](https://app.notion.com/p/3ef228b830258130b788d4e2d9c2d357) are approved input and are not repeated here; this file only resolves how they land in this repository.

## R1. How the license service is replaced by Enterprise

- **Decision**: An abstract `LicenseService` in `backend/infrahub/license/service.py`, a `LicenseServiceCommunity` default, and a `build_license_service` / `get_license_service` pair in `backend/infrahub/workers/dependencies.py`, cached in `_singletons` exactly like `build_ldap_auth_service` / `get_ldap_auth_service`. Enterprise replaces it with `dependency_provider.override(build_license_service, …)` in its `set_enterprise_dependencies()`. Unlike its LDAP counterpart, `get_license_service()` never raises: a builder that raises is logged once and replaced for the rest of the process by `LicenseServiceUnavailable`, which reports `invalid` / `internal_error` in quiet mode, because a build failure is a defect in the edition rather than the customer's license.
- **Rationale**: Same mechanism as LDAP and log forwarding (`infrahub.ldap_auth.service::LDAPAuthService`, `LDAPAuthServiceCommunity`). Tests already have `tests/helpers/dependency_override.py::override_dependency` to swap it.
- **Alternatives considered**: a module-level registry or entry-point plugin (new pattern, rejected by constitution VII "follow established project patterns"); calling the Enterprise checker from community code behind `installation_type` (puts vendor logic in the public repo, rejected by design D7).

## R2. Where the state is decided

- **Decision**: Two pure functions in `backend/infrahub/license/status.py`: `evaluate(check, now) -> LicenseStatus` decides the state, `notice_for(status, mode) -> Notice` decides the banner audience, dismissibility and header. `invalid` with `internal_error` stays with super-admins, dismissible and without the header in both modes, because it is a defect in Infrahub rather than in the customer's license. The service holds the verification outcome (a `License`, a `LicenseFailure` with a reason, or nothing) and calls `evaluate` with the current time on every `status()` call.
- **Rationale**: Pure functions are unit-testable at every time boundary without a JWT or a server (spec SC-002, SC-003). Enterprise reuses them, so the state rules exist once.
- **Alternatives considered**: each service computing its own state (the rules would be duplicated in the private repo); computing the state once at startup (a license that ends while running would not expire, spec FR-003).

## R3. Release mode and the enforcing release name

- **Decision**: The service exposes `notice_mode` (`NoticeMode.QUIET` for the first licensing release, `NoticeMode.ENFORCE` for the second) and `enforcing_release: str | None` (the version in which every user starts seeing problem banners, used in the quiet-mode wording). The community default returns `QUIET` and `None`.
- **Rationale**: Design D12 makes the mode a per-release constant owned by Enterprise. The quiet-mode banner and upgrade message must name the enforcing release, which is an open question (Q1 in the design), so the name travels with the mode instead of being hardcoded here. When it is `None`, the wording falls back to "in a future release".
- **Alternatives considered**: a setting (customers would set it to quiet, rejected by design D12); a constant in this repo (the release that changes it is an Enterprise release).

## R4. The license key setting

- **Decision**: A `LicenseSettings` group in `backend/infrahub/config.py` with `env_prefix="INFRAHUB_LICENSE_"` and one field `key: str | None = None`, registered on `Settings` as `license`. A blank or whitespace-only value is read as `None`, because deployment templates render an unset variable as an empty string. It is not added to `enterprise_features`, so `server.py::_validate_feature_selection` does not refuse it on Community. At startup, a process whose state is `not_required` (Community, or Enterprise with no license service registered) and that has a key set logs once at INFO that it is ignored, without the value.
- **Rationale**: Every Infrahub server setting is a settings group with an env prefix; design D4 puts the license in `INFRAHUB_LICENSE_KEY`. Refusing to start on Community would break production for a harmless value (design D6).
- **Alternatives considered**: `SecretStr` for the key. The token is not a credential and no other setting uses `SecretStr`; leakage is prevented by never logging it, enforced by a test (spec FR-012, SC-005). Reading `os.environ` directly in the Enterprise package (Community could not log the ignored value, and the configuration reference would not list the setting).
- **Consequence**: the generated `docs/docs/reference/configuration.mdx` gains the setting, described as "License for Infrahub Enterprise, as a signed token. Infrahub Community ignores it." Regenerated with `uv run invoke docs.generate`.

## R5. The response header

- **Decision**: A small pure-ASGI middleware in `backend/infrahub/license/middleware.py`, built with the license service provider and registered in `backend/infrahub/server.py` just inside the admission gate (`dev/guidelines/backend/asgi-middleware.md` keeps `@app.middleware("http")` off the per-request path, and the license package imports nothing from the workers layer). It adds `X-Infrahub-License-Status: <state>` only when the path is `/api`, starts with `/api/`, is `/graphql` or starts with `/graphql/`, and `notice_for(...)` says to send it. Any error while computing the notice is logged once and the response goes out without the header.
- **Rationale**: `/api-static` must not match, so the check is on `/api` plus a slash, not on the `/api` prefix alone. The status computation is a clock comparison on cached data, so it costs nothing per request. The header is sent whatever the authentication: it is the signal for API-only clients, carries the state only, and is the one deliberate place where a caller who is not signed in sees the state, since `/api/info` gives such callers `license: null` (R6).
- **Alternatives considered**: a FastAPI dependency on every router (misses GraphQL and error responses); a GraphQL `extensions` field (rejected by design D10).

## R6. The info endpoint

- **Decision**: `backend/infrahub/api/internal.py::InfoAPI` gains `license: LicenseInfoAPI | None`. For a signed-in session, `get_info` builds it from `read_license_status(get_license_service())` and `notice_for(status, service.notice_mode)`; for an anonymous session it is `null`. `ConfigAPI` is unchanged. `schema/openapi.json` and `frontend/app/src/shared/api/rest/types.generated.ts` are regenerated.
- **Rationale**: `/api/info` goes through `get_current_user`, which lets anonymous `GET` requests through when `main.allow_anonymous_access` is on, and it is on by default. Who holds the license and why it failed are for signed-in users only, so anonymous callers get `license: null`. In the enforcing release, the response header (R5) is the one deliberate place where any caller, signed in or not, sees the state; it is never sent in quiet mode and never carries the reason. `/api/config` stays license-free (design D9). The banner decision is resolved on the server ("backend is authoritative", `dev/knowledge/frontend/entities-structure.md`), and the UI only applies the audience to the signed-in user.
- **Alternatives considered**: resolving visibility per user on the server (would duplicate the frontend's existing super-admin check and make the response user-specific for no gain); a new `/api/license` endpoint (one more request on every page load).

## R7. Telemetry

- **Decision**: `backend/infrahub/telemetry/models.py` gains `TelemetryLicenseData` and `TelemetryData.license: TelemetryLicenseData | None = None`. `AnonymousTelemetryGatherer` receives the license service as a constructor argument (wired in `build_anonymous_telemetry_gatherer`) and fills the block through a pure `license_block(status)` function. `TELEMETRY_VERSION` in `backend/infrahub/telemetry/constants.py` is bumped.
- **Rationale**: Constructor injection matches the gatherer's existing design (`account_gatherer`, `activity_gatherer`), and the snapshot is stored even when sending is turned off (`telemetry/tasks.py::send_telemetry_push`), so the export carries it.
- **Alternatives considered**: reading the service inside `gather()` through `get_license_service()` (hides the dependency from tests).
- **Coordination**: the resource-allocation telemetry PR (#10003) also bumps the format. Whichever lands second bumps it again; the cloud processor is told before release.

## R8. The upgrade command

- **Decision**: A pure `license_report_lines(status, notice_mode, enforcing_release) -> list[str]` in `backend/infrahub/license/reporting.py`, printed at the end of `cli/upgrade.py::_upgrade_check` and `_upgrade_execute` through the existing migration console. Empty list when no license is required. Errors while building the report are caught at that call site, logged, and never change the exit code.
- **Rationale**: Text built by a pure function is testable without running migrations. The upgrade command runs in the server container through the Enterprise command line (`infrahub_enterprise/cli.py` calls `set_enterprise_dependencies()` first), so it sees the Enterprise service when one is registered.
- **Alternatives considered**: refusing the upgrade (rejected by design D5).

## R9. Startup logs

- **Decision**: `backend/infrahub/license/reporting.py::log_license_state(service, key_is_set)` is called once in `server.py::app_initialization` after `validate_graph_version`, and once in `workers/infrahub_async.py::InfrahubWorkerAsync.setup` after `validate_graph_version`. It logs INFO for valid or not required, WARNING for unlicensed, not yet valid, expiring and expired, ERROR for invalid. When the state is not required and a key is set, the one line says the key is ignored, in either edition. It never includes the key. A service that raises, while being built or while being read, yields two ERROR entries: the traceback from the boundary that caught it, then the invalid state line.
- **Rationale**: Spec FR-011 and EC-001 rely on per-process startup logs to diagnose a key missing on the task workers. The daily repeat belongs to the Enterprise workflow (design D10, out of scope).

## R10. Frontend

- **Decision**: A new `frontend/app/src/entities/license/` entity:
  - `domain/model/license.ts`: the license types, re-exported from the generated REST types;
  - `domain/rules/license-banner.ts`: pure functions for "should this user see the banner" and the banner text per state, with the release note when the server's `banner.shown_to_all_users_when_enforced` is true;
  - `ui/license-banner.tsx`: the banner, placed in `pages/app-layout.tsx` above `AppHeader`;
  - `ui/hooks/use-license-banner-dismissal.ts`: dismissal in `sessionStorage`, keyed by license ID, state and failure reason;
  - `ui/license-about-rows.tsx`: rows rendered by `entities/config/ui/about-modal.tsx`.

  The app-info query in `entities/config/ui/queries/get-app-info.query.ts` gains `refetchInterval` of one hour and `refetchOnWindowFocus: "always"`. Super-admin comes from `entities/permission/ui/queries/has-global-permission.query.ts::useHasGlobalPermission(SUPER_ADMIN)`.
- **Rationale**: Follows the three-layer entity structure and its import rules: `domain/` never touches browser storage, `ui/` may import other entities' `ui/` and `domain/`, never their `api/`. The license object arrives with app info, which the config entity already fetches, so no new request.
- **Alternatives considered**: putting the banner in `shared/` (shared must not import entities); a new fetch for license data (extra request, duplicated cache).

## R11. The signature backend dependency

- **Decision**: `pyproject.toml` changes `pyjwt==2.15.0` to `pyjwt[crypto]==2.15.0`, and `uv.lock` is refreshed. `cryptography` 50.0.0 is already locked through `authlib`, `jwcrypto` and `prefect`, so no new package enters the tree.
- **Rationale**: Design D6 and the AGENTS.md "new dependencies" gate, already approved in the design; the Enterprise package resolves through this lock file.

## R12. Tests, end-to-end tests and the changelog

- **Decision**:
  - unit tests for `evaluate`, `notice_for`, the report lines, the telemetry block, the settings, the middleware (a minimal Starlette app) and the community service;
  - component tests for `/api/info` (in `backend/tests/component/api/test_50_internals.py`) and the stored telemetry snapshot (in `backend/tests/component/telemetry/`), both with a test service swapped in through `override_dependency`;
  - Vitest for the banner rules, the dismissal hook and the About rows.

  No end-to-end test and no changelog fragment in this feature.
- **Rationale**: Nothing a user can see changes in this feature (spec SC-001). An end-to-end test needs a registered license service, which only the Enterprise package provides, so the end-to-end banner tests move to the first licensing release, where the Enterprise CI licence exists (design D12 follow-up). The fragment ships with that release, when the behaviour becomes visible.
- **Alternatives considered**: an end-to-end test of "no banner on Community", which passes today without this feature and proves nothing.

## R13. Developer documentation

- **Decision**: A new `dev/knowledge/backend/licensing.md` describing the service contract, the states, the banner rules and the Enterprise override, and a short addition to `dev/knowledge/backend/telemetry.md` for the license block.
- **Rationale**: Constitution "Documentation Requirements": backend architecture changes update `dev/knowledge/backend/`. User documentation in `docs/` ships with the first licensing release, when there is something to configure.
