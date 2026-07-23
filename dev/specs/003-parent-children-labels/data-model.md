# Phase 1 Data Model: Peer-derived labels for hierarchical parent/children relationships

No new data is created or persisted. This feature reads existing schema types already loaded client-side. The "model" here is the set of existing fields the resolver depends on.

## Existing types consumed (read-only)

### `RelationshipSchema` (generated — `frontend/app/src/shared/api/rest/types.generated.ts`)

| Field | Type | Role in this feature |
|-------|------|----------------------|
| `name` | `string` | Final fallback for the display label. |
| `label` | `string \| null` | Existing display label ("Parent"/"Children"); used when not hierarchical or peer label absent. |
| `peer` | `string` | Kind of the related object; used to resolve the peer schema whose label we surface. |
| `hierarchical` | `string \| null` | **Discriminator** — truthy (the hierarchy generic kind) exactly on the auto-generated parent/children relationships. |
| `cardinality` | `"one" \| "many"` | Not branched on; parent is `one`, children is `many`. Label used verbatim regardless. |

### `ModelSchema` (peer schema — `frontend/app/src/entities/schema/domain/model/schema.ts`)

`NodeSchema | GenericSchema | ProfileSchema | TemplateSchema`, resolved from `peer` via existing `resolveSchema`/`useSchema`/`getSchema`.

| Field | Type | Role |
|-------|------|------|
| `label` | `string \| null` | The value surfaced in place of "Parent"/"Children" when present. |

## New unit of logic

### `getRelationshipFieldLabel` (pure rule)

- **Location**: `frontend/app/src/entities/schema/domain/rules/get-relationship-field-label.ts`
- **Signature**: `(relationshipSchema: RelationshipSchema, peerSchema?: ModelSchema | null) => string`
- **Behavior**:
  1. If `relationshipSchema.hierarchical` is truthy **and** `peerSchema?.label` is present **and** `peerSchema` is a concrete node (not a generic, via `isGenericSchema`) → return `peerSchema.label`.
  2. Otherwise → return `relationshipSchema.label ?? relationshipSchema.name`.
- **Purity**: no store access, no side effects; peer schema is supplied by the caller.
- **Invariants**:
  - Non-hierarchical relationships are behaviorally identical to the inline `label ?? name` expression it replaces (guarantees SC-002).
  - When the peer is a generic, the generic "Parent"/"Children" label is kept (a generic's label is too broad to identify the related kind).
  - Never returns empty/undefined — `name` is always a string fallback.

## State / lifecycle

None. No state transitions; pure derivation on each render.
