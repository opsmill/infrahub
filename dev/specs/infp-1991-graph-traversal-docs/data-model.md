# Phase 1 Content Inventory: Graph Traversal Documentation

For a documentation feature, the "data model" is the **content inventory**: each deliverable
page, the sections it must contain, which functional requirements it satisfies, and the
authoritative source for its facts. This is what `/speckit-tasks` turns into authoring tasks.

## Page 1 — Topic: `docs/docs/graph-traversal/overview.mdx`

**Type**: Explanation (understanding-oriented). **Title**: `Graph traversal`.
**Satisfies**: FR-001, FR-005, FR-010, FR-011. Anchors links for SC-003.

| Section | Content | Source of truth |
|---|---|---|
| Intro (1–2 sentences) | What graph traversal is and the problem it solves | release notes 1.10.0 |
| Introduced in | "Available since Infrahub 1.10.0" | research R3 |
| Path discovery vs dependency discovery | The two modes and when to use each | release notes; spec US1/US4 |
| Core concepts | path, hop, depth, path limit, shortest-first ordering | feature spec; `path.py` |
| Branch & time awareness | Only edges active on the current branch/time are followed | FR-005; constitution II |
| Permission safety | A path crossing an unreadable object is dropped entirely | release notes |
| Always-excluded namespaces | Core, Internal, Builtin, Lineage, Profile, Template | release notes |
| Where to go next | Links to the guide and reference; links from/to relationships, objects, branches | FR-008 |

**Validation rules**: Must not describe traversal as writing data (read-only). Must state the
version. Must link to the guide and reference. Terminology per research R6.

## Page 2 — Guide: `docs/docs/graph-traversal/topology-explorer.mdx`

**Type**: How-to (task-oriented). **Title**: verb-led, e.g. `Explore topology and trace paths`.
**Satisfies**: FR-002, FR-003, FR-006, FR-010.

| Section | Content | Source of truth |
|---|---|---|
| Opening | What you will accomplish; prerequisite (a running instance with data) | spec US2 |
| Open the Topology Explorer | Menu "Path Traversal" / route `/path-traversal` | `menu.py`; release notes |
| Path mode | Pick source & destination, read the path graph (hops, highlight a path, keyboard-step) | release notes; frontend |
| Dependency mode | Pick a source + target kinds; read reachable objects ("what depends on this?") | FR-003; release notes |
| Filtering & bounds | Filter by kind & namespace; adjust depth & path limits; note always-excluded namespaces | FR-004 (brief, links to reference) |
| Trace from an object | The "Trace from this object" action on object detail pages | release notes |
| What you'll see in edge cases | No path found; same source/destination; missing object; results hit the limit | FR-006; spec Edge Cases |
| Related | Links to overview (topic) and reference | FR-008 |

**Validation rules**: Reference values appear here only by **link** to the reference page, not
restated (FR-012). Keep UI-step coupling light (research R4).

## Page 3 — Reference: `docs/docs/graph-traversal/reference.mdx`

**Type**: Reference (information-oriented). **Title**: `Graph traversal reference`.
**Satisfies**: FR-004, FR-007, FR-012. Single authoritative location for values (SC-002).

| Section | Content | Source of truth |
|---|---|---|
| `InfrahubPathTraversal` | Purpose; every input param with type, default, allowed range; result shape (paths → hops → node+relationship); shortest-first | `contracts/graph-traversal-reference.md`; `path.py`; `schema/schema.graphql` |
| `InfrahubReachableNodes` | Purpose; inputs (`source_id`, `target_kinds`); result (reachable objects + shortest path each) | same |
| Defaults & limits table | max depth (default 5 / max 20), max paths (default 10), namespace exclusions | feature spec + **verify in code** |
| Programmatic example | A runnable GraphQL query (FR-007) | quickstart example, casing verified |
| Availability | Same queries usable over the MCP server | release notes |

**Validation rules**: Field names, casing, and defaults MUST match `schema/schema.graphql` /
`path.py` exactly — verify before publishing (research R7). This page is the only place values
are stated (FR-012).

## Navigation & cross-links (not a page; an integration)

**Satisfies**: FR-008, SC-003.

| Change | File | Detail |
|---|---|---|
| Register section | `docs/sidebars.ts` | Add a `graph-traversal` category (overview, topology-explorer, reference) in a logical position |
| Cross-link (API) | `docs/docs/development-resources/graphql/queries-and-mutations.mdx` | Link to the graph-traversal reference |
| Cross-link (concept) | `docs/docs/schema/relationships.mdx` | Link to the graph-traversal overview where relationships-as-traversable is relevant |
| Cross-link (concept) | `docs/docs/objects/overview.mdx` | Link to the overview / "Trace from this object" |

## Traceability: every FR maps to a deliverable

| FR | Deliverable |
|---|---|
| FR-001 | Topic: concepts + mode distinction |
| FR-002 | Guide: end-to-end Topology Explorer walkthrough |
| FR-003 | Guide: dependency mode |
| FR-004 | Reference: defaults & limits table |
| FR-005 | Topic: branch/time awareness |
| FR-006 | Guide: edge-case behaviors |
| FR-007 | Reference: programmatic GraphQL example |
| FR-008 | Sidebar entry + ≥2 cross-links |
| FR-009 | All pages pass `docs.lint` + `docs.build`; Diátaxis split |
| FR-010 | Terminology per research R6 across all pages |
| FR-011 | Topic states "since 1.10.0" |
| FR-012 | Reference is the single source of values; others link to it |
