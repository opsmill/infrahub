# Data Model: Enterprise Licensing, Community Contract

Nothing in this feature is stored in the database. All entities are in-memory values; internal ones are frozen dataclasses, API and telemetry ones are Pydantic models (constitution III).

## Enumerations

| Name | Values | Meaning |
| --- | --- | --- |
| `LicenseState` | `not_required`, `unlicensed`, `invalid`, `not_yet_valid`, `expired`, `expiring`, `valid` | The single state derived for a moment in time |
| `LicenseFailureReason` | `malformed`, `bad_signature`, `unknown_key`, `wrong_issuer`, `wrong_product`, `internal_error` | Why a supplied license is invalid |
| `LicenseType` | `evaluation`, `commercial` | Known types. Unknown values are kept as received and behave like `commercial` |
| `NoticeMode` | `quiet`, `enforce` | `quiet`: first licensing release, banners for super-admins only, no header. `enforce`: second licensing release |
| `NoticeAudience` | `none`, `super_admins`, `all_users` | Who sees the banner |

## License (internal, frozen dataclass)

The verified content of a license, produced by the Enterprise checker.

| Field | Type | Rule |
| --- | --- | --- |
| `license_id` | `str` | Stable across reissues |
| `customer_name` | `str` | Shown in the About dialog; never sent in telemetry |
| `license_type` | `str` | `evaluation` or `commercial`; any other value is kept and treated as `commercial` |
| `product_tier` | `str` | Free string, shown as received |
| `support_tier` | `str` | Free string, shown as received |
| `starts_at` | `datetime` (UTC, aware) | First instant the license is valid |
| `ends_at` | `datetime` (UTC, aware) | First instant the license is no longer valid; `ends_at > starts_at` |
| `issued_at` | `datetime` (UTC, aware) | When the token was signed |
| `issuer` | `str` | Which accepted issuer verified it |

Derived: `is_evaluation` is true only when `license_type == "evaluation"`.

Validation at construction: `starts_at`, `ends_at` and `issued_at` must be timezone-aware; they are normalized to UTC. A naive datetime raises `ValueError`, so a vendor translation bug fails in the Enterprise checker, where it becomes `invalid` / `malformed`, instead of in a comparison.

## LicenseFailure (internal, frozen dataclass)

| Field | Type |
| --- | --- |
| `reason` | `LicenseFailureReason` |

## Verification outcome

What a license service passes to `evaluate`: a `License`, a `LicenseFailure`, or `None` when no license was supplied.

## LicenseStatus (internal, frozen dataclass)

Returned by `evaluate(outcome, now)`, or built directly as `not_required` by the community service.

| Field | Type | Rule |
| --- | --- | --- |
| `state` | `LicenseState` | See the transitions below |
| `reason` | `LicenseFailureReason \| None` | Set only when `state == invalid` |
| `license` | `License \| None` | Set when verification produced a license (states `not_yet_valid`, `expired`, `expiring`, `valid`) |
| `days_remaining` | `int \| None` | When `now < ends_at`: whole days until `ends_at`, rounded up. Otherwise `None` |
| `days_since_expiry` | `int \| None` | When `now >= ends_at`: whole days since `ends_at`, rounded down. Otherwise `None` |

### State derivation in `evaluate` (first match wins)

`not_required` never comes out of `evaluate`: only a service for an edition without licensing returns it.

| # | Condition | State |
| --- | --- | --- |
| 1 | outcome is `None` | `unlicensed` |
| 2 | outcome is a `LicenseFailure` | `invalid` |
| 3 | `now < starts_at` | `not_yet_valid` |
| 4 | `now >= ends_at` | `expired` |
| 5 | `now >= ends_at - 30 days` | `expiring` |
| 6 | otherwise | `valid` |

The 30-day window applies to every license type (design D8). `now` is the server's current UTC time on every read (spec FR-003).

## Notice (internal, frozen dataclass)

Returned by `notice_for(status, mode)`.

| Field | Type |
| --- | --- |
| `audience` | `NoticeAudience` |
| `dismissible` | `bool` |
| `send_header` | `bool` |

| State | `quiet` | `enforce` |
| --- | --- | --- |
| `not_required`, `valid` | none, -, no header | none, -, no header |
| `expiring` | super_admins, dismissible, no header | super_admins, dismissible, header |
| `unlicensed`, `invalid`, `not_yet_valid`, `expired` | super_admins, dismissible, no header | all_users, not dismissible, header |

## LicenseService (internal, abstract)

| Member | Type | Community default |
| --- | --- | --- |
| `status(now: datetime \| None = None)` | `LicenseStatus` | `not_required` |
| `notice_mode` | `NoticeMode` | `quiet` |
| `enforcing_release` | `str \| None` | `None` |

`status()` never raises. An Enterprise implementation that hits an unexpected error returns `invalid` with `internal_error` and logs it.

When building the service raises, `get_license_service()` logs it once and returns `LicenseServiceUnavailable` for the rest of the process: `status()` is `invalid` with `internal_error`, `notice_mode` is `quiet`, `enforcing_release` is `None`.

## LicenseSettings (configuration)

| Field | Environment variable | Type | Default |
| --- | --- | --- | --- |
| `key` | `INFRAHUB_LICENSE_KEY` | `str \| None` | `None` |

A blank or whitespace-only value is read as `None`, because deployment templates render an unset variable as an empty string.

## LicenseInfoAPI (REST, Pydantic)

Field of `InfoAPI` returned by `GET /api/info`. See [contracts/api-info.md](contracts/api-info.md).

`InfoAPI.license` is `null` for an anonymous caller, whatever the state. When present, the object always carries its details.

## TelemetryLicenseData (telemetry, Pydantic)

Field `license` of `TelemetryData`, `None` when the state is `not_required`. See [contracts/telemetry-license-block.md](contracts/telemetry-license-block.md).

| Field | Type |
| --- | --- |
| `state` | `str` |
| `license_id` | `str \| None` |
| `license_type` | `str \| None` |
| `product_tier` | `str \| None` |
| `support_tier` | `str \| None` |
| `starts_at` | `datetime \| None` |
| `ends_at` | `datetime \| None` |
| `issuer` | `str \| None` |
