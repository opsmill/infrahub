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

Submission **ignores** fields outside the write contract rather than rejecting them: read-only,
internal, and unknown fields are dropped, and only invalid *settable* values are rejected. This
half of the decision reverses the original design, which rejected them.

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
- A mistyped field name is silently dropped instead of reported, so a typo in a schema file fails
  quietly rather than loudly. Revisit this if it proves to be a common source of confusion —
  reporting unrecognised fields as warnings would preserve the round-trip while restoring the
  feedback.

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
rejected: tolerance as the default achieves the same result without a second code path.

### Filter non-write fields with a hand-written projection step

Rejected once the generated write models were configured to ignore unknown input, which drops
non-write fields at every nesting level with no bespoke code. The projection helper written for
this was removed after it was shown to produce identical results to the models alone.
