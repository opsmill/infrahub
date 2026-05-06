# Schema & Data migration — content review

Companion to `2026-05-schema-doc-migration.md`. For each new file, this documents the source, what changed, and what to focus on during review.

---

## Fully new content

| File | What it is |
|---|---|
| `schema/index.mdx` (35 lines) | Written from scratch. Hub page: 2-paragraph intro, building blocks list (4 types with links), video embed, "In this section" nav list. Nothing carried from source files except the video URL. |

---

## Full content lifts — link updates only

Direct copies of existing topic files. Content, structure, and prose are identical to the source. The only changes are updated cross-links (e.g. `./schema.mdx` → `./index`, `../guides/import-schema.mdx` → `./create-and-load`).

| New file | Source | Notable link changes |
|---|---|---|
| `schema/extensions.mdx` (158 lines) | `topics/schema-extensions.mdx` | `./schema.mdx` → `./index`; `../guides/import-schema.mdx` → `./create-and-load` |
| `schema/field-visibility.mdx` (91 lines) | `topics/schema-display.mdx` | `./order-weight.mdx` → `./order-weight`; `./display_label.mdx` → `./display_label`; `./permissions-roles.mdx` → `../topics/permissions-roles` |
| `schema/display_label.mdx` (356 lines) | `topics/labels.mdx` | `./schema.mdx` → `./index`; HFID anchor → `./nodes-and-attributes#human-friendly-identifier-hfid`; `../guides/menu.mdx` → `../menu/` |
| `schema/order-weight.mdx` (335 lines) | `topics/order-weight.mdx` | `./schema.mdx` (relationship kinds ref) → `./relationships` |
| `schema/number-pool.mdx` (137 lines) | `topics/schema-attr-kind-number-pool.mdx` | No link changes needed |
| `schema/file-object.mdx` (155 lines) | `topics/file-object.mdx` | All `./` topic links prefixed with `../topics/`; `./schema.mdx` → `./index` |

---

## Extractions from `topics/schema.mdx` (1,293-line monolith)

Each file pulls one or more sections out of the source. An intro paragraph was added to each; h3 headings were promoted to h2. Source prose is verbatim unless noted.

| New file | Extracted sections from `schema.mdx` | What was added / dropped |
|---|---|---|
| `schema/branch-awareness.mdx` (71 lines) | "Branch support" (~55 lines) | **Added**: 2-sentence intro; "Restrictions" note (distilled from the migration page); "Related concepts" footer |
| `schema/hierarchy.mdx` (106 lines) | "Hierarchical mode" (~95 lines) | **Added**: 2-sentence intro; "Related concepts" footer |
| `schema/generics-and-inheritance.mdx` (252 lines) | "Nodes vs. Generics", "Generics", "Inheritance between generics and nodes", "Inherited properties" | **Added**: intro paragraph; moved "Reserved namespaces" admonition here (it was in the schema.mdx opening section); replaced inline computed-attribute link with `../computed-attributes/`; added "Related concepts" footer |
| `schema/relationships.mdx` (375 lines) | "Relationship kinds", Car/Person/Wheel example, "Direction and Identifier", "Common parent relationships" | **Added**: intro paragraph; "Related concepts" footer. Nothing dropped. |
| `schema/nodes-and-attributes.mdx` (277 lines) | "Node example", "Node attribute kinds", "Uniqueness constraints", "Display Label", "Human friendly identifier" | **Added**: intro paragraph; new "Menu placement" section (condensed from the Menu section in schema.mdx, with link to `../menu/`); cross-refs to Profiles and Templates. **Replaced**: full order_weight sub-section with a one-liner + link to `schema/order-weight` (no duplication). |
| `schema/migration.mdx` (144 lines) | "Schema update and data migrations", "Schema strict mode" | **Added**: intro sentence; "Related concepts" footer. Strict-mode closing paragraph slightly condensed. |

---

## Operational merge

| New file | Sources merged | What was dropped |
|---|---|---|
| `schema/create-and-load.mdx` (88 lines) | Primary: `guides/import-schema.mdx` (schema file format, infrahubctl load, git integration). Supplemented with: `infrahubctl schema check` command from the loading section of `schema.mdx` (missing from the guide). | Dropped the hands-on lab and tutorial sections — those live in the Academy tutorial now. **Added post-migration**: "Troubleshooting" section (YAML boolean coercion issue with Dropdown choice names) moved here from the tutorial; intro and prose lifted and polished. |

---

## Tutorial reframe

| New file | Source | What changed |
|---|---|---|
| `academy/tutorials/build-your-first-schema.mdx` (550 lines) | `guides/create-schema.mdx` | **Added**: "By the end of this tutorial you will have…" preamble. **Updated**: all internal links adjusted for the deeper directory level (`../../schema/`, `../../reference/`, `../../guides/`); VideoPlayer import path updated (`../../../src/`). All 4 steps, YAML examples, GraphQL mutations, and troubleshooting are verbatim. **Removed post-migration**: "Relationship best practices" section (content already present in `schema/relationships.mdx`); "Troubleshooting" section moved to `schema/create-and-load.mdx`. |

---

## What `topics/schema.mdx` content was not migrated

Two sections from the 1,293-line source were intentionally left out:

- **"Exploring the Infrahub Schema video"** — the video was moved to `schema/index.mdx`; the original intro context in `schema.mdx` is now redundant.
- **"Load a schema into Infrahub"** — absorbed into `schema/create-and-load.mdx`; the source section in `schema.mdx` can be removed in the Phase 2 cleanup.

---

## Sidebar changes (`docs/sidebars.ts`)

- **Schema & Data** — the flat `Schema` hub (pointing at `topics/schema`) replaced with 4 nested sub-categories: About Schema, Schema operations, Extended schema kinds, Display & presentation.
- **Computed Attributes** and **Menu Customization** — previously standalone entries at the top level of Schema & Data; now nested inside Extended schema kinds and Display & presentation respectively. No file changes.
- **Objects** — `topics/file-object` removed (it now lives as `schema/file-object` under Extended schema kinds).
- **Learn > Tutorials** — `academy/tutorials/build-your-first-schema` added as the first tutorial entry.
