# Data Model: Number pool details header

The work adds no entity and changes no stored data. The header reads existing fields and turns them into text.

## Number pool (`CoreNumberPool`, existing)

`GET_NUMBER_POOL` reads these fields, and `mapToNumberPoolData` turns them into `NumberPoolData` (see [research.md R1](research.md#r1-a-number-pool-page-that-loads-a-typed-number-pool-and-passes-it-down)).

| Field | Type | Values | Header use |
|-------|------|--------|-----------|
| `id` | string | UUID | Full ID with a copy button, Copy ID |
| `hfid` | string[] | `[name]` | Copy HFID |
| `name` | Text | any | Heading, cut to one line |
| `description` | Text | may be empty | Line under the heading, left out when empty |
| `pool_type` | Text, read-only | `"User"` or `"Schema"` | Managed-by tag, schema lock on Edit, Groups and Delete |
| `node` | Text | a kind name, such as `InfraAutonomousSystem` | "Allocates to `<kind>`", schema links |
| `node_attribute` | Text | an attribute name, such as `asn` | "attribute `<attribute>`", schema lock message |
| `allocation_scope` | List | `string[]` or `null` | Not shown; the UI does not handle allocation scopes yet |

The header does not read `start_range`, `end_range` or `ranges`.

## `NumberPoolData` (new domain type)

Location: `entities/resource-manager/domain/model/number-pool.ts`, next to the existing `NumberPool` type that the forms use.

It extends `NodeCore` and keeps the API field names with `NodeAttribute<T>` values, like `ProposedChangeDetail` and `ArtifactObject`, so it reads the same way as a `NodeObject`.

```ts
export interface NumberPoolData extends NodeCore {      // id, hfid, display_label, __typename
  __typename: typeof NUMBER_POOL_KIND;
  name: NodeAttribute<string>;                          // missing → ""
  description: NodeAttribute<string | null>;            // empty string → null
  pool_type: NodeAttribute<NumberPoolType>;             // "User" | "Schema"; any other value → "User"
  node: NodeAttribute<string>;                          // the kind the pool allocates to
  node_attribute: NodeAttribute<string>;                // the attribute of that kind
  allocation_scope: NodeAttribute<string[]>;            // null, or not a list of strings → []
}
```

The mapper (`api/number-pool.mappers.ts::mapToNumberPoolData`) fills the missing values above and narrows `allocation_scope`. Later work adds fields, such as the ranges, to this type.

## Schema of the pool's kind on the current branch (existing)

`useSchema(pool.node.value)` returns the schema of the kind, or `null` when the kind is not in the schema of the current branch.

| Field | Header use |
|-------|-----------|

The pool's own schema (`CoreNumberPool`) provides `documentation` for the Documentation menu item.

## Derived values

### Managed by

| `pool_type` | Tag | Tag target | Edit, Groups and Delete |
|-------------|-----|------------|-----------------|
| `"Schema"` | "Managed by schema" | Opens `SchemaViewerModal` for `node`, attributes tab, focused on `node_attribute` | Disabled: `Defined by the schema attribute <node>.<node_attribute>` |
| `"User"` | none | | Edit and Groups follow `permission.update`, Delete follows `permission.delete` |

### Schema references in the sentence

The kind and the attribute use the same style: medium weight with a dotted underline that turns solid on hover, the style of a link.

| Reference | Text | When selected |
|------|------|---------------|
| Kind | the kind name | `SchemaViewerModal` with the kind's schema |
| Attribute | the attribute name | `SchemaViewerModal`, attributes tab, focused on the attribute |

When the kind's schema is missing on the current branch, the reference is shown in medium weight, without an underline, and opens nothing.
