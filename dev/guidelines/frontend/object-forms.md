# Form Guidelines

> Part of: `dev/guidelines/frontend/`

Prescriptive rules for form handling with react-hook-form.

## Value Structure

All form fields use the `{ source, value }` structure to track data provenance.

### FormAttributeValue

```tsx
type FormAttributeValue =
  | { source: { type: "user" | "schema" }; value: string | number | boolean | null }
  | { source: { type: "profile"; id: string; kind: string; label: string | null }; value: ... }
  | { source: { type: "pool"; id: string; kind: string; label: string | null }; value: { from_pool: { id: string } } }
  | { source: { type: "template"; id: string; kind: string; label: string | null }; value: ... }
  | { source: null; value: null };  // Empty/unset
```

### Why Source Tracking?

The source indicates where a value came from:
- `user` - User entered the value directly
- `schema` - Default from schema definition
- `profile` - Inherited from a profile
- `pool` - Allocated from a resource pool
- `template` - Inherited from a template
- `null` - Field is empty/unset

This enables UI features like showing inheritance indicators and reset actions.

## Default Values

Always use `DEFAULT_FORM_FIELD_VALUE` for empty fields:

```tsx
import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";

const InputField = ({
  defaultValue = DEFAULT_FORM_FIELD_VALUE,
  ...
}: InputFieldProps) => { ... };
```

The constant is:
```tsx
{ source: null, value: null }
```

## Field Component Pattern

Form fields wrap react-hook-form's Controller via the `FormField` component.

### Structure

```tsx
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";
import { LabelFormField } from "@/shared/components/form/fields/common";

const MyField = ({ name, rules, defaultValue = DEFAULT_FORM_FIELD_VALUE, label, ...props }) => {
  return (
    <FormField
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      render={({ field }) => {
        const fieldData: FormAttributeValue = field.value;

        return (
          <div className="space-y-2">
            <LabelFormField
              label={label}
              required={!!rules?.required}
              fieldData={fieldData}
            />

            <FormInput>
              <Input
                {...field}
                value={fieldData?.value ?? ""}
                onChange={(e) => field.onChange(updateFormFieldValue(e.target.value, defaultValue))}
              />
            </FormInput>

            <FormMessage />
          </div>
        );
      }}
    />
  );
};
```

### Key Points

1. **FormField** - Wraps Controller, provides form context
2. **LabelFormField** - Renders label with source indicators
3. **FormInput** - Wrapper for input styling and error states
4. **FormMessage** - Displays validation errors
5. **updateFormFieldValue** - Wraps raw values in source structure

## Updating Values

Use the utility functions from `@/shared/components/form/utils/updateFormFieldValue`:

### updateFormFieldValue

For basic attribute values:

```tsx
onChange={(e) => field.onChange(updateFormFieldValue(e.target.value, defaultValue))}
```

This:
- Compares new value to default
- Returns default if unchanged (preserves source)
- Returns `{ source: { type: "user" }, value: newValue }` if changed

### updateAttributeFieldValue

For values that may come from pools:

```tsx
onChange={(poolValue) => field.onChange(updateAttributeFieldValue(poolValue, defaultValue))}
```

Handles pool allocation responses with `{ from_pool: { id } }` structure.

### updateRelationshipFieldValue

For relationship fields:

```tsx
onChange={(node) => field.onChange(updateRelationshipFieldValue(node, defaultValue))}
```

## Validation Rules

Use validator functions for consistent validation across the codebase. Validators follow the pattern of returning `{ success: true; data }` or `{ success: false; error }`:

```tsx
// Define validator (e.g., in src/entities/schema/utils/validation/)
function validateHostname(value: string) {
  if (!value?.trim()) return { success: false, error: "Hostname is required" };
  if (!/^[a-z0-9-]+$/.test(value)) return { success: false, error: "Invalid format" };
  return { success: true, data: value };
}

// Use in form with validate function
<InputField
  name="hostname"
  rules={{
    validate: (fieldData) => {
      const result = validateHostname(fieldData?.value ?? "");
      return result.success ? true : result.error;
    }
  }}
/>
```

This approach:
- Centralizes validation logic for reuse
- Provides consistent error handling
- Makes testing validators easier
- Separates concerns (validation from form binding)

## Forms with Profiles

Profiles allow users to pre-populate form fields with inherited values. Infrahub supports profile-based forms for creating objects with default values from selected profiles.

### Profile Pattern

For forms that support profiles, use the `*WithProfileForm` wrapper components:

```tsx
// For standard node forms
import { NodeWithProfileForm } from "@/shared/components/form/node-with-profile-form";

<NodeWithProfileForm
  schema={schema}
  profiles={currentProfiles}  // Optional: initial profiles
  onSuccess={handleSuccess}
/>
```

```tsx
// For file upload forms
import { FileWithProfileForm } from "@/shared/components/form/file-with-profile-form";

<FileWithProfileForm
  schema={schema}
  profiles={currentProfiles}
  onSuccess={handleSuccess}
/>
```

### ProfileData Type

Profiles extend `NodeCore` with a priority field:

```tsx
type ProfileData = NodeCore & {
  profile_priority?: { value: number | null };
  [key: string]: unknown;  // Dynamic attributes/relationships
};
```

### How Profile Forms Work

1. **Profile Selection** - The `ProfilesSelector` component renders at the top of the form:
   - Shows selected profiles as removable badges
   - Provides a combobox to add more profiles
   - Displays "optional" indicator in the label
   - Fetches available profiles via `useGetProfiles({ schema })`

2. **Value Inheritance** - When profiles are selected:
   - Form fields check for values in the selected profiles
   - Profile values populate as defaults with `source: { type: "profile", id, kind, label }`
   - User can override profile values (changes source to `"user"`)
   - Priority order determines which profile wins if multiple provide same field

3. **Form Submission** - Profile IDs are sent with the mutation:
   ```tsx
   createObject.mutateAsync({
     objectKind: schema.kind,
     data: newObject,
     profileIds: profiles?.map((profile) => profile.id),
   });
   ```

### Implementation Details

The wrapper components (`NodeWithProfileForm`, `FileWithProfileForm`) follow this pattern:

```tsx
export const NodeWithProfileForm = ({ schema, profiles, ...props }) => {
  const [selectedProfiles, setSelectedProfiles] = useState<ProfileData[] | undefined>();

  return (
    <>
      <ProfilesSelector
        schema={schema}
        defaultValue={profiles}
        value={selectedProfiles}
        onChange={setSelectedProfiles}
      />

      <NodeForm schema={schema} profiles={selectedProfiles} {...props} />
    </>
  );
};
```

Key points:
- Wrapper manages profile selection state
- `ProfilesSelector` handles UI and profile fetching
- Core form (`NodeForm`/`CoreFileForm`) receives selected profiles
- Profiles flow through `getFormFieldsFromSchema` to populate defaults

### When to Use Profile Forms

Use profile-based forms when:
- The schema supports profiles (check schema definition)
- Creating new objects (not for updates)
- Users benefit from reusable configuration templates
- Multiple objects share common field values

Examples: Network device configurations, user account templates, infrastructure patterns.

### Integration with ObjectForm

The `ObjectForm` router automatically selects the appropriate form:

```tsx
// In object-form.tsx
import { NodeWithProfileForm } from "@/shared/components/form/node-with-profile-form";
import { FileWithProfileForm } from "@/shared/components/form/file-with-profile-form";

// For FILE_OBJECT_KIND
if (isOfKind(schema, FILE_OBJECT_KIND)) {
  return <FileWithProfileForm schema={schema} profiles={currentProfiles} {...props} />;
}

// For standard nodes with profiles
if (isNode && !isGeneric) {
  return <NodeWithProfileForm schema={schema} profiles={currentProfiles} {...props} />;
}
```

### Best Practices

1. **Always pass profiles through** - Don't consume profiles at intermediate layers
2. **Use undefined for unselected** - Let `ProfilesSelector` initialize from defaultValue
3. **Show profile source** - The `LabelFormField` component displays profile inheritance indicators
4. **Allow overrides** - Users can always override profile values (changes source to "user")
5. **Test empty profiles** - Forms should work with zero profiles selected

## Focus Management

### AutoFocus Usage

Use `autoFocus` only for:
- Modal search inputs and first form fields
- Bulk operation inputs requiring immediate attention
- Dedicated search interfaces

Avoid in long forms, mobile contexts, or when multiple fields could compete for focus.

### Styling

Standard inputs use `focusVisibleStyle` from `@/shared/components/ui/style`:

```tsx
import { focusVisibleStyle, inputErrorStyle } from "@/shared/components/ui/style";

// Normal focus: blue ring
<input className={focusVisibleStyle} />

// Error focus: red ring
<input className={classNames(focusVisibleStyle, hasError && inputErrorStyle)} />
```

React Aria components use `data-focus-visible` variant from `@/shared/components/aria/style-rac`.

### Ref-Based Focus Control

**Number inputs** - Prevent scroll-to-change:

```tsx
const ref = usePreventScrollOnNumberInput();
<input type="number" ref={ref} />
```

**Modal initial focus** - Control dialog focus order:

```tsx
const focusRef = useRef(null);
<Dialog initialFocus={focusRef}>
  <button tabIndex={-1} ref={focusRef} />
  <input name="field" />
</Dialog>
```

**Dynamic focus** - Pool allocation toggle:

```tsx
const [override, setOverride] = useState(false);
<Input
  autoFocus={override}
  onBlur={() => setOverride(false)}
/>
```

### Dialog Focus

HeadlessUI Dialog and React Aria Modal provide automatic focus trap, restoration, and keyboard handling. Use `initialFocus` prop to control focus order.

### Best Practices

- Use `focus-visible` (not `focus`) to show outline only for keyboard navigation
- Let framework components (Dialog, Modal) handle focus management
- Style error states with red focus ring
- Test keyboard navigation (Tab order, focus trap, restoration)
