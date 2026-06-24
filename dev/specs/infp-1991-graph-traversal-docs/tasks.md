# Tasks: Graph Traversal Documentation

**Input**: Design documents from `/specs/infp-1991-graph-traversal-docs/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/graph-traversal-reference.md, quickstart.md

**Tests**: No automated tests apply to a documentation feature. The validation gates are
`uv run invoke docs.lint` (Vale + markdownlint) and `uv run invoke docs.build` (build + link
check), per plan.md Constitution Check (FR-009, SC-004).

**Organization**: Tasks are grouped by the four user stories from spec.md so each story can be
authored and previewed independently. Each story maps to one deliverable page; US4 wires
navigation and cross-links.

## Path Conventions

Documentation lives in the Docusaurus site under `docs/`. New section:
`docs/docs/graph-traversal/`. Navigation: `docs/sidebars.ts`. Media: `docs/docs/media/`.

---

## Phase 1: Setup

**Purpose**: Establish the authoring conventions and scaffolding before writing content.

- [x] T001 Review docs conventions and record the concrete rules (frontmatter, heading hierarchy, terminology, capitalization, notification blocks, code-fence languages) from `docs/docs/development/style-guide.mdx`, `docs/docs/development/docs.mdx`, `docs/docs/topics/AGENTS.md`, and `docs/docs/guides/AGENTS.md`
- [x] T002 [P] Create the section directory `docs/docs/graph-traversal/` and the media directory `docs/docs/media/graph-traversal/`; identify the reusable release-notes image `docs/docs/media/release_notes/infrahub_1_10_0/path_traversal.png` for potential reuse (research.md R4)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Lock down the authoritative facts every page depends on. Content must match the
shipped 1.10.0 API, not the spec's assumed numbers. **Blocks all content phases.**

- [x] T003 Verify the reference contract against the shipped code: confirm input fields, defaults, and limits in `backend/infrahub/graphql/queries/path.py` and `backend/infrahub/graphql/queries/reachable.py`, and confirm field names/casing in `schema/schema.graphql`; reconcile any drift into `specs/infp-1991-graph-traversal-docs/contracts/graph-traversal-reference.md` (note: `max_depth` max is 30; path-traversal `max_paths` 10/100; reachable `max_results` 50/200 and `max_paths` 500/5000; args are snake_case)
- [x] T004 Confirm the introducing version and feature narrative against `docs/docs/release-notes/infrahub/release-1_10_0.mdx` (section "Graph path traversal and topology explorer"); record the canonical terminology set (research.md R6) to apply across all pages

**Checkpoint**: Authoritative facts and terminology fixed — content authoring can begin.

---

## Phase 3: User Story 1 - Understand What Graph Traversal Is (Priority: P1) 🎯 MVP

**Goal**: A reader new to the feature can understand what graph traversal is, the two modes, the
key concepts, and its branch/time/permission semantics — the conceptual anchor other pages link to.

**Independent Test**: Open `docs/docs/graph-traversal/overview.mdx` via `uv run invoke docs.serve`;
a reader unfamiliar with the feature can state what traversal produces, path vs dependency
discovery, the depth/path bounds, and how branch context affects results.

- [x] T005 [US1] Author the Topic page `docs/docs/graph-traversal/overview.mdx` with frontmatter `title: Graph traversal`, h1, and the sections from data-model.md Page 1: intro, "Available since Infrahub 1.10.0", path discovery vs dependency discovery, core concepts (path/hop/depth/path limit/shortest-first), branch & time awareness (FR-005), permission safety (path crossing an unreadable object is dropped), always-excluded namespaces (Core, Internal, Builtin, Lineage, Profile, Template), and a "where to go next" section linking to the guide and reference (FR-001, FR-011)
- [x] T006 [US1] Add forward links from `overview.mdx` to the guide (`topology-explorer.mdx`) and reference (`reference.mdx`) pages, and ensure terminology matches the recorded set (FR-010); confirm the page states it is read-only and does not imply writes
- [x] T007 [US1] Preview the page and fix any lint findings: `uv run invoke docs.format && uv run invoke docs.lint`

**Checkpoint**: The conceptual page stands alone and is correct — MVP delivered.

---

## Phase 4: User Story 2 - Complete a Path Traversal Task (Priority: P1)

**Goal**: A reader can operate the Topology Explorer end to end — path mode, dependency mode,
filtering, the "Trace from this object" action — and knows what edge cases look like.

**Independent Test**: Following `topology-explorer.mdx` against a running instance with data, a
first-time reader can discover a path between two connected objects, run a dependency discovery,
apply a kind/namespace filter, and interpret the results — without other sources.

- [x] T008 [US2] Author the Guide page `docs/docs/graph-traversal/topology-explorer.mdx` with frontmatter (verb-led title, e.g. `Explore topology and trace paths`), h1, and the sections from data-model.md Page 2: opening + prerequisite, "Open the Topology Explorer" (menu "Path Traversal" / route `/path-traversal`), path mode, dependency mode (FR-003), filtering & bounds (brief — link to reference, do NOT restate values per FR-012), "Trace from this object" action on object detail pages (FR-002)
- [x] T009 [US2] Add the edge-cases subsection to the guide describing what the user sees for: no path found, same source/destination, missing object, and results hitting the limit (FR-006, spec Edge Cases)
- [x] T010 [US2] Add a "Related" section linking to `overview.mdx` and `reference.mdx`; optionally embed the reused release-notes image; keep UI-step coupling light (research.md R4)
- [x] T011 [US2] Preview and fix lint findings: `uv run invoke docs.format && uv run invoke docs.lint`

**Checkpoint**: A reader can complete the core task using the guide.

---

## Phase 5: User Story 3 - Look Up Parameters, Defaults, and Limits (Priority: P2)

**Goal**: The single authoritative reference for both queries — every parameter, default, limit,
result shape, a working example, and MCP availability.

**Independent Test**: A reader can find each parameter's meaning/default/bounds and construct a
valid programmatic query from `reference.mdx` alone; values match `schema/schema.graphql`.

- [x] T012 [US3] Author the Reference page `docs/docs/graph-traversal/reference.mdx` (frontmatter `title: Graph traversal reference`, h1) documenting `InfrahubPathTraversal`: every input (`source_id`, `destination_id`, `max_depth` 5/30, `max_paths` 10/100, `kind_filter`, `relationship_filter` = schema identifiers e.g. `device__interface`, `excluded_namespaces`, `excluded_kinds`, `included_kinds`) and the result shape (paths→hops→node+relationship, source, destination, count, excluded_kinds), shortest-first — sourced from `contracts/graph-traversal-reference.md` (FR-004)
- [x] T013 [US3] In the same page, document `InfrahubReachableNodes`: inputs (`source_id`, `target_kinds`, `max_depth` 5/30, `max_results` 50/200, `max_paths` 500/5000, `shortest_paths_only` default true) and result (`source`, `dependencies[]` of node+depth+path, count); add a defaults & limits table (FR-004, FR-012)
- [x] T014 [US3] Add a runnable GraphQL example and verify it compiles against the live schema before publishing; add an "Availability" note that the same queries are reachable over the MCP server (FR-007)
- [x] T015 [US3] Preview and fix lint findings: `uv run invoke docs.format && uv run invoke docs.lint`

**Checkpoint**: Reference is complete and value-accurate; it is the only page stating defaults/limits.

---

## Phase 6: User Story 4 - Discover the Documentation (Priority: P2)

**Goal**: The pages are reachable from the sidebar and from related existing pages.

**Independent Test**: From the sidebar and from at least one related page, a reader reaches the
overview and guide within three clicks without using search; `docs.build` resolves all links.

- [x] T016 [US4] Register the new section in `docs/sidebars.ts`: add a `graph-traversal` category (items: `graph-traversal/overview`, `graph-traversal/topology-explorer`, `graph-traversal/reference`) in a logical position (FR-008, SC-003)
- [x] T017 [P] [US4] Add a contextual cross-link to the graph-traversal reference from `docs/docs/development-resources/graphql/queries-and-mutations.mdx`
- [x] T018 [P] [US4] Add a contextual cross-link to the graph-traversal overview from `docs/docs/schema/relationships.mdx`
- [x] T019 [P] [US4] Add a contextual cross-link to the overview / "Trace from this object" from `docs/docs/objects/overview.mdx`

**Checkpoint**: Documentation is discoverable and all links resolve.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final validation against all success criteria.

- [x] T020 Run the full build and link check: `uv run invoke docs.build`; fix any broken links, orphan-doc warnings, or build errors
- [x] T021 [P] Cross-page consistency pass: confirm reference values appear only in `reference.mdx` (FR-012/SC-002), terminology is consistent (FR-010), and the 1.10.0 version is stated (FR-011/SC-006); confirm no spec-kit FR IDs, ticket IDs, or internal class names leak into the published MDX (per `.agents/rules/code-doc-style.md`)
- [x] T022 [P] Verify all documented edge-case behaviors match actual behavior in a running instance (SC-005); adjust wording where the UI differs
- [x] T023 Confirm whether a `changelog/` fragment is required for this docs PR (research.md R5 — likely not, since the feature already shipped); add a `documentation`-type fragment if repo policy requires one
- [x] T024 Final read-through against spec Success Criteria SC-001…SC-006 and the spec quality checklist

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)** must complete before any content phase.
- **US1 (Phase 3)** is the MVP and has no dependency on US2/US3.
- **US2 (Phase 4)** and **US3 (Phase 5)** depend only on Foundational; they can be authored in
  parallel with each other and with US1 (different files), each linking to the others' known paths.
- **US4 (Phase 6)** depends on US1+US2+US3 existing (sidebar IDs and cross-link targets must
  resolve, else `docs.build` fails).
- **Polish (Phase 7)** runs last; T020 (full build) requires US4 complete.

```text
Setup → Foundational → ┌─ US1 (overview)  ─┐
                       ├─ US2 (guide)      ─┤→ US4 (sidebar+links) → Polish
                       └─ US3 (reference)  ─┘
```

## Parallel Execution Opportunities

- **Phase 1**: T002 [P] runs alongside T001.
- **Content authoring**: T005 (US1), T008 (US2), T012 (US3) touch three distinct files and can
  be written in parallel once Phase 2 is done.
- **Phase 6**: T017, T018, T019 [P] edit three different existing pages — parallelizable (T016
  edits `sidebars.ts` separately).
- **Phase 7**: T021 and T022 [P] are independent review passes.

## Implementation Strategy

- **MVP**: Phases 1–3 (Setup + Foundational + US1 topic). Delivers a correct conceptual page a
  reader can use immediately; previewable via `docs.serve` without the rest.
- **Incremental delivery**: add US2 (operate the feature), then US3 (precise reference), then US4
  (discoverability), validating lint after each page.
- **Single PR** to `stable`/`develop` is reasonable given the small surface; could also ship the
  topic first and the guide/reference as a follow-up if the UI is still settling.
