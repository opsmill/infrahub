# Phase 0 Research: `Sequence` typing for `RelationshipManager.update()`

All items below were verified against the code on `pha/INBOX-8` (base `develop` @ `5f33d12e5`).
No `NEEDS CLARIFICATION` markers remained after this pass.

## R1 — Why the suppression exists: `list` invariance

**Question**: Is the `# type: ignore[arg-type]` at the call site really caused by container
invariance, or is something else wrong?

**Finding**: Container invariance, confirmed. `update()`'s `data` parameter
(`backend/infrahub/core/relationship/model.py:1213-1218`) declares its collection member as
`list[str | Node | dict[str, Any] | PeerWithRelationshipMetadata]`. The caller in
`backend/infrahub/core/manager.py:1346` holds a `list[PeerWithRelationshipMetadata]`.

`list[T]` is **invariant** in `T`, so `list[PeerWithRelationshipMetadata]` is *not* assignable to
`list[str | Node | dict | PeerWithRelationshipMetadata]` even though every element would be valid.
The invariance is not gratuitous pedantry: if `update()` were allowed to `append` a `str` into a
list the caller believes is `list[PeerWithRelationshipMetadata]`, the caller's own type would be
violated. Invariance is the type system correctly refusing an unsound assignment *for a mutable
container*.

**Decision**: `Sequence[T]` is **covariant** in `T` and exposes no mutators, so the unsoundness
invariance guards against cannot arise. Re-typing the collection member as `Sequence` is the
correct fix, and it is only sound because R2 holds.

**Alternatives rejected**:
- *Keep the `type: ignore`* — this is exactly what the card and the reviewer asked to undo; it
  keeps the `arg-type` class of error suppressed on this path.
- *Widen the caller's variable to the full union* (`list[str | Node | dict | Peer...]`) — pushes
  imprecision into the caller to satisfy the callee; the caller's narrow type is genuinely correct
  and worth keeping.
- *`cast()` at the call site* — same suppression in a different costume, and less honest than the
  `type: ignore` it replaces.
- *`Iterable` instead of `Sequence`* — would also be covariant and would type-check, but is a
  weaker contract than the code needs: the narrowing logic distinguishes "a collection of peers"
  from "one peer", and a single `Node` could plausibly be `Iterable` in future without being a
  collection of peers. `Sequence` (ordered, sized, indexable, non-consuming) matches how the value
  is actually used and is what the reviewer proposed. A one-shot iterator would also silently
  break the method's two passes over the data if `Iterable` were used.

## R2 — Does `update()` mutate `data`? (soundness precondition for `Sequence`)

**Question**: `Sequence` advertises "I will not mutate this". Is that actually true of the method
body? If not, the annotation would be a lie.

**Finding**: **True — no mutation.** Reading the method body
(`model.py:1230-1260`), the bound collection `list_data` is used in exactly one way:

```python
for item in list_data:
    changed |= await self._process_update_item(...)
```

It is iterated once, positionally, and never assigned into. There is no `append`, `extend`,
`insert`, `clear`, `remove`, `pop`, `sort`, `reverse`, `+=`, or `list_data[i] = ...` anywhere in the
method.

The one nearby `.clear()` call — `self._relationships.clear()` at `model.py:1240` — operates on the
manager's *own* relationship collection, an entirely different object from the caller's `data`. It
is not a mutation of the parameter.

**Decision**: The `Sequence` annotation is honest. No defensive copy is needed, so the change costs
nothing at runtime.

## R3 — The runtime narrowing must move with the annotation

**Question**: Is changing the annotation alone sufficient?

**Finding**: **No — annotation-only would introduce a latent bug.** The method narrows with:

```python
if not isinstance(data, list):
    list_data: Sequence[...] = [data]
else:
    list_data = data
```

This test keys on `list` **specifically**. Widening the annotation to `Sequence` makes a `tuple` a
statically valid argument, but the runtime test would send it down the `not isinstance(data, list)`
branch and wrap it as `[the_tuple]` — a single opaque "peer" instead of N peers. The tuple would
then fail `_process_update_item`'s validity check and raise `ValidationError`, or worse, be
misinterpreted.

An annotation that accepts an input the runtime mishandles is a worse contract than the invariant
`list` it replaced. So the narrowing is re-keyed on `Sequence`.

**Decision**: `if isinstance(data, str) or not isinstance(data, Sequence):` → single-value branch.

## R4 — `str` is a `Sequence`: the sharp edge

**Question**: What breaks if the narrowing is widened naively to `isinstance(data, Sequence)`?

**Finding**: `str` satisfies `collections.abc.Sequence`, and `str` is a **legitimate single-value
member** of the union — a bare peer id. A naive widening would route a peer id such as
`"1815b1a4-..."` into the collection branch and iterate it **character by character**, turning one
peer into 36 garbage peers. `_process_update_item` accepts `str` items, so each character would be
treated as a candidate peer id rather than failing loudly — a silent, severe data-corruption
regression, not a crash.

**Decision**: `str` must be excluded explicitly and **first**, before the `Sequence` test. This is
the single highest-risk line in the change and is covered by a dedicated acceptance scenario
(spec User Story 2, scenario 2).

**Note on `bytes`**: `bytes` is also a `Sequence` and would suffer the same issue, but it is not a
member of the accepted union and no caller passes it, so it needs no special case. If it were ever
added to the union it would need the same treatment as `str`.

## R5 — `dict`, `Node`, `PeerWithRelationshipMetadata`, `None` under the new test

**Question**: Do the remaining single-value union members still land on the single-value branch?

**Finding**: Yes, all four, with no special-casing:

| Member | Is a `Sequence`? | Branch | Correct? |
|--------|------------------|--------|----------|
| `dict[str, Any]` | No — it is a `Mapping` | single-value | ✅ |
| `Node` | No | single-value | ✅ |
| `PeerWithRelationshipMetadata` | No — a `@dataclass` (`model.py:89`) | single-value | ✅ |
| `None` | No | single-value | ✅ |

**Decision**: Only `str` needs an explicit carve-out. `dict` in particular is often assumed to need
one; it does not, because `Mapping` is not a `Sequence`.

## R6 — `Sequence` import origin: `typing` vs `collections.abc`

**Question**: `Sequence` is already imported in the module — is that import usable for an
`isinstance` check?

**Finding**: It is currently imported from **`typing`** (`model.py:7-17`), not `collections.abc`,
and the module has no `collections.abc` import at all. `isinstance(x, typing.Sequence)` does work at
runtime, but `typing.Sequence` has been deprecated since Python 3.9 in favour of
`collections.abc.Sequence`, and using a deprecated typing alias as an `isinstance` target in new
code is the wrong thing to leave behind. The card and the reviewer both name
`collections.abc.Sequence` explicitly.

`Sequence` appears in only **two** places in the file — the import at line 14 and the `list_data`
annotation at line 1231 — so relocating the import is a contained, two-line change.
`collections.abc.Sequence` is subscriptable (3.9+), so the existing annotation continues to work
unchanged, and `from __future__ import annotations` is already in effect at the top of the file.

**Decision**: Drop `Sequence` from the `typing` import block and add
`from collections.abc import Sequence`.

**Alternative rejected**: *Reuse the existing `typing.Sequence` for the `isinstance` check.* It
would function, and ruff's `UP035` (deprecated typing imports) is currently in the repo's ignore
list so lint would not complain — but it deliberately entrenches a deprecated alias in a change
whose entire purpose is typing hygiene. Also rejected: migrating `Iterable`, `Iterator`, and
`Mapping` from `typing` in the same import block — correct in principle, but unrelated to this card
and exactly the drive-by refactor `.agents/rules/backend-component-design.md` warns against.

## R7 — Blast radius: every existing call site

**Question**: Which callers exist, what do they pass, and does any of them change behaviour?

**Finding**: Seven call sites of `RelationshipManager.update()`, none affected:

| Call site | What it passes | Branch before | Branch after |
|-----------|----------------|---------------|--------------|
| `core/manager.py:1346` | `list[PeerWithRelationshipMetadata]` | collection | collection |
| `core/node/__init__.py:1335` | `value` (union) | per type | unchanged |
| `core/ipam/reconciler.py:168` | `str` (a uuid) | single | single (str carve-out) |
| `core/migrations/graph/m064_...py:130` | `source` | single | single |
| `core/migrations/graph/m064_...py:153` | `source` | single | single |
| `graphql/mutations/relationship.py:622` | `peer_data` | single | single |
| `core/convert_object_type/repository_conversion.py:55,59` | `new_repository` | single | single |

No caller passes a `tuple` or any other non-`list` sequence, so R3's fixed row is latent-only —
the change is behaviour-preserving for all current code.

`core/ipam/reconciler.py:168` is worth calling out: it passes a bare uuid `str`, so it is the live
caller that R4's carve-out protects. If the `str` exclusion were omitted, this call site would
break in production.

## R8 — Is the fix actually verifiable, or is `arg-type` disabled here?

**Question**: `infrahub.core.manager` has a module-level mypy override. If it disables `arg-type`,
removing the ignore would prove nothing.

**Finding**: The override at `pyproject.toml:231-239` disables `assignment`, `attr-defined`,
`index`, `no-untyped-def`, `return-value`, and `union-attr` — **`arg-type` is not in the list**.
So `arg-type` is live for this module and mypy genuinely re-reports the error if the fix is wrong or
incomplete.

Separately, `warn_unused_ignores` is **not** enabled anywhere in the mypy config. Two consequences:
1. A suppression that becomes redundant elsewhere will not fail CI (see R9).
2. mypy will not, by itself, tell us the removed ignore was necessary — so the verification in
   `quickstart.md` deliberately checks the error *reappears* when the fix is reverted.

**Decision**: The change is properly guarded. SC-001 is a meaningful gate.

## R9 — The other `arg-type` ignore on a `.update()` call

**Question**: `backend/infrahub/menu/repository.py:105` has `# type: ignore[arg-type]` on
`node.parent.update(data=parent, db=self.db)`. Does this fix clear it too?

**Finding**: No. That call passes `parent: CoreMenuItem | None` — a **single value**, not a list —
so its error has nothing to do with container invariance. It is a different root cause (the
generated `CoreMenuItem` protocol type not matching the `Node` union member).

Because `warn_unused_ignores` is off (R8), leaving it in place cannot fail CI even if it were
somehow rendered redundant.

**Decision**: Out of scope, untouched (spec FR-006). Widening this card to chase it would break the
card's single-concern Effort-S framing.

## R10 — Test placement and repo conventions

**Finding**: Per `.specify/memory/constitution.md` principle IV, unit tests live under
`backend/tests/unit/` and must mirror source structure; existing schema fixtures must be reused
rather than declaring new inline schemas.

Per `.agents/rules/code-doc-style.md`, **no work-item or spec IDs** (`INBOX-8`, `FR-003`, `T042`)
may appear in comments, docstrings, or test names — those belong in the commit message, PR
description, and these `dev/specs/` files only. Comments must explain *why*, never restate *what*.

**Decision**: The new test for the non-`list` sequence path goes under
`backend/tests/unit/core/` alongside existing relationship-manager tests, reusing their fixtures,
named for the behaviour (not the ticket). The `str` carve-out gets an explanatory comment stating
the *why* (`str` is a `Sequence` but is one peer id) — a genuine invariant, which is precisely the
kind of comment that rule permits.
