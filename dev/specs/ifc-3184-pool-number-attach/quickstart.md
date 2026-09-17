# Quickstart: validating "Numbers you give the pool"

**Feature**: `specs/ifc-3184-pool-number-attach` | **Date**: 2026-09-16

How to prove the feature works. Validation scenarios and the commands that run them — not
implementation. Each scenario names the success criterion it verifies.

---

## Prerequisites

```bash
uv sync --all-groups
```

Component and functional tests start Neo4j via testcontainers, so a running Docker daemon is
required. To reuse an already-running database instead:

```bash
INFRAHUB_USE_TEST_CONTAINERS=false uv run pytest backend/tests/component/core/resource_manager/
```

Container memory is pinned deliberately in `backend/tests/conftest.py` (heap 1g, pagecache 512m)
because the image auto-sizes from **host** memory and several xdist workers otherwise overcommit and
get OOM-killed. Do not raise it casually.

---

## Running the suites

```bash
# Pure logic — no database, runs in seconds
uv run pytest backend/tests/unit/pools/

# Queries, ledger, migration behaviours
uv run pytest backend/tests/component/core/resource_manager/
uv run pytest backend/tests/component/core/migrations/graph/m079_reanchor_number_pool_reservations/
uv run pytest backend/tests/component/core/agnostic_retirement/

# Lifecycle and branch behaviour end to end, in process
uv run pytest backend/tests/functional/pools/
uv run pytest backend/tests/functional/convert_object_type/

# Upgrade path, full stack
GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
  uv run pytest backend/tests/integration_docker/test_number_pool_migration.py
```

Before pushing: `/pre-ci`. It runs the locally-executable CI checks including
`uv run invoke docs.validate`, which fails on any stale generated file. This slice changes the
published GraphQL schema, so generated artefacts **will** be stale until regenerated:

```bash
uv run invoke backend.generate
uv run invoke schema.generate-graphqlschema
uv run invoke schema.generate-jsonschema
uv run invoke docs.generate
```

---

## Scenario 1 — Bring existing numbers under a pool (SC-001, SC-002, SC-003)

The headline journey.

1. Create a pool over 1–100 for a kind and a Number attribute. Allocate five times — you get 1–5.
2. Query the pool. It reports 5 in use.
3. Create an object with `value: 50` **and** that pool named.
4. **Expected**: the save keeps 50. The pool reports 50 in use. The next allocation returns **6**,
   and 50 is never handed out.
5. Take an object created earlier holding 37 with no pool. Update it with `value: 37` and the pool
   named.
6. **Expected**: 37 is unchanged and the pool now reports it.

**Adoption check (SC-003)**: point a *new* pool over 1–100 at forty objects already holding 1–40 and
query it. **Expected**: it reports nothing. Creating a pool adopts nothing — a pool knows exactly what
it handed out plus what you handed it.

---

## Scenario 2 — Provenance and duplicates (SC-001)

With no uniqueness constraint on the attribute:

1. Allocate 50 to object A.
2. Attach 50 on object B.
3. Query the pool's in-use list.

**Expected**: **two rows** for 50 — one `allocated`, one `provided`, each naming its holder — while
utilization counts 50 **once**. Utilization counts distinct elements of the space; the list shows
every holder.

Then attach 50 to a third object: three rows, still one element.

---

## Scenario 3 — Out of space (SC-015)

1. With a pool over 1–100, save an object with `value: 500` and that pool named.
2. **Expected**: the save **succeeds**. 500 is tracked, and reported in the **out-of-space bucket**
   rather than in the utilization fraction. The row carries value, holder and branch.
3. Widen a range to cover 500.
4. **Expected**: 500 moves into the in-use fraction **with no re-attach**.

Reach the same state the other way — attach a number inside the ranges, then remove the range under
it. The resulting state must be identical.

---

## Scenario 4 — Change the number the ordinary way (SC-013)

1. Take a tracked object holding 50.
2. Send a plain `value: 60` update naming **no** pool.
3. **Expected**: the pool releases 50 and tracks 60, with **no second call**. The in-use count is
   unchanged, 60 is reported in use, 50 is free and is returned by the next allocation.

Nothing is written to the ledger by this update — the record tracks the attribute, and what it
reserves is whatever the attribute holds.

---

## Scenario 5 — Detach (SC-014)

1. Send `from_pool: null` on a number the pool tracks.
2. **Expected**: the number on the object is **unchanged**, the pool's in-use count drops by one, and
   the number is allocatable again.
3. With 50 held by two objects under one pool, detach one.
4. **Expected**: only that record ends; the other object's record still reports 50 in use.

---

## Scenario 6 — Re-pool in one update (SC-018)

1. Move an object from pool A to pool B in a single update — naming B, with or without a value.
2. **Expected**: A reports nothing for that object **and A's out-of-space bucket is empty**. B reports
   the number. No second call.

The empty-bucket assertion is the one that catches a half-finished implementation: if A's record
survives, A does not report the number as *in use* (it is outside A's ranges) — it reports it in the
**bucket**, telling the operator to widen A to cover a number B handed out. Nonsense, and easy to
miss without checking.

---

## Scenario 7 — The single refusal

1. On an object holding a non-default number that no pool tracks, send `from_pool` **alone**.
2. **Expected**: refused, with an error naming **both** ways forward — restate the value to attach
   it, or send `value: null` to discard it and allocate.

Check the negative cases too. These must **not** be refused:
- a number outside the pool's ranges (FR-029 deleted);
- a user setting their own `source` on a pooled attribute (FR-030a deleted);
- re-sending the same `value` + `from_pool` an object already owns — a silent no-op.

A duplicate value is refused by the **uniqueness constraint** with the ordinary duplicate error, not
by the pool.

---

## Scenario 8 — Source (SC-019, SC-020)

1. Read an attribute whose number the pool allocated, with no user source set.
2. **Expected**: `source` reports the **pool** — and no source edge is stored behind it. Check the
   resolved GraphQL **kind**, not only the uuid: the concrete type is selected from the returned
   node's labels, so an implementation returning an id alone passes a uuid assertion and still breaks.
3. Set a user source on that attribute.
4. **Expected**: the reported source becomes the user's, and **nothing the pool reports changes** —
   utilization, the in-use list and the next number are all unaffected.
5. Detach on a branch, then delete that branch.
6. **Expected**: no branch reports a pool source for that attribute, and the pool reports nothing for
   it.

---

## Scenario 9 — Cross-branch liveness (SC-016) — the release blocker

This reproduces a **confirmed defect**. Start from `artifacts/test_fr036a_repro.py`.

1. Allocate a pooled number to an object on the default branch.
2. Create a branch and **delete the object there**, while the default branch still holds it.
3. Ask the pool for its next number.

**Expected after the fix**: the held number is still reported in use and is **never offered**.

**Today**: it is reported free on *every* branch, and on a non-unique attribute the pool hands it to a
second object while the first still holds it — a manufactured collision, reproduced.

Run **both polarities**:
- **non-unique** — reproduces today;
- **unique** — masked today by the 1.11 hand-set-value scan, and starts failing when P1 deletes it
  (FR-011). P1 therefore converts a latent read defect into a live collision, which is why this fix
  cannot land after P1.

**Keep the passing case as a regression**: a branch-level **value change** must **not** free the
default branch's value. That works today and must keep working — it is a different mechanism (a new
value edge without tombstoning the default branch's).

---

## Scenario 10 — Object conversion (SC-021)

1. Convert an object holding a pooled number to another type.
2. **Expected**: the pool keeps reporting the number, **attributed to the new object**, and never
   offers it.

Assert the value the pool **reports**, not that an edge exists. The existing test asserts through a
query with no liveness join, so it proves the edge is there while the pool has already freed the
number — which is exactly the confirmed defect.

---

## Scenario 11 — The migration (SC-022) — the strongest safety evidence

Run against a database populated **before** the change.

1. Record every figure the pool reports — utilization, the branch split, the in-use list.
2. Run the migration.
3. Re-read the same figures.

**Expected**: **identical**, except where FR-036a corrects a known defect.

This is only measurable at a boundary where nothing else has moved the numbers, which is why the
foundational change set merges ahead of P1's ranges and this slice's bucket.

Then check each destructive behaviour and its reported **count**:

| Behaviour | Check |
|---|---|
| Orphan drop | Records whose object no longer exists are gone; the count is reported |
| Multi-pool collapse | Several live records on one attribute become one; the survivor is the most recent `from`; the count is reported |
| Legacy source deletion | A pool-written `HAS_SOURCE` is removed; **an unrelated user source is left alone**; the count is reported |
| Duplicate-uuid node | A node with several same-uuid vertices re-anchors to the **active** one |
| **Ordering** | Two pools with live records on one attribute, both carrying legacy pool source edges. After migration the attribute reports the **surviving** pool and has **no** stored source edge. This fails if the collapse runs before the source deletion. |

Counts reach an operator only through the migration console, so assert on the logged string — that is
the testable surface, and it is how `m078`'s tests do it. Each destructive behaviour logs a
**pre-count** as well as a post-count, because the migration is **irreversible** — three of its four
behaviours delete data and the only recourse after a bad upgrade is a database restore.

---

## Scenario 12 — The benchmark (replaces SC-017)

No numeric gate. SC-017 was withdrawn: the repo has no evidence for a realistic live-branch ceiling
and the performance task runner is not parameterised on branch count, which left an invented constant
carrying the whole criterion.

1. Benchmark allocation against `develop`, before and after the cross-branch liveness fix.
2. Vary **live branch count** — a new axis; `BenchmarkConfig` has only `neo4j_image`,
   `neo4j_runtime` and `load_db_indexes` today, and the one branch-aware benchmark creates exactly one
   extra branch.
3. Review the curve.

A superlinear curve, or a large constant from nesting per-branch resolution inside a query that
already fans out over records, is a **release decision** — not something to wave through. Per-branch
resolution happens inside the pool-wide allocation lock, which is what makes this the slice's one
real performance risk.

---

## Scenario 13 — Sweeps keep the record global

1. **Rename** a pool-tracked attribute in the schema. The record must stay `-global-` and the pool
   must still report the number.
2. **Remove** a pool-tracked attribute from the schema. The record must be closed.

The rename case is a confirmed bug today and fails until fixed. It matters more than it looks: the
record is the sole storage of the pool's claim, so relocating it onto a branch makes it invisible to a
derivation matching only `-global-` edges — the attribute then reports **no source at all** while the
ledger still holds the number reserved.

---

## Before opening a PR

- [ ] `/pre-ci` clean, including `docs.validate`
- [ ] Generated files regenerated and committed, never hand-edited
- [ ] Seven towncrier changelog fragments (see spec.md, *Behaviour changes needing changelog entries*)
- [ ] `GRAPH_VERSION` 78 → 79 and `uv run pytest backend/tests/unit/core/graph/test_graph_version.py`
- [ ] The `integration_docker` test carries a module-level shard marker with a matching entry in the
      `backend-docker-integration` `shard:` matrix in `.github/workflows/ci.yml` — `conftest.py`
      validates the whole collection `tryfirst`, so a missing marker fails CI rather than silently
      never running
- [ ] This slice named in the published-contract review (ADR 0010) **with FR-030b named in words** —
      the generated schema will not show it
- [ ] `dev/knowledge/backend/database-schema.md` documents `IS_RESERVED`, which it does not today
