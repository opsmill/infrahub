# Contract: License service (for the Enterprise package)

The interface `opsmill/infrahub-private` implements to make licensing visible. Everything else in this feature reads only this interface.

## Interface

```python
# backend/infrahub/license/service.py
class LicenseService(ABC):
    @property
    @abstractmethod
    def notice_mode(self) -> NoticeMode: ...          # QUIET or ENFORCE, a per-release constant

    @property
    @abstractmethod
    def enforcing_release(self) -> str | None: ...    # e.g. "1.13"; None falls back to "a future release"

    @abstractmethod
    def status(self, now: datetime | None = None) -> LicenseStatus: ...
        # Never raises. `now` defaults to the current UTC time; tests pass a fixed instant.


class LicenseServiceCommunity(LicenseService):
    notice_mode -> NoticeMode.QUIET
    enforcing_release -> None
    status() -> LicenseStatus(state=NOT_REQUIRED, reason=None, license=None,
                              days_remaining=None, days_since_expiry=None)
```

## Shared pure functions

```python
# backend/infrahub/license/status.py
def evaluate(outcome: License | LicenseFailure | None, now: datetime) -> LicenseStatus
def notice_for(status: LicenseStatus, mode: NoticeMode) -> Notice
```

An Enterprise service verifies the key once at construction, keeps the outcome, and returns `evaluate(outcome, now or utcnow())` from `status()`. It catches any unexpected error and returns `evaluate(LicenseFailure(INTERNAL_ERROR), now)` after logging it. An error it raises while being built is contained by `get_license_service()` (see the guarantees below).

## Registration

```python
# backend/infrahub/workers/dependencies.py
def build_license_service() -> LicenseService          # community default, cached in _singletons; the override point
def get_license_service() -> LicenseService            # resolves build_license_service through @inject; never raises

# opsmill/infrahub-private: infrahub_enterprise/enterprise.py::set_enterprise_dependencies()
# registered only once a production issuer exists
dependency_provider.override(build_license_service, build_ent_license_service)
```

## Requirements on the Enterprise package

- Register the service in every process that reads it: the API server, the task worker and the command line. Today all three call `set_enterprise_dependencies()` (`infrahub_enterprise/server.py`, `workers/infrahub_async.py`, `cli.py`); a new entry point must do the same.
- Fill `license_id`, `customer_name`, `license_type`, `product_tier`, `support_tier` and `issuer` with `str` values. Any other type raises `ValueError` when the `License` is constructed; report that as `invalid` / `malformed`.
- Fill `starts_at`, `ends_at` and `issued_at` with timezone-aware `datetime` values. Another type, such as an integer timestamp copied from the token, or a naive datetime raises `ValueError` when the `License` is constructed; report that as `invalid` / `malformed`.
- Return statuses built by `evaluate`. A `LicenseStatus` built directly must set exactly the fields its state carries; any other combination raises `ValueError` when it is constructed:
  - `not_required` and `unlicensed`: no other field.
  - `invalid`: `reason`.
  - `not_yet_valid`, `valid` and `expiring`: `license` and `days_remaining`.
  - `expired`: `license` and `days_since_expiry`.
- Use only the reasons in `LicenseFailureReason`. A new reason is added in this repository first.
- Make `notice_mode` and `enforcing_release` per-release constants that never raise.

## Guarantees this repository gives the Enterprise service

- Every surface (info endpoint, About dialog, banner, header, telemetry, upgrade output, startup log) reads `status()`, `notice_mode` and `enforcing_release` only.
- A raised exception from `status()` is still caught at every call site and treated as `invalid` / `internal_error`.
- An exception while building the service is contained too: `get_license_service()` logs it once with the traceback and returns `LicenseServiceUnavailable` (`invalid` / `internal_error`, quiet mode, no enforcing release) for the rest of the process, without retrying the builder. `notice_for` keeps `invalid` / `internal_error` with super-admins, dismissible and without the header in every release mode, because a build failure is a defect in the edition, not the customer's license.
- Together these mean an exception while building the service or from `status()` cannot fail a request or a startup, and no surface wraps those two calls itself. Each surface that reads `notice_mode` or `enforcing_release` guards that read as well, so the constants rule above is a requirement on the Enterprise package, not something a surface relies on.
- The license key's value is never read by these surfaces; only the Enterprise service reads `config.SETTINGS.license.key`, and the startup log only checks whether a key is set. A blank or whitespace-only value counts as no key.
