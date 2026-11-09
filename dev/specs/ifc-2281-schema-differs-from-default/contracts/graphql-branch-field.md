# Contract: Branch `schema_differs_from_default_branch` GraphQL field

The externally observable contract for this feature is the GraphQL schema. Both the legacy
`Branch` type and the `InfrahubBranch` type gain a new field; the old field is marked deprecated
on both. This contract is verified against the regenerated `schema/schema.graphql` and via
introspection.

## `Branch` (legacy query type)

Target shape after regeneration (`schema/schema.graphql`, Branch type ~L233-246):

```graphql
type Branch {
  branched_from: String
  created_at: String
  description: String
  graph_version: Int
  has_schema_changes: Boolean @deprecated(reason: "Use schema_differs_from_default_branch instead. has_schema_changes is scheduled for removal in Infrahub 1.14.0.")
  schema_differs_from_default_branch: Boolean
  id: String!
  is_default: Boolean
  is_isolated: Boolean @deprecated(reason: "non isolated mode is not supported anymore")
  name: String!
  origin_branch: String
  status: BranchStatus!
  sync_with_git: Boolean
}
```

## `InfrahubBranch` (paginated query type)

Target shape after regeneration (`schema/schema.graphql`, InfrahubBranch type ~L8827-8839):

```graphql
type InfrahubBranch {
  branched_from: NonRequiredStringValueField
  created_at: String
  description: NonRequiredStringValueField
  graph_version: NonRequiredIntValueField
  has_schema_changes: NonRequiredBooleanValueField @deprecated(reason: "Use schema_differs_from_default_branch instead. has_schema_changes is scheduled for removal in Infrahub 1.14.0.")
  schema_differs_from_default_branch: NonRequiredBooleanValueField
  id: String!
  is_default: NonRequiredBooleanValueField
  is_isolated: NonRequiredBooleanValueField @deprecated(reason: "non isolated mode is not supported anymore")
  name: RequiredStringValueField!
  origin_branch: NonRequiredStringValueField
  status: StatusField!
  sync_with_git: NonRequiredBooleanValueField
}
```

## Behavioral contract

| # | Given | When (query) | Then | Spec ref |
|---|-------|--------------|------|----------|
| C1 | branch schema == default | `schema_differs_from_default_branch` | `false` | FR-001, US1-1 |
| C2 | branch uploaded own schema change | `schema_differs_from_default_branch` | `true` | US1-2 |
| C3 | untouched branch, default changed after | `schema_differs_from_default_branch` | `true` | US1-3 |
| C4 | any branch state | both fields in one query | identical values | FR-002, US1-4, SC-001 |
| C5 | any branch state | `has_schema_changes` | unchanged value (no breakage) | FR-003, SC-004 |
| C6 | introspection | inspect `has_schema_changes` on both types | `@deprecated` present, reason names replacement + 1.14.0 | FR-004/005, SC-002 |
| C7 | default branch | either field | `false` | Edge cases |
| C8 | mutation (`BranchCreate`/`BranchRebase`) payload | request `schema_differs_from_default_branch` | resolves correctly | FR-001 |

## Verification

- Regenerate: `uv run invoke schema.generate-graphqlschema`; the diff against
  `schema/schema.graphql` shows exactly the two added fields + two `@deprecated` annotations.
- Introspection query on `__type(name: "Branch")` and `__type(name: "InfrahubBranch")` returns
  `isDeprecated: true` and the `deprecationReason` for `has_schema_changes` (C6).
- A GraphQL query requesting both fields on assorted branch states returns equal values (C4).

## Non-contract (must NOT change)

- The `has_schema_changes` value or resolution logic (OOS-003).
- `SchemaAnalyzer.has_schema_changes()` and its callers (OOS-004).
- `schema/openapi.json` (field is GraphQL-only).
