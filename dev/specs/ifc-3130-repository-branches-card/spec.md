# Feature Specification: Repository branches card and branch-scoped details

**Feature Branch**: `ple-branches-card-ifc-3130`

**Created**: 2026-09-10

**Status**: Draft

**Ticket**: [IFC-3130](https://opsmill.atlassian.net/browse/IFC-3130) "Branches card on the repository page" — epic [IFC-3104](https://opsmill.atlassian.net/browse/IFC-3104), product [INFP-671](https://opsmill.atlassian.net/browse/INFP-671)

**Contract**: `dev/specs/infp-671-cross-branch-repo-status/contracts/graphql-repository-branch-status.md` (frozen; final from increment A)

**Design**: [Git sync visibility canvas](https://claude.ai/design/p/d8efb789-c722-4622-b8d8-0bceb7054774?file=Git+sync+visibility.dc.html&via=share), section 1

**Input**: Synthesized brief from two PRDs, the frozen backend GraphQL contract, the design canvas and three parallel codebase explorations. The brief, the verbatim design transcription and the verified codebase facts are the authoritative inputs to this spec.

---

## Overview

The repository page today reports the default branch's Git state as though it were the repository's. A user who wants to know whether a particular branch imported must switch to that branch and look again; on a repository with 200 branches that is 200 page loads. Two separate problems are bundled into that one symptom:

1. There is no per-branch view. Nothing on the page lists branches and what each one imported.
2. The values that *are* shown do not say which of them are repository-wide and which belong to the branch in the branch selector. `commit` and `sync_status` change per branch; `name`, `location` and `operational_status` do not. They sit in one undifferentiated list.

This feature is the user-facing half of epic IFC-3104. Everything else in that epic is the data path that feeds it.

## Clarifications

### Session 2026-09-10

- Q: Improve the existing paging component or build a new one for tables? → A: Build a new one. The existing component is out of date and stays untouched; it becomes legacy and is migrated separately, outside this feature.
- Q: How does the user reach rows beyond the first page — page controls or a "load more" button? → A: Page controls (previous/next, page numbers, page-size selector), with the position carried in the URL. This deviates from the design's `Showing 5 of 12 · Load more` footer, deliberately, and should be raised with the designer.
- Q: Default page size and the sizes offered? → A: Default 20, selectable from 10, 20 and 50.
- Q: What is the branch-scoped details card titled? → A: "On this branch", with the branch name as a caption beneath it (the design's own group-header wording).
- Q: Where does the branch-scoped card sit? → A: Main column, directly below the repository-wide details card and above the branches card.
- Q: Is the branch name a link, and is there a row-action menu? → A: The branch name links to that branch's detail page. No row-action menu column — the design does not specify its contents, so it is not invented here.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See every branch's repository status from the repository page (Priority: P1)

A user opens a connected repository and sees a card listing each branch in scope with the commit that branch has imported and its sync status, without switching branches and without opening any other page. When there are more branches than fit one page, the user moves through them with page controls.

**Why this priority**: This is the ticket's stated purpose and the only story that removes the "open 200 pages" problem. Delivered alone it is a viable slice: an operator can find the failing branch of a large repository.

**Independent Test**: Open a repository with more branches than one page holds. Assert the rendered rows carry each branch's own values, that the count reflects every in-scope branch rather than the page, and that moving to page 2 returns different rows.

**Acceptance Scenarios**:

1. **Given** a `CoreRepository` with 12 branches that synchronise with Git, one of which has a failing sync status on its own branch, **When** the user opens the repository page, **Then** the branches card lists those branches with each one's sync status and imported commit as that branch resolves them, and the failing branch shows its own status.
2. **Given** a repository whose in-scope branch count exceeds the page size, **When** the user opens the repository page, **Then** the card shows the first page of rows, states how many rows exist in total, and offers controls to reach the remaining rows.
3. **Given** the user is on page 2 of the branches card, **When** the user reloads the page or shares the URL, **Then** the same page of rows is shown, because the paging position is carried in the URL.
4. **Given** a branch that has never imported on its own branch, **When** the user views its row, **Then** the row shows the value inherited from its origin branch at that branch's fork point — presented as an ordinary value, not as an error and not as an empty cell.
5. **Given** a branch whose status is `MERGED` or `DELETING`, or the global branch, **When** the user views the card, **Then** that branch is absent from the rows and from the total count.
6. **Given** a `CoreReadOnlyRepository`, **When** the user opens the repository page, **Then** every branch is listed together with the ref that branch tracks — including branches whose Git synchronisation is disabled, which are excluded only on a read-write repository — and the card is titled for Infrahub branches rather than Git branches.
7. **Given** a branch whose inherited commit moves forward because the branch was rebased, **When** the user re-opens the card, **Then** the row shows the new value, with nothing suggesting that anything imported on that branch.

---

### User Story 2 - Tell repository-wide values apart from values that belong to this branch (Priority: P2)

A user reading a repository's details can see at a glance which values are the same on every branch and which describe only the branch currently selected, because the two groups are presented as two separate cards, the branch-scoped one naming the branch it describes.

**Why this priority**: It resolves the second half of the reported confusion and is independently valuable — it makes the existing values trustworthy even before any per-branch table exists. It is second because a user can still get the per-branch answer from Story 1 without it.

**Independent Test**: Open a repository page, assert two distinct cards exist, assert a known repository-wide attribute appears in the first and a known branch-scoped attribute appears in the second, then switch branch and assert only the second card's values change.

**Acceptance Scenarios**:

1. **Given** a repository page, **When** the user views the details area, **Then** repository-wide attributes appear in one card and branch-scoped attributes in a second card, and the second card identifies the branch its values belong to.
2. **Given** the user switches to a different branch using the branch selector, **When** the page re-renders, **Then** the branch-scoped card's values and its stated branch both change, and the repository-wide card's values do not.
3. **Given** a `CoreReadOnlyRepository`, **When** the user views the cards, **Then** the tracked ref appears in the branch-scoped card (because it is branch-aware and two branches may pin different refs), and any attribute the read-only kind does not define is simply absent rather than shown empty.
4. **Given** an object of any kind that is not a repository, **When** the user opens its detail page, **Then** it renders exactly as it does today, as a single details card.
5. **Given** the backend later adds a new branch-scoped attribute to the repository schema, **When** a user opens the repository page, **Then** that attribute appears in the branch-scoped card with no change to this feature's code, because the grouping is decided from the schema rather than from a list of field names.

---

### User Story 3 - Isolate the branch you care about in a large repository (Priority: P3)

A user with a repository of many branches narrows the list to the branch or branches they are looking for, by name fragment or by branch status, and the total count narrows with it.

**Why this priority**: It is what makes Story 1 usable at real scale rather than merely correct. It is third because paging alone already reaches every branch.

**Independent Test**: On a repository with many branches, type a fragment matching a known subset, and assert both the rows and the stated total narrow to that subset — verifying the narrowing happened before the page boundary was applied, not after.

**Acceptance Scenarios**:

1. **Given** a repository with many branches, **When** the user types a fragment of a branch name into the card's search, **Then** only branches whose name contains that fragment are listed, and the stated total counts only those branches.
2. **Given** an active name filter that matches more rows than one page holds, **When** the user moves to the next page, **Then** the filter still applies and paging walks the filtered set.
3. **Given** an active filter, **When** the user changes the filter, **Then** the view returns to the first page rather than leaving the user on a page that no longer exists.
4. **Given** a filter matching no branch, **When** the results return, **Then** the card states that nothing matched, rather than appearing to be loading or broken.

---

### Edge Cases

- **A repository with no branches in scope.** A `CoreRepository` all of whose branches have Git synchronisation disabled has an empty row set. The card must say so explicitly rather than render an empty frame.
- **Exactly one page of rows.** Paging controls must not imply pages that do not exist.
- **The user lacks the required permission.** The query is denied outright rather than returning fewer rows. The card must report that it cannot show the branches, and must not be mistaken for "this repository has no branches".
- **The query fails for any other reason** (network, server error). The card must report a failure state distinct from both "empty" and "loading", and must not blank the rest of the page.
- **While the data is loading.** The card must occupy its space and indicate loading, rather than appearing empty and then jumping.
- **A second paginated table on the same route.** Paging state is carried in the URL; two tables sharing one URL key would move together. The paging state for this card must be independent of any other paginated table.
- **A branch name long enough to overflow its column**, and a commit value long enough to overflow its own. Neither may push the table wider than the card or paint over another column.
- **The repository-wide card is empty of branch-scoped attributes, or vice versa.** A card with no rows to show must not render as an empty titled box.
- **Values shown are placeholders.** During the preview window the backend fabricates the four attribute values from the branch name. The card must be indistinguishable in behaviour from the finished one; nothing in this feature may depend on the values being real.
- **The git-derived comparison column never appears in this slice.** Rows must render and remain useful with no upstream-commit column present at all.

## Requirements *(mandatory)*

### Functional Requirements — the branches card

- **FR-001**: The repository page MUST present a card listing one row per in-scope branch of the repository being viewed, retrieved in a single request that returns both the rows and the total count. _Verify_: component test asserting one request produced the rendered rows and the stated total; e2e test asserting rendered row data.
- **FR-002**: Each row MUST show the branch name, the branch's sync status, and the commit that branch has imported. On a read-only repository each row MUST additionally show the ref that branch tracks. _Verify_: component tests per repository kind asserting the full visible text of each cell.
- **FR-003**: The row for the repository's default branch MUST be marked as the default. _Verify_: component test asserting the marker is present on the default row and absent on the others.
- **FR-003a**: Each row's branch name MUST link to that branch's own detail page, so a user who finds the branch here can reach it. The card MUST NOT render a row-action menu. _Verify_: component test asserting the link target for a known branch, and asserting no row-action control is present.
- **FR-004**: The sync status MUST be rendered using the existing dropdown-chip presentation, taking its label and colour from the values the schema supplies rather than from a mapping held in this feature. _Verify_: component test asserting the rendered label and colour come from the supplied values; a value the test invents must render with that invented label and colour.
- **FR-005**: Column headers and attribute labels MUST come from the schema. This feature MUST NOT hardcode a label that differs from the schema's own, in particular MUST NOT present `sync_status` under a renamed heading. _Verify_: component test varying the schema-supplied label and asserting the rendered header follows it.
- **FR-006**: The card MUST NOT display an upstream or remote commit, any "N commits behind" indicator, or any last-import timestamp — including any substitute drawn from an attribute's or the branch metadata's `updated_at`. _Verify_: component test asserting no such column or indicator is rendered given a payload that carries `updated_at` values.
- **FR-007**: The card's title MUST identify Git branches on a read-write repository and Infrahub branches on a read-only repository, and MUST carry the total count. _Verify_: component tests per kind asserting the full title text and count.
- **FR-008**: The rows MUST render whether or not any git-derived column ever exists. No row value may depend on data outside the graph read. _Verify_: the feature makes no request to any other source; asserted by the single-request test in FR-001.

### Functional Requirements — paging and filtering

- **FR-009**: Paging MUST be server-side: the request MUST ask for one page, and the stated total MUST be the server's count of all matching rows, not the number of rows received. _Verify_: component test asserting the request carries a page window and that the displayed total exceeds the row count when the set is larger than a page.
- **FR-010**: The user MUST be able to move between pages using previous/next controls and direct page selection, and MUST be able to change how many rows a page holds — defaulting to 20, selectable from 10, 20 and 50. Rows MUST be replaced page by page, not accumulated. _Verify_: component test asserting a page change and a page-size change each issue a new request with the corresponding window, and that the previous page's rows are no longer rendered after a page change.
- **FR-010a**: The card MUST state the window being shown and the total, so the user can tell a page from the whole set. _Verify_: component test asserting the full visible text of that statement for a set larger than one page and for a set smaller than one page.
- **FR-011**: Paging position MUST be reflected in the URL so it survives a reload and can be shared, and MUST be independent of the paging state of any other table on the same route. _Verify_: unit test on the paging state asserting two independently-keyed instances do not affect one another; component test asserting the URL carries the position and that a reload restores the same page.
- **FR-011a**: The paging controls MUST be a new component built for a table inside a card, and MUST NOT require the table to be the page-level scroll area. _Verify_: component test rendering the table inside a fixed-height card and asserting paging works with no page-level scroll container present.
- **FR-012**: Branch-name filtering MUST be a partial match applied server-side, and the total MUST narrow with it. _Verify_: component test asserting the request carries the fragment and the partial-match flag, and that the displayed total follows the server's count.
- **FR-013**: Branch-status filtering MUST be applied server-side, and the total MUST narrow with it. Every filter MUST send the schema's own wire value — the branch status enum is `BranchStatus` on the wire even though the backend symbol is `InfrahubBranchStatus`, and `sync_status` values are hyphenated (`in-sync`, `error-import`) even though their labels are title-cased and the backend enum members are underscored. A re-cased or underscored form MUST NOT be sent. _Verify_: component test asserting the request carries the status and the displayed total follows the server's count; a second asserting the hyphenated wire value is sent for a chip whose visible label is title-cased.
- **FR-014**: Changing any filter MUST reset the view to the first page. _Verify_: component test asserting the request after a filter change carries a zero offset.
- **FR-015**: No filtering, ordering or counting may be performed on rows already received. _Verify_: component test asserting that a filter change issues a new request rather than reducing the rendered rows in place.
- **FR-016**: This feature MUST NOT send the attribute-value filters (`sync_status__value`, `internal_status__value`) or the own-values-only flag, which the backend rejects during the preview window. These three are named in IFC-3130's own scope; they are **deferred, not dropped** — they become buildable once IFC-3127 lifts the rejection, as follow-on work outside this spec. _Verify_: component test asserting these arguments are absent from every request the feature makes.
- **FR-017**: Every page that already offers paging MUST continue to behave exactly as it does today — same default page size, same size options, same position in the URL. _Verify_: the three existing paginated views render and page unchanged; the simplest guarantee, and the one this feature adopts, is that the paging they use is not altered at all.

### Functional Requirements — the two details cards

- **FR-018**: On a repository, the details area MUST present repository-wide attributes and branch-scoped attributes as two separate cards. The branch-scoped card MUST be titled "On this branch" and MUST show the name of the branch whose values it holds as a caption beneath that title. _Verify_: component test asserting both card titles as complete strings, the caption's branch name, and which attribute appears in which card.
- **FR-018a**: The branch-scoped card MUST sit in the page's main column, directly below the repository-wide details card and above the branches card, so the page reads repository-wide, then branch-scoped, then per-branch. _Verify_: component test asserting the document order of the three cards.
- **FR-019**: The division between the two cards MUST be derived from each attribute's branch-support declaration in the schema, falling back to the node's own declaration when the attribute does not declare one. It MUST NOT be a list of attribute names held in this feature. _Verify_: component test supplying a schema with an invented attribute and asserting it lands in the card its declared branch support dictates.
- **FR-020**: The two-card presentation MUST apply only to the two repository kinds. Every other object kind MUST render its details exactly as it does today. _Verify_: component test asserting a non-repository kind renders one card; existing detail-page behaviour unchanged.
- **FR-021**: An attribute the viewed kind does not define MUST be absent, not rendered empty. _Verify_: component test on the read-only kind asserting the attribute it lacks produces no row.
- **FR-022**: A card with no attributes to show MUST NOT render as an empty titled box. _Verify_: component test with an all-repository-wide schema asserting no empty branch-scoped card appears.

### Functional Requirements — states

- **FR-023**: The card MUST present four distinguishable states — loading, populated, empty, and failed — and the failure state MUST distinguish a permission denial from other failures. _Verify_: component tests per state asserting the full user-visible message; the empty and denied states must not render the same text.
- **FR-024**: A failure in the branches card MUST NOT prevent the rest of the repository page, including both details cards, from rendering. _Verify_: component test asserting the details cards render while the branches query is in a failed state.

### Functional Requirements — accessibility, testing and documentation

- **FR-025**: Every status value, state and marker on the branches card and on both details cards MUST be identifiable from a text label or an accessible name alone, with colour disregarded. Component tests MUST query by accessible name rather than by class or colour. _Verify_: component tests locating every chip, state and the default-branch marker by accessible name; no test may depend on a colour or a class to identify one. Matches the bar the sibling epic sets for the Commits tab, so two cards on one page are not held to different standards.
- **FR-026**: An end-to-end test MUST cover the branches card on a repository with more rows than one page, asserting rendered row data, a page change and a name filter. It MUST live in `tests/e2e/repository/`, carry the `shard_branches_repo` module marker, and run against the `demo_edge_repo` fixture. _Verify_: the test passes in CI in that shard.
- **FR-027**: Read-only-repository behaviour MUST be covered by component tests. It is deliberately **not** covered end to end, because the e2e data set contains no `CoreReadOnlyRepository`; adding that fixture is shared with IFC-3153 and is not budgeted here. _Verify_: component tests for the read-only row set, the ref column and the card title; the absence of e2e coverage is recorded rather than silent.
- **FR-028**: This feature MUST add a `dev/knowledge/frontend/` note covering the new table pagination component — its URL-key scoping, its use inside a card, and that it is the intended successor to the existing paging component, which is not to be used for new tables. _Verify_: the note exists and names both components; a reader choosing paging for a new table reaches the new one from it.

### Key Entities

- **Repository branch status row**: what one repository looks like as seen from one branch. Carries the branch's own identity and status, and the repository's per-branch attribute values as that branch resolves them. Identified by branch name; the row set never contains two rows for one branch. Not a stored object — it exists only as a read.
- **Branch-support declaration**: a per-attribute property of the schema stating whether an attribute's value is the same on every branch or varies by branch. Already delivered to the client and already displayed in the schema viewer; this feature is the first to make presentation depend on it.
- **Page window**: the position and size of the slice of rows currently shown, owned by the URL so it survives reload and sharing, and scoped so that two tables on one route do not share it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can determine the sync status and imported commit of every branch of a repository without switching branch and without opening a worker log.
- **SC-002**: An operator can isolate the branches of a large repository that match a name fragment or a branch status in one interaction, with the stated total reflecting the match.
- **SC-003**: Opening a repository page issues one request for the branch rows regardless of how many branches the repository has, and the number of rows transferred is bounded by the page size rather than by the branch count.
- **SC-004**: A reader of the repository page can state, for any value shown, whether it is the same on every branch or belongs only to the branch they are viewing, without consulting the schema.
- **SC-005**: A branch-scoped attribute added to the repository schema after this feature ships appears in the correct card with no change to this feature's code.
- **SC-006**: Every detail page for a non-repository kind is unchanged by this feature.
- **SC-007**: A user who cannot see the branch list is told so, and never sees an empty list that would suggest the repository has no branches.
- **SC-008**: The card behaves identically whether the backend's attribute values are the preview's fabricated ones or the real graph values, so no rework is required when the graph read lands.

## Assumptions

- **The backend contract is final and available.** `InfrahubRepositoryBranchStatus` is frozen from increment A; only the truthfulness of four attribute values changes afterwards. During the preview window those values are fabricated from the branch name, stable across reloads, and cover every dropdown value — sufficient to build and screenshot against.
- **The row set and every filter, order and count are the server's.** This feature performs none of them locally.
- **Default ordering is the server's** — default branch first, then branch name ascending. This feature does not impose an order and does not expose an order control.
- **The read-only variant is paginated on the same terms as the read-write variant**, because that kind returns every branch and can therefore exceed one page even though the design shows only four rows.
- **The ref-kind indicator from the design is dropped.** The design shows a `tag` / `branch` pill beside the tracked ref; no field in the contract carries that distinction and deriving it from the ref string would be guesswork.
- **The design's explanatory footer on the read-only card is kept as designed.** The designer flagged it as a question for the team, not a blocker.
- **The design's `Showing 5 of 12 · Load more` footer is replaced by page controls.** A "load more" affordance cannot express a position in the URL, so it is incompatible with FR-011, and it cannot serve the "jump to the failing branch among 200" journey. This is the one place where this feature knowingly diverges from the canvas, and it should be raised with the designer rather than absorbed silently.
- **The existing paging component is legacy.** It is not modified here, and migrating its three call sites onto the new component is follow-on work outside this spec.
- **The upstream-commit column is out of scope by ticket**, belonging to epic IFC-3101 on a separate data path. The design's two-tint comparison scheme therefore has only its Infrahub-side half in this slice; the tint is kept so the later column joins an established convention.
- **That column arrives as a second query, not a wider first one.** IFC-3101 settled this: `InfrahubRepositoryBranchDrift` answers for every branch in one worker request, and on a timeout returns rows with a null remote head and a column-local unavailable reason rather than failing. Two consequences this spec does not otherwise anticipate: the finished card merges two row sources with independent failure states, so FR-023's four states will need a fifth, column-scoped one when that column lands; and drift can never join FR-015's server-side filtering, because a live-read value cannot narrow, order or count a row set.
- **The design's `activity`, `import_error` and `upstream_commit` attributes do not exist in the schema yet** and are out of scope for the epic that owns this ticket. Because the card division is schema-driven, they require no work here when they arrive.
- **The design's rename of `sync_status` to "Import status" is not performed in the frontend.** Renaming the attribute is out of scope in the PRD; labels follow the schema.
- **No pull request is produced by this work.** It stays on its branch in its worktree.
- **The schema and the generated frontend types are already on the base branch.** IFC-3126 merged into `cross-branch-repo-status-infp-671`, which committed both `schema/schema.graphql` and the regenerated frontend types. Type generation therefore needs no local overlay and regenerates to zero drift. (An earlier revision of this spec assumed an overlay would be required; it no longer is.)
- **Inheritance is from the branch's *origin* branch, not necessarily the default branch.** The two usually coincide, and the frozen contract's prose says "default branch", but IFC-3147 states the implementation resolves the origin branch and warns that tests must not assume they are the same. This feature renders whatever value the query returns and computes no inheritance itself, so the distinction is a matter of wording here — but the two backend documents disagree and that is worth settling with the backend rather than inheriting the ambiguity.
- **The end-to-end test lands here.** The backend slice explicitly deferred the epic's end-to-end requirement to this card.

## Dependencies

- **IFC-3126** (backend, in progress) — ships the query with real rows, paging, ordering and permission denials, and fabricated attribute values. This feature is unblocked by it and does not wait for IFC-3127.
- **IFC-3127** (backend) — replaces the fabricated values with the graph read and lifts the rejection of the three attribute-value filters. Adding those filters is follow-on work, not part of this spec.
- **Epic IFC-3101** — owns the git-derived upstream commit and the drift column that later joins this card, plus the Commits tab (IFC-3150) that lands as a sibling route on the same repository page. This card must therefore stay inside the detail route's outlet rather than replacing the page shell.
- **IFC-3131** (manual validation of this card) — its instructions are written by **IFC-3132**, which has not landed. If IFC-3131 is treated as this card's acceptance gate, that gate is currently blocked on an unwritten ticket.
- **T094 in IFC-3101** — an open design task settling unresolved canvas decisions, and the existing forum for this spec's own divergence from the design (page controls in place of `Showing 5 of 12 · Load more`). Raise it there rather than opening a separate conversation.

## Out of Scope

- The upstream/remote commit column and any drift or "N behind" indicator.
- Any last-import timestamp column, and any substitute for one.
- The attribute-value filters and the own-values-only restriction.
- The Commits tab and the commit log (design section 2, epic IFC-3101).
- The top-bar Git status icon that turns red when the integration failed on the current branch (design section 1, but not in this ticket's scope).
- Added columns on the global branches view, and the branch detail view (design sections 3 and 4).
- Renaming `sync_status`, and any change to what its values mean.
- Extending the two-card division to object kinds other than the two repository kinds.
- Migrating the three existing users of the legacy paging component onto the new one.
- A row-action menu on the branches card.
- Adding a `CoreReadOnlyRepository` to the end-to-end data set. That fixture is shared with IFC-3153 and is not budgeted here; read-only behaviour is covered at component level instead (FR-027).

## Constitution Alignment

- **I. Schema-Driven Integrity**: the card division and every label are derived from the schema rather than from field-name lists held in the frontend, which is what makes a later schema addition free.
- **II. Branch-Safe by Default**: read-only; writes nothing. The one branch-semantics risk — a branch showing a value inherited from its origin branch at its fork point — is stated as correct behaviour and pinned by an acceptance scenario rather than described in prose only.
- **III. Type Safety & Explicit Contracts**: the query is typed against the frozen contract; the page window and filter set are explicit inputs rather than ambient state.
- **IV. Test Discipline**: every functional requirement carries a verification method; the four card states, the URL-scoped paging and the schema-driven division are each asserted rather than assumed. The end-to-end test deferred by the backend slice is included.
- **V. Query Performance & Efficiency**: one request per page, server-side count and filters, and no client-side narrowing. Row transfer is bounded by page size, not branch count.
- **VII. Simplicity & Maintainability**: reuses the existing details card, table grid and status-chip presentation rather than adding parallel ones. The one deliberate addition is a new paging component: the existing one is out of date, is built for a page-level scroll area, and is shared by three unrelated pages, so generalising it in place would put this feature's regression risk on all three. The new component is the intended successor and migrating those three onto it is follow-on work, tracked separately — a temporary duplication accepted knowingly rather than a parallel mechanism left unexplained.
