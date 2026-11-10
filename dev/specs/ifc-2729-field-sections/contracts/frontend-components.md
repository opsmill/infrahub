# Contract: frontend components for field sections

The new pieces, the props added to existing components, and the accessibility behaviour the tests
assert. Paths are under `frontend/app/src/`.

## Section partition rule

`entities/nodes/object/domain/rules/group-fields-by-section.ts::groupFieldsBySection`

```typescript
function groupFieldsBySection<T>(
  containers: ContainerSchema[] | null | undefined,
  items: T[],
  getContainer: (item: T) => string | null | undefined
): FieldSection<T>[];
```

Order and dropping rules: [data-model.md](../data-model.md#frontend-section-model). The detail view
and the form both call it, so both show the same sections in the same order.

## ObjectDetailsSections

`entities/nodes/object/ui/object-details/object-details-sections.tsx::ObjectDetailsSections` takes
the props of the plain card (`objectSchema`, `objectData`, `permission`, `excludeRelationships`).
It partitions the fields that `getDataDisplayFields` returns (the detail view's visibility rules,
sorted by order weight) and renders one `ObjectDetailsCard` per section with the full schema and
`fieldNames` set to the section's field names. The Details card gets no `section`; each
declared container's card gets that container as `section`. With no visible field, it
renders the plain card.

Callers: `ObjectDetails` (the object detail page) and the IPAM detail page. The repository,
GraphQL query and user profile pages keep `ObjectDetailsCard`.

## ObjectDetailsCard

`entities/nodes/object/ui/object-details/object-details-card.tsx::ObjectDetailsCard` gains two
optional props; a caller that passes neither renders as before.

```typescript
interface ObjectDetailsCardProps {
  // existing props unchanged
  fieldNames?: string[];                        // show only these fields of objectSchema
  section?: FieldSection<unknown>["container"]; // undefined: plain card; set: collapsible card
}
```

- `fieldNames`: the card keeps the full schema, so an attribute allocated from a resource pool
  still finds its `<name>_from_resource_pool` relationship.
- `section` undefined: the header is the title and the Extra button; the card has
  `data-testid="object-details"`.
- `section` set: the card is a react-aria `Disclosure` that starts open unless
  `section.collapsed` is true. The header is
  `CardHeader > [h2 > trigger button(chevron, label)] [p description] [Extra button]`. The trigger
  button has `aria-describedby` set to the description. The card has
  `data-testid="object-details-section"` and `data-section={section.name}`.
- The Extra button appears only when one of the card's fields has `display: extra`, and is hidden
  while the card is collapsed. Its state is local to the card.
- Collapsing is not stored; a reload restores the schema's `collapsed` value.

`getDataDisplayFields` in `object-data-display/object-data-display.tsx` is the one place that
applies the visibility rules, for the card, the sections and the data display.

## SectionTitle

`entities/nodes/object/ui/object-details/section-title.tsx::SectionTitle` takes `label`,
`description`, `titleId` and `descriptionId`. It renders the label in an `h2` and, when set, the
description as a muted `<p>` after the `h2`, never inside it. The detail card passes the trigger
button as the label; the form panel passes text. Both headers use it (FR-020).

## DynamicForm, DynamicFields and FormSectionPanel

`shared/components/form/dynamic-form.tsx`:

- `DynamicForm` gains an optional `sections?: ContainerSchema[]` prop and renders
  `DynamicFields`.
- `DynamicFields({ fields, sections })` partitions `fields` with the rule, reading each field's
  container from the schema attached to it (`field.relationship.container` or
  `field.attribute?.container`). Without `sections`, or when every field is in Details, it
  renders the flat list. Otherwise it renders one `FormSectionPanel` per section.
- `fields` stays the only source of default values and submitted data, so a sectioned form sends
  the same request as a flat one (FR-025).
- Panels are always expanded and have no Extra control. A section whose fields the form left out
  has no panel.

Callers that pass sections: `NodeForm` (`sections={schema.containers}`) and `CoreFileForm`
(`<DynamicFields fields={fields} sections={schema.containers} />`). Other forms pass none.

`shared/components/form/form-section-panel.tsx::FormSectionPanel` takes `label`, `description`
and `children`, and renders a `Card` with `variant="panel"`, `role="region"`, a `CardHeader` with
`SectionTitle`, and the fields in `CardContent`.

## Schema viewer

- `entities/schema/ui/schema-viewer.tsx`: a Containers block lists each container's name, label,
  order weight, collapsed flag and description; nothing is shown when the list is empty.
- `entities/schema/ui/attribute-display.tsx` and `relationship-display.tsx`: a Container row
  showing the container name or `-`.

## Accessibility

- Each detail card and each form panel is a `region` labelled by its `h2`, so tests find it by
  name: `Details` or the container label (`LACP`). The description is not part of the name.
- A collapsible card's trigger button is named by the container label and has `aria-expanded`.
  A non-collapsible card and a form panel have no button in the title.
- The Extra control is a button named `Extra`.
- Tests query by role and name (`getByRole("region", { name })`, `getByRole("button", { name })`),
  plus the `data-testid` values above.
