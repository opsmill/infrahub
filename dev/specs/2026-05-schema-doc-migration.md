# Schema & Data Documentation Migration Plan

## Context

The current schema documentation is fragmented across legacy `topics/` and `guides/` paths:
- `topics/schema.mdx` — a 1,293-line monolith covering every schema concept in a single file
- Several standalone topic files (`schema-extensions`, `schema-display`, `labels`, `order-weight`, `file-object`, `schema-attr-kind-number-pool`)
- Two how-to guides (`create-schema`, `import-schema`)
- Two already-migrated feature directories (`computed-attributes/`, `menu/`)

The goal is to reorganise everything under `docs/docs/schema/` using 4 sub-categories, expose the create-schema guide as an Academy tutorial, and leave existing files untouched while recording redirects.

---

## Target Structure

```
docs/docs/schema/               ← NEW directory (all files new)
  index.mdx                     About schema (hub, new content)
  nodes-and-attributes.mdx      extracted from topics/schema.mdx
  relationships.mdx             extracted from topics/schema.mdx
  generics-and-inheritance.mdx  extracted from topics/schema.mdx
  branch-awareness.mdx          extracted from topics/schema.mdx
  hierarchy.mdx                 extracted from topics/schema.mdx
  extensions.mdx                from topics/schema-extensions.mdx
  create-and-load.mdx           merged from guides/import-schema.mdx + schema.mdx loading sections
  migration.mdx                 from topics/schema.mdx update/strict-mode sections
  number-pool.mdx               from topics/schema-attr-kind-number-pool.mdx
  file-object.mdx               from topics/file-object.mdx
  field-visibility.mdx          from topics/schema-display.mdx
  display_label.mdx                    from topics/display_label.mdx
  order-weight.mdx              from topics/order-weight.mdx

docs/docs/academy/tutorials/
  build-your-first-schema.mdx   from guides/create-schema.mdx (reframed as tutorial)

docs/redirects-pending/
  schema.yml                    NEW redirect tracking file
```

Existing files untouched: `topics/schema.mdx`, `topics/schema-extensions.mdx`, `topics/schema-display.mdx`, `topics/display_label.mdx`, `topics/order-weight.mdx`, `topics/file-object.mdx`, `topics/schema-attr-kind-number-pool.mdx`, `guides/create-schema.mdx`, `guides/import-schema.mdx`, `computed-attributes/index.mdx`, `menu/index.mdx`.

---

## Sidebar (`docs/sidebars.ts`) — Schema & Data section

The current flat `Schema` hub (pointing at `topics/schema`) is replaced with 4 nested sub-categories. The rest of Schema & Data (Resource Manager, IPAM, Objects, Groups, Profiles) is unchanged.

```typescript
{
  type: 'category',
  label: 'Schema & Data',
  collapsible: false,
  collapsed: false,
  link: { type: 'generated-index', slug: 'schema-and-data' },
  items: [
    // ── About Schema ──────────────────────────────────────
    {
      type: 'category',
      label: 'About Schema',
      link: { type: 'doc', id: 'schema/index' },
      items: [
        'schema/nodes-and-attributes',
        'schema/relationships',
        'schema/generics-and-inheritance',
        'schema/branch-awareness',
        'schema/hierarchy',
        'schema/extensions',
      ],
    },
    // ── Schema operations ─────────────────────────────────
    {
      type: 'category',
      label: 'Schema operations',
      link: { type: 'generated-index' },
      items: [
        'schema/create-and-load',
        'schema/migration',
      ],
    },
    // ── Advanced schema features ─────────────────────────────
    {
      type: 'category',
      label: 'Advanced schema features',
      link: { type: 'generated-index' },
      items: [
        { type: 'doc', id: 'computed-attributes/index', label: 'Computed attributes' },
        { type: 'doc', id: 'schema/number-pool', label: 'Number pools' },
        { type: 'doc', id: 'schema/file-object', label: 'File objects' },
      ],
    },
    // ── Display & presentation ────────────────────────────
    {
      type: 'category',
      label: 'Display & presentation',
      link: { type: 'generated-index' },
      items: [
        'schema/field-visibility',
        'schema/display_label',
        'schema/order-weight',
        { type: 'doc', id: 'menu/index', label: 'Menu customization' },
      ],
    },
    // ── rest unchanged (Resource Manager, IPAM, Objects, Groups, Profiles) ──
  ],
},
```

Learn > Academy > Tutorials also gains:
```typescript
'academy/tutorials/build-your-first-schema',
```

---

## Content extraction map

| New file | Source sections |
|---|---|
| `schema/index.mdx` | New: ~60-line intro. Draw from `schema.mdx` opening paragraphs + "Node, Attributes, Relationships, and Generics" definitions. Include video embed. Scannable, navigational — no deep content. |
| `schema/nodes-and-attributes.mdx` | From `topics/schema.mdx`: "Nodes vs. Generics", "Node example", "Node attribute kinds", "Attribute parameters", "Uniqueness constraints", "Display Label", "Human friendly identifier (hfid)". Include a short paragraph on `include_in_menu`/`menu_placement`/`icon` with link to `menu/index`. Mention `order_weight` briefly with link to `schema/order-weight`. Add cross-refs to Profiles and Templates (object-template). |
| `schema/relationships.mdx` | From `topics/schema.mdx`: "Relationship kinds", "Direction and Identifier in relationships", "Common parent relationships". Add intro paragraph. |
| `schema/generics-and-inheritance.mdx` | From `topics/schema.mdx`: "Generics" concept, "Inheritance between generics and nodes" (basic/single/multiple/restricted), "Inherited properties". Add intro paragraph. |
| `schema/branch-awareness.mdx` | From `topics/schema.mdx`: entire "Branch support" section. Add intro paragraph. |
| `schema/hierarchy.mdx` | From `topics/schema.mdx`: entire "Hierarchical mode" section. Add intro paragraph. |
| `schema/extensions.mdx` | Full content of `topics/schema-extensions.mdx`. Add intro paragraph if needed. |
| `schema/create-and-load.mdx` | Purely operational: merge `guides/import-schema.mdx` (primary) with the "Load a schema into Infrahub" section from `topics/schema.mdx` (infrahubctl + Git integration). No hands-on authoring content — that lives in the Academy tutorial. |
| `schema/migration.mdx` | From `topics/schema.mdx`: "Schema update and data migrations" section only. Cross-ref to `reference/schema/validator-migration`. "Schema strict mode" moved to `reference/schema-validation.mdx`. |
| `schema/number-pool.mdx` | Full content of `topics/schema-attr-kind-number-pool.mdx`. |
| `schema/file-object.mdx` | Full content of `topics/file-object.mdx`. |
| `schema/field-visibility.mdx` | Full content of `topics/schema-display.mdx`. |
| `schema/display_label.mdx` | Full content of `topics/display_label.mdx`. |
| `schema/order-weight.mdx` | Full content of `topics/order-weight.mdx`. |
| `academy/tutorials/build-your-first-schema.mdx` | Based on `guides/create-schema.mdx`. Reframe with "By the end of this tutorial you will have…" preamble. Preserve all YAML examples. Redirect `guides/create-schema` → new tutorial URL. |

---

## Redirects (`docs/redirects-pending/schema.yml`)

```yaml
---
feature: Schema & Data
pr: TBD
description: |
  Section-wide migration of schema docs. topics/schema.mdx (1,293-line monolith) split
  into 6 concept pages + 2 operation pages under docs/schema/. Five standalone topic files
  moved. guides/create-schema extracted into an Academy tutorial.
  computed-attributes and menu stay in place; sidebar only re-nests them.

redirects:
  - from: /docs/topics/schema
    to: /docs/schema/
  - from: /docs/topics/schema-extensions
    to: /docs/schema/extensions
  - from: /docs/topics/schema-display
    to: /docs/schema/field-visibility
  - from: /docs/topics/order-weight
    to: /docs/schema/order-weight
  - from: /docs/topics/labels
    to: /docs/schema/display_label
  - from: /docs/topics/file-object
    to: /docs/schema/file-object
  - from: /docs/topics/schema-attr-kind-number-pool
    to: /docs/schema/number-pool
  - from: /docs/guides/create-schema
    to: /docs/academy/tutorials/build-your-first-schema
  - from: /docs/guides/import-schema
    to: /docs/schema/create-and-load

new_pages:
  - path: /docs/schema/
    title: About schema (hub)
  - path: /docs/schema/nodes-and-attributes
    title: Nodes & attributes
  - path: /docs/schema/relationships
    title: Relationships
  - path: /docs/schema/generics-and-inheritance
    title: Generics & inheritance
  - path: /docs/schema/branch-awareness
    title: Branch awareness
  - path: /docs/schema/hierarchy
    title: Hierarchy
  - path: /docs/schema/extensions
    title: Schema extensions
  - path: /docs/schema/create-and-load
    title: Create and load schema
  - path: /docs/schema/migration
    title: Schema migration
  - path: /docs/schema/number-pool
    title: Number pools
  - path: /docs/schema/file-object
    title: File objects
  - path: /docs/schema/field-visibility
    title: Controlling field visibility in the UI
  - path: /docs/schema/display_label
    title: Labels
  - path: /docs/schema/order-weight
    title: Order weight
  - path: /docs/academy/tutorials/build-your-first-schema
    title: Build your first schema (tutorial)

cross_links_to_update:
  - file: docs/docs/topics/schema.mdx
    current: ../guides/import-schema
    should_be: ../schema/create-and-load
  - file: docs/docs/topics/schema.mdx
    current: ../topics/order-weight
    should_be: ../schema/order-weight
  - file: docs/docs/topics/schema.mdx
    current: labels
    should_be: ../schema/display_label
  - file: docs/docs/overview/concepts.mdx
    current: ../guides/create-schema
    should_be: ../academy/tutorials/build-your-first-schema
  - file: docs/docs/reference/schema-validation.mdx
    current: ../guides/create-schema
    should_be: ../academy/tutorials/build-your-first-schema
```

---

## Decisions

1. **Video embed**: include the YouTube embed on `schema/index.mdx` (keep it as a learning resource on the hub page).
2. **Menu section in nodes-and-attributes**: include a short paragraph covering `include_in_menu`, `menu_placement`, and `icon` with a link to `menu/index.mdx` for the full operational guide.
3. **Order weight**: brief mention + link to `schema/order-weight` only — no duplicated YAML examples.
4. **Create and load scope**: purely operational (CLI commands + Git integration). The hands-on authoring approach lives exclusively in the Academy tutorial.

---

## Verification

```bash
uv run invoke docs.lint          # Vale + markdownlint — must pass clean
cd docs && npm run build         # Docusaurus build — must succeed with no broken links
```
