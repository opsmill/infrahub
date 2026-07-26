---
status: accepted
date: 2026-07-26
decision-makers: [@opsmill-team]
---

# 10. Generate the user-facing schema contract and host it in the SDK

**Source:** `specs/archive/002-user-facing-schema/research.md` (D2, D3, D5) and the review of the
implementing pull request, which reversed the submission-strictness half of D3.

## Context and problem statement

The schema Infrahub published to users was a direct projection of its internal model. It
advertised internal-only fields such as `inherited` as settable, and described fields with a
closed set of valid values, such as an attribute's `kind`, as free-form strings. Users — and
especially LLM agents working from the published contract — produced technically-invalid schemas
as a result.

Two questions had to be answered together, because the answer to one constrains the other: where
the user-facing contract comes from, and how strict submission should be about fields a user is
not allowed to set. A hand-maintained contract can be as strict as we like but drifts from the
model it describes; a generated one cannot drift, but then strictness is a property of the
generator rather than something tuned per endpoint.

## Decision drivers

- The contract a client reads must be complete enough to author a valid schema without
  trial-and-error against a running server.
- One definition of a field's visibility, so the contract cannot disagree with the model.
- A client must be able to validate a payload offline and get the server's verdict.
- Schemas already in the wild must keep loading; reading a schema back, editing it, and
  re-submitting it is an established workflow.

## Considered options

- Generate the write and read contracts from the internal definitions, into the SDK
- Hand-maintain a second set of user-facing models alongside the internal ones
- Generate the contracts twice, once per repository
- Reject, rather than ignore, fields outside the write contract

## Decision outcome

Chosen option: **generate the write and read contracts from the internal definitions and emit
them into the Python SDK**, because it is the only option where the contract cannot drift from
the model and where one implementation produces both the server's verdict and the client's
offline verdict.

We will classify every field in the internal schema definitions with a `visibility` level, nested
as `write ⊆ read ⊆ internal`, and generate the write and read model families from those
definitions. The generated models are committed, shipped artifacts inside the published SDK
package, and the server validates submissions through them rather than through a backend-local
copy.

Submission **ignores** fields outside the write contract rather than rejecting them: read-only,
internal, and unknown fields are dropped, and only invalid *settable* values are rejected. This
half of the decision reverses the original design, which rejected them.

### Consequences

- Good, because a field's visibility is declared once and both the write contract and the read
  shape follow from it automatically.
- Good, because the offline validator and the server run the same models, so a client can check a
  payload before submitting and get the same answer.
- Good, because a payload read from `GET /api/schema` can be edited and re-submitted unchanged —
  no stripping of derived fields, which is what makes the round-trip workflow survive.
- Bad, because the server now depends on the client library for its validation boundary, inverting
  the usual direction.
- Bad, because changing a schema field spans two repositories: the generated artifact must be
  regenerated, committed in the submodule, and released in step with the server.
- Bad, because a mistyped field name is silently dropped instead of reported, so a typo in a
  schema file fails quietly rather than loudly.
- Neutral, because the generated artifacts are committed rather than built on install, and CI
  validates them for drift in both repositories.

### Confirmation

`invoke backend.validate-generated` regenerates the models and fails on any diff, in the backend
tree and inside the SDK submodule; CI runs it. A unit test asserts that no field classified below
`write` appears in a write model, and that each family publishes its constrained fields'
allowed-value sets.

## More information

How the visibility axis, the generated families, and the load boundary work is documented in
[Schema Definitions](../knowledge/backend/schema-definitions.md) and
[Code Generation](../knowledge/backend/code-generation.md).

Retiring the SDK's remaining hand-written schema models is tracked as a follow-up in
`specs/archive/002-user-facing-schema/opsmill-implement-followups.md`; until it lands, the SDK
still carries a hand-written family alongside the generated one, so the "one definition" property
above holds for the write boundary but not yet for every SDK consumer.

Revisit the tolerance half if silently-dropped typos prove to be a common source of confusion —
reporting unrecognised fields as warnings, without rejecting them, would preserve the round-trip
while restoring the feedback.
