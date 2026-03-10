# Feature Specification: GraphQL Fragment Inlining at Import

**Feature Branch**: `infp-496-graphql-fragment-inlining`
**Created**: 2026-03-09
**Status**: Draft
**Jira**: INFP-496

## Summary

Users building infrastructure automation pipelines often have multiple GraphQL queries that share overlapping field selections (e.g., every transform that touches network interfaces needs the same ~20 fields). Today, they must copy-paste those field selections into every `.gql` file. When the data model evolves, each query file must be updated independently — a brittle, error-prone process that blocks scale.

This feature allows users to define reusable GraphQL fragment files in their Git repositories and reference them from query files using standard GraphQL fragment spread syntax (`...fragmentName`). When Infrahub imports the repository, the importer analyzes each query, identifies which fragments it depends on, extracts those fragment definitions from the declared fragment files, and stores a fully-rendered, self-contained query in the database. No new database object types are introduced.

Fragment files are kept within the same repository as the queries that use them by design. This preserves the local development experience: when a developer works on queries in their IDE, features such as "go to definition" and inline fragment previews work because both the query and the fragment file live in the same local checkout. Cross-repository fragment references would break this — a developer's IDE cannot follow a reference to a file that only exists in a separate repository they may not have checked out.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Import Query with Fragment Spreads Resolved Across Multiple Fragment Files (Priority: P1)

A platform engineer has a repository declaring multiple fragment files in `.infrahub.yml` under `graphql_fragments` — for example, `fragments/interfaces.gql` and `fragments/devices.gql`. A query file uses `...interfaceFragment` and `...deviceFragment`. The importer scans all declared fragment files, locates each required fragment definition by name regardless of which file it lives in, and stores a single fully-rendered query that includes only those two definitions. Other fragment definitions present in either file but not referenced by this query are not included.

**Why this priority**: This is the core end-to-end flow. All other stories depend on this working correctly. Without it, no other aspect of the feature is testable.

**Independent Test**: Push a repository with two declared fragment files and a query that references one fragment from each. After sync, retrieve the stored query and verify it contains exactly the two referenced fragment definitions (not others from those files) and executes without error.

**Acceptance Scenarios**:

1. **Given** a repository declaring two fragment files — `fragments/interfaces.gql` (defines `interfaceFragment`, `portFragment`) and `fragments/devices.gql` (defines `deviceFragment`, `chassisFragment`) — and a query that uses only `...interfaceFragment` and `...deviceFragment`, **When** the repository is synced, **Then** the stored query contains the `interfaceFragment` and `deviceFragment` definitions and does not contain `portFragment` or `chassisFragment`.

2. **Given** the same setup, **When** the stored query is retrieved via the API, **Then** the query text is a single valid GraphQL document containing both the operation and exactly the required fragment definitions.

3. **Given** a query that uses no fragment spreads, **When** the repository is synced, **Then** the query is stored as-is with no modification.

---

### User Story 2 - Transitive Fragment Dependencies Resolved Automatically (Priority: P2)

A platform engineer has a fragment `deviceFragment` that itself uses `...interfaceFragment`. The query only spreads `...deviceFragment` directly. The importer detects that `deviceFragment` depends on `interfaceFragment`, searches the declared fragment files for that definition (which may be in a different file), and includes both in the rendered output — without the user having to explicitly list `interfaceFragment` in the query.

**Why this priority**: Transitive resolution is what makes fragment reuse actually composable. Without it, users would need to manually track and list every transitive dependency in each query.

**Independent Test**: Create a query that uses `...deviceFragment`, where `deviceFragment` is defined in one fragment file and itself spreads `...interfaceFragment` defined in a second fragment file. After sync, verify the stored query contains both fragment definitions even though `interfaceFragment` was never referenced directly in the query.

**Acceptance Scenarios**:

1. **Given** a query that spreads `...deviceFragment`, and `deviceFragment` is defined as using `...interfaceFragment`, and `interfaceFragment` is defined in a separate fragment file, **When** the repository is synced, **Then** the stored query contains both `deviceFragment` and `interfaceFragment` definitions.

2. **Given** a fragment file defining fragments A, B, C, D, E and a query that directly spreads only `...A` and `...C` (none of which use other fragments), **When** the repository is synced, **Then** the stored query contains only fragment definitions A and C, not B, D, or E.

---

### User Story 3 - Fragment File Scoped Per Repository (Priority: P3)

Users may declare the same fragment name in different repositories. Each repository's fragment scope is independent — fragment resolution uses only the fragment files declared in the same `.infrahub.yml` as the query being imported.

**Why this priority**: Scoping correctness is important for preventing cross-repository pollution, but it is less urgent than the core import flow.

**Independent Test**: Sync two repositories each declaring a fragment named `deviceFragment` with different field selections. Verify each stored query uses the fragment definition from its own repository.

**Acceptance Scenarios**:

1. **Given** two repositories each declaring a fragment named `deviceFragment` with different field selections, **When** both are synced, **Then** each stored query contains the fragment definition from its own repository, not the other repository's definition.

---

### User Story 4 - Query Import Fails Gracefully When Fragment Is Unresolved (Priority: P2)

A query file uses `...missingFragment` but no fragment file declared in `.infrahub.yml` contains that definition. The importer detects the unresolved spread and reports a clear error rather than storing an invalid query.

**Why this priority**: Failure mode clarity is important for operator confidence. Storing a broken query silently would be worse than a clear error.

**Independent Test**: Attempt to import a query with an unresolved fragment spread. Verify the sync reports an error for that specific query file identifying the missing fragment name.

**Acceptance Scenarios**:

1. **Given** a query that references `...undeclaredFragment` and no fragment file declares it, **When** the repository is synced, **Then** the query import fails with an error message naming the missing fragment and the query file it appears in.

2. **Given** the above error, **When** the error is reported, **Then** other queries in the same repository that have no missing fragments are still imported successfully.

---

### User Story 5 - Re-sync Updates Dependent Queries When Fragment File Changes (Priority: P2)

A platform engineer updates a fragment definition in the fragment file (e.g., adds a new field). After re-syncing the repository, all queries that referenced that fragment are updated in Infrahub to reflect the new fragment content.

**Why this priority**: Without this, the inlining approach breaks maintainability — the whole point is that updating a fragment propagates to all dependent queries.

**Independent Test**: Sync a repository, then update the fragment file, then re-sync. Verify the stored queries that used that fragment now contain the updated field selection.

**Acceptance Scenarios**:

1. **Given** a synced repository where a query uses `...interfaceFragment`, **When** the fragment definition is updated in the repository and the repository is re-synced, **Then** the stored query text reflects the updated fragment definition.

2. **Given** the above re-sync, **When** the updated query is executed, **Then** it returns results using the new field selection.

---

### Edge Cases

- What happens when a fragment file is listed in `graphql_fragments` but does not exist in the repository? Import should fail with a clear error identifying the missing file path.
- What happens when a fragment definition has a syntax error? The import of any query using that fragment should fail with the syntax error reported.
- What happens when a fragment name is defined more than once — either within the same fragment file or across different fragment files declared in `graphql_fragments`? The importer treats this as an error and reports it, since the correct definition to use would be ambiguous.
- What happens when a fragment's type condition (`on TypeName`) references a type that does not exist in the Infrahub schema? Not validated at import time; the stored query is valid GraphQL and any type error surfaces at execution time.
- What happens when a query uses the same fragment spread more than once? The fragment definition is included only once in the rendered output.
- What happens when fragments are circularly dependent (A uses B, B uses A)? The importer detects the cycle and reports it as an import error.

## Architecture / Component Responsibilities

Fragment parsing, resolution, and rendering is **SDK responsibility**, not server responsibility. The Infrahub server calls into the SDK during repository sync; it does not own this logic itself.

### Why the SDK owns fragment rendering

`infrahubctl` executes GraphQL queries directly from the local filesystem — it never imports them into a running Infrahub instance first. If fragment rendering lived only on the server, local `infrahubctl` workflows (e.g. `infrahubctl run`, `infrahubctl transform`) would not benefit from fragment inlining and would break when encountering fragment spreads in local query files.

Placing the logic in the SDK means a single implementation is reused by:

1. **Infrahub server** — calls the SDK rendering function during repository sync to produce the fully-rendered query text before storing it in the database.
2. **infrahubctl** — calls the same SDK rendering function when loading queries from the local filesystem before executing them.

### Component split

| Responsibility | Owner |
|---|---|
| Parse `.gql` files and resolve fragment spreads | Python SDK |
| Detect transitive dependencies, cycles, duplicate names | Python SDK |
| Produce fully-rendered, self-contained query document | Python SDK |
| Declare `graphql_fragments` in `.infrahub.yml` | Python SDK config model |
| Call SDK renderer during repository sync | Infrahub server (import pipeline) |
| Store rendered query text in database | Infrahub server |
| Call SDK renderer when loading local query files | infrahubctl |

### Constraint

No fragment rendering logic should be added to the Infrahub server codebase directly. Any logic needed by the server must live in the SDK and be imported from there.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The `.infrahub.yml` configuration file MUST support a `graphql_fragments` section that declares one or more fragment files, each identified by a name and a file path relative to the repository root.
- **FR-002**: When importing a GraphQL query from a repository, the importer MUST scan the query document for named fragment spreads (`...fragmentName`).
- **FR-003**: For each named fragment spread found, the importer MUST search across all fragment files declared in the same `.infrahub.yml` to locate a matching fragment definition by name — the required fragment may be in any of the declared files.
- **FR-004**: The importer MUST resolve transitive fragment dependencies — if fragment A uses fragment B, both definitions must be included in the rendered output.
- **FR-005**: The importer MUST include only the fragment definitions that are directly or transitively required by the query, not all fragments defined in the fragment file.
- **FR-006**: The rendered query stored in Infrahub MUST be a valid, self-contained GraphQL document that can be executed without any external fragment resolution at runtime.
- **FR-007**: If a query contains a fragment spread for which no definition can be found in the declared fragment files, the import of that query MUST fail with an error message identifying the unresolved fragment name and the query file.
- **FR-008**: If a declared fragment file path does not exist in the repository, the repository sync MUST report an error identifying the missing file path.
- **FR-009**: A failure to resolve fragments for one query MUST NOT prevent other queries in the same repository (that have no missing fragments) from being imported successfully.
- **FR-010**: When a repository is re-synced and a fragment file has changed, all queries that depend on that fragment MUST be re-rendered with the updated fragment definition and updated in the database.
- **FR-011**: The fragment rendering logic MUST handle queries that use no fragment spreads, storing them as-is without modification.
- **FR-012**: Fragment scoping MUST be per-repository — fragment files from one repository are not accessible when importing queries from a different repository.
- **FR-013**: If the same fragment name is defined more than once — either within a single fragment file or across multiple declared fragment files in the same repository — the importer MUST report this as an error, since the correct definition would be ambiguous.
- **FR-014**: Circular fragment dependencies (A uses B, B uses A) MUST be detected and reported as an import error.
- **FR-015**: Fragment parsing, resolution, and rendering logic MUST reside in the Python SDK, not in the Infrahub server codebase. The server MUST call SDK functions for this; it MUST NOT duplicate the logic.
- **FR-016**: `infrahubctl` commands that load GraphQL query files from the local filesystem MUST apply the same fragment rendering logic (via the SDK) before executing those queries. Local workflows MUST continue to work when queries reference fragment spreads defined in local fragment files.

### Key Entities

- **GraphQL Query (CoreGraphQLQuery)**: Existing entity. After this feature, its stored query text may be a rendered composite of the original query operation plus one or more fragment definitions extracted from the repository's fragment files. The stored text is always a complete, valid, executable GraphQL document.
- **Fragment File**: A file in the repository (not stored as a database object) containing one or more GraphQL fragment definitions. Declared in `.infrahub.yml` under `graphql_fragments`. Fragment files exist only in Git; they are not persisted in the Infrahub database.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A repository containing queries with fragment spreads can be fully synced to Infrahub without any manual query editing — zero copy-pasting of fragment definitions into query files required by the user.
- **SC-002**: All stored queries that used fragment spreads at import time execute successfully against the GraphQL endpoint — 100% execution success rate for correctly declared fragments.
- **SC-003**: When a fragment file is updated and the repository is re-synced, all dependent queries reflect the updated fragment definition within one sync cycle — no additional manual steps required.
- **SC-004**: Import errors for unresolved or missing fragments are actionable without log inspection — the error message identifies the specific query file and missing fragment name.
- **SC-005**: Queries that do not use fragments continue to behave identically to before this feature — no regression in the existing query import path.

## Assumptions

- Fragment files are standard GraphQL documents containing only `fragment` definitions (no operation definitions).
- Fragment names are intended to be unique across all of a repository's declared fragment files combined. A duplicate name in any two files (or twice within the same file) is treated as an error because the correct definition to use would be ambiguous.
- The `graphql_fragments` section in `.infrahub.yml` follows the same list-of-items structure as the existing `graphql_queries` section, with `name` and `file_path` fields per entry.
- Fragment resolution and inlining happens at import time (repository sync), not at query execution time. The stored query text is the fully rendered document.
- Fragment type condition validation (checking that `on TypeName` references a valid Infrahub schema type) is deferred to execution time, not enforced at import time.
- Fragment files may contain more fragment definitions than any single query needs — the importer selects only the required ones.
