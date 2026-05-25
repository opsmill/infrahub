# Quickstart: GraphQL Error Catalogue

**Feature**: INFP-468 | **Created**: 2026-05-19 | **Plan**: [plan.md](./plan.md)

How to do the four most common things with the error catalogue, once it ships.

---

## 1. Add a new code to the catalogue (backend contributor)

Three steps:

### a. Declare the payload model

In `backend/infrahub/errors/payloads.py`:

```python
class RepositoryUnreachableData(BaseModel):
    repository_name: str
    last_attempt_at: datetime | None = None
```

### b. Register the code

In `backend/infrahub/errors/catalogue.py`, add to the `CATALOGUE` `OrderedDict`:

```python
CATALOGUE["REPOSITORY_UNREACHABLE"] = CatalogueEntry(
    description="The remote Git repository is unreachable.",
    stability="evolving",      # promote to "stable" after one release of observation
    http_status=503,
    payload_model=RepositoryUnreachableData,
    exception_class=RepositoryUnreachableError,   # or None if raised directly
)
```

The OrderedDict key (`"REPOSITORY_UNREACHABLE"`) is the single source of truth for the code string; the exception class is reachable from the formatter via the `EXCEPTION_TO_CODE` reverse-lookup map, which is rebuilt automatically from the registry.

### c. Regenerate artefacts and commit

```bash
uv run invoke backend.export-error-catalogue       # writes schema/error-catalogue.json
cd frontend/app && pnpm generate:error-bindings    # writes catalogue.generated.ts
uv run invoke docs.generate-error-catalogue        # writes docs page

git add backend/infrahub/errors/ schema/error-catalogue.json \
        frontend/app/src/shared/api/errors/catalogue.generated.ts \
        docs/docs/reference/error-catalogue/index.md
```

CI's sync check (`frontend.check-error-bindings`) verifies the generated artefacts match the catalogue. If you skip step c, CI fails with the regeneration command.

---

## 2. Consume a code from the frontend

The generated bindings expose a discriminated union. Switch on `extensions.code` and the TypeScript compiler narrows `data` for you:

```ts
import type { CatalogueError } from "@/shared/api/errors";

function handle(err: CatalogueError) {
  switch (err.code) {
    case "PERMISSION_DENIED":
      openPermissionDialog({ action: err.data.action ?? "perform this action" });
      break;

    case "ATTRIBUTE_REQUIRED":
    case "ATTRIBUTE_INVALID_TYPE":
    case "ATTRIBUTE_CONSTRAINT_VIOLATION":
      form.setFieldError(err.data.field_name, err.message);
      break;

    case "TOKEN_EXPIRED":
      attemptSilentRefresh();
      break;

    case "UNDEFINED_ERROR":
      // typed-fallback branch — log + show generic toast
      logUncaughtCatalogueError(err);
      break;

    default:
      // exhaustiveness check — adding a new code forces this case to surface
      const _exhaustive: never = err;
      void _exhaustive;
  }
}
```

For form validation (US2), iterate the response's `errors[]`, filter on the three `ATTRIBUTE_*` codes, and feed each into `form.setFieldError(data.field_name, message)`.

---

## 3. Consume a code from the Python SDK

The SDK lives in `python_sdk/` (separate repo). Once its bindings are regenerated against the published `error-catalogue.json`, consumers do:

```python
from infrahub_sdk.errors import NodeNotFoundError, PermissionDeniedError

try:
    await client.delete(kind="BuiltinTag", id=tag_id)
except NodeNotFoundError as exc:
    log.info("tag already gone", kind=exc.node_kind, identifier=exc.identifier)
except PermissionDeniedError:
    raise
```

The SDK exposes one exception class per catalogue code. The exception's typed attributes mirror the `data` payload. No more `if "Unable to find the node" in exc.message:` checks.

---

## 4. Verify the contract end-to-end (developer)

Run the integration test that triggers every catalogued code plus a synthetic uncovered exception:

```bash
uv run pytest backend/tests/functional/graphql/test_error_catalogue.py -v
```

The test asserts:
- Every catalogued code in `schema/error-catalogue.json` is triggerable.
- Each response carries `extensions.code` + `extensions.http_status` + `extensions.data` matching the catalogue schema.
- The synthetic uncovered exception surfaces as `UNDEFINED_ERROR` (per SC-008).
- A multi-field form mutation produces N entries in `errors[]` with the correct sub-codes and `path` values (per FR-016, FR-017).

If a code is missing a triggering scenario, the test fails with a clear message — keeping the SC-001 coverage promise honest.

---

## CI sync check — what failure looks like

```text
$ uv run invoke frontend.check-error-bindings
Comparing schema/error-catalogue.json with backend catalogue...
  diff: schema/error-catalogue.json has 8 codes, backend catalogue has 9
Comparing catalogue.generated.ts with regenerated output...
  diff: REPOSITORY_UNREACHABLE missing from catalogue.generated.ts

ERROR: catalogue bindings are out of date.

Fix:
  uv run invoke backend.export-error-catalogue
  cd frontend/app && pnpm generate:error-bindings
  uv run invoke docs.generate-error-catalogue

Then commit the regenerated files and push again.
```

---

## Telemetry

Every formatted GraphQL error emits a structured log record with the catalogue `code` as a first-class field:

```text
graphql.error  code=PERMISSION_DENIED http_status=403 path=BuiltinTagDelete operation=mutation
```

Dashboards filter on `code=UNDEFINED_ERROR` to surface catalogue gaps (per SC-008 driving the gap rate toward zero).
