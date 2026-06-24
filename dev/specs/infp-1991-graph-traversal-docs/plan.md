# Implementation Plan: Graph Traversal Documentation

**Branch**: `docs-graph-traversal-infp-1991` | **Date**: 2026-06-24 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/infp-1991-graph-traversal-docs/spec.md`

## Summary

Author end-user documentation for the Graph Traversal feature shipped in Infrahub
**1.10.0** (JPD `infp-1991`). The feature exposes two top-level GraphQL queries —
`InfrahubPathTraversal` (paths between two objects) and `InfrahubReachableNodes`
(reachable objects of given kinds from one source) — and a **Topology Explorer** UI
(menu "Path Traversal", route `/path-traversal`, plus a "Trace from this object" action
on object detail pages). It is read-only, branch- and time-aware, permission-safe, and
also reachable by AI agents over the MCP server.

The deliverable is Diátaxis-structured MDX content in the existing Docusaurus site
(`docs/`): one **Topic** (explanation), one or more **Guides** (how-to for the Topology
Explorer, including dependency discovery), and **Reference** material for the two GraphQL
queries (parameters, defaults, limits). Plus sidebar registration and contextual
cross-links from related existing pages. No product code changes.

## Technical Context

**Language/Version**: MDX (Markdown + JSX) on Docusaurus; content authored against Infrahub 1.10.0 behavior
**Primary Dependencies**: Docusaurus docs site under `docs/`; Diátaxis framework (Tutorials/Guides/Topics/Reference); `@theme/Tabs`/`TabItem` for tabbed examples
**Storage**: N/A (static documentation files committed to the repo)
**Testing**: `uv run invoke docs.lint` (Vale + markdownlint), `uv run invoke docs.build` (link/build validation), `uv run invoke docs.validate` (generated-doc staleness, run in CI)
**Target Platform**: Published docs site (docs.infrahub.app)
**Project Type**: Documentation (content within the existing web application repo)
**Performance Goals**: N/A — measured by reader task-completion and discoverability (see spec Success Criteria), not runtime
**Constraints**: Must match shipped 1.10.0 behavior exactly; pass docs linters with zero errors; no duplication of reference values across pages; minimal fragile UI-step/screenshot coupling
**Scale/Scope**: ~3–4 new MDX pages (1 topic, 1–2 guides, 1 reference), 1 sidebar entry/category, ≥2 cross-links from existing pages, optional screenshots

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

This is a documentation-only feature. The code-oriented principles are satisfied vacuously
(no code is written) but constrain what the docs must *accurately describe*:

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Schema-Driven Integrity | N/A | No code/schema change. Docs must not imply traversal writes data — it is read-only. |
| II. Branch-Safe by Default | PASS (described) | Docs MUST explain traversal is branch- and time-aware (only edges active on the current branch/time are followed) per FR-005. |
| III. Type Safety & Explicit Contracts | PASS (described) | Reference page MUST match the GraphQL contract exactly (param names, types, defaults). Source of truth: `backend/infrahub/graphql/queries/path.py` + `schema/schema.graphql`. |
| IV. Test Discipline | PASS | "Tests" for docs = linters + build + link checks. `docs.lint` and `docs.build` MUST pass (FR-009, SC-004). |
| V. Query Performance & Efficiency | N/A | No queries authored. Docs accurately state the depth/path bounds that protect performance. |
| VI. Security & Input Boundaries | PASS (described) | Docs MUST state traversal is permission-safe: a path crossing an unreadable object is dropped entirely, not leaked. |
| VII. Simplicity & Maintainability | PASS | Reuse existing docs sections, components, and patterns. Single authoritative location for reference values (FR-012). No new docs tooling. |

**Code Quality Gate — Changelog**: Per the constitution, every user-facing change includes a
Towncrier fragment in `changelog/`. The graph traversal *feature* already shipped in 1.10.0;
this docs work is not a new user-facing product change, so a changelog fragment is likely
**not** required — flagged for confirmation in research.md (Decision R5).

### Frontend principles (apply when feature includes UI)

**Not applicable** — no UI code is created. The documentation *describes* the existing
Topology Explorer UI but adds no React components, hooks, or pages. The Shared Components
Inventory is therefore omitted.

## Project Structure

### Documentation (this feature — the spec-kit artifacts)

```text
specs/infp-1991-graph-traversal-docs/
├── plan.md              # This file (/speckit-plan output)
├── spec.md              # Feature specification
├── research.md          # Phase 0 output: placement, page split, version, screenshots, changelog
├── data-model.md        # Phase 1 output: page content inventory (page → FRs → source of truth)
├── quickstart.md        # Phase 1 output: how to author/preview/lint docs locally
├── contracts/           # Phase 1 output: the GraphQL-reference contract the docs MUST match
│   └── graph-traversal-reference.md
├── checklists/
│   └── requirements.md  # Spec quality checklist (from /speckit-specify)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Deliverable Content (repository `docs/`)

The deliverable is a new dedicated docs section plus navigation and cross-links. Exact
filenames confirmed in research.md (Decision R1/R2):

```text
docs/
├── docs/
│   ├── graph-traversal/                 # NEW dedicated section
│   │   ├── overview.mdx                 # TOPIC: what graph traversal is, concepts, limits (FR-001, FR-005)
│   │   ├── topology-explorer.mdx        # GUIDE: use the Topology Explorer UI end-to-end (FR-002, FR-006)
│   │   └── reference.mdx                # REFERENCE: the two queries, params, defaults (FR-003, FR-004, FR-007, FR-012)
│   ├── development-resources/
│   │   └── graphql/
│   │       └── queries-and-mutations.mdx   # EDIT: cross-link to graph-traversal reference (FR-008)
│   ├── schema/
│   │   └── relationships.mdx               # EDIT: contextual cross-link (FR-008)
│   ├── objects/
│   │   └── overview.mdx                     # EDIT: contextual cross-link (FR-008)
│   └── media/
│       └── graph-traversal/                 # OPTIONAL screenshots (research.md R4)
└── sidebars.ts                              # EDIT: register the new section (FR-008)
```

**Structure Decision**: A **dedicated `docs/docs/graph-traversal/` section** is chosen over
burying the content under `development-resources/graphql/`. Rationale: the feature spans a
headline UI (Topology Explorer) *and* an API, mirroring how other cross-cutting features get
their own section (`branches/`, `objects/`, `groups/`, `ipam/`). A single section keeps the
topic, guide, and reference together so reference values live in one authoritative place
(FR-012, SC-002), while a cross-link from the existing GraphQL queries page preserves
discoverability for API users (FR-008). The alternative (all under `graphql/`) is recorded in
research.md and rejected for under-serving the UI and scattering the concept.

## Complexity Tracking

> No constitution violations. No new dependencies, abstractions, or docs tooling introduced.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| (none) | — | — |
