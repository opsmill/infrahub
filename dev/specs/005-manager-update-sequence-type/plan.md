# Implementation Plan: Type `RelationshipManager.update()` data as `Sequence`

**Branch**: `pha/INBOX-8` | **Date**: 2026-07-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-manager-update-sequence-type/spec.md`

**Tracking**: [INBOX-8](https://opsmill.atlassian.net/browse/INBOX-8) · [opsmill/infrahub#9977 review comment](https://github.com/opsmill/infrahub/pull/9977#discussion_r3614911929)

## Summary

Re-type the collection member of `RelationshipManager.update()`'s `data` parameter from an
invariant `list[...]` to a covariant `collections.abc.Sequence[...]`, widen the method's runtime
narrowing to match (treating any non-`str` `Sequence` as a collection), and delete the
`# type: ignore[arg-type]` — plus its now-stale explanatory comment — at the call site in
`backend/infrahub/core/manager.py`.

The technical approach is deliberately minimal: two production files, no behavioural change for any
existing caller. The one non-obvious element is that the annotation and the runtime `isinstance`
test must move together — widening only the annotation would leave `tuple` statically valid but
mishandled at runtime, and widening the runtime test carelessly would break bare-`str` peer ids
(because `str` satisfies `Sequence`).

## Technical Context

**Language/Version**: Python 3.12 (backend)

**Primary Dependencies**: None added. Uses `collections.abc.Sequence` from the standard library,
already imported in the target module.

**Storage**: N/A — no database, schema, or migration surface is touched.

**Testing**: pytest. Unit tests under `backend/tests/unit/`, mirroring source structure.

**Target Platform**: Linux server (Infrahub backend)

**Project Type**: Web service — Python backend (`backend/`) + frontend (`frontend/`, untouched here)

**Performance Goals**: N/A — typing/narrowing change only; no hot-path behaviour change. The
widened `isinstance` test is O(1) and runs once per `update()` call.

**Constraints**: No DB schema or migration changes, no GraphQL/REST contract changes, no auth
changes, no new dependencies, no CI workflow changes, no manual edits to generated files.
(Hard constraints from the originating card.)

**Scale/Scope**: 2 production files, single method signature + single narrowing branch + 2 deleted
comment lines. Effort S.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Applies? | Assessment |
|-----------|----------|------------|
| **I. Schema-Driven Integrity** | No | No schema, migration, or generated-schema surface touched. |
| **II. Branch-Safe by Default** | No | No query, branch, or temporal filtering logic changed. `update()`'s branch handling is untouched. |
| **III. Type Safety & Explicit Contracts** | **Yes — this is the principle being served** | The change *removes* a type suppression rather than adding one, and tightens the contract by advertising the parameter as non-mutating. No `Any` widening, no new `type: ignore`. Fully aligned. |
| **IV. Test Discipline** | Yes | Existing unit tests cover the `list`/single-value/`None` paths. A unit test is added for the newly-permitted non-`list` sequence path (spec User Story 3), placed to mirror source structure. |
| **V. Query Performance & Efficiency** | No | No queries added or modified. |
| **VI. Security & Input Boundaries** | No | Internal method; no user-input boundary, no Cypher, no secrets. |

**Gate result: PASS.** No violations, nothing to justify in Complexity Tracking.

Post-design re-check: **PASS** — the design below adds no new module, abstraction, or dependency;
it edits two existing methods and adds one test.

## Project Structure

### Documentation (this feature)

```text
specs/005-manager-update-sequence-type/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output — variance & narrowing analysis
├── quickstart.md        # Phase 1 output — how to verify
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

No `data-model.md` (no entities or persisted data) and no `contracts/` (no API contract surface) —
both are intentionally omitted as not applicable to a typing change.

### Source Code (repository root)

```text
backend/
├── infrahub/
│   └── core/
│       ├── manager.py                  # call site: delete the type: ignore + stale comment
│       └── relationship/
│           └── model.py                # RelationshipManager.update(): re-type `data`,
│                                       #   widen the runtime narrowing
└── tests/
    └── unit/
        └── core/                       # unit test for the non-list-sequence path
```

**Structure Decision**: Existing Infrahub backend layout, unchanged. The two production edits live
in `backend/infrahub/core/`; the added test mirrors that path under `backend/tests/unit/core/`, per
constitution principle IV ("test files MUST mirror source structure"). No new directories, modules,
or packages.

## Design

### D1 — Parameter re-typing (`backend/infrahub/core/relationship/model.py`)

`RelationshipManager.update()`'s `data` parameter changes from:

```python
data: list[str | Node | dict[str, Any] | PeerWithRelationshipMetadata]
    | dict[str, Any] | str | Node | PeerWithRelationshipMetadata | None,
```

to the same union with the collection member widened to `Sequence`:

```python
data: Sequence[str | Node | dict[str, Any] | PeerWithRelationshipMetadata]
    | dict[str, Any] | str | Node | PeerWithRelationshipMetadata | None,
```

`Sequence` is covariant in its element type, so `list[PeerWithRelationshipMetadata]` is assignable
to it and the caller's `arg-type` error disappears. `Sequence` is already imported in this module.

### D2 — Runtime narrowing must move with the annotation

The existing narrowing keys on `list` specifically:

```python
if not isinstance(data, list):
    list_data: Sequence[...] = [data]
else:
    list_data = data
```

Under D1 a `tuple` becomes statically valid but would fall into the `not isinstance(data, list)`
branch and be wrapped as `[the_tuple]` — one opaque "peer" instead of N peers. The narrowing is
therefore re-keyed on `Sequence`, with `str` explicitly excluded:

```python
if isinstance(data, str) or not isinstance(data, Sequence):
    list_data: Sequence[...] = [data]
else:
    list_data = data
```

**Why `str` is special-cased**: `str` satisfies `collections.abc.Sequence`, and it is a legitimate
single-value member of the union (a bare peer id). Without the explicit exclusion, a peer id like
`"abc123"` would be iterated into `["a", "b", "c", "1", "2", "3"]` — a silent, severe regression.
This is the single highest-risk line in the change.

**Why `dict` needs no special case**: `dict` does not satisfy `collections.abc.Sequence` (it is a
`Mapping`), so it falls through to the single-value branch unchanged.

**Behaviour matrix** (the invariant this design must hold):

| `data` | Before | After | Same? |
|--------|--------|-------|-------|
| `list[...]` | collection | collection (is a `Sequence`, not a `str`) | ✅ |
| `str` | single | single (explicitly excluded) | ✅ |
| `dict` | single | single (not a `Sequence`) | ✅ |
| `Node` | single | single (not a `Sequence`) | ✅ |
| `PeerWithRelationshipMetadata` | single | single (not a `Sequence`) | ✅ |
| `None` | single | single (not a `Sequence`) | ✅ |
| `tuple[...]` | single *(wrong)* | collection *(correct)* | ⚠️ intentional fix; no current caller |

Only the last row changes, and no existing caller exercises it (verified: all seven call sites pass
a `list`, a bare `str`, a `Node`, or a `PeerWithRelationshipMetadata`).

### D3 — Suppression removal (`backend/infrahub/core/manager.py`)

Delete both the `# type: ignore[arg-type]` and the preceding comment that explained why the
suppression was needed (it becomes false once the parameter is covariant):

```python
# invariant list parameter; update() only reads data, so the narrower element type is safe
await rel_manager.update(db=db, data=rel_peers_with_metadata)  # type: ignore[arg-type]
```

becomes:

```python
await rel_manager.update(db=db, data=rel_peers_with_metadata)
```

### D4 — Non-mutation obligation

The `Sequence` annotation advertises that `update()` does not mutate `data`. Confirm the method
body only reads `list_data` (iteration / length / indexing) and never calls `append`, `extend`,
`clear`, `remove`, `pop`, or item assignment on it. If any mutation exists, copy into a local
`list` instead — the annotation must not lie.

### D5 — Out of scope (explicit)

`backend/infrahub/menu/repository.py:105` carries its own `# type: ignore[arg-type]` on a
`.update(data=parent, ...)` call, but its cause is different (`parent` is a single
`CoreMenuItem | None`, not a list), so D1 does not clear it. It is left untouched per spec FR-006.
This is safe because `warn_unused_ignores` is not enabled in this repo's mypy config, so even a
suppression that *became* redundant would not fail CI.

## Complexity Tracking

> Fill ONLY if Constitution Check has violations that must be justified

No violations — nothing to track.
