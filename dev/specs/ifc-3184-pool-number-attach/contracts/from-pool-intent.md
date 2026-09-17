# Contract: `from_pool` intent resolution

**Status**: published *behaviour*, unpublished *shape*. No GraphQL input field is added, removed or
retyped. What changes is what the existing inputs mean.

**Owner**: `backend/infrahub/pools/intent.py::FromPoolIntentResolver` (new, pure — no database, no
node access).

---

## Why this is a contract

`from_pool` changes meaning without changing shape, so the generated schema will not show the change
and a client cannot discover it by introspection. The decision table **is** the contract
(Constitution III). That is why it is extracted into a pure module with its own unit suite rather
than left inline in `Node.handle_pool`, where it is reachable only through a database.

---

## Inputs

| Input | Type | Source |
|---|---|---|
| `value_present` | `bool` | payload key membership — `"value" in data` |
| `value` | `int \| None` | payload |
| `from_pool_present` | `bool` | payload key membership — `"from_pool" in data` |
| `from_pool_id` | `str \| None` | `from_pool["id"]` when present and non-null |
| `current_value_is_default` | `bool` | the attribute holds a schema default |
| `tracking_pool_id` | `str \| None` | the pool whose live record is on this attribute, if any |
| `current_value` | `int \| None` | the attribute's current value on the write's branch |

**Presence, not truthiness.** graphene preserves the distinction: graphql-core omits an unset field
from the coerced dict entirely, while an explicit `null` lands as `key -> None`. The update path
already relies on this (`BaseAttribute.from_graphql` tests `if "from_pool" in data`). The **create**
path currently discards it — `BaseAttribute.__init__` does `data.get(...)` — so presence flags must
be carried into it. See `research.md` D3.

---

## Output

One intent:

| Intent | Meaning |
|---|---|
| `ALLOCATE` | Pool picks the next free number; record created with `provenance=allocated` |
| `ATTACH` | Keep the provided number; record created with `provenance=provided` |
| `DETACH` | End the record; the number on the object is unchanged |
| `RE_POOL_ALLOCATE` | End pool A's record, allocate from pool B — one operation |
| `RE_POOL_ATTACH` | End pool A's record, attach the provided number under pool B — one operation |
| `DISCARD_AND_ALLOCATE` | Throw away the provided `null` value and allocate |
| `NO_OP` | Nothing to do |
| `REFUSE` | The single refusal |

An enum, not strings.

---

## The table

`P` is the pool named in the payload; `A` and `B` are distinct pools.

| # | `value` | `from_pool` | Currently tracked by | Current value | Intent |
|---|---|---|---|---|---|
| 1 | present, non-null | `P` | nothing | any | `ATTACH` |
| 2 | present, non-null | `P` | `P` | equal to provided | `NO_OP` |
| 3 | present, non-null | `P` | `P` | different | `ATTACH` — the record is already anchored on the attribute, so no new record is written; the value write plus a `provenance` update to `provided` is all that is needed |
| 4 | present, non-null | `B` | `A` | any | `RE_POOL_ATTACH` |
| 5 | present, non-null | absent | anything | any | Ordinary value write. Ledger untouched, whether or not a pool tracks the attribute (FR-022, FR-031) |
| 6 | present, **null** | `P` | nothing | any | `DISCARD_AND_ALLOCATE` |
| 7 | present, **null** | `P` | `P` | any | `DISCARD_AND_ALLOCATE` |
| 8 | present, **null** | `B` | `A` | any | `RE_POOL_ALLOCATE` |
| 9 | absent | `P` | nothing | schema default | `ALLOCATE` — allocation overwrites the default |
| 10 | absent | `P` | nothing | **non-default** | **`REFUSE`** ← the only refusal |
| 11 | absent | `P` | `P` | any | `NO_OP` |
| 12 | absent | `B` | `A` | any | `RE_POOL_ALLOCATE` |
| 13 | any | **null** | `P` | any | `DETACH` |
| 14 | any | **null** | nothing | any | `NO_OP` |
| 15 | absent | absent | anything | any | `NO_OP` |

### Row 10 — the single refusal

> `from_pool` alone on an attribute holding a non-default, untracked number.

The message must name **both** ways forward:

- restate the value alongside the pool to **attach** it, or
- send `value: null` with the pool to **discard** it and allocate.

Rationale: silently overwriting a hand-set number is the behaviour this slice exists to end, and the
user's intent is genuinely ambiguous — both readings are reasonable. This is the one place the
contract asks rather than guesses.

This is the **only** refusal the resolver emits. Earlier drafts carried three more, all deleted:
- the out-of-range refusal (FR-029 deleted — the pool refuses no provided value);
- two `source` refusals (FR-030a deleted — a user may set their own source on a pooled attribute).

A duplicate value reuses the **existing** uniqueness error and is raised by the constraint, not the
pool (FR-028).

### Row 4 and 12 — re-pool is not a refusal

Re-homing objects between pools is the brownfield journey this slice exists for, so naming pool B on
an attribute pool A tracks moves the claim in a single update rather than erroring. "Tracked by a
*different* pool" is therefore a dimension of the table, not an error case (FR-024a).

It is also unavoidable: the resolver must detect the case anyway to satisfy the one-record-per-
attribute invariant (FR-024b).

### Row 2 — idempotence is required, not incidental

Clients that resend every field — generators, object loads, SDK round-trips — must be able to
re-send `value` + `from_pool` for a number the object already owns without side effects.

---

## Out of the resolver's scope

These stay in `Node.handle_pool`, which remains the executor:

- resolving the pool by uuid **or** name (database I/O);
- the FR-023 check that the named pool is attached to the kind and attribute being written, including
  via a generic the kind inherits from — it needs the resolved pool node;
- the template refusal (`from_pool` is not supported on template attributes);
- the schema-declared `NumberPool` attribute path, which never reaches a user payload because
  read-only attributes are stripped from mutation inputs entirely.

---

## Scope (FR-030)

Applies to **plain writable Number attributes**. The `NumberPool` attribute kind stays read-only and
accepts no provided value. Templates remain refused.

> Note: `Bandwidth` also maps to `NumberAttributeCreate`/`NumberAttributeUpdate`, so `from_pool`
> appears on it in the generated schema. It is unreachable in practice — pool creation validates that
> the target attribute's kind is `"Number"` — so an attach against a `Bandwidth` attribute fails the
> FR-023 attachment check. No additional guard is needed; recorded so a reviewer does not read it as
> an oversight.

---

## Test obligations

Unit, no database:

1. **Every cell** of the table above.
2. Both re-pool cells (4, 12) resolve to a re-pool intent, not a refusal.
3. Exactly one input combination produces `REFUSE` — assert the count, not just the case, so a future
   edit cannot quietly add a second refusal.
4. Row 2 is a true no-op.
5. Presence is distinguished from truthiness: `value: null` (row 6) and `value` absent (row 9)
   produce different intents from the same `from_pool`.
