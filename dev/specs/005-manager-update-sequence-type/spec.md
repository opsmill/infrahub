# Feature Specification: Type `RelationshipManager.update()` data as `Sequence`

**Feature Branch**: `pha/INBOX-8`

**Created**: 2026-07-29

**Status**: Draft

**Tracking**: [INBOX-8](https://opsmill.atlassian.net/browse/INBOX-8) · source review comment: [opsmill/infrahub#9977 (discussion_r3614911929)](https://github.com/opsmill/infrahub/pull/9977#discussion_r3614911929)

**Input**: User description: "Type the `update()` parameter in `core/manager.py` as `Sequence` and remove the `type: ignore`. `RelationshipManager.update()`'s `data` parameter is typed with an invariant `list[...]` member, which forces a scoped `# type: ignore[arg-type]` at its caller in `backend/infrahub/core/manager.py`. Typing that collection member as a covariant `collections.abc.Sequence[...]` lets the suppression be removed and keeps mypy meaningful on that path."

## Context

`RelationshipManager.update()` (`backend/infrahub/core/relationship/model.py`) declares its `data`
parameter as a union whose collection member is an **invariant** `list[...]`:

```python
data: list[str | Node | dict[str, Any] | PeerWithRelationshipMetadata]
    | dict[str, Any] | str | Node | PeerWithRelationshipMetadata | None,
```

Because `list` is invariant in its element type, a caller holding a narrower
`list[PeerWithRelationshipMetadata]` cannot pass it without a type error, even though `update()`
only *reads* the collection. That forced a scoped suppression at the call site in
`backend/infrahub/core/manager.py`:

```python
# invariant list parameter; update() only reads data, so the narrower element type is safe
await rel_manager.update(db=db, data=rel_peers_with_metadata)  # type: ignore[arg-type]
```

The reviewer's guidance on PR #9977 was that suppressing the warning is the wrong fix — the
parameter should be typed as a non-mutating `collections.abc.Sequence`, which is **covariant** in
its element type and therefore accepts the narrower list directly.

There is a correctness consequence that the naive annotation-only change would miss. `update()`
narrows its argument at runtime with:

```python
if not isinstance(data, list):
    list_data: Sequence[...] = [data]
else:
    list_data = data
```

Widening the annotation to `Sequence` makes non-`list` sequences (notably `tuple`) *statically*
valid, but the existing `isinstance(data, list)` test would route a tuple down the single-value
branch and wrap it as `[some_tuple]` instead of iterating its elements. That would be a latent bug
introduced by the type change, so the runtime narrowing must be widened in step with the
annotation.

## User Scenarios & Testing *(mandatory)*

The "users" here are Infrahub backend developers and the type checker that guards their changes.

### User Story 1 - Passing a narrowly-typed peer list type-checks without suppression (Priority: P1)

A developer calls `RelationshipManager.update()` with a `list` whose element type is narrower than
the full accepted union (for example `list[PeerWithRelationshipMetadata]`). The call type-checks on
its own merits, with no `# type: ignore` needed and no change in runtime behaviour.

**Why this priority**: This is the entire point of the card — it removes the suppression that is
currently hiding the `arg-type` class of error on this code path, restoring mypy's usefulness
there.

**Independent Test**: Delete the `# type: ignore[arg-type]` at the `core/manager.py` call site and
run mypy over `backend/infrahub/core/manager.py`; it reports no `arg-type` error. Verifiable
entirely by the type checker with no runtime setup.

**Acceptance Scenarios**:

1. **Given** `rel_peers_with_metadata: list[PeerWithRelationshipMetadata]`, **When** mypy checks
   `await rel_manager.update(db=db, data=rel_peers_with_metadata)` with no suppression comment,
   **Then** no `arg-type` error is reported.
2. **Given** the suppression comment and its explanatory comment have been deleted, **When** the
   repository's configured lint and type-check gates run, **Then** they pass.
3. **Given** `infrahub.core.manager`'s mypy override in `pyproject.toml` does **not** disable
   `arg-type`, **When** the fix is incorrect or incomplete, **Then** the error resurfaces and CI
   fails — i.e. this story is genuinely guarded, not silently disabled.

---

### User Story 2 - Every existing caller keeps its current runtime behaviour (Priority: P1)

All present callers of `RelationshipManager.update()` — passing a `list`, a bare `str` peer id, a
`dict`, a `Node`, a `PeerWithRelationshipMetadata`, or `None` — behave exactly as before the type
change.

**Why this priority**: Equal-priority with P1 above because a typing cleanup that alters runtime
dispatch is a regression, not a cleanup. `str` is the sharp edge: `str` *is* a `Sequence`, so a
carelessly widened runtime check would iterate a peer-id string character by character.

**Independent Test**: Run the existing test suites covering relationship updates and the known
call sites; all pass unchanged.

**Acceptance Scenarios**:

1. **Given** `data` is a `list` of peers, **When** `update()` runs, **Then** the list is iterated
   as the collection (unchanged from today).
2. **Given** `data` is a bare `str` peer id, **When** `update()` runs, **Then** it is treated as a
   single peer — **not** iterated into individual characters.
3. **Given** `data` is a `dict`, a `Node`, a `PeerWithRelationshipMetadata`, or `None`, **When**
   `update()` runs, **Then** it is treated as a single value, as today.

---

### User Story 3 - A non-list sequence is handled coherently (Priority: P2)

If a caller passes a `tuple` (now statically permitted by the widened annotation), `update()`
iterates it as a collection rather than wrapping it as one opaque value.

**Why this priority**: P2 because no current caller passes a tuple, so nothing is broken today.
It matters because the widened annotation *invites* this call, and an annotation that accepts an
input the runtime mishandles is worse than the invariant `list` it replaced.

**Independent Test**: Call `update()` with a tuple of peers and assert the same outcome as the
equivalent list.

**Acceptance Scenarios**:

1. **Given** `data` is a `tuple` of peers, **When** `update()` runs, **Then** it is iterated as a
   collection, producing the same result as passing the equivalent `list`.

### Edge Cases

- **`str` is a `Sequence`** — a bare peer-id string must stay on the single-value branch. This is
  the primary trap of the widened runtime check.
- **`dict` is not a `Sequence`** — dicts continue to fall to the single-value branch with no
  special handling required.
- **`None`** — continues to fall to the single-value branch, as today.
- **Other non-list sequences** — anything satisfying `collections.abc.Sequence` and not a `str`
  is treated as a collection.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The collection member of `RelationshipManager.update()`'s `data` parameter MUST be
  typed as a covariant, non-mutating `collections.abc.Sequence[...]` rather than an invariant
  `list[...]`, preserving the existing element union.
- **FR-002**: The `# type: ignore[arg-type]` at the `backend/infrahub/core/manager.py` call site
  MUST be removed, together with the now-stale comment that explained it.
- **FR-003**: `update()`'s runtime narrowing MUST classify `data` consistently with the widened
  annotation: any non-`str` `Sequence` is treated as a collection, and `str`, `dict`, `Node`,
  `PeerWithRelationshipMetadata`, and `None` are each treated as a single value.
- **FR-004**: `update()` MUST NOT mutate the collection it receives (which the `Sequence`
  annotation now advertises as part of its contract).
- **FR-005**: Observable behaviour for every existing caller MUST be unchanged.
- **FR-006**: The scoped `# type: ignore[arg-type]` at `backend/infrahub/menu/repository.py:105`
  MUST be left untouched — it has a different root cause (a single `CoreMenuItem | None`, not a
  list) and is out of scope.

### Key Entities

- **`RelationshipManager.update()`** — the method whose `data` parameter is being re-typed.
- **`data` parameter** — a union of one collection form and several single-value forms.
- **Call site in `core/manager.py`** — the caller currently carrying the suppression.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: mypy reports zero errors on `backend/infrahub/core/manager.py` and
  `backend/infrahub/core/relationship/model.py` with no `arg-type` suppression at the call site.
- **SC-002**: The count of `# type: ignore[arg-type]` occurrences in
  `backend/infrahub/core/manager.py` drops by exactly one; no new suppression of any kind is
  introduced anywhere.
- **SC-003**: The repo's lint gate (ruff) and the local pre-CI gate pass.
- **SC-004**: The existing test suites covering relationship updates and the known call sites pass
  with no modifications to their assertions.
- **SC-005**: Passing a `tuple` of peers to `update()` yields the same result as passing the
  equivalent `list`.
- **SC-006**: Net production-code change stays within a handful of lines across at most two files,
  consistent with the card's Effort-S sizing.

## Assumptions

- The element union of the `data` parameter is correct as it stands; only its *container* typing
  (and the matching runtime check) is in scope. No union member is added or removed.
- `Sequence` is already imported in `backend/infrahub/core/relationship/model.py` (it is used in
  the local `list_data` annotation), so no new import of it is required there.
- `warn_unused_ignores` is not enabled in this repo's mypy configuration, so an existing
  suppression elsewhere that becomes redundant will not fail CI — this is why FR-006's out-of-scope
  ignore can safely be left in place.
- The `infrahub.core.manager` mypy override in `pyproject.toml` does not disable `arg-type`, so
  this path is genuinely type-checked and the fix is verifiable.
- No DB schema, migration, GraphQL/REST contract, auth, dependency, CI-workflow, or generated-file
  changes are needed; this is a pure typing/narrowing change in two backend modules.
- Existing tests are expected to cover the `list`, single-value, and `None` paths. A focused test
  is added only for the newly-permitted non-`list` sequence case (User Story 3) if no equivalent
  coverage already exists.
