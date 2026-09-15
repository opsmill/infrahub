# Phase 1 data model — Git status indicator (IFC-3199)

This feature introduces no persisted data and no backend schema change. It reads two counts
and derives one display state. The "model" here is therefore the derived state and the shape
of its inputs.

## Derived value: `GitStatus`

The single value the component renders from. A closed union of five members — closed because
FR-005a forbids a third status treatment, so the set must not grow by accident.

| Member | Meaning | Rendering |
|---|---|---|
| `loading` | A count is still outstanding and the total is not a confirmed zero | Spinner in the glyph's slot |
| `check-failed` | At least one count failed; branch health is unknown | `mdi:error-outline`, muted/warning — **never** the danger colour, which is reserved for a real failure (FR-011) |
| `inert` | No Git repositories are configured | Dimmed glyph, not activatable |
| `error` | At least one repository on the branch has the import-error status | Glyph in danger colour + pulsing dot |
| `neutral` | Repositories exist and none carry the import-error status | Glyph in default foreground |

## Inputs to the derivation

Two count queries, each contributing three facts:

| Input | Type | Source |
|---|---|---|
| `totalIsPending` / `failingIsPending` | `boolean` | TanStack Query lifecycle |
| `totalError` / `failingError` | `Error \| null` | TanStack Query lifecycle |
| `totalCount` / `failingCount` | `number \| undefined` | The GraphQL count field |

Loading and failure are query lifecycle facts, not domain facts. They are layered on top of
the two counts rather than modelled as repository states — the same separation the existing
task indicator uses around its own boolean.

## Derivation rule and precedence

Precedence is the substance of this model, not an implementation detail:

```
1. totalError                           -> check-failed
2. totalCount === 0                     -> inert
3. totalIsPending || failingIsPending   -> loading
4. failingError                         -> check-failed
5. failingCount > 0                     -> error
6. otherwise                            -> neutral
```

A confirmed total of zero is checked before the pending guard on purpose: no repositories
means none failing, so the second lookup cannot change the answer and is not waited for. A
hung failing-count request would otherwise trap an empty deployment in the loading state
indefinitely.

**Why this order:**

- **Loading first** — the indicator must never present a resolved state it has not confirmed
  (spec edge case: first load). A glyph that flashes neutral before turning red reads as a
  glitch and trains operators to distrust it.
- **A failed total lookup is unrecoverable** — without it nothing is known, so check-failed
  is the only honest state. This is also the permission-denied path, per the spec amendment.
- **Inert outranks a failed failure-lookup** — this ordering is load-bearing and was wrong in
  an earlier draft. If the total is zero, the failing count is necessarily zero: it counts a
  subset of an empty set. The successful lookup fully determines the answer, so alarming
  about the failed one would be a false alarm about a question that cannot matter. Rule 3
  must therefore sit above rule 4, not below a combined "either errored" rule.
- **A failed failure-lookup, with repositories present, is genuinely unknown** — the
  application knows repositories exist but not whether any are broken. Neither `neutral` nor
  `error` is a fact in hand, so check-failed is correct here. This is the case SC-007 exists
  for.
- **No "all failing" special case** — `failingCount > 0` covers one failure and total
  collapse identically, per the spec's edge case.

**Implementation trap — `isPending`, never `isFetching`.** With a refresh interval,
`isFetching` is true on every poll while `isPending` is true only until data first arrives.
Reading the wrong one makes the glyph flash its loading treatment every ten seconds, and a
test written against a first render would not catch it. Rule 1 means `isPending`. A component
test must assert that a resolved state survives a background refetch.

## Entities referenced, not owned

| Entity | Where it lives | What this feature uses |
|---|---|---|
| Git repository (generic kind) | Backend schema, generic repository | Existence and count on a branch, across every concrete kind |
| Repository sync status | Per-branch attribute on the generic repository | One distinction only: is it the import-error value |
| Current branch | Frontend branch context | `name` for query scoping, `is_default` for URL construction |

## Vocabulary added

`entities/repository/domain/model/repository.ts` gains the import-error status value as a
named constant, alongside the existing attribute-name and kind constants. Without it the
literal would appear in the filter, the link builder and the tests independently.

The value must stay in step with the backend enum. Its label in the UI dropdown is
"Import Error"; the stored value is the enum's import-error member.
