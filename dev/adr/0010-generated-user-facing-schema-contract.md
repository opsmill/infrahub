# 10. Generated user-facing schema contract, hosted in the SDK

**Status:** Accepted
**Date:** 2026-07-26
**Author:** @opsmill-team

**Source:** `specs/archive/002-user-facing-schema/research.md` (D2, D3, D5) and the review of the
implementing pull request, which reversed the submission-strictness half of D3.

## Context

The schema Infrahub published to users was a direct projection of its internal model. It advertised
internal-only fields such as `inherited` as settable, and described fields with a closed set of
valid values, such as an attribute's `kind`, as free-form strings. Users — and especially LLM
agents working from the published contract — produced technically-invalid schemas as a result.

Two questions had to be answered together, because the answer to one constrains the other: where
the user-facing contract comes from, and how strict submission should be about fields a user is not
allowed to set. A hand-maintained contract can be as strict as we like but drifts from the model it
describes; a generated one cannot drift, but then strictness becomes a property of the generator
rather than something tuned per endpoint.

The options were judged against four things: the contract a client reads must be complete enough to
author a valid schema without trial-and-error against a running server; a field's visibility should
be defined once, so the contract cannot disagree with the model; a client must be able to validate
a payload offline and get the server's verdict; and schemas already in the wild must keep loading,
including the established workflow of reading a schema back, editing it, and re-submitting it.

## Decision

Every field in the internal schema definitions carries a `visibility` level, nested as
`write ⊆ read ⊆ internal`. The write and read model families are generated from those definitions
and emitted into the Python SDK as committed, shipped artifacts. The server validates submissions
through the SDK-hosted write models rather than through a backend-local copy, so one
implementation produces both the server's verdict and the client's offline verdict.

Submission never applies a field outside the write contract, and reports it according to what it
is. A field the contract knows at that location but the user may not set — a read-only field, the
bookkeeping a schema dumped from the internal models carries, a field belonging to a sibling
variant of a discriminated union — is dropped and reported as a warning. Any other extra field is
rejected, because the only ways to produce one are a typo and a field that no longer exists.
Invalid *settable* values are rejected as before.

The warning/error split is driven by a generated table of the non-settable fields of each write
class, and applied by walking the submitted payload alongside the validated write document: the
validated document resolves which model applies at each location, including which member of a
discriminated union an attribute matched, so the payload is compared against the fields that
location actually accepts.

`invoke backend.validate-generated` regenerates the models and fails on any diff, in the backend
tree and inside the SDK submodule, and CI runs it. A unit test asserts that no field classified
below `write` appears in a write model, and that each family publishes the allowed-value sets of
its constrained fields.

How the visibility axis, the generated families, and the load boundary work is documented in
[Schema Definitions](../knowledge/backend/schema-definitions.md) and
[Code Generation](../knowledge/backend/code-generation.md).

## Consequences

### Positive

- A field's visibility is declared once, and both the write contract and the read shape follow
  from it automatically.
- The offline validator and the server run the same models, so a client can check a payload before
  submitting and get the same answer.
- A payload read from `GET /api/schema` can be edited and re-submitted unchanged, with no stripping
  of derived fields — which is what keeps the round-trip workflow working.
- Closed-value sets travel with the contract as generated enums, so a client or an agent can
  enumerate valid values without consulting a running server.

### Negative

- The server now depends on the client library for its validation boundary, inverting the usual
  direction.
- Changing a schema field spans two repositories: the generated artifact must be regenerated,
  committed in the submodule, and released in step with the server.
- One payload shape that the last released version accepted now fails: attribute `parameters`
  belonging to a different attribute `kind`, which were accepted and then discarded, so the schema
  quietly differed from the one the author wrote. The cost of reporting them is that a repository
  whose committed schema carries one stops importing until it is corrected. A mistyped field name
  was already rejected before this work, since the load endpoint validated through a model with
  `extra="forbid"`; only the wording of that rejection changes.
- Extra fields are reported only once the payload validates against the write models, since the
  validated document is what resolves the contract applying at each location. A payload rejected
  for another reason names its extra fields on the next run rather than in the same response.
- Read-only fields ride the existing `deprecation` warning type rather than a dedicated one, so
  that an SDK older than this change can still parse a load response. A dedicated type has to wait
  until an SDK tolerant of unknown warning types is the supported floor.

### Neutral

- The generated artifacts are committed rather than built on install, and CI validates them for
  drift in both repositories.
- Retiring the SDK's remaining hand-written schema models is tracked as a follow-up in
  `specs/archive/002-user-facing-schema/opsmill-implement-followups.md`. Until it lands, the SDK
  carries a hand-written family alongside the generated one, so the single-definition property
  holds for the write boundary but not yet for every SDK consumer.

## Alternatives Considered

### Hand-maintain a second set of user-facing models

Rejected: this is the drift the decision exists to remove. The SDK already carried a hand-written
write/read split that had fallen out of step with the backend model, which is what produced the
misleading published contract in the first place.

### Generate the contracts twice, once per repository

Rejected: it doubles the drift-review burden, and parity between the two copies would still have to
be proven by a test rather than following from construction.

### Reject non-write fields on submission

The original design — implemented, then reversed in review. Rejecting them broke the read → edit →
load path for every client that round-trips a schema, and what it bought was a clearer error for a
field the user had not intended to set. An `ignore_extras` opt-in flag was also considered and
rejected: tolerance as the default achieves the same result without a second code path. Splitting
the two cases, as the decision above now does, keeps the round-trip working *and* restores the
error for the fields where an error is the only useful answer.

### Generate a third model family to classify extra fields

A `tolerant` variant carrying the read-level field set with `extra="allow"`, validated alongside
the write models, would have let pydantic classify extra fields with no traversal code. Rejected as
disproportionate: it is a second full family of generated models, and a validated write document
plus a generated table of non-settable field names answers the same question. It also risked
extras leaking into the document the server loads.

### Classify extra fields with a `mode="before"` validator on the write models

A hook on every generated write class, appending findings to the pydantic validation context, needs
no traversal code and fires even when validation fails elsewhere. Rejected because a before-validator
does not know where it sits in the document, so a finding could name neither the path nor the owning
kind — and reconstructing the parent chain would mean stateful validators pushing and popping
context.

### Filter non-write fields with a hand-written projection step

Rejected once the generated write models were configured to ignore unknown input, which drops
non-write fields at every nesting level with no bespoke code. The projection helper written for
this was removed after it was shown to produce identical results to the models alone.
