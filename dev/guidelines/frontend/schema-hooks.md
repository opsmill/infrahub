# Schema Hooks Guidelines

> Part of: `dev/guidelines/frontend/` | Index: [Frontend Guidelines](./README.md)

Guidelines for using schema resolution hooks in the React frontend.

## Overview

Schema hooks provide type-safe access to Infrahub schemas with discriminated union return types for compile-time type narrowing.

## Hooks

### `useSchema(kind)`

**Location:** `frontend/app/src/entities/schema/ui/hooks/useSchema.ts`

General-purpose hook for retrieving any schema by kind. Returns a discriminated union that handles nullable schemas.

**When to use:**
- When the schema kind is dynamic or user-provided
- When the schema may or may not exist
- When you need to handle all schema types (node, generic, profile, template)

**Signature:**
```typescript
useSchema(kind: string | null | undefined): SchemaResult
```

**Return type:**
```typescript
type SchemaResult =
  | { schema: NodeSchema; isNode: true; isGeneric: false; isProfile: false; isTemplate: false; }
  | { schema: GenericSchema; isGeneric: true; isNode: false; isProfile: false; isTemplate: false; }
  | { schema: ProfileSchema; isProfile: true; isNode: false; isGeneric: false; isTemplate: false; }
  | { schema: TemplateSchema; isTemplate: true; isNode: false; isGeneric: false; isProfile: false; }
  | { schema: null; isNode: false; isGeneric: false; isProfile: false; isTemplate: false; }
```

**Example:**
```typescript
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

function MyComponent({ schemaKind }: { schemaKind: string | null }) {
  const { schema, isNode, isGeneric } = useSchema(schemaKind);

  if (!schema) {
    return <div>Schema not found</div>;
  }

  if (isNode) {
    // schema is typed as NodeSchema
    return <div>{schema.name}</div>;
  }

  // Handle other schema types...
}
```

**Key features:**
- Accepts `string | null | undefined` for flexibility
- Returns discriminated union for type-safe narrowing
- Schema can be `null` if not found or kind is nullish

---

### `useCoreSchema(kind)`

**Location:** `frontend/app/src/entities/schema/ui/hooks/useCoreSchema.ts`

Specialized hook for Core namespace schemas that are guaranteed to exist in the system.

**When to use:**
- For built-in Core schemas like `CoreProposedChange`, `CoreBranch`, `CoreAccount`, etc.
- When you know the schema must exist and want to avoid null checks
- When you want to fail fast if a Core schema is unexpectedly missing

**Signature:**
```typescript
useCoreSchema(kind: string): CoreSchemaResult
```

**Return type:**
```typescript
type CoreSchemaResult =
  | { schema: ModelSchema; isNode: true; isGeneric: false; isProfile: false; isTemplate: false; }
  | { schema: ModelSchema; isGeneric: true; isNode: false; isProfile: false; isTemplate: false; }
  | { schema: ModelSchema; isProfile: true; isNode: false; isGeneric: false; isTemplate: false; }
  | { schema: ModelSchema; isTemplate: true; isNode: false; isGeneric: false; isProfile: false; }
```

**Example:**
```typescript
import { useCoreSchema } from "@/entities/schema/ui/hooks/useCoreSchema";

function ProposedChangeDetails() {
  // No need to check for null - throws if schema not found
  const { schema, isNode } = useCoreSchema("CoreProposedChange");

  return <div>{schema.name}</div>;
}
```

**Key features:**
- Throws error if schema not found (Core schemas should always exist)
- Returns non-nullable schema (no null case in discriminated union)
- Provides better type safety for Core schema usage
- Fail-fast behavior catches configuration/loading errors early

---

## Choosing Between Hooks

| Scenario | Hook to use | Reason |
|----------|-------------|--------|
| Core namespace schema (`CoreProposedChange`, `CoreBranch`, etc.) | `useCoreSchema` | Guaranteed to exist, no null checks needed |
| User-defined schema kind from props/state | `useSchema` | May not exist, handle null case |
| Dynamic schema kind from URL params | `useSchema` | May be invalid, handle null case |
| Schema from user input/selection | `useSchema` | May not exist, handle null case |
| Built-in system schema | `useCoreSchema` | Should always exist, fail fast if missing |

## Type Narrowing Pattern

Both hooks return discriminated unions with boolean flags for type narrowing:

```typescript
const { schema, isNode, isGeneric, isProfile, isTemplate } = useSchema(kind);

if (!schema) {
  // Handle missing schema
  return null;
}

if (isNode) {
  // TypeScript knows schema is NodeSchema here
  const attributes = schema.attributes;
}

if (isGeneric) {
  // TypeScript knows schema is GenericSchema here
  const generics = schema.used_by;
}
```

**Best practice:** Check the most specific type first (e.g., `isNode` before falling back to generic checks).

## Common Patterns

### Pattern: Core Schema Access

```typescript
// ✅ Good: Use useCoreSchema for Core schemas
const { schema } = useCoreSchema("CoreProposedChange");

// ❌ Bad: Using useSchema requires unnecessary null check
const { schema } = useSchema("CoreProposedChange");
if (!schema) return null; // This should never happen for Core schemas
```

### Pattern: Dynamic Schema Lookup

```typescript
// ✅ Good: Use useSchema for dynamic kinds
function ObjectCard({ kind }: { kind: string | null }) {
  const { schema } = useSchema(kind);

  if (!schema) {
    return <div>Unknown object type</div>;
  }

  return <div>{schema.label || schema.name}</div>;
}
```

### Pattern: Schema Type-Specific Logic

```typescript
// ✅ Good: Use discriminated union flags
const { schema, isNode, isProfile } = useSchema(kind);

if (!schema) return null;

if (isNode) {
  // Access node-specific properties
  return <NodeForm schema={schema} />;
}

if (isProfile) {
  // Access profile-specific properties
  return <ProfileBadge schema={schema} />;
}
```

### Pattern: Multiple Schema Types

```typescript
// ✅ Good: Handle different schema types explicitly
const { schema, isNode, isGeneric, isProfile, isTemplate } = useSchema(kind);

if (!schema) {
  return <EmptyState message="Schema not found" />;
}

if (isNode || isGeneric) {
  // Both have similar properties
  return <ObjectDetails schema={schema} />;
}

if (isProfile || isTemplate) {
  // Different rendering for these types
  return <MetaObjectDetails schema={schema} />;
}
```

## Related

- `frontend/app/src/entities/schema/utils/resolve-schema.ts` - Core resolution logic
- `frontend/app/src/entities/schema/stores/schema.atom.ts` - Schema state management
- `dev/knowledge/frontend/entities-structure.md` - Entity layer architecture
