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
