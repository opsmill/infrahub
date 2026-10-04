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

An Enterprise service verifies the key once at construction, keeps the outcome, and returns `evaluate(outcome, now or utcnow())` from `status()`. It catches any unexpected error and returns `evaluate(LicenseFailure(INTERNAL_ERROR), now)` after logging it.

## Registration

```python
# backend/infrahub/workers/dependencies.py
def build_license_service() -> LicenseService          # community default, cached in _singletons
@inject
def get_license_service(service = Depends(build_license_service)) -> LicenseService

# opsmill/infrahub-private: infrahub_enterprise/enterprise.py::set_enterprise_dependencies()
# registered only once a production issuer exists
dependency_provider.override(build_license_service, build_ent_license_service)
```

## Requirements on the Enterprise package

- Register the service in every process that reads it: the API server, the task worker and the command line. Today all three call `set_enterprise_dependencies()` (`infrahub_enterprise/server.py`, `workers/infrahub_async.py`, `cli.py`); a new entry point must do the same.
- Return timezone-aware UTC datetimes in `License`; a naive datetime is rejected when the `License` is constructed.
- Use only the reasons in `LicenseFailureReason`. A new reason is added in this repository first.

## Guarantees this repository gives the Enterprise service

- Every surface (info endpoint, About dialog, banner, header, telemetry, upgrade output, startup log) reads `status()`, `notice_mode` and `enforcing_release` only.
- A raised exception from `status()` is still caught at every call site and treated as `invalid` / `internal_error`, so a defect in the Enterprise service cannot fail a request or a startup.
- The license key is never read from these surfaces; only the Enterprise service reads `config.SETTINGS.license.key`.
