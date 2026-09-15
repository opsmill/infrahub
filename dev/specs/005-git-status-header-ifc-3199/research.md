# Phase 0 research — Git status indicator (IFC-3199)

Five questions were open at the start of planning. All are resolved; no NEEDS CLARIFICATION
remains. Each entry records what was chosen, why, and what was rejected.

---

## R1. Data source for "is any repository failing on this branch?"

**Decision**: Two counts of `CoreGenericRepository`, one unfiltered and one filtered on the
import-error sync status, with the branch supplied as GraphQL query context.

**Rationale**: `sync_status` is defined on the generic repository schema with per-branch
support, so the value is already branch-scoped — which is what makes the question answerable
at all. Querying the generic kind covers every concrete repository kind through one lookup,
satisfying FR-012. Counts keep cost constant in the number of repositories (SC-006).

**Alternatives considered**:

- **`InfrahubRepositoryBranchStatus` (IFC-3126)** — rejected, despite sitting at the tip of
  this branch's base and appearing purpose-built. It is a contract stub. It takes a single
  repository identifier and returns one row per branch, which is the opposite axis from the
  one this feature needs. Its values are derived from a hash of the branch name. Its own
  module documentation states it will be deleted once a real graph-reading source lands. Its
  resolver raises a validation error if `sync_status__value` is passed, because the values
  are placeholders. Building on it would have produced an indicator that reports convincing
  nonsense, which is worse for this feature than reporting nothing.
- **One combined GraphQL document with two aliased root fields** — rejected by explicit user
  decision in favour of two separate lookups. It would also make the one-succeeds-one-fails
  state impossible to construct, which is the case SC-007 exists to protect.
- **Deriving status from task state** — rejected by the ticket itself, and it is the reason
  the epic exists: a task can finish green while the import left the branch in `Import Error`.

## R2. Disabled state on `LinkButton`

**Decision**: `isDisabled` on `LinkButton` for the inert state.

**Rationale**: `isDisabledAndFocusable` is declared on `ButtonProps`
(`packages/ui/src/components/button/button.tsx::ButtonProps`) and consumed only by `Button`.
`LinkButtonProps extends AriaLinkProps` and has no such property, so a plan calling for it on
`LinkButton` would not compile. This was a direct contradiction between two planning agents
and was settled by reading the source.

**RESOLVED during implementation — the tooltip does NOT fire, and the decision changed.**

A test written specifically to settle this (`still explains itself on hover while inert`)
timed out hovering the control. A disabled `LinkButton` renders as `<span role="link"
aria-disabled="true" data-disabled="true">`, and `buttonVariants` carries
`data-disabled:pointer-events-none`, so the hover never reaches the element and no tooltip
appears. FR-010a — the inert state must explain itself — would have been silently unmet, with
nothing failing to signal it.

**Final decision**: the inert state renders a `Button` with `isDisabledAndFocusable` instead of
a disabled `LinkButton`. That prop exists on `ButtonProps` for exactly this case; its own
documentation reads "Uses isPending internally to keep the button hoverable/focusable while
appearing disabled. Useful for tooltip triggers." It shares `buttonVariants`, so the control's
dimensions are unchanged and SC-004 still holds.

A button is also the more honest element here: with no repositories there is nowhere to
navigate to, so presenting a link at all was overstating what the control does.

The `nonInteractiveTrigger` fallback anticipated above was not needed — the design system had
already solved this, one component over from the one the plan reached for.

## R3. Polling configuration through the shared count hook

**Decision**: Widen `useObjectsCount`'s `config` parameter from `{ enabled?: boolean }` to
`{ enabled?: boolean; refetchInterval?: number | false }`.

**Rationale**: the hook already spreads `config` into `useQuery`, so the runtime behaviour is
present; only the type blocks it. The widening is additive and optional, so no existing call
site changes behaviour or fails to type-check. This is the only edit outside the feature's own
files, and a reviewer should confirm no consumer's inference narrows unexpectedly.

**Alternatives considered**: a bespoke repository-local count hook duplicating branch and
date wiring — rejected as a second path to the same capability, contrary to Principle VII.

## R4. Permission-denied handling

**Decision**: permission-denied renders as check-failed, not as the inert empty state. The
spec was amended during planning rather than the implementation quietly diverging from it.

**Rationale**: `getObjectsCount` throws `new Error(errors[0].message)`, discarding the error
code, so a consumer of the shared use-case cannot distinguish a permission error from any
other failure. Delivering the original requirement would have meant a repository-local
fetcher and use-case preserving the code via the existing `hasCatalogueCode` /
`ERROR_CODES.PERMISSION_DENIED` helpers — roughly four files duplicating
`entities/nodes/object`, for one error code on a header glyph.

Beyond cost, check-failed is the more honest state. Telling an operator "no Git repositories
on this branch" when they simply cannot see them asserts something the application does not
know, and a branch full of failing repositories would read as an empty one. "Status could not
be checked" is accurate in both cases.

**Alternatives considered**: build the error-preserving layer (rejected on cost and
Principle VII); drop the edge case silently (rejected — it leaves the next reader to
rediscover the question).

## R5. Seeding the import-error status for E2E

**Decision**: set `sync_status` to the import-error value directly on an existing fixture
repository, via a normal update mutation. Superseded an earlier decision to build a
purpose-broken repository, once the attribute was confirmed writable.

**Rationale**: three independent planning explorations each searched `tests/e2e/` and each
reported the same finding — **no fixture seeds an error sync status today**. The only
occurrence of the error value is in `tests/e2e/conftest.py`, where the existing repository
fixture treats it as a hard failure to raise on, because every current consumer wants a
healthy repository.

All three then assumed the only way forward was to engineer a genuine import failure. The
critique found that assumption unnecessary: `sync_status` is a plain Dropdown attribute on the
generic repository schema (`optional=False`, `branch=BranchSupportType.LOCAL`, no read-only
flag) with four choices, one of them the import-error value. It can simply be set.

The indicator reads `sync_status` and nothing else, so a test that sets it exercises the whole
contract the feature depends on. What such a test does not prove is that a real import failure
*results in* that status — but that is the importer's behaviour, already owned by backend
tests and untouched by this frontend ticket.

**Alternatives considered**:

- **A purpose-built repository that genuinely fails to import** (a `.infrahub.yml` referencing
  a missing transform file, so the importer's exception path sets the status). This was the
  original decision and was reversed on the evidence above. It would have added a second
  session-scoped import fixture to the slowest shard tier, and would have been the suite's
  only test depending on an import failing by design — re-verifiable whenever the importer's
  error handling moved.
- **Point a repository at an unreachable URL** — network-dependent, a flakiness source in CI.
- **Assert only that the indicator renders, without any failure state** — satisfies the letter
  of the constitution's E2E requirement while proving nothing about the state the feature
  exists for. Rejected.

**Remaining cost**: the test mutates shared fixture state, so it must restore the status
afterwards or run on its own branch. Otherwise it leaves a repository in an error state for
every later test sharing that session-scoped fixture — a cheap mistake with confusing
downstream symptoms.
