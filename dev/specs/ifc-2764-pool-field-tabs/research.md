# Research — pool-field tabs and target-type override

## 1. What is already delivered (baseline, do not re-plan)

Verified against the code on this branch. Cited by module and symbol, never line number.

### Backend — covers FR-001..FR-006

| Symbol | Behaviour |
|---|---|
| `backend/infrahub/graphql/types/attribute.py::IPAddressPoolInput` | gained `address_type`. `IPPrefixPoolInput` already had `prefix_type`. |
| `backend/infrahub/core/node/resource_manager/kind_validation.py::validate_allocated_kind` | generic peer → requested type must be in the peer's `used_by`; concrete peer → must equal it; `peer_kind is None` stays unconstrained. Reads the peer on the allocation's own branch. |
| `backend/infrahub/core/node/resource_manager/reservation.py::validate_reserved_kind` | mirrors `validate_reserved_prefix_length`: a reservation keeps the type it was allocated with. |
| `backend/infrahub/core/relationship/model.py::Relationship.resolve` | passes `peer_kind=self.schema.peer`, guarded to IP pool kinds via `get_labels()` so `CoreNumberPool.get_resource` never receives the kwarg. |
| `backend/infrahub/graphql/mutations/resource_manager.py` | the standalone allocate mutations pass the builtin IP generic, so that path is validated too. |

Two decisions worth preserving because they are easy to "fix" wrongly later:

- **Only the caller's explicit type is validated, never the pool's configured default.**
  Validating after the `or default_*_type` fallback would newly reject pools whose default is
  outside the peer's `used_by`, breaking working setups.
- **Validation happens on the reservation path too**, against the *reserved node's* type, because
  a reservation created under a permissive peer could otherwise be reused on a stricter one.

### Frontend — covers FR-007..FR-022

- `ui/tabs.tsx` — Radix wrapper with two variants. `underline` is the pre-existing look (still
  used by `relationship-hierarchical-input.tsx`'s All/Explore tabs); `field` is full width, with
  the rule drawn by *inactive* triggers and the active one boxed on all sides but the bottom.
- `form/field-tabs.tsx` — `FieldTabs*` wrappers pinning the `field` variant and panel spacing, so
  the strip cannot drift between the five fields. Mirrors the existing `PopoverTabs*` precedent.
- `form/pool-allocation-panel.tsx` — the shared "From pool" panel: pool on its own line, then the
  mask and type overrides sharing the next line. `empty:hidden` on that row so it occupies no
  space before a pool is chosen.
- `inputs/pool-select.tsx` — split into `PoolCombobox`, `PoolPrefixLengthField`,
  `PoolKindOverrideField`. `PoolSelect` and the whole of `form/pool-selector.tsx` were deleted.
- All five pool-backed fields migrated. The pool channel converged on `field.pool`, with Number's
  prefetched pools normalised into `pool.options`.
- `getUpdateMutationFromFormData` already skips any field that deep-equals its default, which is
  what makes FR-021 hold once a tab switch restores the default instead of emptying the field.

### Deliberate reversal recorded during implementation

FR-017 originally required the opening mode to reflect provenance. It now requires the **value**
mode always, with provenance shown as a badge. The reason, observed in a browser against a real
allocated object: the pool mode exists to *stage* an allocation, so for a resolved one it showed
an empty pool picker, no overrides, and no sign of the allocated address. The value mode shows the
allocated object, its type, and a badge naming the pool — strictly more information.

## 2. Open decisions, resolved

### D1 — Rebase before or after the remaining work

**Decision: rebase first.**

**Rationale**: the branch is 71 commits behind `origin/develop` (`2e28611d65`). The drift covers
the same form area this branch rewrote — `form/fields/**`, `inputs/pool-select.tsx`,
`ui/popover.tsx` — and `form/pool-selector.tsx` was *deleted* here, which is exactly the shape of
change that conflicts badly. Doing the harness first would mean resolving those conflicts against
a larger diff and then re-verifying the UI a second time.

**Alternatives considered**: rebase last (rejected: same conflicts, later, with more to re-verify);
merge instead of rebase (rejected: the repo's `/rebase` workflow and history convention expect a
rebase); ship as-is and rebase in a follow-up (rejected: the PR cannot merge 71 commits behind).

**Risk**: the deletion of `form/pool-selector.tsx` will conflict if `develop` touched it. Check
`git log origin/develop -- frontend/app/src/shared/components/form/pool-selector.tsx` before
starting, and be ready to re-apply the deletion deliberately rather than accepting either side.

### D2 — One harness schema file, or a second

**Decision: extend `models/examples/ipam_kind_override.yml` and its data script.**

**Rationale**: the trial guide (`quickstart.md`) documents exactly one
`infrahubctl schema load` and one `infrahubctl run`. A second file would mean a second pair of
commands for every reader, to separate concerns that only a maintainer cares about.

**Alternatives considered**: a dedicated `ipam_pool_availability.yml` (rejected: doubles the setup
instructions); adding the shapes to `models/base/ipam.yml` (rejected: ships demo-only kinds into
the default dev schema).

**Consequence**: the file grows to roughly a dozen nodes. Group it with comments naming the matrix
row each shape unlocks, so it reads as a fixture rather than a pile of schema.

### D3 — Is `getFieldDefaultValue.ts` genuinely defective?

**Decision: treat as unknown; plan a spike, gated on the attribute schema shape.**

**Rationale**: `getFieldDefaultValue` has fallback paths that can return `source: {type:"user"}`
for an attribute whose value came from a pool. If that is reachable, FR-017's badge and mode are
both wrong for attribute fields. It is currently *unreachable by hand* — no demo node has a
pool-backed attribute — so the defect can be neither reproduced nor ruled out. The relationship
half of FR-017 is verified end-to-end; the attribute half is not.

**Both outcomes are planned for**: if reproducible, fix `getFieldDefaultValue` so an
attribute-sourced pool value reports `source.type === "pool"`, and add the missing regression
test. If not reproducible, document in spec.md precisely which code path made it look possible
and why it cannot be reached, so the next reader does not re-open the question.

**Alternatives considered**: fixing it blind (rejected: no way to prove the fix or its need);
dropping the concern (rejected: it silently misreports provenance, which FR-017 exists to prevent).

### D4 — How to reshape `tests/e2e/helpers.py::select_pool`

**Decision: absorb the tab click into the helper; leave all 8 call sites unchanged.**

**Rationale**: `select_pool()` encodes the old single-slot layout (click the pool button beside the
input, then pick a pool). Under tabs the same intent is "open the From pool tab, then pick a
pool". Putting that inside the helper keeps the 8 call sites across ~10 files untouched, so the
e2e diff stays proportional to the behaviour change rather than to the call count.

**Alternatives considered**: updating each call site (rejected: 8× the diff for no gain);
a new helper alongside the old one (rejected: the old one can no longer work, so leaving it is a
trap).

**Consequence**: assertions of the form `expect(page.get_by_label("Address *")).to_contain_text("Allocated by pool")`
still encode the old layout at the call sites and must be revisited individually — the helper
cannot absorb those.

## 3. Documentation imagery

The tutorial and guide e2e tests call `save_screenshot_for_docs`, so the images they produce
regenerate as a side effect of running them. That is a deliberate part of FR-024 rather than
collateral: the published screenshots currently show a pool button that no longer exists.
