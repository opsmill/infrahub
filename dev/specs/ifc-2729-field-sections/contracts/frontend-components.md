# Contract: frontend components for field sections

Props added to existing components, the new pieces, and the accessibility behaviour the tests
assert. Paths are under `frontend/app/src/`.

## ObjectDetailsCard

`entities/nodes/object/ui/object-details/object-details-card.tsx::ObjectDetailsCard` gains two
optional props. Every existing caller passes neither and renders exactly as today.

```typescript
interface ObjectDetailsCardProps {
  objectSchema: ModelSchema;
  objectData: NodeObjectWithMetadata;
  permission: Permission;
  className?: string;
  excludeRelationships?: string[];
  title?: React.ReactNode;
  description?: string | null;   // new: muted text under the title, rendered when set
  defaultCollapsed?: boolean;    // new: undefined = not collapsible; true = starts collapsed
}
```

- `defaultCollapsed` undefined: the header is the current `h2` title plus the Extra button; the
  rows are always shown.
- `defaultCollapsed` defined: the card wraps its header and rows in a react-aria `Disclosure`.
  The `h2` holds the trigger button with the chevron and the container label only; the
  description renders as a `<p>` sibling under the header, outside the `h2` and the button, and
  the button carries `aria-describedby` pointing at it. The rows sit in a `DisclosurePanel`.
  `defaultCollapsed: true` starts with the panel closed; `false` starts open.
- The Extra button is rendered only when `hasExtraFields(objectSchema)` is true for the schema
  the card receives, so a card that receives a narrowed schema shows it only when that section has
  an `extra` field. Its state is local to the card.
- Collapsing is not stored; a page reload restores the schema's `collapsed` value.

The detail view (`object-details.tsx::ObjectDetails`) renders one card per section with
`objectSchema={{ ...objectSchema, attributes, relationships }}`, splitting the section's items with
`isRelationshipSchema`. The Details card passes no `defaultCollapsed`; the Advanced card passes
`defaultCollapsed: true`; a declared container passes its `collapsed` value.

## SectionTitle

`entities/nodes/object/ui/object-details/section-title.tsx::SectionTitle`

```typescript
interface SectionTitleProps {
  label: React.ReactNode;
  description?: string | null;
  titleId: string;
  descriptionId: string;
}
```

Renders the label with `id={titleId}` and, when `description` is set, the description as a muted
`<p>` sibling with `id={descriptionId}` under it, never inside the label element. The detail card
header and the form panel header both use it, so both show the same header (FR-020, FR-021), and
the collapsible card can point `aria-labelledby` at the label and `aria-describedby` at the
description.

## Section partition rule

`entities/nodes/object/domain/rules/group-fields-by-section.ts::groupFieldsBySection`

```typescript
function groupFieldsBySection<T>(
  containers: ContainerSchema[] | null | undefined,
  items: T[],
  getContainer: (item: T) => string | null | undefined
): FieldSection<T>[];
```

Order and dropping rules are in [data-model.md](../data-model.md#frontend-section-model). The
rule is pure: it does not filter, sort or copy the items. Callers:

- The detail view, with the attributes and relationships that pass the detail view's visibility
  rules, sorted by `sortByOrderWeight`, and `getContainer = (field) => field.container`.
- The form, with the `DynamicFieldProps[]` that `getFormFieldsFromSchema` built, and
  `getContainer = (field) => "relationship" in field ? field.relationship.container : field.attribute?.container`,
  written inline in `DynamicForm`; it returns `undefined` for a field built without a schema.

## DynamicForm

`shared/components/form/dynamic-form.tsx::DynamicForm` gains one optional prop.

```typescript
interface DynamicFormProps extends Omit<FormProps, "onSubmit"> {
  fields: Array<DynamicFieldProps>;
  sections?: ContainerSchema[];   // new: the schema's containers
  // other props unchanged
}
```

- `fields` stays the single source for default values and for the submitted data; `sections`
  changes the layout only, so the request a sectioned form sends is identical to the one the same
  fields send without sections (FR-025).
- `sections` undefined: the flat list of today. Every caller other than `NodeForm` passes nothing.
- `sections` defined but the partition yields only the Details section: the flat list, with no
  panel.
- Otherwise: one `FormSectionPanel` per section, Details first, then declared containers by
  `order_weight`, then Advanced. A section whose fields were all removed by the form's own
  filtering (read-only, bulk-update rules) renders no panel (FR-024). Every panel is expanded and
  cannot be collapsed, whatever `collapsed` says (FR-023).
- A validation error on a field is shown on that field inside its panel, as today.

`shared/components/form/node-form.tsx::NodeForm` passes `sections={schema.containers}`.

## FormSectionPanel

`shared/components/form/form-section-panel.tsx::FormSectionPanel`

```typescript
interface FormSectionPanelProps {
  label: React.ReactNode;
  description?: string | null;
  children: React.ReactNode;
}
```

Renders `Card` with `variant="panel"`, a `CardHeader` holding `SectionTitle` with ids the panel
generates, and a `CardContent` holding the fields. No Extra control: the form never filters
`display: extra` fields.

## Schema viewer

- `entities/schema/ui/schema-viewer.tsx`: a "Containers" block on a node, generic, profile or
  template panel listing each container's name, label, order weight, collapsed flag and
  description, with the existing `PropertyRow`; nothing is shown when the list is empty.
- `entities/schema/ui/attribute-display.tsx` and `entities/schema/ui/relationship-display.tsx`: a
  `Container` row next to the `Display` row, showing the container name or a dash when `null`.

## Accessibility contract

Detail view:

- Each card keeps `role="region"` and `aria-labelledby` pointing at its title, so a test can find
  the region by its accessible name: `Details`, the container label (`LACP`), or `Advanced`. The
  description is never part of that name.
- A collapsible card's title is a button inside the `h2` whose content is the chevron and the
  container label only, so its accessible name is the label, with `aria-expanded` reflecting the
  state; pressing it toggles the rows. A non-collapsible card has no button in its title.
- The container description is a `<p>` outside the `h2` and outside the button; the button's
  `aria-describedby` points at it, so a screen reader announces it as the description of the
  button, not as part of the name of the button, the heading or the region.
- The Extra control is a button named `Extra`, a sibling of the title in the header, never inside
  the trigger button. It is present only on a card whose section has a `display: extra` field.
- The chevron rotation uses the same reduced-motion classes as the repository activity card.

Form:

- Each panel is a region labelled by its header, so a test can find the `LACP` region and the
  field inside it. A form without sections has no region.
- Panel headers are not buttons. The description is a `<p>` sibling of the label, as in the detail
  card, and is not part of the region's name.

Tests assert through accessible roles and names (`getByRole("region", { name })`,
`getByRole("button", { name })`), not through class names or test ids, except the existing
`data-testid="object-details"` on the card, which stays.
