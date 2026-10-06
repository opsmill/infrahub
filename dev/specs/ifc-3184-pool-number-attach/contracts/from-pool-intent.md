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
| `value` | `Sent[int] \| None` | `None` when `"value" not in data`; otherwise `Sent` holding the payload value, `None` for an explicit `null` |
| `from_pool` | `Sent[str] \| None` | `None` when `"from_pool" not in data`; otherwise `Sent` holding the resolved pool id, `None` for an explicit `null` |
| `held_value_is_default` | `bool` | the attribute holds a schema default; read only when the write sends no `value` |
| `tracking_pool_id` | `str \| None` | the pool whose live record is on this attribute, if any |
| `held_value` | `int \| None` | the number the attribute holds; read only when the write sends no `value` |

**Presence, not truthiness.** graphql-core omits an unset field from the coerced dict entirely,
while an explicit `null` lands as `key -> None` — but only for a field with no default. `from_pool`
on the Number attribute inputs is therefore declared as a plain input field
(`GenericPoolInput(required=False)`): mounted as `Field(GenericPoolInput, ...)`, graphene gives it a
`null` default, so an omitted `from_pool` arrived as `None` and read as an explicit detach. The update path
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
| `NO_OP` | Nothing to do |
| `REFUSE` | The refusal: `from_pool` alone over a number it would overwrite (rows 10 and 12) |

An enum, not strings.

**Revised 2026-10-05: no separate re-pool or discard intents.** Writing a pool's record ends every other
record on the attribute in the same query, so moving from pool A to pool B is the same write as an
attach or an allocation, and `value: null` with a pool asks for the next number from that pool, which
is an allocation. `RE_POOL_ATTACH`, `RE_POOL_ALLOCATE` and `DISCARD_AND_ALLOCATE` were removed.

---

## The table

`P` is the pool named in the payload; `A` and `B` are distinct pools.

| # | `value` | `from_pool` | Currently tracked by | Current value | Intent |
|---|---|---|---|---|---|
| 1 | present, non-null | `P` | nothing | any | `ATTACH` |
| 2 | present, non-null | `P` | `P` | equal to provided | `ATTACH` — the write to the database leaves the record unchanged, including an `allocated` provenance, because the attribute already holds that value on the branch (revised 2026-10-05) |
| 3 | present, non-null | `P` | `P` | different | `ATTACH` — the record is already anchored on the attribute, so no new record is written; the value write plus a `provenance` update to `provided` is all that is needed |
| 4 | present, non-null | `B` | `A` | any | `ATTACH` — writing B's record ends A's |
| 5 | present, non-null | absent | anything | any | Ordinary value write. Ledger untouched, whether or not a pool tracks the attribute (FR-022, FR-031) |
| 6 | present, **null** | `P` | nothing | any | `ALLOCATE` |
| 7 | present, **null** | `P` | `P` | any | `ALLOCATE` — take the next number from `P`, which may be the number the attribute already holds; no new IS_RESERVED edge unless the pool or provenance changes |
| 8 | present, **null** | `B` | `A` | any | `ALLOCATE` — writing B's record ends A's |
| 9 | absent | `P` | nothing | schema default | `ALLOCATE` — allocation overwrites the default |
| 10 | absent | `P` | nothing | **non-default** | **`REFUSE`** |
| 11 | absent | `P` | `P` | any | `NO_OP` |
| 12 | absent | `B` | `A` | **non-default** | **`REFUSE`**; with a schema default or no value, `ALLOCATE`, and writing B's record ends A's (revised 2026-10-05) |
| 13 | any | **null** | `P` | any | `DETACH` |
| 14 | any | **null** | nothing | any | `NO_OP` |
| 15 | absent | absent | anything | any | `NO_OP` |

### Rows 10 and 12 — the refusal

> `from_pool` alone on an attribute holding a non-default number, unless the named pool already tracks it.

*Revised 2026-10-05: row 12 (another pool tracks the number) refuses for the same reason as row 10. Moving
to a new pool with no value could mean keep the number or take the new pool's next one.*

The message must name **both** ways forward:

- restate the value alongside the pool to **attach** it, or
- send `value: null` with the pool to **discard** it and allocate.

Rationale: silently overwriting a hand-set number is the behaviour this slice exists to end, and the
user's intent is genuinely ambiguous — both readings are reasonable. This is the one place the
contract asks rather than guesses.

This is the **only** refusal rule the resolver applies. Earlier drafts carried three more, all deleted:
- the out-of-range refusal (FR-029 deleted — the pool refuses no provided value);
- two `source` refusals (FR-030a deleted — a user may set their own source on a pooled attribute).

A duplicate value reuses the **existing** uniqueness error and is raised by the constraint, not the
pool (FR-028).

### Rows 4, 8 and 12 — re-pool is not a refusal

Re-homing objects between pools is the brownfield journey this slice exists for, so naming pool B on
an attribute pool A tracks moves the claim in a single update rather than erroring, once the write
says which number to keep (row 4), asks for a new one (row 8), or the attribute holds no value or only
its schema default (row 12). "Tracked by a *different* pool" is therefore a dimension of the table, not an error case (FR-024a).

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
2. Row 4 attaches and row 12 refuses over a held number; row 12 over a default allocates.
3. Only the combinations of rows 10 and 12 produce `REFUSE` — assert the exact list, not just the cases,
   so a future edit cannot quietly add another refusal.
4. Row 2 is a true no-op.
5. Presence is distinguished from truthiness: `value: null` (row 6) and `value` absent (row 9)
   produce different intents from the same `from_pool`.
