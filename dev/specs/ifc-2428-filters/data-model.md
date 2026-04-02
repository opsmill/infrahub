# Data Model: Unified Filter Menu with Metadata Filters

## Entities

### Filter (existing, unchanged)

```typescript
type Filter = {
  name: string;  // format: "fieldName__filterType" (e.g., "status__value", "created_at__after")
  value: any;    // filter value (string, boolean, array of RelationshipNode, etc.)
};
```

**Storage**: URL query string parameter `filters` as JSON array, managed by `useFilters()` hook via `nuqs`.

### MetadataFilterDefinition (new)

Pseudo-schema objects that allow metadata fields to reuse existing filter form components.

```typescript
// Timestamp metadata filters (created_at, updated_at)
// Name uses node_metadata__ prefix so filters serialize correctly for the backend
const metadataDatetimeFilter: AttributeSchema = {
  name: string;       // "node_metadata__created_at" | "node_metadata__updated_at"
  label: string;      // "Created At" | "Updated At"
  kind: "DateTime";
  // remaining AttributeSchema fields with sensible defaults
};

// User reference metadata filters (created_by, updated_by)
const metadataUserFilter: RelationshipSchema = {
  name: string;       // "node_metadata__created_by" | "node_metadata__updated_by"
  label: string;      // "Created By" | "Updated By"
  peer: "CoreAccount";
  kind: "Attribute";
  cardinality: "one";
  // remaining RelationshipSchema fields with sensible defaults
};
```

**Backend GraphQL filter syntax**: `node_metadata__created_at__after`, `node_metadata__created_by__ids`, etc. The `node_metadata__` prefix is mandatory.

### FilterMenuItem (new)

Represents a single item in the filter menu.

```typescript
type FilterMenuItemType = "suggested" | "metadata" | "attribute" | "relationship";

type FilterMenuItem = {
  type: FilterMenuItemType;
  name: string;
  label: string;
  schema: AttributeSchema | RelationshipSchema;  // for attribute/relationship/metadata items
  // OR for suggested filters:
  onToggle?: () => void;  // direct toggle action
  isActive?: boolean;     // current toggle state
};
```

### SuggestedFilter (new)

```typescript
type SuggestedFilter = {
  id: string;
  label: string;
  isActive: boolean;
  onToggle: () => void;
};
```

## Relationships

- `Filter` ← stored in → URL query string (via `useFilters` hook)
- `FilterMenu` ← reads → `ModelSchema.attributes` + `ModelSchema.relationships` (existing schema)
- `FilterMenu` ← includes → `MetadataFilterDefinition[]` (static, all schemas)
- `FilterMenu` ← includes → `SuggestedFilter[]` (context-dependent, from parent component)
- `ActiveFilterTags` ← reads → `Filter[]` (from `useFilters` hook)
- `ActiveFilterTags` ← resolves display → via `fieldSchemas` map (existing) + metadata definitions (new)

## State Flow

```
User clicks Filter button
  → FilterMenu opens (Popover)
  → Menu lists: suggested filters, metadata, attributes, relationships
  → User hovers menu item
    → Side panel shows filter form (AttributeFilterForm or RelationshipFilterForm)
  → User submits filter form
    → setFilters() called (useFilters hook)
    → URL query string updated
    → Table query re-fetches with new filters
    → Active filter tag appears below toolbar
  → User clicks active filter tag
    → Popover opens with pre-filled filter form
    → User modifies and submits
  → User clicks remove icon on tag
    → Filter removed from state
    → URL updated, table re-fetches
```
