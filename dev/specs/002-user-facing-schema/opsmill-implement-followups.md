# Follow-ups: user-facing schema separation

## Follow-up: publish the write contract in the REST OpenAPI

### Status

Deferred (documented, not implemented). Attempting it inside the review-fix pass
was judged too risky for the value: it changes a broadly-consumed published
artifact (`schema/openapi.json`) and risks the downstream internal parsing path.

### Problem

The load endpoint (`POST /api/schema/load`) enforces the user-facing **write**
contract at runtime via a Pydantic `model_validator(mode="before")` on
`SchemaLoadAPI` (`backend/infrahub/api/schema.py`), delegating to the SDK's
`validate_schema`. That gate rejects non-settable fields and out-of-enum values
with field-level messages.

However, the gate is invisible to FastAPI's OpenAPI generation. The request body
schema is still generated from the internal models
(`SchemaLoadAPI` → `SchemaRoot` → `NodeSchema` / `AttributeSchema-Input` /
`RelationshipSchema-Input`). As a result the published contract in
`schema/openapi.json`:

- shows `kind` as a bare `{"type": "string"}` with no `enum` (allowed values not
  enumerated), and
- includes non-settable fields (`id`, `state`, `inherited`, and other
  read-level/internal fields) in the request body.

Regenerating the OpenAPI schema alone (`uv run invoke schema.generate-jsonschema`)
does not fix this, because the generator reads the declared request model, not the
before-validator.

### Why it was not fixed here

Two viable approaches, both carrying more risk than a review-fix pass should take:

1. **Declare the endpoint request model as the generated write models and convert
   to the internal models downstream.** This is the clean, single-source-of-truth
   fix: FastAPI would then generate the correct published contract for free. But it
   changes the runtime request type and forces a conversion step into the internal
   `SchemaRoot`/`NodeSchema` models that the rest of the load pipeline consumes.
   A full swap of the request model was deliberately avoided during implementation
   as risky, precisely because downstream code parses into the internal models.

2. **Inject a custom OpenAPI body schema via the route's `openapi_extra`.** Keeps
   runtime parsing untouched and overrides only the published requestBody schema
   with one derived from the SDK write models. Lower runtime risk than (1), but it
   introduces a second source of truth for the contract that must be kept in sync
   with the write models, and it still rewrites a broadly-consumed published
   artifact. Needs its own tests asserting the published `kind` enum and the
   absence of non-settable fields.

### Recommended approach

Prefer (1) if the downstream conversion can be introduced cleanly: declare the
`/api/schema/load` request as the generated write models and convert to the
internal `SchemaRoot` models in one place at the top of the handler. This removes
the dual-model drift risk and makes the runtime gate and the published contract
share one source of truth. Fall back to (2) (`openapi_extra`) if the conversion
proves too invasive.

### Acceptance check

After the fix, regenerating with `uv run invoke schema.generate-jsonschema` must
show, for the load request body:

- `kind` on the attribute/relationship schema published with its `enum` of allowed
  values, and
- no non-settable fields (`id`, `state`, `inherited`, and other read-level/internal
  fields) in the request body,

with all existing backend and SDK tests still green and `uv run invoke docs.validate`
clean.
