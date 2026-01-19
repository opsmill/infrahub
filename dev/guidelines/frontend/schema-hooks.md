# Schema Hooks Guidelines

> Part of: `dev/guidelines/frontend/` | Index: [Frontend Guidelines](./README.md)

Guidelines for using the schema resolution hook in the React frontend.

## Overview

The `useSchema` hook provides type-safe access to Infrahub schemas with discriminated union return types for compile-time type narrowing. It supports both optional (nullable) and required (non-nullable) modes.

## Hook

### `useSchema(kind, options?)`

**Location:** `frontend/app/src/entities/schema/ui/hooks/useSchema.ts`

Hook for retrieving schemas by kind with optional required behavior.

**Signatures:**
```typescript
// Optional mode (nullable schema)
useSchema(kind: string | null | undefined, options?: { required?: false }): SchemaResult

// Required mode (non-nullable schema, throws if not found)
useSchema(kind: string, options: { required: true }): RequiredSchemaResult
```

**Return types:**

```typescript
// SchemaResult - includes null case
type SchemaResult =
  | { schema: NodeSchema; isNode: true; isGeneric: false; isProfile: false; isTemplate: false; }
  | { schema: GenericSchema; isGeneric: true; isNode: false; isProfile: false; isTemplate: false; }
  | { schema: ProfileSchema; isProfile: true; isNode: false; isGeneric: false; isTemplate: false; }
  | { schema: TemplateSchema; isTemplate: true; isNode: false; isGeneric: false; isProfile: false; }
  | { schema: null; isNode: false; isGeneric: false; isProfile: false; isTemplate: false; }

// RequiredSchemaResult - no null case, throws if missing
type RequiredSchemaResult =
  | { schema: ModelSchema; isNode: true; isGeneric: false; isProfile: false; isTemplate: false; }
  | { schema: ModelSchema; isGeneric: true; isNode: false; isProfile: false; isTemplate: false; }
  | { schema: ModelSchema; isProfile: true; isNode: false; isGeneric: false; isTemplate: false; }
  | { schema: ModelSchema; isTemplate: true; isNode: false; isGeneric: false; isProfile: false; }
```

---

## Usage

### Optional Mode (Default)

Use when the schema might not exist and you need to handle the null case.

**When to use:**
- Schema kind is dynamic or user-provided
- Schema may not exist
- Need to display error/fallback UI when schema is missing

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

### Required Mode

Use when the schema is guaranteed to exist and you want to fail fast if missing.

**When to use:**
- Built-in Core schemas (`CoreProposedChange`, `CoreBranch`, `CoreAccount`, etc.)
- System-level schemas that must exist
- Want to catch configuration/loading errors early

**Example:**
```typescript
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

function ProposedChangeDetails() {
  // No need to check for null - throws if schema not found
  const { schema, isNode } = useSchema("CoreProposedChange", { required: true });

  return <div>{schema.name}</div>;
}
```

**Key features:**
- Throws error if schema not found
- Returns non-nullable schema (no null case in discriminated union)
- Better type safety - no need for null checks
- Fail-fast behavior catches errors early

---

## Choosing Between Modes

| Scenario | Mode to use | Example |
|----------|-------------|---------|
| Core namespace schema (`CoreProposedChange`, `CoreBranch`, etc.) | `required: true` | `useSchema("CoreBranch", { required: true })` |
| User-defined schema kind from props/state | Optional (default) | `useSchema(userProvidedKind)` |
| Dynamic schema kind from URL params | Optional (default) | `useSchema(params.kind)` |
| Schema from user input/selection | Optional (default) | `useSchema(selectedKind)` |
| Built-in system schema | `required: true` | `useSchema("CoreAccount", { required: true })` |

---

## Type Narrowing Pattern

Both modes return discriminated unions with boolean flags for type narrowing:

```typescript
const { schema, isNode, isGeneric, isProfile, isTemplate } = useSchema(kind);

// Optional mode - check for null first
if (!schema) {
  return <NotFound />;
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

---

## Common Patterns

### Pattern: Core/System Schema Access

```typescript
// ✅ Good: Use required mode for Core schemas
const { schema } = useSchema("CoreProposedChange", { required: true });

// ❌ Bad: Using optional mode requires unnecessary null check
const { schema } = useSchema("CoreProposedChange");
if (!schema) return null; // This should never happen for Core schemas
```

### Pattern: Dynamic Schema Lookup

```typescript
// ✅ Good: Use optional mode for dynamic kinds
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

### Pattern: Required Mode with Core Schemas

```typescript
// ✅ Good: Core schemas with required mode
function BranchList() {
  const { schema } = useSchema("CoreBranch", { required: true });

  return <ObjectTable schema={schema} />;
}

// ✅ Good: Multiple Core schemas
function ProposedChangeWidget() {
  const { schema: pcSchema } = useSchema("CoreProposedChange", { required: true });
  const { schema: branchSchema } = useSchema("CoreBranch", { required: true });

  return <Widget schemas={{ pc: pcSchema, branch: branchSchema }} />;
}
```

---

## Migration from useCoreSchema

The deprecated `useCoreSchema` hook has been replaced by `useSchema` with `required: true`:

```typescript
// ❌ Old (deprecated)
import { useCoreSchema } from "@/entities/schema/ui/hooks/useCoreSchema";
const { schema } = useCoreSchema("CoreProposedChange");

// ✅ New
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
const { schema } = useSchema("CoreProposedChange", { required: true });
```

---

## Related

- `frontend/app/src/entities/schema/utils/resolve-schema.ts` - Core resolution logic
- `frontend/app/src/entities/schema/stores/schema.atom.ts` - Schema state management
- `dev/knowledge/frontend/entities-structure.md` - Entity layer architecture
