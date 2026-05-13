# Plan: Migrate Objects & Object Templates docs

## Context

The V3 nav restructure introduced "Schema & Data" as a top-level section. Two sub-sections need to be wired up properly:

- **Object Templates** — currently lives as a legacy topic/guide pair (`topics/object-template.mdx` + `guides/object-template.mdx`). The sidebar shows a one-item category with no real hub. Needs to become a hub + 3 spokes that match the structured guide.
- **Objects** — currently uses `generated-index` as its hub (no real landing page). Needs a proper "About Objects" page that defines the concept.

Constraints: no content changes, no deletion of old pages, one genuinely new page (About Objects).

---

## Files to Create

### Object Templates

| File | Label in sidebar | Origin |
|------|-----------------|--------|
| `docs/docs/object-templates/index.mdx` | Object Templates (hub) | Content from `topics/object-template.mdx` |
| `docs/docs/object-templates/use.mdx` | Use object templates | 3 core sections from `guides/object-template.mdx` |
| `docs/docs/object-templates/with-profiles.mdx` | Assign Profiles to a template | Split from guide |
| `docs/docs/object-templates/allocate-resources-from-pools.mdx` | Allocate resources from pools | Split from guide |

### Objects

| File | Label in sidebar | Origin |
|------|-----------------|--------|
| `docs/docs/objects/index.mdx` | Objects (hub) | New content |
| `docs/docs/objects/convert-object-kind.mdx` | Convert object kind | Moved from `topics/object-conversion.mdx` |
| `docs/docs/objects/metadata.mdx` | Metadata & lineage | Moved from `topics/metadata.mdx` |
| `docs/docs/objects/load-from-yaml.mdx` | Load data in bulk using YAML file | Moved from `guides/object-load.mdx` |

---

## Files to Keep Unchanged (legacy)

- `docs/docs/topics/object-template.mdx`
- `docs/docs/guides/object-template.mdx`
- `docs/docs/topics/object-conversion.mdx`
- `docs/docs/topics/metadata.mdx`
- `docs/docs/guides/object-load.mdx`

---

## File to Modify

### `docs/sidebars.ts`

**Object Templates category** — replace `Templates` (hub: `topics/object-template`, one spoke) with:

```typescript
{
  type: 'category',
  label: 'Object Templates',
  link: { type: 'doc', id: 'object-templates/index' },
  items: [
    { type: 'doc', id: 'object-templates/use', label: 'Use object templates' },
    { type: 'doc', id: 'object-templates/with-profiles', label: 'Assign Profiles to a template' },
    { type: 'doc', id: 'object-templates/allocate-resources-from-pools', label: 'Allocate resources from pools' },
  ],
},
```

**Objects category** — replace `generated-index` hub with:

```typescript
{
  type: 'category',
  label: 'Objects',
  link: { type: 'doc', id: 'objects/index' },
  items: [
    { type: 'doc', id: 'objects/convert-object-kind', label: 'Convert object kind' },
    { type: 'doc', id: 'objects/metadata', label: 'Metadata & lineage' },
    { type: 'doc', id: 'objects/load-from-yaml', label: 'Load data in bulk using YAML file' },
  ],
},
```

---

## Execution Order

1. Create `docs/docs/object-templates/index.mdx`
2. Create `docs/docs/object-templates/use.mdx`
3. Create `docs/docs/object-templates/with-profiles.mdx`
4. Create `docs/docs/object-templates/allocate-resources-from-pools.mdx`
5. Create `docs/docs/objects/index.mdx`
6. Create `docs/docs/objects/convert-object-kind.mdx`
7. Create `docs/docs/objects/metadata.mdx`
8. Create `docs/docs/objects/load-from-yaml.mdx`
9. Update `docs/sidebars.ts`

---

## Verification

```bash
cd docs && node_modules/.bin/docusaurus build
```

- Schema & Data → Object Templates → hub page loads
- Each of the 3 spokes loads
- Schema & Data → Objects → hub page loads (not a generated index)
- All 3 Objects sub-pages present and linked
- Old `topics/object-template` and `guides/object-template` still accessible by direct URL
