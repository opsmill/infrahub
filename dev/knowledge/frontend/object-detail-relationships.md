# Relationship Display on Object Detail Pages

> Part of: `dev/knowledge/frontend/` | Related: [Architecture](architecture.md), [E2E Tests Guide](../../guides/frontend/writing-e2e-tests.md)

## Tab vs Inline Rendering

Not all many-cardinality relationships get their own tab on object detail pages. The visibility is controlled by `src/entities/nodes/object/utils/get-relationships-visible-in-tab.ts`.

| RelKind     | Visible as tab? |
|-------------|----------------|
| Generic     | Yes            |
| Component   | Yes            |
| Hierarchy   | Yes            |
| Template    | Yes            |
| Attribute   | No (inline)    |
| Parent      | No (inline)    |

Additionally, `cardinality=one` relationships are always rendered inline regardless of kind, and resource pool relationships are excluded.

## Inline Relationships

Relationships that don't get tabs are rendered as rows in the Details panel by `RelationshipManyRow` in `src/entities/nodes/object/ui/object-details/object-data-display/object-relationship-row.tsx`:

- **Empty**: shows the label with a `-` value
- **Populated**: shows a list of peer links

## Hidden Tab Navigation

The `ObjectDetails` component (`src/entities/nodes/object/ui/object-details/object-details.tsx`) renders `ObjectDetailsTabContent` whenever a `tab` query string parameter is present, regardless of whether a visible tab exists for that relationship. This means any many-cardinality relationship can be managed via URL:

```
/objects/CoreWebhook/<id>?tab=headers
```

This is the only way to reach the relationship management view (add/remove peers) for `Attribute`-kind relationships.

## Tab Count Badge

Relationship tabs render the label and count as separate DOM elements:

```tsx
<ObjectDetailsTab>
  {relationshipSchema.label}        <!-- e.g. "Headers" -->
  <Badge>{relationshipCount}</Badge> <!-- e.g. "0" -->
</ObjectDetailsTab>
```

In Playwright, `getByText("Members0")` works because Playwright merges child text content. `getByText("Members 0")` with a space will NOT match.

## Key Files

- `src/entities/nodes/object/utils/get-relationships-visible-in-tab.ts` — tab visibility rules
- `src/entities/nodes/object/ui/object-details/object-details.tsx` — tab routing via `?tab=` param
- `src/entities/nodes/object/ui/object-tabs.tsx` — `RelationshipTab` component
- `src/entities/nodes/object/ui/object-details/object-data-display/object-relationship-row.tsx` — inline relationship rendering
