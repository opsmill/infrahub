# Feature Specification: Graph Traversal Documentation

**Feature Branch**: `docs-graph-traversal-infp-1991`
**Created**: 2026-06-24
**Status**: Draft
**Input**: User description: "I need to add docs for the graph traversal feature"

## User Scenarios & Testing *(mandatory)*

> Context: Graph Path Traversal (JPD `infp-1991`) lets users select infrastructure
> nodes and discover the nodes and relationships connecting them — path discovery
> between two points, visual path results, filtering by node/relationship type, and
> single-node dependency discovery. This specification covers the **documentation**
> that ships alongside that feature. No graph-traversal code is in scope here; the
> deliverable is published documentation that lets users understand, use, and
> reference the feature without reading the source.

### User Story 1 - Understand What Graph Traversal Is and When to Use It (Priority: P1)

As an automation engineer new to the feature, I want a conceptual explanation of graph
traversal in Infrahub — what it does, the problems it solves, and its key concepts (path,
hops, depth/path limits, branch awareness, dependency discovery) — so I can decide whether
and how it fits my use case before I try to use it.

**Why this priority**: Without a conceptual anchor, every other piece of documentation is
harder to follow. Readers who don't understand *what* a path or traversal depth means cannot
successfully act on a how-to guide or interpret reference material. This is the foundation
the rest of the documentation links back to.

**Independent Test**: A reader unfamiliar with the feature can read the explanation page and
correctly answer what graph traversal produces, what bounds a query (depth and path limits),
and how branch context affects results — verified by review against the feature's behavior.

**Acceptance Scenarios**:

1. **Given** the published documentation, **When** a reader looks for "graph traversal" or
   "path traversal", **Then** they find a conceptual explanation page that defines the feature,
   its core terms, and its limits and defaults.
2. **Given** the explanation page, **When** a reader finishes it, **Then** they understand the
   difference between path discovery (two nodes) and dependency discovery (one node), and that
   traversal respects the current branch and point in time.
3. **Given** the explanation page, **When** a reader wants to act, **Then** the page links them
   to the relevant task guide(s) and reference material.

---

### User Story 2 - Complete a Path Traversal Task (Priority: P1)

As an infrastructure operator, I want step-by-step instructions for running a path traversal —
selecting two nodes, applying filters, and reading the results (including the visual view) — so I
can accomplish the task in the product without trial and error.

**Why this priority**: The feature delivers no value to a user who cannot operate it. A
task-oriented guide is what turns the conceptual understanding from Story 1 into a completed
action, and it is the documentation users reach for most often.

**Independent Test**: Following the guide against a running Infrahub instance with sample data, a
reader who has never used the feature can discover a path between two connected nodes, apply a
node-kind or relationship-type filter, and interpret the returned result — without consulting any
other source.

**Acceptance Scenarios**:

1. **Given** the how-to guide, **When** a reader follows it end to end, **Then** they can initiate
   a path query from an object's detail page (or the dedicated entry point), select start and end
   nodes, and view results.
2. **Given** the guide, **When** a reader needs to narrow results, **Then** the guide shows how to
   filter by node kind and relationship type, exclude kinds/namespaces, and adjust depth and path
   limits.
3. **Given** the guide, **When** a query returns no path, the same node twice, or a missing node,
   **Then** the guide explains the message the user will see and what to do next.
4. **Given** the guide, **When** a reader wants to discover dependencies of a single node, **Then**
   the guide covers the dependency-discovery flow (one source node + target kinds).

---

### User Story 3 - Look Up Exact Parameters, Defaults, and Limits (Priority: P2)

As an engineer integrating or scripting against the feature, I want reference documentation that
lists every traversal parameter, its default, and its allowed range — and how to invoke traversal
programmatically through the existing query interface — so I can use the feature precisely without
guessing.

**Why this priority**: Power users and integrators need authoritative, lookup-style facts (default
depth 5, max 20; default 10 paths; default excluded namespaces) rather than prose. This builds on
Stories 1–2 but serves a distinct, recurring need.

**Independent Test**: A reader can find each parameter's name, default value, and bounds, and can
construct a valid programmatic traversal query from the reference page alone — verified against the
feature's actual parameters and defaults.

**Acceptance Scenarios**:

1. **Given** the reference documentation, **When** a reader looks up a parameter (e.g. maximum
   depth, maximum paths, node-kind filter, relationship-type filter, namespace exclusions),
   **Then** they find its meaning, default, and allowed values.
2. **Given** the reference, **When** an integrator wants to call traversal programmatically,
   **Then** they find how it is exposed through the existing query interface with a working example.
3. **Given** the reference, **When** the feature's defaults or limits change, **Then** the reference
   is the single place that must be updated (no duplicated values scattered across guides).

---

### User Story 4 - Discover the Documentation (Priority: P2)

As any reader, I want the graph traversal documentation to be findable from the documentation
navigation and from related existing pages, so I encounter it at the moment I need it rather than
only when I already know it exists.

**Why this priority**: Documentation that exists but cannot be found is functionally absent.
Placement in navigation and cross-links from adjacent topics (e.g. objects, schema/relationships,
branches) determine whether the content from Stories 1–3 is actually reached.

**Independent Test**: Starting from the documentation home/navigation and from at least one related
existing page, a reader can reach the graph traversal explanation and how-to guide within a few
clicks, without using site search.

**Acceptance Scenarios**:

1. **Given** the documentation navigation, **When** a reader browses it, **Then** the graph
   traversal pages appear in a logical, expected location.
2. **Given** a related existing page (e.g. relationships, objects, branches), **When** a reader is
   there, **Then** a contextual link points them to the graph traversal documentation where relevant.

---

### Edge Cases

- **Feature still evolving**: If the implementation's defaults or UI entry points are not yet final,
  the documentation must state the version/release it describes and avoid documenting behavior that
  is not yet shipped.
- **Visual/UI references**: Screenshots or UI walkthroughs go stale as the interface changes; the
  docs should minimize fragile UI-step coupling and note where the UI is the source of truth.
- **Overlap with existing concepts**: Relationships, branches, and object pages already exist; the
  new docs must reference rather than duplicate those, to avoid conflicting or drifting explanations.
- **Programmatic interface**: If parts of the query interface are generated reference (e.g. GraphQL
  schema), the hand-written docs must link to the generated reference rather than restate it.
- **Terminology consistency**: "Path traversal", "graph traversal", and "dependency discovery" must
  be used consistently and match the in-product terminology.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Documentation MUST include a conceptual explanation (Topic) of graph traversal that
  defines the feature, its core terms (path, hop, depth, path limit, branch/time awareness), and the
  distinction between path discovery and dependency discovery.
- **FR-002**: Documentation MUST include at least one task-oriented how-to guide that walks a reader
  through running a path traversal end to end: selecting start/end nodes, applying filters, adjusting
  limits, and reading the (visual and listed) results.
- **FR-003**: Documentation MUST cover the dependency-discovery flow (single source node + target
  kinds) as a usage path.
- **FR-004**: Documentation MUST document all traversal parameters with their defaults and allowed
  ranges: maximum depth (default 5, max 20), maximum paths (default 10), node-kind filters,
  relationship-type filters, node-kind exclusions, and default namespace exclusions (Core, Internal,
  Builtin, Lineage, Profile, Template).
- **FR-005**: Documentation MUST explain how traversal respects branch context and point in time
  (only relationships active on the current branch are followed).
- **FR-006**: Documentation MUST describe expected behavior and user-facing messaging for edge cases:
  no path found, same start/end node, missing node, cycles, and results exceeding limits.
- **FR-007**: Documentation MUST describe how to invoke traversal programmatically through the
  existing query interface, including at least one concrete example.
- **FR-008**: Documentation MUST be placed in the documentation navigation in a discoverable location
  and cross-linked from at least one related existing page.
- **FR-009**: Documentation MUST follow the project's Diátaxis structure (separating explanation,
  how-to, and reference) and pass the project's documentation linters.
- **FR-010**: Documentation MUST use terminology consistent with the in-product feature and the
  project style guide.
- **FR-011**: Documentation MUST state the Infrahub release/version the described behavior applies to.
- **FR-012**: Reference values (defaults, limits) MUST have a single authoritative location to avoid
  duplication and drift across pages.

### Key Entities

- **Explanation page (Topic)**: Understanding-oriented content defining graph traversal and its
  concepts; the conceptual anchor other pages link to.
- **How-to guide(s)**: Task-oriented, step-by-step content for performing path traversal and
  dependency discovery in the product.
- **Reference material**: Lookup-oriented content listing parameters, defaults, limits, and the
  programmatic interface.
- **Navigation/cross-links**: Sidebar placement and contextual links from related existing pages that
  make the documentation discoverable.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reader unfamiliar with the feature can, using only the published documentation,
  successfully run a path traversal between two nodes and a dependency discovery on a single node
  without external help.
- **SC-002**: 100% of the feature's user-facing parameters, defaults, and limits are documented and
  match the shipped behavior, with zero contradictory values across pages.
- **SC-003**: The graph traversal documentation is reachable from the documentation navigation and
  from at least one related existing page within three clicks, without using search.
- **SC-004**: All graph traversal documentation passes the project's documentation linters with no
  errors.
- **SC-005**: All documented edge-case behaviors (no path, same node, missing node, cycles, limit
  overflow) match the feature's actual behavior, verified by review.
- **SC-006**: The documentation explicitly states which Infrahub release it describes, and contains
  no description of unshipped behavior.

## Assumptions

- The graph traversal feature itself (per `specs/infp-1991-graph-path-traversal/spec.md`) is the
  subject; this work documents it and does not change its behavior.
- Documentation is authored in the existing Infrahub Docusaurus site under `docs/`, following the
  Diátaxis framework (Tutorials / Guides / Topics / Reference) already in use.
- The target audience is automation engineers, network operators, and infrastructure teams who know
  Git, CI/CD, and infrastructure-as-code but are not assumed to have prior Infrahub experience.
- Reference material for any generated interface (e.g. the GraphQL query interface) is produced by the
  existing code-generation pipeline and is linked to rather than re-authored by hand.
- The feature's parameters, defaults, and limits documented here are those defined in the feature spec
  (depth default 5 / max 20, 10 paths, listed namespace exclusions); the reference page is updated if
  the implementation finalizes different values.
- Screenshots/visual walkthroughs, if included, are kept minimal to limit maintenance cost as the UI
  evolves.
