# Contract: API Behaviour & SDK Offline Validation

## POST /api/schema/load — submission

- Validates the payload against the **write** model (SDK-hosted).
- **Rejects** any field not at `write` level:
  - A `read`/`internal`/unknown field triggers rejection (via the write model's
    `extra="forbid"`), with a field-level, machine-readable error naming the field.
  - Where feasible, the message distinguishes "field is read-only / not settable"
    from "unknown field" for clarity.
- **Rejects** a `write`-level constrained field set outside its allowed set, naming
  the field and the invalid value.
- On rejection, **nothing is stored** (atomic — existing behaviour).
- The `kind`-from-`namespace`+`name` derivation continues to work under the write model.
- Schema `extensions` payloads are subject to the same rejection rules.

**Verification**:
- POST with `inherited: true` + an unknown field → 4xx naming both.
- POST with a non-existent attribute `kind` → 4xx naming field + value.
- POST of a valid write-shaped schema → loads successfully (idempotent).
- POST that extends an existing node with a non-write field → rejected.

## GET /api/schema — read-back

- Serialises using the **read** model (SDK-hosted).
- Returns `read`-level fields (e.g. `inherited`, `used_by`); never returns
  `internal` fields (parent back-reference) or unclassified fields.
- A schema stored before this change (possibly containing now-`read` fields) reads
  back without error.

**Verification**:
- GET returns `inherited`/`used_by`; response contains no internal-only field.
- Reading a pre-existing stored schema succeeds.

## SDK offline validation

- With only the SDK installed (no server, no backend package), a caller can validate
  a schema payload against the write model and get a pass/fail verdict that names the
  offending field(s) on failure.
- The verdict matches the server's for all field-presence and allowed-value rules.

**Verification**:
- In an SDK-only environment: a valid payload passes; a payload with a non-settable
  field or out-of-range value fails, naming the field.
- Parity test: the same payload yields the same field/enum verdict locally and via
  `POST /api/schema/load`.

## Backward-compatibility notes

- API read-modify-write round-trips break this cycle (read fields rejected on load);
  clients strip non-write fields against the published write schema. The write-shaped
  export that removes this friction is deferred (out of scope).
- Previously loadable write-shaped schemas continue to load unchanged.
