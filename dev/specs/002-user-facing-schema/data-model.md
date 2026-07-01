# Data Model: User-Facing Schema Separation

No database entities change. The "data model" here is the shape of the generated
schema models and the classification metadata that drives them.

## Visibility classification (new metadata)

- Added to `ExtraField` (the `extra={}` TypedDict in `internal.py`) as a `visibility`
  key alongside the existing `update` key.
- Value is an ordinal: `internal < read < write`.
- Default when unset: **internal** (a new field is hidden until deliberately promoted).
- Orthogonal to `update:` (post-create mutability). The two are independent axes.
- Authoritative per-field assignment: `schema-field-classification.md` (repo root).

### Membership rule

For a field classified at level `L`, it appears in a generated model of variant `V`
iff `V ⊇ L` under the ordering `write ⊆ read ⊆ internal`:

| Field level | write model | read model | internal model |
|-------------|:-----------:|:----------:|:--------------:|
| `write`     | ✅ | ✅ | ✅ |
| `read`      | ❌ | ✅ | ✅ |
| `internal`  | ❌ | ❌ | ✅ |

## Model families (generated)

Each of the four schema families is generated in three variants:

- **Node** — `node_schema` (+ shared `base_node_schema`)
- **Generic** — `generic_schema` (+ shared `base_node_schema`)
- **Attribute** — `attribute_schema`
- **Relationship** — `relationship_schema`

Variants:

- **Internal** *(existing)* — full field set; location unchanged
  (`backend/infrahub/core/schema/generated/`). Rich wrapper classes in
  `backend/infrahub/core/schema/*_schema.py` continue to extend these.
- **Write** *(new)* — only `write`-level fields; `extra="forbid"` retained so
  non-write fields are rejected. Generated into `python_sdk`.
- **Read** *(new)* — `write` + `read` fields; excludes `internal`. Generated into
  `python_sdk`. Carries the `kind`-injection behaviour (from `namespace`+`name`).

The base/derived split (`base_node_schema` → node/generic via `without_duplicates`)
is preserved per variant.

## Enum / allowed-value propagation

Fields carrying a known allowed-value set MUST publish it in the write/read models
(they are currently dropped to bare types). Sources:

| Field(s) | Family | Allowed-value source |
|----------|--------|----------------------|
| `kind` | attribute | `ATTRIBUTE_KIND_LABELS` (list) → `Literal[...]` / json_schema enum |
| `kind` | relationship | `RelationshipKind` (enum) |
| `cardinality` | relationship | `RelationshipCardinality` (enum) |
| `direction` | relationship | `RelationshipDirection` (enum) |
| `on_delete` | relationship | `RelationshipDeleteBehavior` (enum) |
| `branch` | base/attribute/relationship | `BranchSupportType` (enum) |
| `allow_override` | attribute/relationship | `AllowOverrideType` (enum) |
| `display` | attribute/relationship | `SchemaAttributeDisplay` (enum) |
| `state` | all | `HashableModelState` (enum) |

Enum-class-backed fields are typed as the enum; list-backed sets render a
`Literal[...]` (or `json_schema_extra={"enum": [...]}`) so the emitted JSON-schema
carries the values.

## Resolved field classification (summary)

Full table in `schema-field-classification.md`. Key resolved decisions:

- **write**: all core authoring fields; `read_only`, `identifier` (relationship),
  `state` (load directive), deprecated fields (`default_filter`, `display_labels`,
  attribute `regex`/`min_length`/`max_length`), and object `id` (used on existing
  objects to drive rename/delete).
- **read** (visible, not settable): `inherited` (attribute + relationship),
  `used_by` (generic), node `hierarchy`, relationship `hierarchical`.
- **internal** (never exposed): the parent back-reference from an attribute or
  relationship to its owning node.

## Invariants

- `write ⊆ read ⊆ internal` (no write-only field).
- Regeneration is idempotent (byte-stable output).
- The SDK write/read models import with no backend/server dependency.
- Server and SDK validate against the *same* generated models.
