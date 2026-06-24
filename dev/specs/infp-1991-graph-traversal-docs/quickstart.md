# Quickstart: Authoring the Graph Traversal Docs

How to create, preview, and validate the documentation pages for this feature.

## Prerequisites

- Repo set up (`uv sync --all-groups`).
- Familiarity with the Diátaxis split (Topic / Guide / Reference) and the docs style guide:
  - `docs/docs/development/docs.mdx` (doc types, MDX, screenshots)
  - `docs/docs/development/style-guide.mdx` (terminology, headings, capitalization)
  - `docs/docs/guides/AGENTS.md`, `docs/docs/topics/AGENTS.md`

## Files to create / edit

Create the section:

```text
docs/docs/graph-traversal/overview.mdx           # Topic
docs/docs/graph-traversal/topology-explorer.mdx  # Guide
docs/docs/graph-traversal/reference.mdx          # Reference
```

Edit for navigation + cross-links:

```text
docs/sidebars.ts                                            # register the section
docs/docs/development-resources/graphql/queries-and-mutations.mdx  # link to reference
docs/docs/schema/relationships.mdx                          # contextual link
docs/docs/objects/overview.mdx                              # contextual link
```

## Page skeleton (frontmatter)

Each MDX page starts with an h1-equivalent title in frontmatter, then an h1:

```mdx
---
title: Graph traversal
---

# Graph traversal

...
```

Tabbed examples (e.g. UI vs GraphQL) use the standard theme components:

```mdx
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
```

## Authoring rules (must follow)

- **Terminology** (research R6): "graph traversal" (concept), "path traversal" (two-node;
  UI menu label "Path Traversal"), "dependency discovery", "Topology Explorer";
  `InfrahubPathTraversal` / `InfrahubReachableNodes` in code font.
- **Reference values live only in `reference.mdx`** (FR-012); other pages link to it.
- **Match the shipped API exactly** — use `contracts/graph-traversal-reference.md`
  (defaults: depth 5/max 30, path-traversal paths 10/max 100, snake_case args, etc.).
- **No internal IDs in published content** — per `.agents/rules/code-doc-style.md`, do not put
  FR-IDs, `infp-1991`, or internal class names in the MDX (public GraphQL type names are fine).
- State the introducing version: **Infrahub 1.10.0** (FR-011).
- Keep screenshots minimal; reuse `docs/docs/media/release_notes/infrahub_1_10_0/path_traversal.png`
  where it fits (research R4).

## Preview locally

```bash
uv run invoke docs.serve     # serve the docs site for live preview
```

## Validate before pushing (gates — SC-004, FR-009)

```bash
uv run invoke docs.format    # auto-format markdown
uv run invoke docs.lint      # Vale + markdownlint — must be zero errors
uv run invoke docs.build     # build + link validation
```

CI also runs `uv run invoke docs.validate` (generated-doc staleness). The new pages are
hand-authored (not generated), but run it to be safe before pushing.

## Definition of done (maps to spec Success Criteria)

- A reader can run a path traversal and a dependency discovery using only these pages (SC-001).
- Every parameter/default/limit is documented and matches code; no contradictions (SC-002).
- Pages reachable from the sidebar and ≥1 related page within three clicks (SC-003).
- `docs.lint` + `docs.build` pass with zero errors (SC-004).
- Edge-case behaviors described match actual behavior (SC-005).
- Pages state they describe Infrahub 1.10.0; no unshipped behavior (SC-006).
