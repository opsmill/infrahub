# Licensing

> Part of: `dev/knowledge/backend/` | Related: [Telemetry](telemetry.md), [Permissions](permissions.md)

How Infrahub derives a license state, who gets told about it, and where. Infrahub Community needs no
license, and an edition that does replaces one service. Every surface that shows the license reads
that service's interface and nothing else, so the edition decides the state and the shared code
decides how each surface shows it. Read this before touching the license service, a license
surface, or the `INFRAHUB_LICENSE_KEY` setting. Code paths in the prose are relative to
`backend/infrahub/`.

## The service contract

`license/service.py::LicenseService` has three members:

| Member | Returns | Rule |
|--------|---------|------|
| `notice_mode` | `NoticeMode.QUIET` or `NoticeMode.ENFORCE` | A per-release constant; must never raise |
| `enforcing_release` | The release in which every user starts seeing license problems, or `None` | A per-release constant; must never raise |
| `status(now=None)` | `LicenseStatus` at `now`, the current UTC time by default | Documented never to raise; the shared code still contains it when it does |

`LicenseServiceCommunity` answers `QUIET`, `None` and `not_required`.

`license/models.py::LicenseStatus` carries the `state`, a `reason` (only for `invalid`), the verified
`License` (whenever verification produced one, even if it is expired or not yet valid), and
`days_remaining` / `days_since_expiry`. Which of these a state sets is fixed; see [States](#states).

`License` raises `ValueError` when it is constructed with:

- a text field (`license_id`, `customer_name`, `license_type`, `product_tier`, `support_tier`,
  `issuer`) that is not a `str`;
- a date (`starts_at`, `ends_at`, `issued_at`) that is not a timezone-aware `datetime`, such as an
  integer timestamp copied from the token;
- an end not after its start.

An edition's checker must report that error as `invalid` / `malformed`, so a malformed token fails
during verification rather than in a surface such as `/api/info`. `License` stores every date in
UTC. `ends_at` is the first instant the license is no longer valid. A `license_type` that is not
`evaluation` is treated as commercial.

An edition's service verifies the key once, keeps the outcome (`License`, `LicenseFailure` or `None`
for no key), and returns `license/status.py::evaluate(outcome, now)` from `status()`. The state rules
therefore live once, in this repository, and the edition only verifies.

### How an edition replaces it

`workers/dependencies.py::build_license_service` is the override point: by default it returns
`LicenseServiceCommunity`, cached in `_singletons`. An edition overrides it through the
`dependency_provider` in every process that reads the license: the API server, the task worker and
the command line. An edition that registers no service gets the community default and reports
`not_required`.

The overriding builder must cache its instance, as the default one does. `get_license_service()`
resolves the builder on every call, which means on every request, and an edition's service verifies
the key once, when it is constructed. A builder that constructs a new service on each call verifies
the key on every request.

Surfaces never call `build_license_service`. They call `get_license_service()` and then
`read_license_status(service)`; see [Failure containment](#failure-containment) for why that pair
needs no guard of its own.

## States

A status has exactly one state. `evaluate(outcome, now)` derives all of them except `not_required`,
which only the community default returns:

| State | When | Fields set besides `state` |
|-------|------|----------------------------|
| `not_required` | The community default; no license is needed | None |
| `unlicensed` | No key was supplied | None |
| `invalid` | Verification failed; `reason` says why | `reason` |
| `not_yet_valid` | `now` is before `starts_at` | `license`, `days_remaining` |
| `expiring` | `now` is within 30 days (`EXPIRING_WINDOW`) of `ends_at` | `license`, `days_remaining` |
| `valid` | Otherwise, before `ends_at` | `license`, `days_remaining` |
| `expired` | `now` is at or after `ends_at` | `license`, `days_since_expiry` |

Constructing a `LicenseStatus` with any other combination raises `ValueError`, so no surface has to
handle an impossible status, such as an expired status with no license. `evaluate`, the community
default and the stand-in build only these combinations. `status()` must not let that error escape;
if an edition's service lets it escape, `read_license_status` reports it as `invalid` /
`internal_error`.

`days_remaining` rounds up and `days_since_expiry` rounds down, so a license that ended an hour ago
reads "expired today" rather than "expired 1 day ago".

The `invalid` reasons are `malformed`, `bad_signature`, `unknown_key`, `wrong_issuer`,
`wrong_product` and `internal_error`. `internal_error` is the only one that is not about the
customer's license: it means Infrahub itself failed to determine the state.

## Who is told: notices

`license/status.py::notice_for(status, mode)` returns a `Notice`: who sees the banner, whether they
can dismiss it, and whether API responses carry the header.

| State | Quiet mode | Enforce mode |
|-------|------------|--------------|
| `not_required`, `valid` | Nobody | Nobody |
| `expiring` | Super-admins, dismissible | Super-admins, dismissible, header |
| `unlicensed`, `invalid`, `not_yet_valid`, `expired` | Super-admins, dismissible | All users, not dismissible, header |
| `invalid` with `internal_error` | Super-admins, dismissible | Super-admins, dismissible |

The mode comes from the service, not from the state. Quiet mode lets a release ship licensing while
only super-admins learn about a problem and no response carries the header; enforce mode shows
problems to every user. `enforcing_release` names the release that enforces, so quiet-mode messages
can say when the change lands. `internal_error` stays with super-admins in both modes, because a
defect in Infrahub must never put a banner in front of every user.

`shown_to_all_users_when_enforced(status, mode)` is true when the mode is quiet and the enforce-mode
audience for the same status is all users. The server sends it inside the banner object and the
upgrade output uses it, so neither the frontend nor the CLI holds a copy of the notice table.

## Surfaces

| Surface | Code | What it shows |
|---------|------|---------------|
| Startup log | `server.py::app_initialization`, `workers/infrahub_async.py::InfrahubWorkerAsync.setup` → `license/reporting.py::log_license_state` | One line per process, at INFO, WARNING or ERROR by urgency, with the state, reason, license ID, type, dates and day count as structured fields |
| `GET /api/info` | `api/internal.py::get_info` → `LicenseInfoAPI.from_status` | The full license object, including the customer name and the banner decision, to signed-in callers; `license: null` to anonymous ones |
| Banner and About rows | `frontend/app/src/entities/license/` | Reads the `/api/info` license object; see below |
| Response header | `license/middleware.py::LicenseStatusHeaderMiddleware` | `X-Infrahub-License-Status: <state>` on `/api` and `/graphql` paths when the notice asks for it |
| Telemetry | `license/reporting.py::license_block` | The license block of the daily snapshot; see [Telemetry](telemetry.md#license-block) |
| `infrahub upgrade` | `cli/upgrade.py::_print_license_section` → `license/reporting.py::license_report_lines` | A license section after the branch report in `--check`, and after "Upgrade complete" in a real upgrade; nothing for `not_required` |

`GET /api/config` needs no sign-in and carries no license information. `/api/info` answers anonymous
callers when anonymous access is on, so it returns `license: null` to them in every state: whether
and to whom a deployment is licensed is for signed-in users only.

The header is the one deliberate anonymous signal. It is sent whatever the authentication, including
on a 401, but only in enforce mode, and it carries the state alone: never the customer name, the
reason or any other detail. An API client such as the SDK therefore learns the state even from a
rejected request. It is not in the CORS expose list (`middleware.py::CORS_EXPOSE_HEADERS`), so browser code on another
origin cannot read it.

The frontend shows the banner from `banner.audience`: to every signed-in user for `all_users`, and
for `super_admins` only once the super-admin permission check has answered, so a regular user never
sees it flash. A dismissal is kept in `sessionStorage` per license ID, state and failure reason, so a
new license, a new state or a new reason shows the banner again: dismissing an `internal_error`
notice does not hide a later `bad_signature` one. The app-info query refetches hourly and on window
focus, because the state changes with the clock. The About dialog adds license rows for every
signed-in user and none for `not_required`; for `not_yet_valid` it adds a "Starts" row, so a license
that has not started does not look like an active one.

The banner, the About dialog and the upgrade output show an end date as the last day the license
covers, in UTC: the day of the instant just before `ends_at`. The frontend subtracts one millisecond, the smallest unit a browser `Date`
keeps, and the upgrade output subtracts one microsecond, the smallest unit a `License` datetime
keeps. Either way, an end at `00:00:00.500Z` still shows that day.

The upgrade section prints with Rich markup turned off, because the customer name comes from the
license and may contain square brackets.

## Failure containment

A license problem must never fail a startup, a request, a telemetry snapshot or an upgrade. Three
layers contain it.

**Building the service.** `get_license_service()` never raises. When the builder raises, it logs the
traceback once, caches a `LicenseServiceUnavailable` stand-in in `_singletons`, and returns it for
the rest of the process without retrying the builder. The stand-in reports `invalid` with
`internal_error`, in quiet mode and with no enforcing release. Only super-admins see it, because
`notice_for` keeps `internal_error` with super-admins in both modes.

**Reading the status.** `read_license_status(service)` catches any exception from `status()` and
returns `invalid` with `internal_error`. It logs the traceback the first time each exception type is
raised in the process, so a service that keeps failing does not log on every request.

**What each surface still guards.** Those two calls are safe, so a surface adds a guard only for
what they do not cover:

- The header middleware wraps its whole computation, including `notice_mode`. On an error it sends
  the response without the header and logs once per middleware instance.
- `/api/info` wraps the build of its license object, including the `notice_mode` and
  `enforcing_release` reads. On an error it answers with `invalid` / `internal_error` in quiet mode
  with no enforcing release, instead of a 500, and logs the traceback on the first failure in the
  process.
- The upgrade section wraps its whole computation, including `notice_mode`. On an error it logs and
  prints no section, because upgrades run unattended.
- The telemetry block is gathered through `safe_metric`, so a block that cannot be built is stored
  as `null`.
- The startup log adds nothing.

An edition must still keep `notice_mode` and `enforcing_release` constant and non-raising, because
each guard above answers with a fallback instead of the edition's own answer.

## Where the key is read

The key is `config.py::LicenseSettings.key`, set by `INFRAHUB_LICENSE_KEY`. A blank or
whitespace-only value counts as unset (`treat_blank_key_as_unset`), because deployment templates
render an unset variable as an empty string.

Only an edition's service reads the key's value. The shared code checks only whether a key is set:
the startup log on Community says the key is ignored when one is set. No log line, response, header,
telemetry snapshot or upgrade line carries the key. Three tests guard that:

- `backend/tests/component/api/test_license_key_never_leaks.py`: the startup log and the `/api/info`
  and `/api/config` responses;
- `test_stored_snapshot_never_carries_the_license_key` in
  `backend/tests/component/telemetry/test_tasks.py`: the stored telemetry snapshot;
- `test_print_license_section_never_prints_the_license_key` in
  `backend/tests/unit/cli/test_upgrade_license.py`: the upgrade output.

An edition's service verifies the key in each process on its own, so the key must be set on every
API server and task worker, and in the environment where `infrahub upgrade` runs. Both `docker-compose.yml` and
`development/docker-compose.yml` declare `INFRAHUB_LICENSE_KEY` in the shared `x-infrahub-config`
environment, because compose forwards only declared variables.

## Testing

- `backend/tests/adapters/license.py`:
  - `RecordingLicenseService` reports a fixed status and records each `now` it was asked for.
  - `FailingLicenseService` raises on every status read.
  - `FailingNoticeModeLicenseService` raises on `notice_mode`.
  - `build_license(**overrides)` builds a commercial license valid from 2026-01-01 to 2027-01-01 UTC.
  - `build_license_status(state, reason)` builds a complete status in any state through `evaluate`
    or the community default, so a test cannot build a combination the status rejects.
- `use_license_service` in `backend/tests/component/conftest.py` swaps a service in for the rest of
  a component test.
- `unreported_license_failures`, autouse in `backend/tests/unit/conftest.py`, clears the
  once-per-exception record, so log assertions hold in any test order.
- A test that overrides `build_license_service` with a builder that raises must save and restore
  `_singletons`, or the cached stand-in leaks into later tests on the same worker.

## Key locations

| Path | Purpose |
|------|---------|
| `backend/infrahub/license/models.py` | States, reasons, `License`, `LicenseStatus`, `Notice` |
| `backend/infrahub/license/status.py` | State rules (`evaluate`) and notice rules (`notice_for`) |
| `backend/infrahub/license/service.py` | Service contract, community default, stand-in, `read_license_status` |
| `backend/infrahub/license/reporting.py` | Startup log line, telemetry block, upgrade section |
| `backend/infrahub/license/middleware.py` | Response header |
| `backend/infrahub/workers/dependencies.py` | Override point and `get_license_service` |
| `backend/infrahub/api/internal.py` | License object on `/api/info` |
| `frontend/app/src/entities/license/` | Banner, dismissal and About rows |
