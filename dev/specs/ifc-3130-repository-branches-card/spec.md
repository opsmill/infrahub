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
- Q: How does the user reach rows beyond the first page — page controls or a "load more" button? → A: Page controls (previous/next, page numbers), with the position carried in the URL. This deviates from the design's `Showing 5 of 12 · Load more` footer, deliberately, and should be raised with the designer.
- Q: Default page size and the sizes offered? → A: Default 20, selectable from 10, 20 and 50. **Revised 2026-09-16 to a single fixed size of 10, with no page-size selector.** Two things settled it. 20 rows made the card dominate the page once seen against real data, so the size came down to 10. And no user story asks for a page-size control: a card on a detail page does not need one, while offering one costs a URL-state surface, a second filter-reset path and a test axis. Dropping it also makes FR-011b's height guarantee unconditional — with one size, the height the table reserves is always the height a full page occupies. For a repository with many branches the answer is the filters in US3, not a bigger page.
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
- **While the data is loading.** The card must occupy a full page of space and indicate loading, rather than appearing empty and then jumping (FR-023, which states what happens when fewer rows than that arrive).
- **A second paginated table on the same route.** Paging state is carried in the URL; two tables sharing one URL key would move together. The paging state for this card must be independent of any other paginated table.
- **A branch name long enough to overflow its column**, and a commit value long enough to overflow its own. Neither may push the table wider than the card or paint over another column.
- **The repository-wide card is empty of branch-scoped attributes, or vice versa.** A card with no rows to show must not render as an empty titled box.
- **Values shown are placeholders.** During the preview window the backend fabricates the four attribute values from the branch name. The card must be indistinguishable in behaviour from the finished one; nothing in this feature may depend on the values being real.
- **The git-derived comparison column never appears in this slice.** Rows must render and remain useful with no upstream-commit column present at all.

## Requirements *(mandatory)*

> **33 requirement statements**: FR-001…FR-028 plus FR-003a, FR-010a, FR-011a, FR-011b and FR-018a. Refer to
> them individually — a range like "FR-002–006" silently omits FR-003a.

### Functional Requirements — the branches card

- **FR-001**: The repository page MUST present a card listing one row per in-scope branch of the repository being viewed, retrieved in a single request that returns both the rows and the total count. _Verify_: component test asserting one request produced the rendered rows and the stated total; e2e test asserting rendered row data.
- **FR-002**: Each row MUST show the branch name, the branch's sync status, and the commit that branch has imported. On a read-only repository each row MUST additionally show the ref that branch tracks. _Verify_: component tests per repository kind asserting the full visible text of each cell.
- **FR-003**: The row for the repository's default branch MUST be marked as the default. _Verify_: component test asserting the marker is present on the default row and absent on the others.
- **FR-003a**: Each row's branch name MUST link to that branch's own detail page, so a user who finds the branch here can reach it. The card MUST NOT render a row-action menu. _Verify_: component test asserting the link target for a known branch, and asserting no row-action control is present.
- **FR-004**: The sync status MUST be rendered using the existing dropdown-chip presentation, taking its label and colour from the values the schema supplies rather than from a mapping held in this feature. _Verify_: component test asserting the rendered label and colour come from the supplied values; a value the test invents must render with that invented label and colour.
- **FR-005**: Column headers and attribute labels MUST come from the schema. This feature MUST NOT hardcode a label that differs from the schema's own, in particular MUST NOT present `sync_status` under a renamed heading. _Verify_: component test varying the schema-supplied label and asserting the rendered header follows it.
- **FR-006**: The card MUST NOT display an upstream or remote commit, any "N commits behind" indicator, or any last-import timestamp — including any substitute drawn from an attribute's or the branch metadata's `updated_at`. _Verify_: component test asserting no such column or indicator is rendered given a payload that carries `updated_at` values.
- **FR-007**: The card MUST be titled exactly `Branches` on a read-write repository and `Infrahub branches` on a read-only repository, following the design canvas verbatim, and MUST carry the total count beside the title. _Verify_: component tests per kind asserting the complete title string including the count.
- **FR-008**: The rows MUST render whether or not any git-derived column ever exists. No row value may depend on data outside the graph read. _Verify_: **by review against two structural facts** — the card imports exactly one api module, and the query's selection set omits `node_metadata` entirely. Both are readable from source in seconds and neither can drift silently. This requirement is deliberately **not** pinned by a call-count assertion: "the api mock is called exactly once per render" measures render-loop stability rather than data provenance, and breaks the first time a legitimate refetch is added.

### Functional Requirements — paging and filtering

- **FR-009**: Paging MUST be server-side: the request MUST ask for one page, and the stated total MUST be the server's count of all matching rows, not the number of rows received. _Verify_: component test asserting the request carries a page window and that the displayed total exceeds the row count when the set is larger than a page.
- **FR-010**: The user MUST be able to move between pages using previous/next controls and direct page selection. A page holds a fixed 10 rows; the card MUST NOT offer a page-size control. Rows MUST be replaced page by page, not accumulated. _Verify_: component test asserting a page change issues a new request with the corresponding window, that the previous page's rows are no longer rendered after it, and that no page-size control is rendered.
- **FR-010a**: The card MUST state the window being shown and the total, so the user can tell a page from the whole set. _Verify_: component test asserting the full visible text of that statement for a set larger than one page and for a set smaller than one page.
- **FR-011**: Paging position MUST be reflected in the URL so it survives a reload and can be shared, and MUST be independent of the paging state of any other table on the same route. _Verify_: unit test on the paging state asserting two independently-keyed instances do not affect one another; component test asserting the URL carries the position and that a reload restores the same page.
- **FR-011a**: The paging controls MUST be a new component built for a table inside a card, and MUST NOT require the table to be the page-level scroll area. _Verify_: component test rendering the table inside a fixed-height card and asserting paging works with no page-level scroll container present.
- **FR-011b**: Moving between pages MUST NOT change the height of the card. A last page holding fewer rows than a full one otherwise shortens the card, moving everything below it and taking the window's scrollbar with it — the same class of layout jump FR-023 forbids while loading, and equally disruptive. The table MUST therefore reserve the height of a full page — the page size plus the header row — whenever more than one page exists, and MUST reserve nothing when every row fits on one page, so a short table carries no dead space. Because the page size is fixed (FR-010), the reservation always matches exactly what a full page occupies. _Verify_: component test asserting the reserved height on a **short last page** of a set larger than one page, and its absence for a set that fits one.
- **FR-012**: Branch-name filtering MUST be a partial match applied server-side, and the total MUST narrow with it. _Verify_: component test asserting the request carries the fragment and the partial-match flag, and that the displayed total follows the server's count.
- **FR-013**: Branch-status filtering MUST be applied server-side, and the total MUST narrow with it. Every filter MUST send the schema's own wire value — the branch status enum is `BranchStatus` on the wire even though the backend symbol is `InfrahubBranchStatus`, and `sync_status` values are hyphenated (`in-sync`, `error-import`) even though their labels are title-cased and the backend enum members are underscored. A re-cased or underscored form MUST NOT be sent. _Verify_: component test asserting the request carries the status and the displayed total follows the server's count; a second asserting the hyphenated wire value is sent for a chip whose visible label is title-cased.
- **FR-014**: Changing any filter MUST reset the view to the first page. _Verify_: component test asserting the request after a filter change carries a zero offset.
- **FR-015**: No filtering, ordering or counting may be performed on rows already received. _Verify_: component test asserting that a filter change issues a new request rather than reducing the rendered rows in place.
- **FR-016**: This feature MUST NOT send the attribute-value filters (`sync_status__value`, `internal_status__value`) or the own-values-only flag, which the backend rejects during the preview window. These three are named in IFC-3130's own scope; they are **deferred, not dropped** — they become buildable once IFC-3127 lifts the rejection, as follow-on work outside this spec. _Verify_: component test asserting these arguments are absent from every request the feature makes.
- **FR-017**: Every page that already offers paging MUST continue to behave exactly as it does today — same default page size, same size options, same position in the URL. _Verify_: the three existing paginated views render and page unchanged; the simplest guarantee, and the one this feature adopts, is that the paging they use is not altered at all.

### Functional Requirements — the two details cards

- **FR-018**: On a repository, the details area MUST present repository-wide attributes and branch-scoped attributes as two separate cards. The branch-scoped card MUST be titled "On this branch" and MUST show the name of the branch whose values it holds as a caption beneath that title. _Verify_: component test asserting both card titles as complete strings, the caption's branch name, and which attribute appears in which card.
- **FR-018a**: The branch-scoped card MUST sit in the page's main column, directly below the repository-wide details card and above the branches card, so the page reads repository-wide, then branch-scoped, then per-branch. _Verify_: component test asserting the document order of the three cards.
- **FR-019**: The division between the two cards MUST be derived from each **field's** branch-support declaration in the schema, falling back to the node's own declaration when the field does not declare one. It MUST NOT be a list of field names held in this feature. **`BranchSupportType` has three values, and both `aware` and `local` are branch-scoped**; only `agnostic` is repository-wide. On `CoreRepository`, `commit` and `sync_status` are both declared `local`, so treating only `aware` as branch-scoped would file them under repository-wide and make SC-004 false. The rule MUST also cover **relationships**, which `ObjectDataDisplay` renders alongside attributes. _Verify_: unit test with one case per `BranchSupportType` value plus the node-level fallback; component test supplying a schema with an invented attribute and asserting it lands in the card its declared branch support dictates; component test asserting each relationship label appears exactly once on the page.
- **FR-020**: The two-card presentation MUST apply only to the two repository kinds. Every other object kind MUST render its details exactly as it does today. _Verify_: component test asserting a non-repository kind renders one card; existing detail-page behaviour unchanged.
- **FR-021**: An attribute the viewed kind does not define MUST be absent, not rendered empty. _Verify_: component test on the read-only kind asserting the attribute it lacks produces no row.
- **FR-022**: A card with no attributes **and no relationships** to show MUST NOT render as an empty titled box. _Verify_: component test with an all-repository-wide schema asserting no empty branch-scoped card appears.

### Functional Requirements — states

- **FR-023**: The card MUST present four distinguishable states — loading, populated, empty, and failed — and the failure state MUST distinguish a permission denial from other failures. The empty state MUST further distinguish "your filter matched nothing" from "this repository has no branch in scope", which are different facts. The user-visible string for each state is pinned in the [UI contract](contracts/repository-branch-status-ui.md) §4 rather than left to a component default, so copy can be reviewed without reading code. The loading state MUST render as many skeleton rows as a full page holds. For a set of at least one full page this means no layout jump when the rows arrive; for a smaller set the card necessarily shrinks to the rows returned, because the total is unknown until the response lands and FR-011b deliberately reserves nothing for a set that fits one page. That shrink is accepted: reserving a full page for every repository would leave permanent dead space under the common case of a handful of branches. _Verify_: component tests per state asserting the full user-visible message; the empty and denied states must not render the same text.
- **FR-024**: A failure in the branches card MUST NOT prevent the rest of the repository page, including both details cards, from rendering. This MUST hold for **render-time** failures as well as query failures — a mapper crash on an unexpected payload shape, or a null reaching a cell that requires a value, must be contained by a card-scoped error boundary rather than propagating to the route's boundary and blanking the page. _Verify_: component test asserting the details cards render while the branches query is in a failed state, **and** a second asserting they still render when the branches card throws during render.

### Functional Requirements — accessibility, testing and documentation

- **FR-025**: Every status value, state and marker on the branches card and on both details cards MUST be identifiable from a text label or an accessible name alone, with colour disregarded. Component tests MUST query by accessible name rather than by class or colour. This extends to three things the card introduces: the **paging controls** (the active page carries `aria-current`, and a page change is announced), the **truncated commit hash** (the visible short form is its label; the full value is reachable via `title` rather than through an accessible name, because ARIA forbids naming a role-less element), and the **branch-name caption** on the branch-scoped details card (part of that card's accessible name, not decorative text). The same carve-out covers the **default-branch marker**: it too is role-less, so its visible `default` text is its label and tests locate it with `within(row)` + `getByText`. _Verify_: component tests locating every chip, state and paging control by accessible name, and the commit hash and default marker by their visible text; no test may depend on a colour or a class to identify one. Matches the bar the sibling epic sets for the Commits tab, so two cards on one page are not held to different standards.
- **FR-026**: An end-to-end test MUST cover the branches card on a repository with more rows than one page, asserting rendered row data, a page change and a name filter. It MUST live in `tests/e2e/repository/`, carry the `shard_branches_repo` module marker, and run against the `demo_edge_repo` fixture. _Verify_: the test passes in CI in that shard.
- **FR-027**: Read-only-repository behaviour MUST be covered by component tests. It is deliberately **not** covered end to end, because the e2e data set contains no `CoreReadOnlyRepository`; adding that fixture is shared with IFC-3153 and is not budgeted here. This is a knowing deviation from the constitution's "E2E tests MUST be included for all user-facing features", and is recorded as such in [plan.md](plan.md)'s Complexity Tracking. The gap MUST also be noted on **IFC-3153**, so the fixture's owner inherits it rather than it living only in this spec. _Verify_: component tests for the read-only row set, the ref column and the card title; the absence of e2e coverage is recorded rather than silent.
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
- **SC-008**: The card **behaves** identically whether the backend's attribute values are the preview's fabricated ones or the real graph values, so no rework is required when the graph read lands. This is a statement about behaviour, not about chrome: it does not by itself forbid a preview marker, should the epic owner decide one is needed (open question Q2).

### How this is verified, and what would trigger a rollback

These criteria are acceptance statements, not instrumented metrics — **there is no frontend telemetry
behind them**, and this spec does not add any. They are verified by the component and e2e suites plus
the manual scenarios in [quickstart.md](quickstart.md). Stating that plainly is more useful than
implying a measurement that does not exist.

**Rollback path**: revert the `isOfKind(GENERIC_REPOSITORY_KIND, schema)` gate in `object-details.tsx`.
That single edit restores every repository page to today's one-card rendering and removes the branches
card, without touching any other object kind — the gate is the feature's only entry point into shared
code. **Rollback trigger**: any regression on a non-repository detail page (which SC-006 asserts cannot
happen, and whose violation would mean the gate is wrong rather than the card is).

## Assumptions

- **The backend contract is final and available.** `InfrahubRepositoryBranchStatus` is frozen from increment A; only the truthfulness of four attribute values changes afterwards. During the preview window those values are fabricated from the branch name, stable across reloads, and cover every dropdown value — sufficient to build and screenshot against.
- **The row set and every filter, order and count are the server's.** This feature performs none of them locally.
- **Default ordering is the server's** — default branch first, then branch name ascending. This feature does not impose an order and does not expose an order control.
- **The read-only variant is paginated on the same terms as the read-write variant**, because that kind returns every branch and can therefore exceed one page even though the design shows only four rows.
- **The ref-kind indicator from the design is dropped.** The design shows a `tag` / `branch` pill beside the tracked ref; no field in the contract carries that distinction and deriving it from the ref string would be guesswork.
- **The design's explanatory footer on the read-only card is kept as designed.** The designer flagged it as a question for the team, not a blocker.
- **The design's `Showing 5 of 12 · Load more` footer is replaced by page controls.** A "load more" affordance cannot express a position in the URL, so it is incompatible with FR-011. It is one row in the **divergence register in [plan.md](plan.md)**, which records every knowing departure from the canvas — the largest being the two-card split, which the canvas explicitly ruled against. Take the whole register to the designer together, on T094 in IFC-3101, **before work unit 1 starts** — pagination is built first and would otherwise be rejected last.
- **Page controls are justified by URL-shareability alone**, which is sufficient. They do *not* deliver the "jump to the failing branch among 200" journey either: FR-013 filters only the branch lifecycle `BranchStatus`, FR-016 defers `sync_status__value` to IFC-3127, and there is no sort control. In this slice, isolating the failing branch of a large repository means paging through looking for a red chip. That is a real limitation of the slice; SC-002 should not be read as claiming otherwise.
- **The existing paging component is legacy.** It is not modified here, and migrating its three call sites onto the new component is follow-on work outside this spec.
- **The upstream-commit column is out of scope by ticket**, belonging to epic IFC-3101 on a separate data path. The design's two-tint comparison scheme therefore has only its Infrahub-side half in this slice; the tint is kept so the later column joins an established convention.
- **That column arrives as a second query, not a wider first one.** IFC-3101 settled this: `InfrahubRepositoryBranchDrift` answers for every branch in one worker request, and on a timeout returns rows with a null remote head and a column-local unavailable reason rather than failing. Two consequences this spec does not otherwise anticipate: the finished card merges two row sources with independent failure states, so FR-023's four states will need a fifth, column-scoped one when that column lands; and drift can never join FR-015's server-side filtering, because a live-read value cannot narrow, order or count a row set.
- **The design's `activity`, `import_error` and `upstream_commit` attributes do not exist in the schema yet** and are out of scope for the epic that owns this ticket. Because the card division is schema-driven, they require no work here when they arrive.
- **The design's rename of `sync_status` to "Import status" is not performed in the frontend.** Renaming the attribute is out of scope in the PRD; labels follow the schema.
- **This work merges into the epic branch, not into `develop`.** The PR targets `cross-branch-repo-status-infp-671`, where IFC-3126 already sits and IFC-3127 will land. So **the preview window's fabricated attribute values reach no user** — which is why the card carries no preview banner. If the epic branch is ever released with IFC-3127 still outstanding, that decision must be revisited: plausible-looking fake commit hashes with nothing marking them are worse than showing nothing. Open question Q2 in [plan.md](plan.md).
- **The schema and the generated frontend types are already on the base branch.** IFC-3126 merged into `cross-branch-repo-status-infp-671`, which committed both `schema/schema.graphql` and the regenerated frontend types. Type generation needs no local overlay and regenerates to zero drift.
- **Inheritance is from the branch's *origin* branch, not necessarily the default branch.** The two usually coincide, and the frozen contract's prose says "default branch", but IFC-3147 states the implementation resolves the origin branch and warns that tests must not assume they are the same. This feature renders whatever value the query returns and computes no inheritance itself, so the distinction is a matter of wording here — but the two backend documents disagree and that is worth settling with the backend rather than inheriting the ambiguity.
- **The end-to-end test lands here.** The backend slice explicitly deferred the epic's end-to-end requirement to this card.

## Dependencies

- **IFC-3126** (backend, in progress) — ships the query with real rows, paging, ordering and permission denials, and fabricated attribute values. This feature is unblocked by it and does not wait for IFC-3127.
- **IFC-3127** (backend) — replaces the fabricated values with the graph read and lifts the rejection of the three attribute-value filters. Adding those filters is follow-on work, not part of this spec.
- **Epic IFC-3101** — owns the git-derived upstream commit and the drift column that later joins this card, plus the Commits tab (IFC-3150) that lands as a sibling route on the same repository page. This card must therefore stay inside the detail route's outlet rather than replacing the page shell.
- **IFC-3131** (manual validation of this card) — its instructions are written by **IFC-3132**, which has not landed. If IFC-3131 is treated as this card's acceptance gate, that gate is currently blocked on an unwritten ticket.
- **T094 in IFC-3101** — an open design task settling unresolved canvas decisions, and the existing forum for the divergence register in [plan.md](plan.md). Take the register there as one conversation rather than opening a separate one per row.

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
