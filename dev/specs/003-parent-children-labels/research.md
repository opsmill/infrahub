# Phase 0 Research: Peer-derived labels for hierarchical parent/children relationships

## Decision 1 — Discriminator: how to recognize a hierarchical parent/children relationship

**Decision**: Key off `relationshipSchema.hierarchical` being truthy.

**Rationale**: `RelationshipSchema.hierarchical` (`types.generated.ts`, "Internal attribute to track the type of hierarchy this relationship is part of, must match a valid Generic Kind") is set to the hierarchy generic's kind precisely on the auto-generated `parent`/`children` relationships and is `null` otherwise. It lives on the relationship object itself, so no site needs the containing node/generic schema — every render site already holds `relationshipSchema`. This is simpler and more robust than the two alternatives.

**Alternatives considered**:
- **`relationshipSchema.kind` in (`"Parent"`, `"Hierarchy"`)** — rejected. `kind: "Parent"` is also used for non-hierarchical component parent relationships, so it would over-match and rename normal relationships (violates FR-004). The two exploration passes also disagreed on the exact `kind` value stamped on the parent auto-rel, making it an unreliable discriminator.
- **Containing schema `isHierarchicalSchema()` + relationship name `parent`/`children`** — rejected. Correct, but forces several sites (C, F, I) to resolve and thread the containing schema they don't currently hold, for no gain over the `hierarchical` field.

## Decision 2 — Shape of the resolver

**Decision**: A pure function `getRelationshipLabel(relationshipSchema, peerSchema): string` where `peerSchema` is the already-resolved peer schema (or `undefined`).

```
getRelationshipLabel(relationshipSchema, peerSchema):
  if relationshipSchema.hierarchical && peerSchema?.label:
      return peerSchema.label
  return relationshipSchema.label ?? relationshipSchema.name
```

**Rationale**: Keeping it pure (peer passed in, not resolved inside) means the unit test needs no jotai store mock — it just passes plain schema objects (constitution IV/VII). It matches the codebase pattern: sites D, E, G, H already resolve the peer via `useSchema`/`resolveSchema` for icons, so they pass what they have. Sites that don't yet resolve the peer (C, F, I) add one cheap `useSchema(relationshipSchema.peer)` call (atom-backed, effectively free).

**Alternatives considered**:
- **Rule resolves the peer internally via `getSchema(peer)`** — rejected. Couples the pure rule to the global store, forces `vi.spyOn(store, "get")` mocking in tests, and duplicates a lookup most sites already do.

## Decision 3 — Fallback and non-hierarchical behavior

**Decision**: When `hierarchical` is falsy, or the peer schema / its `label` is missing, return today's `relationshipSchema.label ?? relationshipSchema.name`.

**Rationale**: Satisfies FR-002 (fallback to "Parent"/"Children") and FR-004 (non-hierarchical rels untouched — the guard is `hierarchical &&`, so they never enter the peer branch). Guarantees SC-002 (zero regression on non-hierarchical labels): for any non-hierarchical relationship the function is behaviorally identical to the inline expression it replaces.

## Decision 4 — Plurality for children

**Decision**: Use the peer label verbatim for both parent and children; no pluralization (per spec, Assumptions + FR-003).

**Rationale**: No reliable frontend pluralization primitive; naive `+ "s"` breaks on irregulars and non-English labels; constitution VII (don't build machinery for a cosmetic edge). A singular children label is still strictly more informative than "Children".

## Decision 5 — Scope of call sites

**Decision**: Route all relationship-label render sites through the new rule: A (detail row), B (metadata tooltip), C (relationship tab), D (IPAM tab), E (table column header), G (sort picker item), H (sortable-fields hook), I (filter form). Also apply to F (form field label) for consistency, accepting that it composes with the existing "Add "/"Remove " prefixes ("Add Region").

**Rationale**: The spec's five surfaces map onto sites A/B, C/D, E, I, G/H. Since all funnel through one helper, F is a low-cost consistency win and avoids a form saying "Add Parent" while the detail view says "Region". No shared helper exists today — the `label ?? name` pattern is duplicated inline in ~40 places; we only touch the relationship-label sites relevant to hierarchical parent/children.

**Alternatives considered**: Detail-view only — rejected during grilling; inconsistency across surfaces is worse than the original problem (FR-005).

## Decision 6 — Test strategy

**Decision**: Colocated Vitest unit test for the rule covering: hierarchical + peer label → peer label; hierarchical + no peer label → fallback; non-hierarchical (incl. a rel named `parent`) → unchanged; children (cardinality many) → verbatim peer label. Plus one Playwright E2E on a real hierarchical object (Location or IPAM prefix hierarchy in demo data) asserting the rendered label.

**Rationale**: Constitution IV mandates E2E for user-facing features ("not complete until E2E tests pass"). The pure rule is exhaustively unit-testable without a store mock; the E2E proves the wiring reaches at least the primary surface.

**Open item for implementation**: use a hierarchy whose parent and children peers are **distinct** kinds so the E2E assertion proves the peer label actually replaced "Parent"/"Children" (prefer a Location hierarchy such as `Region`→`Site`). Avoid a self-referential fixture like IPAM `IpamIPPrefix`, where parent and children both resolve to "Prefix" and the assertion would prove little (see spec Edge Cases — self-referential hierarchy).

**Discriminator validation (finding E3)**: as the first implementation step, verify that `relationshipSchema.hierarchical` is populated (truthy) on **both** the serialized `parent` and `children` auto-relationships. If only one carries it, extend the discriminator to also match the relationship `kind`/`name` for the other.
