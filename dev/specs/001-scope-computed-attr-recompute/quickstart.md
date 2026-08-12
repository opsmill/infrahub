# Quickstart / Test Scenarios: Scope Computed-Attribute Recompute

**Date**: 2026-06-03 (regenerated for Session 2026-06-03 clarifications)
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

How to validate the feature. Maps each spec user story / success criterion to a concrete test. Reuse existing fixtures where noted. Scenarios H and J are **mandatory** under Constitution Principle II (branch-safe / merge tested).

## Test placement

| Level | Location | What it covers |
|-------|----------|----------------|
| Unit | `backend/tests/unit/computed_attribute/` | `RecomputeScoper.scope()` logic; `PythonTransformDependencyDeriver` query parsing — no DB. |
| Component | `backend/tests/component/computed_attribute/` | Setup flows select the right attributes against a real `SchemaBranch` + DB. Reuse `schema_with_jinja2` from `test_local_computation.py`. |
| Integration (docker) | `backend/tests/integration_docker/test_computed_attributes.py` | End-to-end: applying a schema change submits jobs only for impacted attributes; fallback, merge, branch isolation. |

## Scenario A — Unrelated schema change produces zero jobs (US1, SC-001)

1. Branch with a computed attribute `A.label` reading only fields of type `A`.
2. Apply a schema change touching only type `B` (nothing `A.label` reads).
3. **Assert**: `RecomputeScopingReport.selected` excludes `A.label`; it is in `skipped` with reason. Zero `process_*` jobs submitted for `A.label`.

## Scenario B — Recompute across a relationship, at depth (US2, FR-002, FR-004)

1. Computed attribute on type `A` whose value reads a field on a related type — direct (`{{ owner__name__value }}`) and, for transforms, deeper (`device.site.region.name`).
2. Apply a schema change modifying that field on the related/peer type.
3. **Assert**: `A`'s attribute is in `selected`; recompute submitted — including when the read is multiple relationship hops away.

## Scenario C — Definition edit recomputes (US2 #2, FR-003)

1. Edit the computed attribute's own definition (template or transform reference) in the schema.
2. **Assert**: the attribute is in `selected` (its own `kind.attribute` appears in `changed_fields`).

## Scenario D — Type added/removed (US2 #3, FR-005)

1. Computed attribute whose value reads type `C`.
2. Schema change adds or removes type `C`.
3. **Assert**: attribute selected (`read_kinds ∩ (added ∪ removed)`).

## Scenario E — Display-label dependency is conservative (US2 #4, FR-006)

1. Transform-based attribute whose query reads a related object's `display_label`.
2. Any change to that related type.
3. **Assert**: `DependencySet.depends_on_everything is True` for that related type → attribute selected.

## Scenario F — Template-based attribute on data-field change (US3, FR-009)

1. Template-based attribute reading field `X` (template unchanged).
2. Schema migration changes field `X`.
3. **Assert**: attribute recomputed. And: a change touching only fields the template does not read → not recomputed.

## Scenario G — Path-level fallback when diff unavailable (Edge cases, FR-008, SC-005)

1. Trigger recompute via a path with no changed-element set (`changed_elements is None`, e.g. `BranchDeletedEvent`).
2. **Assert**: `fallback_full_recompute is True`; behavior identical to pre-change (all candidates selected). Cover at integration level (branch deletion) in addition to unit/component.

## Scenario H — Branch isolation (FR-010, Principle II — MANDATORY)

1. Two branches each with computed attributes.
2. Schema change on branch 1.
3. **Assert**: branch 2's attributes are untouched; scoping applied only within branch 1's already-selected set. No recompute jobs target branch 2.

## Scenario I — Observability via task logs (FR-012, SC-006)

1. Apply any scoped schema change.
2. **Assert**: an info-level log records count + identities of selected attributes; a debug-level log lists skipped attributes with reasons.

## Scenario J — Merge / rebase path (Edge cases, FR-008, Principle II — MANDATORY)

1. Apply a schema change on a branch, then merge/rebase it.
2. **Assert (diff surfaced)**: recompute is scoped to impacted attributes on the merge path.
3. **Assert (diff not surfaced)**: `changed_elements is None` → full recompute (no regression vs current behavior).

## Scenario K — Per-attribute opaque dependency does not escalate (FR-013)

1. One transform-based attribute with an unanalyzable query (`depends_on_everything`) alongside a normally-scoped attribute, on the same branch.
2. Apply a schema change unrelated to the scoped attribute.
3. **Assert**: the opaque attribute is in `selected`; the unrelated scoped attribute is in `skipped`; `fallback_full_recompute is False` (no branch-wide full recompute).

## Scenario L — Work scales with impacted count (SC-003)

1. Branch with many computed attributes, only one of which reads field `X`.
2. Change field `X`.
3. **Assert**: exactly one attribute's worth of recompute jobs is submitted; submitted-job count is independent of the total number of computed attributes on the branch.

## Running

```bash
# Unit
uv run pytest backend/tests/unit/computed_attribute/ -x

# Component (DB via TestContainers)
uv run pytest backend/tests/component/computed_attribute/ -x

# Integration (full stack)
uv run invoke backend.test-integration
```

## Success-criteria coverage map

| Criterion | Scenario(s) |
|-----------|-------------|
| SC-001 zero jobs for unrelated change | A |
| SC-002 exactly N of M selected | A, B, F, K (selected/skipped disjoint + complete) |
| SC-003 work scales with impacted count | L |
| SC-004 no permanently stale values | B, C, D, E, F (integration, post-recompute assertions) |
| SC-005 no regression when diff unavailable | G, J |
| SC-006 operator can observe selected/skipped | I |
| FR-010 branch isolation (Principle II) | H |
| FR-008 merge path (Principle II) | J |
| FR-013 per-attribute opaque, no escalation | K |
