# Follow-ups: user-facing schema separation

## Follow-up: retire the SDK's hand-written schema models (FR-008)

### Status

Deferred (documented, not implemented). The generated write models are the single
source of truth for the load boundary, but the SDK's hand-written read models and
their in-SDK consumers still exist, so the "no second parallel definition"
requirement is not met yet.

### Problem

PRD FR-008 (spec FR-009) requires the SDK's hand-written schema models to be
replaced by the generated write/read models. They are not: the generated read
models lack `hash` and differ from the hand-written ones in field set and typing
(dedicated enum classes vs. `Literal`, extra fields, required `min_count`/
`max_count`), so repointing the in-SDK consumers naively changes serialization
shape and breaks the export path, the protocols generator, and the node
consumers.

### Recommended approach

Keep the generated models as the data models and layer the behaviour
(the `hash` property and the other methods on the hand-written models) on top as
subclasses or mixins, reconciling the typing deltas first, then repoint the
in-SDK consumers in one chunk with the SDK suite green. Details and the per-task
history are in `opsmill-implement-report.md`.

### Acceptance check

No hand-written schema model definitions remain in the SDK, every in-SDK consumer
imports the generated models, and both the SDK and backend suites stay green.

## Follow-up: extract schema code generation off the attribute definition model

### Status

Deferred (documented, not implemented). Raised in review: the code-generation
concerns should live in a dedicated component rather than on the schema
attribute definition model, which already carries enough responsibility.

### Problem

The attribute definition model in
`backend/infrahub/core/schema/definitions/internal.py` exposes code-generation
properties (`type_annotation`, `object_kind`, `default_definition`, `pattern`,
`min`, `max`, and the `external_*` variants added in this cycle) alongside its
job of describing a schema field. Two generators consume them: the internal
model generator and the SDK write/read model generator.

### Why it was not done here

The majority of those properties (`type_annotation`, `object_kind`,
`default_definition`, `pattern`, `min`, `max`) predate this cycle and are
consumed directly by the jinja templates as attribute properties. Extracting
them therefore reshapes the template contract for both the internal and the SDK
generator — a refactor with its own blast radius, unrelated to the user-facing
schema separation. Moving only the newly added `external_*` half would leave the
same logic split across two homes, which is worse than the current state.

### Recommended approach

Introduce a dedicated generator component that takes an attribute definition and
answers the rendering questions, then pass that component (rather than the raw
definition) to the templates, migrating the pre-existing and the `external_*`
properties in the same change so the logic ends up in one place. The
`SdkSchemaGenerator` class in `tasks/backend.py` is a natural home for the
SDK-side part of it.

### Acceptance check

The attribute definition model carries no rendering logic, both generators render
through the new component, and regeneration (`uv run invoke backend.generate`) is
byte-identical to before the refactor.

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
