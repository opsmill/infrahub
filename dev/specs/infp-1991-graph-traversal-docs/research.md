# Phase 0 Research: Graph Traversal Documentation

All open decisions from the Technical Context are resolved below. No `NEEDS CLARIFICATION`
items remain.

## R1 — Where do the docs live? (placement)

**Decision**: Create a dedicated section `docs/docs/graph-traversal/` containing the topic,
guide, and reference pages.

**Rationale**: The feature is a headline 1.10.0 capability spanning a UI (Topology Explorer)
and an API (two GraphQL queries). Cross-cutting features in the docs each own a top-level
section (`branches/`, `objects/`, `groups/`, `ipam/`, `generators/`). A dedicated section is
the most discoverable home and keeps the reference values in one authoritative place
(FR-012, SC-002).

**Alternatives considered**:
- *All under `development-resources/graphql/`* (suggested by initial doc-structure scan):
  rejected — under-serves the Topology Explorer UI and splits the concept from its task guide.
- *No new section; extend `objects/` or `schema/`*: rejected — traversal is its own concept,
  not a property of objects or schema.

## R2 — How to split the pages (Diátaxis)

**Decision**: Three pages.
1. `overview.mdx` — **Topic** (explanation): what graph traversal is; path discovery vs
   dependency discovery; concepts (path, hop, depth, path limit); branch/time awareness;
   permission-safety; always-excluded namespaces. (FR-001, FR-005)
2. `topology-explorer.mdx` — **Guide** (how-to): open the Topology Explorer (menu "Path
   Traversal" / `/path-traversal`), use path mode and dependency mode, filter by kind &
   namespace, highlight a path, keyboard-step between paths, and the "Trace from this object"
   action on object detail pages; plus the empty/same-node/missing-node behaviors. (FR-002,
   FR-003, FR-006)
3. `reference.mdx` — **Reference**: the two GraphQL queries, every parameter, default, and
   limit, with a working example and a note that the same query is available over MCP.
   (FR-004, FR-007, FR-012)

**Rationale**: Matches Diátaxis (FR-009) and the repo's topic/guide/reference split. Keeping
reference values in a single page satisfies FR-012 and SC-002.

**Alternatives considered**: A single combined page — rejected, mixes audiences and violates
Diátaxis. A separate dependency-discovery guide — folded into the Topology Explorer guide as a
"dependency mode" section to avoid fragmentation (can be split later if it grows).

## R3 — Which release/version does the doc describe? (FR-011, SC-006)

**Decision**: Infrahub **1.10.0**.

**Rationale**: The feature is announced in `docs/docs/release-notes/infrahub/release-1_10_0.mdx`
under "Graph path traversal and topology explorer", which is the authoritative description of
shipped behavior. The topic page states the introducing version; reference content is verified
against the 1.10.0 implementation.

## R4 — Screenshots / visual walkthrough

**Decision**: Reuse the existing release-notes image where possible
(`docs/docs/media/release_notes/infrahub_1_10_0/path_traversal.png`) and add at most one or two
screenshots under `docs/docs/media/graph-traversal/`. Prefer prose + the existing image over a
dense click-by-click walkthrough.

**Rationale**: Minimizes fragile UI-step coupling (spec Edge Cases; Assumptions). The repo
supports e2e-generated screenshots (`UPDATE_DOCS_SCREENSHOTS=1 ... tests/e2e/tutorial`); adding
that pipeline is out of scope for a docs-authoring task and recorded as a follow-up option.

## R5 — Is a Towncrier changelog fragment required?

**Decision**: **No fragment for the feature**; the feature already shipped in 1.10.0. If repo
policy requires a fragment for any docs PR, add a `documentation`-type fragment in `changelog/`.

**Rationale**: Towncrier fragments track user-facing product changes; documenting an
already-shipped feature is not a new product change. Confirm against `dev/guidelines/git-workflow.md`
and recent docs-only PRs during implementation; the cost of adding a `documentation` fragment is
trivial if required.

## R6 — Terminology (FR-010)

**Decision**: Use these consistently, matching the product and release notes:
- **Graph traversal** — the overall capability / concept (section + topic title).
- **Path traversal** — path discovery between two objects; the UI menu label is "Path Traversal".
- **Dependency discovery** — finding reachable objects of given kinds from one source
  ("what depends on this?" / blast-radius).
- **Topology Explorer** — the UI surface that renders results.
- **`InfrahubPathTraversal`**, **`InfrahubReachableNodes`** — the GraphQL query names, in code font.

**Rationale**: These are the exact names used in the 1.10.0 release notes, menu, and backend.
Run `docs.lint` (Vale) to catch style/terminology drift.

## R7 — Source of truth for reference values

**Decision**: The reference page's parameters/defaults are verified against, in priority order:
1. `backend/infrahub/graphql/queries/path.py` (input types, defaults, resolvers)
2. `schema/schema.graphql` (generated GraphQL schema — exact field names & casing)
3. `docs/docs/release-notes/infrahub/release-1_10_0.mdx` (narrative confirmation)

**Open item flagged for implementation**: argument **casing**. The release notes prose uses
`source_id`/`destination_id`/`max_depth`; the feature's own quickstart example used
`sourceId`/`destinationId`. The reference page MUST use whatever `schema/schema.graphql` /
`path.py` actually expose — verify before publishing. Captured in `contracts/graph-traversal-reference.md`.

## Confirmed feature facts (from release notes + backend, for content accuracy)

- Two top-level queries: `InfrahubPathTraversal`, `InfrahubReachableNodes`.
- `InfrahubPathTraversal`: inputs `source_id`, `destination_id`; bounds `max_depth`, `max_paths`;
  filters `kind_filter`, `relationship_filter`, `excluded_kinds`, `excluded_namespaces`;
  returns connecting paths shortest-first as ordered hops (node + relationship per hop).
- `InfrahubReachableNodes`: inputs `source_id`, `target_kinds`; returns each reachable object of
  those kinds with the shortest path to it; used for blast-radius / impact analysis.
- Defaults & limits (from feature spec; verify exact values against code): max depth default **5**,
  max **20**; max paths default **10**.
- Always-excluded namespaces (cannot be re-included): `Core`, `Internal`, `Builtin`, `Lineage`,
  `Profile`, `Template`. `excluded_namespaces` only **adds** to this set.
- Read-only; branch- and time-aware; **permission-safe** (a path crossing an unreadable object is
  dropped entirely, not leaked).
- UI: **Topology Explorer**, menu "Path Traversal" at `/path-traversal`; path mode & dependency
  mode; filter by kind/namespace; highlight a path; keyboard navigation between paths; object
  detail pages add a **"Trace from this object"** action that pre-seeds the explorer.
- Available to AI agents over the **MCP server** (same GraphQL queries).
